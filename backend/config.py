"""Ruoxue backend configuration.

All settings are read from environment variables with sensible defaults.
A backend/.env file is automatically loaded if present.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)


# --- Server ---
HOST = os.getenv("RUOXUE_HOST", "0.0.0.0")
PORT = int(os.getenv("RUOXUE_PORT", "8000"))

# --- DeepSeek LLM ---
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "your-api-key-here")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# LLM parameters
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))

# --- Conversation ---
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "20"))

# --- TTS (Phase 2) ---
TTS_VOICE = os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural")

# --- ASR (Phase 2) ---
ASR_MODEL_DIR = os.getenv("ASR_MODEL_DIR", "../model_assets/asr/sensevoice-small-int8")
