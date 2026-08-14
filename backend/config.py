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

# --- TTS (Phase 2) — Edge TTS (neural, online) + pyttsx3 (SAPI5, offline fallback) ---
# Edge TTS is the primary engine with 30+ high-quality neural Chinese voices.
# Falls back to pyttsx3 on network error so offline usage still works.
TTS_VOICE = os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural")  # 活泼女声，接近真人
# Other great voices: zh-CN-XiaoyiNeural (温柔), zh-CN-YunxiNeural (温暖男声),
# zh-CN-XiaochenNeural (冷静女声), zh-CN-YunjianNeural (成熟男声)
TTS_PROXY = os.getenv("TTS_PROXY", "") or None  # optional HTTP proxy for Edge TTS

# --- Agent Tools ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# --- RAG 检索参数（配置化: 调参实验不改代码）---
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))  # 最终返回给 LLM 的片段数
RAG_VECTOR_K = int(os.getenv("RAG_VECTOR_K", "20"))  # 向量路候选数
RAG_BM25_K = int(os.getenv("RAG_BM25_K", "20"))  # BM25 路候选数

# --- ASR (Phase 2) ---
# Default path is resolved relative to this config file (backend/ → project root)
_ASR_DEFAULT = str(Path(__file__).resolve().parent.parent / "model_assets" / "asr" / "sensevoice-small-int8")
ASR_MODEL_DIR = os.getenv("ASR_MODEL_DIR", _ASR_DEFAULT)

# --- Structured Logging ---


class JSONFormatter(logging.Formatter):
    """Outputs log records as JSON lines for machine parsing.

    Standard fields (timestamp/level/logger/message) are always present.
    Custom `extra` kwargs on the log call (e.g. request_id, duration_ms)
    are appended as top-level JSON fields, so tracing fields survive
    into Loki/ELK-style indexers.
    """

    _STD_ATTRS = frozenset(
        {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 附加 extra 自定义字段（request_id / duration_ms / skill 等）
        for key, value in record.__dict__.items():
            if key in payload or key in self._STD_ATTRS or key.startswith("_"):
                continue
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                value = str(value)
            payload[key] = value
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
