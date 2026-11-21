"""HTTP bridge for the MERN console. Owner: P5.

    uvicorn api:app --port 8000
    POST /triage {"subject": str|null, "body": str} -> pipeline.run(...) (CONTRACT.md section 9)

The Express server calls this when TRIAGE_PROVIDER=http (see server/.env.example).
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sentineldesk import config, pipeline

app = FastAPI(title="SentinelDesk pipeline", version="1.0")


class TicketIn(BaseModel):
    subject: str | None = Field(default=None, max_length=300)
    body: str = Field(min_length=1, max_length=8000)
    ticket_id: str | None = None


@app.get("/health")
def health() -> dict:
    return {"ok": True, "mocks": config.USE_MOCKS, "llm_model": config.LLM_MODEL}


@app.post("/triage")
def triage_ticket(ticket: TicketIn) -> dict:
    if not ticket.body.strip():
        raise HTTPException(status_code=422, detail="body is empty")
    return pipeline.run(ticket.subject, ticket.body, ticket.ticket_id)
