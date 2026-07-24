"""Ruoxue backend entry point.

FastAPI application serving the AI Agent API.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import HOST, PORT
from backend.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Phase 2: preload ASR model here
    print("[Ruoxue] Server starting...")
    yield
    print("[Ruoxue] Server shutting down...")


app = FastAPI(
    title="Ruoxue AI Agent",
    description="2D AI Agent digital human backend",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        reload=True,
    )
