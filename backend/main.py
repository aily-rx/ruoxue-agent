"""Ruoxue backend entry point.

FastAPI application serving the AI Agent API.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Allow running from any directory (e.g. python main.py inside backend/)
_proj_root = Path(__file__).resolve().parent.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

import uvicorn
from backend.config import HOST, PORT, setup_logging
from backend.routes import router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize structured logging (JSON lines to stdout)
setup_logging()

_logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    _logger.info("server starting")

    # Phase 2: preload ASR model at startup
    try:
        from backend.asr.asr_service import asr_service

        asr_service.load_model()
    except Exception as exc:
        _logger.warning("asr model load failed, voice features disabled", extra={"error": str(exc)})

    # Phase 4: warm up the shared LLM client — ChatOpenAI 构造在 Windows 上
    # 实测约 5s, 若留到首个请求懒加载, 首请求 TTFT 会白付冷启动
    try:
        from backend.agent.agent_graph import warmup_llm

        warmup_llm()
        _logger.info("llm client warmed up")
    except Exception as exc:
        _logger.warning("llm warmup failed", extra={"error": str(exc)})

    yield
    _logger.info("server shutting down")


app = FastAPI(
    title="Ruoxue AI Agent",
    description="2D AI Agent digital human backend",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS: allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],  # 前端可读取 tracing id
)

app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        reload=True,
    )
