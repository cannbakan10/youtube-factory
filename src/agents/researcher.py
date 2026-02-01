from duckduckgo_search import DDGS
from google import genai
from tavily import TavilyClient
from openai import OpenAI
import os

class ResearchAgent:
    def __init__(self):
        # Ultra-Clean Key Loading
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip().replace('"', '').replace("'", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "").strip().replace('"', '').replace("'", "")
        self.client = genai.Client(api_key=self.gemini_key)
        self.oa_client = OpenAI(api_key=self.openai_key) if self.openai_key else None
        
        tavily_key = os.getenv("TAVILY_API_KEY", "").strip().replace('"', '').replace("'", "")
        self.tavily = TavilyClient(api_key=tavily_key) if tavily_key else None
        self.model = "gemini-2.0-flash"
        self.oa_model = "gpt-4o-mini"

    def research(self, topic):
        print(f"[*] AI-Powered Research started for: {topic}")
        results = []
        
        # Priority 1: Tavily (Professional AI Search)
        if self.tavily:
            try:
                print(f"   🚀 Using Tavily AI Search for verified data...")
                # search_depth="advanced" ensures best data for facts
                response = self.tavily.search(query=topic, search_depth="advanced", max_results=5)
                for r in response.get('results', []):
                    results.append(f"Source: {r['url']}\nTitle: {r['title']}\nContent: {r['content']}")
            except Exception as e:
                print(f"   ⚠️ Tavily error: {e}")

        # Priority 2: DuckDuckGo Fallback
        if not results:
            print(f"   📡 Falling back to DuckDuckGo Search...")
            with DDGS() as ddgs:
                try:
                    for r in ddgs.text(f"{topic} facts 2024 2025", max_results=5):
                        results.append(f"Content: {r['body']}")
                except Exception as e:
                    print(f"   ⚠️ DDG search error: {e}")
        
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
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            report = response.text
        except Exception as e:
            print(f"   ⚠️ Gemini Research Error: {e}. Falling back to OpenAI...")
            if not self.oa_client: return "Araştırma başarısız oldu."
            oa_response = self.oa_client.chat.completions.create(
                model=self.oa_model,
                messages=[{"role": "user", "content": prompt}]
            )
            report = oa_response.choices[0].message.content
            
        print(f"   📊 High-Fidelity Data Report Generated ({len(report)} chars)")
        return report
