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
