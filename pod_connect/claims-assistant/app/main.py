"""HTTP API and a small chat page.

The member is identified ONLY by the bearer token. Any member ID in the request body is ignored.
In production, replace `TOKENS` with OIDC token validation from your identity provider.
"""
import logging
import os
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .agent import ClaimsAssistant
from .data import TOKENS
from .llm import LLMClient

# Audit log: records who asked and what happened, never the message text or the answer (PHI).
logging.basicConfig(level=logging.INFO, format="%(message)s")
audit = logging.getLogger("audit")

app = FastAPI(title="Claims Assistant (prototype)", version="0.1.0")
llm = LLMClient()
assistant = ClaimsAssistant(llm)
UI = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    escalate: bool
    intent: str
    request_id: str


def current_member(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    member_id = TOKENS.get(token)
    if not member_id:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return member_id


@app.get("/health")
def health():
    return {"status": "ok", "llm_provider": llm.provider, "model": llm.model}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, member_id: str = Depends(current_member)):
    request_id = uuid.uuid4().hex[:12]
    started = time.time()
    result = assistant.ask(member_id, req.message)
    audit.info(
        "audit request_id=%s member=%s intent=%s claim=%s escalate=%s sources=%s ms=%d",
        request_id, member_id, result.intent, result.claim_id, result.escalate,
        ",".join(result.sources), int((time.time() - started) * 1000),
    )
    return ChatResponse(answer=result.answer, sources=result.sources, escalate=result.escalate,
                        intent=result.intent, request_id=request_id)


@app.get("/", response_class=HTMLResponse)
def index():
    return UI
