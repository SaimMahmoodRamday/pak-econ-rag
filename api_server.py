"""
HTTP API + static frontend for PakEconBot.

Run locally:
    uvicorn api_server:app --reload --host 127.0.0.1 --port 8000

Open http://127.0.0.1:8000
"""

from __future__ import annotations

import logging
import os
import uuid
from collections import OrderedDict
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
ASSETS_DIR = FRONTEND_DIR / "assets"

MAX_CONVERSATIONS = 64
_agents: OrderedDict[str, object] = OrderedDict()

app = FastAPI(title="PakEconBot API", version="1.0.0")

# Allow local dev when UI is served from another origin (optional).
_cors_origins = os.getenv("CORS_ORIGINS", "").strip()
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in _cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=16_000)
    conversation_id: str | None = Field(
        default=None,
        max_length=128,
        description="Client-owned id; omit to start a new conversation thread.",
    )


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str


class ClearRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, max_length=128)


def _evict_if_needed() -> None:
    while len(_agents) > MAX_CONVERSATIONS:
        _agents.popitem(last=False)


def _get_or_create_agent(conversation_id: str):
    from src.agent import create_agent

    if conversation_id in _agents:
        _agents.move_to_end(conversation_id)
        return _agents[conversation_id]
    _evict_if_needed()
    agent = create_agent()
    _agents[conversation_id] = agent
    return agent


def _drop_conversation(conversation_id: str) -> None:
    _agents.pop(conversation_id, None)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    from src.agent import run_agent

    cid = (body.conversation_id or "").strip() or str(uuid.uuid4())
    try:
        agent = _get_or_create_agent(cid)
        answer = await run_in_threadpool(
            run_agent,
            agent,
            body.message.strip(),
            False,
        )
    except KeyError as e:
        logger.exception("Configuration error")
        raise HTTPException(
            status_code=503,
            detail=f"Server configuration error (missing env): {e}",
        ) from e
    except Exception as e:
        logger.exception("Agent run failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return ChatResponse(answer=answer, conversation_id=cid)


@app.post("/api/clear")
async def clear_memory(body: ClearRequest) -> dict[str, str]:
    from src.agent import ReActAgent

    cid = body.conversation_id.strip()
    agent = _agents.get(cid)
    if agent is not None and isinstance(agent, ReActAgent):
        agent.clear_memory()
    return {"status": "cleared", "conversation_id": cid}


@app.delete("/api/conversation/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict[str, str]:
    cid = conversation_id.strip()
    if not cid:
        raise HTTPException(status_code=400, detail="conversation_id required")
    _drop_conversation(cid)
    return {"status": "deleted", "conversation_id": cid}


if ASSETS_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.get("/")
async def serve_index() -> FileResponse:
    index = FRONTEND_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="Frontend not built or missing index.html")
    return FileResponse(index)
