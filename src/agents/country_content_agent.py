import os
import json
import random
from src.utils.logger import get_logger

logger = get_logger(__name__)

class CountryContentAgent:
    def __init__(self, factory_instance):
        self.factory = factory_instance
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
        self.history_file = os.path.join(self.data_dir, "country_history.json")
        os.makedirs(self.data_dir, exist_ok=True)

    def run_automation(self):
        """
        Picks a country and produces a 10-minute long-form video.
        """
        logger.info("Starting Country Long-Form Automation...")
        
        countries = [
            "Japan", "Norway", "Iceland", "Switzerland", "New Zealand", 
            "Canada", "Australia", "Italy", "Greece", "Egypt", 
            "Thailand", "Vietnam", "Peru", "Brazil", "South Africa",
            "Bhutan", "Mongolia", "Madagascar", "Portugal", "Jordan"
        ]
        
        # Load history to avoid repeats
        history = self._load_history()
        available_countries = [c for c in countries if c not in history]
        
        if not available_countries:
            logger.warning("All countries in list have been produced. Resetting history.")
            history = []
            available_countries = countries
            
        selected_country = random.choice(available_countries)
        logger.info(f"Selected Country: {selected_country}")
        
        topic = f"Everything you need to know about {selected_country} - 10 minute comprehensive guide"
        
        # Produce and Upload via Factory
        # Using 10 minute duration context for scriptwriter
        production_id = self.factory.run(
            topic=topic,
            languages=["en"],
            auto_upload=True,
            video_type="long",
            mode="info",
            style_context="Cinematic, educational, and breathtaking visuals with calm narration."
        )
        
        if production_id:
            logger.info(f"Country Automation Success: {production_id}")
            self._update_history(selected_country)
            return True
        else:
            logger.error(f"Country Automation Failed for {selected_country}")
            return False

    def _load_history(self):
        if not os.path.exists(self.history_file):
            return []
        try:
            with open(self.history_file, "r") as f:
                return json.load(f)
        except:
            return []

    def _update_history(self, country):
        history = self._load_history()
        history.append(country)
        with open(self.history_file, "w") as f:
            json.dump(history, f)
