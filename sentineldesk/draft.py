"""Grounded multilingual reply drafting with Claude. Owner: P4."""
from pathlib import Path

from . import config
from .contracts import Case, Draft, Ticket, Triage

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "draft_system.md").read_text(encoding="utf-8")

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "cited_ticket_ids": {"type": "array", "items": {"type": "string"}},
        "grounded": {"type": "boolean"},
        "unsupported_requests": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["reply", "cited_ticket_ids", "grounded", "unsupported_requests"],
    "additionalProperties": False,
}


def format_cases(cases: list[Case]) -> str:
    return "\n".join(
        f'<case id="{c["ticket_id"]}" similarity="{c["similarity"]:.2f}" language="{c["language"]}">\n'
        f"Subject: {c['subject']}\nIssue: {c['body']}\nResolution: {c['answer']}\n</case>"
        for c in cases
    )


def generate(ticket: Ticket, triage: Triage, cases: list[Case]) -> Draft:
    """TODO(P4): mask PII with pii.mask, call client.messages.create(model=config.LLM_MODEL, ...)
    with output_config={"format": {"type": "json_schema", "schema": DRAFT_SCHEMA}, "effort": "low"},
    check stop_reason (incl. "refusal"), parse the JSON. Reply language = triage["language"]."""
    if config.USE_MOCKS:
        return {
            "reply": f"Thanks for reporting this. Based on a similar past case, please ... [{cases[0]['ticket_id']}]"
            if cases else "",
            "cited_ticket_ids": [cases[0]["ticket_id"]] if cases else [],
            "grounded": bool(cases),
            "unsupported_requests": [],
        }
    raise NotImplementedError("TODO(P4)")
