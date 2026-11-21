# SentinelDesk

Multilingual incident triage and precedent-grounded resolution copilot.

A raw ticket (subject + body, English or German) is classified (type, queue, priority with confidence),
passed through an escalation gate, matched against historical resolved tickets (FAISS), and answered
with a draft reply that cites the past ticket IDs it relied on.

## Layout

```
sentineldesk/            core package
  config.py              paths, model names, thresholds
  contracts.py           shared types every module codes against
  data.py                load / clean / 80-20 split            (P1)
  embed.py               multilingual embeddings               (P2)
  triage.py              type / queue / priority classifiers   (P2)
  lang.py                en/de detection                       (P3)
  retrieve.py            FAISS index + top-k search            (P3)
  burst.py               outage burst detection (bonus)        (P3)
  pii.py                 PII masking                           (P4)
  gate.py                escalation rules + citation check     (P4)
  draft.py               grounded Claude reply                 (P4)
  prompts/               system prompts                        (P4)
  pipeline.py            end-to-end run + latency              (P5)
scripts/
  prepare_data.py        download + split -> data/processed/
  build_index.py         embed KB, train classifiers, build FAISS
  evaluate.py            holdout metrics -> results/metrics.json
app.py                   Streamlit console                     (P5)
tests/                   guardrail tests + adversarial tickets
docs/TEAM.md             owners, rules, sync points
data/  artifacts/  results/   generated, not committed
```

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then add ANTHROPIC_API_KEY
```

## Run

```powershell
python -m scripts.prepare_data
python -m scripts.build_index
python -m scripts.evaluate
streamlit run app.py
```

Before the models exist, run the UI on mocks: `$env:SENTINEL_USE_MOCKS="1"; streamlit run app.py`

## Leakage rules
- `answer` is indexed only from the 80% KB split.
- The pipeline only receives `subject` and `body`; holdout labels are loaded only in `scripts/evaluate.py` for scoring.

## Results
_TODO(P1): paste the metrics table here._

## Dataset
[Tobi-Bueck/customer-support-tickets](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets), CC-BY-NC-4.0.

---

## Operator console (MERN): `client/` + `server/`

A React + Express + MongoDB console on top of the Python pipeline. It runs on its own with placeholder triage, so the UI never waits for the models.

```
client/   React 18 + Vite: Console, Insights, front page (light + dark, phone → desktop)
server/   Express API: triage, smart inbox, outages, analytics, chat, live updates (SSE)
```

### Run

```bash
cd server && npm install && cp .env.example .env && npm run dev   # http://localhost:4000
cd client && npm install && npm run dev                           # http://localhost:5173
```

Defaults need nothing else: `TRIAGE_PROVIDER=mock`, `TICKET_STORE=memory`, and ~120 demo tickets (including a live VPN outage across Berlin, Munich, Hamburg and Frankfurt) are seeded on start.

| Switch (server/.env) | Options | Use |
|---|---|---|
| `TRIAGE_PROVIDER` | `mock` / `http` | `http` POSTs `{subject, body}` to `PIPELINE_URL` and expects `PipelineResult` from `sentineldesk/contracts.py` |
| `TICKET_STORE` | `memory` / `mongo` | `mongo` uses `MONGODB_URI` (local MongoDB or Atlas) |
| `SEED_DEMO` | `true` / `false` | Demo data on an empty store |
| `BURST_WINDOW_MIN`, `BURST_MIN_TICKETS` | numbers | Outage = N similar incidents within T minutes |

### Connect the real Python pipeline

```bash
pip install -r requirements.txt
uvicorn api:app --port 8000          # api.py: POST /triage -> pipeline.run() (CONTRACT.md section 9)
# server/.env: TRIAGE_PROVIDER=http  PIPELINE_URL=http://localhost:8000/triage
```

Before the models are trained, run the bridge on stubs with `SENTINEL_USE_MOCKS=1 OFFLINE=1 uvicorn api:app --port 8000`.
`server/src/modules/triage/providers/PipelineResultMapper.js` is the only file that knows the Python result shape.

### What the console shows
- **Smart inbox** sorted by urgency (Needs you / Ready / Done, paginated), live via SSE
- **Outage banner** when similar incidents cluster, plus a **tracker** listing every similar ticket and the affected branches
- **One-screen ticket view**: decision card, Apple-style outage rings, draft with an **Evidence lens** (every sentence → its source ticket; unsupported promises struck out), one primary action, "Was the AI right?" feedback
- **Six detail cards** (Why, Classification, Evidence, Safety checks, Pipeline, Activity & notes): summary on the card, everything in a tabbed drawer
- **Ask SentinelDesk** chat scoped to the ticket (answers only from stored evidence), **⌘K** quick triage
- **Insights**: KPIs, outage **location map**, **branch × topic heatmap**, volume, decisions, departments, gate reasons

### Design principles
- **Ports and adapters:** `TriageProvider` and `TicketRepository` are abstract, with mock/HTTP and memory/Mongo implementations. `server/src/container.js` is the only file that knows concrete classes.
- **Single responsibility:** routes only parse and validate, services hold use cases, `domain/` holds pure rules (severity, topics), repositories hold storage.
- **Open/closed:** a new gate reason, chat intent, topic or provider is one entry or class; callers don't change.
- **Package by feature:** `modules/{triage,tickets,incidents,analytics,chat}` on the server, `features/{inbox,ticket,incidents,insights,chat,composer}` on the client.
- **Presentational vs container components:** pages fetch and wire, feature components render, `detailModel.js` is pure mapping.
- **Design tokens:** every colour lives in `client/src/styles/tokens.css`, so light/dark is one attribute switch. Motion respects `prefers-reduced-motion`.

### API
`POST /api/triage` · `GET /api/tickets?filter&page&limit` · `GET /api/tickets/:id` · `POST /api/tickets/:id/{feedback,notes,actions,chat}` · `GET /api/incidents/active` · `GET /api/incidents/:key` · `GET /api/analytics/overview?hours` · `GET /api/analytics/heatmap?minutes` · `GET /api/events` (SSE) · `GET /api/meta`
