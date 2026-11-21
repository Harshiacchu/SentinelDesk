"""Shared paths, model names, and thresholds. Owner: P5 (thresholds tuned by P2/P3/P4)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
KB_PATH = DATA_PROCESSED / "kb.parquet"      # 80% split: training + RAG index
TEST_PATH = DATA_PROCESSED / "test.parquet"  # 20% holdout: evaluation only
MODELS_DIR = ROOT / "artifacts" / "models"
INDEX_DIR = ROOT / "artifacts" / "index"
EMB_DIR = ROOT / "artifacts" / "embeddings"
RESULTS_DIR = ROOT / "results"

DATASET_ID = "Tobi-Bueck/customer-support-tickets"
SEED = 42
KB_FRACTION = 0.8

EMBED_MODEL = os.getenv("SENTINEL_EMBED_MODEL", "intfloat/multilingual-e5-base")
LLM_MODEL = os.getenv("SENTINEL_LLM_MODEL", "claude-opus-5-5")
USE_MOCKS = os.getenv("SENTINEL_USE_MOCKS", "0") == "1"

TOP_K = 5
# Escalation thresholds: placeholders, tune on validation data
MIN_CLASSIFIER_CONF = 0.55
MIN_RETRIEVAL_SIM = 0.80
# Burst / outage detection
BURST_WINDOW_MIN = 15
BURST_MIN_TICKETS = 3
BURST_SIM = 0.85
