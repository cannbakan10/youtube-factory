from duckduckgo_search import DDGS
from google import genai
from tavily import TavilyClient
from openai import OpenAI
import os
from src.utils.logger import get_logger
from src.utils.retry import retry_with_backoff, APIRateLimiters, gemini_generate_with_retry, is_gemini_quota, is_gemini_transient

logger = get_logger(__name__)


class ResearchAgent:
    GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]

    def __init__(self):
        # Ultra-Clean Key Loading
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip().replace('"', '').replace("'", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "").strip().replace('"', '').replace("'", "")
        self.client = genai.Client(api_key=self.gemini_key) if self.gemini_key else None
        self.oa_client = None
        if self.openai_key:
            import httpx
            self.oa_client = OpenAI(
                api_key=self.openai_key,
                timeout=httpx.Timeout(60.0, connect=10.0),
                max_retries=3,
            )

        tavily_key = os.getenv("TAVILY_API_KEY", "").strip().replace('"', '').replace("'", "")
        self.tavily = TavilyClient(api_key=tavily_key) if tavily_key else None
        self.model = "gemini-2.5-flash"
        self.oa_model = "gpt-4o-mini"

    def research(self, topic):
        logger.info(f"AI-Powered Research started for: {topic}")
        results = []

        # Priority 1: Tavily (Professional AI Search)
        if self.tavily:
            try:
                results = self._search_tavily(topic)
            except Exception as e:
                logger.warning(f"Tavily search failed: {e}")

        # Priority 2: DuckDuckGo Fallback
        if not results:
            try:
                results = self._search_duckduckgo(topic)
            except Exception as e:
                logger.warning(f"DuckDuckGo search failed: {e}")

        if not results:
            logger.error(f"All search methods failed for topic: {topic}")
            return f"Research failed for topic: {topic}. No data sources available."

        context = "\n---\n".join(results)

        prompt = f"""
        TOPIC: {topic}
        RAW DATA:
        {context}

        TASK:
        You are a DATA ANALYST. Analyze this data from Tavily/Internet.

        RULES:
        1. ROUNDED DATA: Never use long decimals. (e.g., instead of "1,463,865,525", use "One and a half billion" or "Approx 1.4 billion").
        2. ACCURACY: Prioritize 2024 and 2025 data.
        3. SUMMARY: Create a clear, bulleted DATA REPORT for the scriptwriter.

        ONLY return the DATA REPORT.
        """

        # Try Gemini first, then OpenAI fallback
        try:
            report = self._generate_report_gemini(prompt)
        except Exception as e:
            logger.warning(f"Gemini Research Error: {e}. Falling back to OpenAI...")
            if not self.oa_client:
                logger.error("OpenAI client not configured. Research incomplete.")
                return f"Research partially failed for topic: {topic}. Raw data: {context[:500]}..."
            try:
                report = self._generate_report_openai(prompt)
            except Exception as oe:
                logger.error(f"OpenAI also failed: {oe}")
                return f"Research failed for topic: {topic}. Raw data: {context[:500]}..."

        logger.info(f"High-Fidelity Data Report Generated ({len(report)} chars)")
        return report

    @retry_with_backoff(max_retries=2, base_delay=2.0)
    def _search_tavily(self, topic):
        """Search using Tavily with retry support."""
        APIRateLimiters.tavily.wait()

        logger.info("Using Tavily AI Search for verified data...")
        response = self.tavily.search(query=topic, search_depth="advanced", max_results=5)
        results = []
        for r in response.get('results', []):
            results.append(f"Source: {r['url']}\nTitle: {r['title']}\nContent: {r['content']}")
        return results

    @retry_with_backoff(max_retries=2, base_delay=1.0)
    def _search_duckduckgo(self, topic):
        """Search using DuckDuckGo with retry support."""
        logger.info("Falling back to DuckDuckGo Search...")
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(f"{topic} facts 2024 2025", max_results=5):
                results.append(f"Content: {r['body']}")
        return results

    def _generate_report_gemini(self, prompt):
        """Generate report using Gemini with model fallback chain + transient retry."""
        if not self.client:
            raise ValueError("Gemini client not configured")

        last_err = None
        for model in self.GEMINI_MODELS:
            try:
                APIRateLimiters.gemini.wait()
                response = gemini_generate_with_retry(self.client, model, contents=prompt)
                text = getattr(response, "text", None)
                if text and text.strip():
                    return text
                raise ValueError(f"{model} returned empty response")
            except Exception as e:
                last_err = e
                if is_gemini_quota(e) or is_gemini_transient(e):
                    logger.warning(f"[Research] {model} failed ({str(e)[:80]}), trying next model…")
                    continue
                raise  # Non-retryable
        raise last_err or RuntimeError("All Gemini models exhausted for research")

    @retry_with_backoff(max_retries=2, base_delay=2.0)
    def _generate_report_openai(self, prompt):
        """Generate report using OpenAI with retry support."""
        oa_response = self.oa_client.chat.completions.create(
            model=self.oa_model,
            messages=[{"role": "user", "content": prompt}]
        )
        return oa_response.choices[0].message.content
