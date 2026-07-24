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
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

# LLM parameters
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8192"))

# --- Conversation ---
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "20"))

# --- TTS (Phase 2) ---
TTS_VOICE = os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural")
# HTTP proxy for Edge TTS (needed if speech.platform.bing.com is blocked)
# Example: "http://127.0.0.1:7890"
TTS_PROXY = os.getenv("TTS_PROXY", os.getenv("HTTP_PROXY", os.getenv("http_proxy", ""))) or None

# --- ASR (Phase 2) ---
# Default path is resolved relative to this config file (backend/ → project root)
_ASR_DEFAULT = str(Path(__file__).resolve().parent.parent / "model_assets" / "asr" / "sensevoice-small-int8")
ASR_MODEL_DIR = os.getenv("ASR_MODEL_DIR", _ASR_DEFAULT)
