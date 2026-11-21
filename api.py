"""HTTP bridge for the MERN console. Owner: P5.

    uvicorn api:app --port 8000
    POST /triage {"subject": str|null, "body": str} -> pipeline.run(...) (CONTRACT.md section 9)

The Express server calls this when TRIAGE_PROVIDER=http (see server/.env.example).
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sentineldesk import config, pipeline

log = logging.getLogger("sentineldesk.api")


def _warm_up() -> dict:
    """Load the heavy models once at startup so the first ticket isn't slow (~3 s otherwise)."""
    timings = {}
    vec = None
    if config.USE_MOCKS:
        return {"skipped": "mocks"}
    # Load models only: no LLM call, and nothing reaches burst detection or the ticket store.
    from sentineldesk import triage

    text = "warm-up: VPN connection drops"
    for name, step in (("embed", lambda: pipeline._embed(text)), ("retrieve", lambda: pipeline._retrieve(vec, text)),
                       ("triage", lambda: triage.predict(text, "en", vec))):
        t = time.perf_counter()
        try:
            out = step()
            if name == "embed":
                vec = out[0]
        except Exception as exc:  # noqa: BLE001 - warm-up must never stop the service
            log.warning("warm-up %s failed: %s", name, exc)
            vec = locals().get("vec")
        timings[f"{name}_ms"] = round((time.perf_counter() - t) * 1000)
    if os.getenv("WARMUP_LLM", "").lower() in ("1", "true", "yes"):
        from sentineldesk import draft

        timings["llm"] = draft.warmup()
    return timings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    app.state.warmup = _warm_up()
    log.info("warm-up done: %s", app.state.warmup)
    yield


app = FastAPI(title="SentinelDesk pipeline", version="1.0", lifespan=lifespan)


class TicketIn(BaseModel):
    subject: str | None = Field(default=None, max_length=300)
    body: str = Field(min_length=1, max_length=8000)
    ticket_id: str | None = None


@app.get("/health")
def health() -> dict:
    return {"ok": True, "mocks": config.USE_MOCKS, "llm_model": config.LLM_MODEL, "warmup": getattr(app.state, "warmup", None)}


@app.post("/triage")
def triage_ticket(ticket: TicketIn) -> dict:
    if not ticket.body.strip():
        raise HTTPException(status_code=422, detail="body is empty")
    return pipeline.run(ticket.subject, ticket.body, ticket.ticket_id)
