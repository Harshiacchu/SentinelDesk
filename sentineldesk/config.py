"""Paths, model names and thresholds shared by every module.

P1 keys are filled in. If P5 already has a config.py, merge these keys into it.
Thresholds are placeholders until P2/P3 tune them on val.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- Data (P1) ---------------------------------------------------------------
DATA_FILE = "aa_dataset-tickets-multi-lang-5-2-50-version.csv"
DATA_URL = (
    "https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/"
    f"resolve/main/{DATA_FILE}"
)
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
RAW_CSV = RAW_DIR / DATA_FILE

KB_PATH = PROCESSED_DIR / "kb.parquet"                  # 80% KB, with answers
VAL_IDS_PATH = PROCESSED_DIR / "val_ids.json"           # last 10% of KB
TEST_INPUTS_PATH = PROCESSED_DIR / "test_inputs.parquet"  # ticket_id, subject, body ONLY
# The test-label path is deliberately NOT defined here. Only data.py (writer)
# and scripts/evaluate.py (reader) know it, and evaluate.py's leakage check
# fails if any other module mentions it.
MANIFEST_PATH = PROCESSED_DIR / "manifest.json"

SEED = 42
KB_FRAC = 0.8
VAL_FRAC_OF_KB = 0.1
LANGUAGES = ("en", "de")
EXPECTED_ROWS = 28_587          # verified on the real CSV (0 duplicates, 0 rows dropped)
EXPECTED_KB = 22_869
EXPECTED_TEST = 5_718
EXPECTED_VAL = 2_287

# Facts from the real-data profile (results/eda.md), for every module:
#  - 13.4% empty subjects; 17.2% high-priority Incidents; body max 171 words.
#  - 26% of rows labelled "de" have English bodies -> detect language from the text.
#  - 2,054 rows stored line breaks as the text "\\n"; data.py converts them.
#  - Answers contain placeholders (<tel_num> 36%, <name> 21%, <acc_num> 9%):
#    replies must never copy them (see eval_metrics.find_placeholders).
#  - 6 KB rows have an empty answer: leave them out of the index.
#  - The brief's VPN/telemedicine ticket is in the KB twice (TKT-17145, TKT-18467),
#    labelled medium: severity rules must be able to raise priority.

# --- Artifacts (P2/P3) ---------------------------------------------------------
ARTIFACTS_DIR = ROOT / "artifacts"
KB_EMB_PATH = ARTIFACTS_DIR / "kb_emb.npy"      # (22869, 768), row order = kb.parquet
TEST_EMB_PATH = ARTIFACTS_DIR / "test_emb.npy"  # (5718, 768), row order = test_inputs.parquet
INDEX_DIR = ARTIFACTS_DIR / "index"
INDEX_META_PATH = INDEX_DIR / "meta.parquet"    # must contain ticket_id

EMBED_MODEL = "intfloat/multilingual-e5-base"
EMBED_FALLBACK = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# --- Thresholds (tuned on val; placeholders) -----------------------------------
TAU_C = float(os.getenv("SENTINEL_TAU_C", 0.45))       # confidence cutoff (P2)
TAU_S = float(os.getenv("SENTINEL_TAU_S", 0.80))       # similarity cutoff (P3)
HIGH_INCIDENT_THRESHOLD = float(os.getenv("SENTINEL_HI_THRESHOLD", 0.30))  # (P2)

# --- LLM (P4) --------------------------------------------------------------------
LLM_MODEL = os.getenv("SENTINEL_LLM_MODEL", "claude-opus-5-5")

# --- Results (P1) ----------------------------------------------------------------
RESULTS_DIR = ROOT / "results"
USE_MOCKS = os.getenv("SENTINEL_USE_MOCKS") == "1"