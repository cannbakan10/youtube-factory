from dotenv import load_dotenv
import os
load_dotenv()
print("Checking imports...")
from src.services.tts_service import TTSService
from src.core.ffmpeg_engine import VideoEngine
from src.agents.researcher import ResearchAgent
from src.agents.scriptwriter import ScriptWriter
print("Imports OK!")
