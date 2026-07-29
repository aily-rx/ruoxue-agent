"""Ruoxue backend configuration.

All settings are read from environment variables with sensible defaults.
Loads .env from project root first, then backend/.env (the latter overrides).
"""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

# Load root .env first, then backend/.env (overrides root)
_proj_root = Path(__file__).resolve().parent.parent
load_dotenv(_proj_root / ".env", override=False)
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

# --- TTS (Phase 2) — offline via pyttsx3 (Windows SAPI5) ---
# Uses system TTS voice (Microsoft Huihui). Zero network, zero proxy.

# --- Agent Tools ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# --- ASR (Phase 2) ---
# Default path is resolved relative to this config file (backend/ → project root)
_ASR_DEFAULT = str(Path(__file__).resolve().parent.parent / "model_assets" / "asr" / "sensevoice-small-int8")
ASR_MODEL_DIR = os.getenv("ASR_MODEL_DIR", _ASR_DEFAULT)

# --- Structured Logging ---


class JSONFormatter(logging.Formatter):
    """Outputs log records as JSON lines for machine parsing."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = str(record.exc_info[1])
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger to emit JSON-structured logs.

    In local development, log lines are readable JSON. In production (e.g.
    Docker + Loki), they can be indexed by timestamp/level/logger fields.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.setLevel(level)
    # Remove default handlers to avoid duplicate output
    root.handlers = [handler]
