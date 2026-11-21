"""Interfaces every module codes against. Owner: P5. Change only with team agreement."""
from typing import Literal, TypedDict


class Ticket(TypedDict):
    subject: str | None
    body: str


class Prediction(TypedDict):
    label: str
    confidence: float


class Triage(TypedDict):
    type: Prediction       # Incident | Request | Problem | Change
    queue: Prediction      # routing department
    priority: Prediction   # high | medium | low
    language: Literal["en", "de"]


class Case(TypedDict):
    ticket_id: str
    similarity: float
    subject: str
    body: str
    answer: str
    language: str


class GateResult(TypedDict):
    decision: Literal["AUTO_DRAFT", "ESCALATE"]
    reasons: list[str]


class Draft(TypedDict):
    reply: str
    cited_ticket_ids: list[str]
    grounded: bool
    unsupported_requests: list[str]


class PipelineResult(TypedDict):
    triage: Triage
    cases: list[Case]
    gate: GateResult
    draft: Draft | None
    latency_ms: dict[str, float]


def ticket_text(ticket: Ticket) -> str:
    """Join subject and body; tolerates a null or empty subject."""
    subject = (ticket.get("subject") or "").strip()
    body = (ticket.get("body") or "").strip()
    return f"{subject}\n{body}" if subject else body
