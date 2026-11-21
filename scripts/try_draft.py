"""Try the gate + LLM draft on one ticket with hand-made cases, before retrieval exists. Owner: P4.

Usage:
  python -m scripts.try_draft                       # needs GEMINI_API_KEY in .env
  python -m scripts.try_draft --list-models         # which Gemini models does our key reach?
  python -m scripts.try_draft --models gemini-3.5-flash gemini-3-flash-preview gemini-3.1-pro-preview
  SENTINEL_USE_MOCKS=1 python -m scripts.try_draft  # offline
"""
import argparse
import json

from sentineldesk import draft, gate

TICKET = "VPN disconnects\nOur VPN drops every few minutes since this morning. Please help."
HITS = [
    {"ticket_id": "TKT-00011", "score": 0.91, "subject": "VPN drops", "language": "en",
     "answer_snippet": "Restart the VPN client, then remove and re-import the connection profile. "
                       "If it still drops, send us the client log from the settings page."},
    {"ticket_id": "TKT-00022", "score": 0.87, "subject": "VPN trennt Verbindung", "language": "de",
     "answer_snippet": "Bitte aktualisieren Sie den VPN-Client auf die neueste Version und starten Sie den Rechner neu."},
]
TRIAGE = {"type": {"label": "Incident", "prob": 0.8}, "queue": {"label": "Technical Support", "prob": 0.8},
          "priority": {"label": "medium", "prob": 0.7}, "high_incident_prob": 0.1, "severity_flags": []}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="en", choices=["en", "de"])
    ap.add_argument("--models", nargs="*", help="time several models on the same ticket")
    ap.add_argument("--list-models", action="store_true", help="show the Gemini models our key can call")
    args = ap.parse_args()

    if args.list_models:
        for row in draft.list_gemini_models():
            print(f"{'OK  ' if row['ok'] else 'no  '} {row['model']:28s} {row['note']}")
        return

    pre = gate.pre(TRIAGE, HITS, TICKET, args.lang)
    print("gate.pre:", json.dumps(pre, ensure_ascii=False, indent=2))
    if pre["reasons"]:
        return

    if args.models:
        for row in draft.time_models(TICKET, args.lang, HITS, args.models):
            post = gate.post(row, HITS, args.lang)
            print(f"\n=== {row['model']}  {row['ms']} ms  -> {post['status']} {[r['code'] for r in post['reasons']]}\n{row['reply']}")
        return

    out = draft.generate(TICKET, args.lang, HITS)
    print("draft:", json.dumps(out, ensure_ascii=False, indent=2))
    print("gate.post:", json.dumps(gate.post(out, HITS, args.lang), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
