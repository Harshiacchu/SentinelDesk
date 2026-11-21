"""Load, clean, dedupe and split the ticket dataset (P1).

Order of operations (locked in section 1 of the plan):
  read CSV -> clean -> dedupe -> shuffle(random_state=42) -> assign TKT-#####
  -> first 80% = KB, last 20% = test -> last 10% of KB = val.

Public helpers other modules may use:
  build_text(subject, body)   the one input-text format everyone uses
  load_kb(), load_val_ids(), load_kb_train_ids(), load_test_inputs()

There is intentionally no load_test_labels() here. Only scripts/evaluate.py reads labels.

Verified on the real CSV: 28,587 rows in, 28,587 out (no duplicates, nothing dropped),
2,054 rows had "\\n" text line breaks fixed, 7 rows have an empty answer (kept; P3 skips
them when indexing).
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from sentineldesk import config

log = logging.getLogger(__name__)

TARGETS = ("type", "queue", "priority")
INPUT_COLS = ["ticket_id", "subject", "body"]
TAG_COLS = [f"tag_{i}" for i in range(1, 9)]
KEEP_COLS = ["subject", "body", "answer", "type", "queue", "priority", "language", *TAG_COLS]
# Written by save_split(), read only by scripts/evaluate.py.
_TEST_LABELS_FILE = "test_labels.parquet"


# --------------------------------------------------------------------------- text
def _clean_str(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def build_text(subject, body) -> str:
    """(subject or "").strip() + "\\n" + body.strip(). Safe for None/NaN subjects."""
    return _clean_str(subject) + "\n" + _clean_str(body)


# --------------------------------------------------------------------------- load
def load_raw(source: str | Path | None = None, cache: bool = True) -> pd.DataFrame:
    """Read the CSV from a local path, the local cache, or the Hugging Face URL."""
    if source is None:
        if config.RAW_CSV.exists():
            source = config.RAW_CSV
        else:
            source = config.DATA_URL
    log.info("Reading %s", source)
    df = pd.read_csv(source, dtype=str, keep_default_na=True)
    if cache and str(source).startswith("http"):
        config.RAW_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(config.RAW_CSV, index=False)
        log.info("Cached raw CSV to %s", config.RAW_CSV)
    return df


# -------------------------------------------------------------------------- clean
@dataclass
class CleanReport:
    raw_rows: int = 0
    dropped_missing_body: int = 0
    dropped_missing_target: int = 0
    dropped_other_language: int = 0
    duplicates_removed: int = 0
    duplicate_groups_with_conflicting_labels: int = 0
    empty_subject_rows: int = 0
    empty_answer_rows: int = 0
    rows_with_literal_newlines_fixed: int = 0
    final_rows: int = 0
    notes: list[str] = field(default_factory=list)


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, CleanReport]:
    rep = CleanReport(raw_rows=len(df))
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    missing = [c for c in ("body", *TARGETS, "language") if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")
    for col in ("subject", "answer", *TAG_COLS):
        if col not in df.columns:
            df[col] = None
            if col in ("subject", "answer"):
                rep.notes.append(f"column '{col}' absent, filled empty")

    df = df[KEEP_COLS]
    for col in ("subject", "body", "answer", *TARGETS, "language"):
        df[col] = df[col].map(_clean_str)
    # The HF rows store line breaks as the two characters backslash + n.
    # Turn them into real newlines so embeddings, the LLM and the UI see clean text.
    literal = df[["subject", "body", "answer"]].apply(lambda c: c.str.contains(r"\\n", regex=True))
    rep.rows_with_literal_newlines_fixed = int(literal.any(axis=1).sum())
    for col in ("subject", "body", "answer"):
        df[col] = df[col].str.replace(r"\\r\\n|\\n", "\n", regex=True).str.strip()
    for col in TAG_COLS:
        df[col] = df[col].map(lambda v: _clean_str(v) or None)
    df["priority"] = df["priority"].str.lower()
    df["language"] = df["language"].str.lower()

    mask = df["body"] != ""
    rep.dropped_missing_body = int((~mask).sum())
    df = df[mask]

    mask = (df[list(TARGETS)] != "").all(axis=1)
    rep.dropped_missing_target = int((~mask).sum())
    df = df[mask]

    mask = df["language"].isin(config.LANGUAGES)
    rep.dropped_other_language = int((~mask).sum())
    df = df[mask]

    key = ["subject", "body"]
    dup_mask = df.duplicated(key, keep=False)
    if dup_mask.any():
        conflicts = df[dup_mask].groupby(key)[list(TARGETS)].nunique().max(axis=1) > 1
        rep.duplicate_groups_with_conflicting_labels = int(conflicts.sum())
    before = len(df)
    df = df.drop_duplicates(key, keep="first")
    rep.duplicates_removed = before - len(df)

    df = df.reset_index(drop=True)
    rep.empty_subject_rows = int((df["subject"] == "").sum())
    rep.empty_answer_rows = int((df["answer"] == "").sum())
    rep.final_rows = len(df)
    if rep.final_rows != config.EXPECTED_ROWS:
        msg = f"final rows {rep.final_rows} != expected {config.EXPECTED_ROWS}"
        rep.notes.append(msg)
        log.warning(msg)
    return df, rep


# -------------------------------------------------------------------------- split
@dataclass
class Split:
    kb: pd.DataFrame          # 80%, has answers and labels
    test: pd.DataFrame        # 20%, full rows (split into inputs/labels on save)
    val_ids: list[str]        # last 10% of KB
    kb_train_ids: list[str]   # rest of KB


def split(df: pd.DataFrame, seed: int = config.SEED) -> Split:
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    df.insert(0, "ticket_id", [f"TKT-{i:05d}" for i in range(len(df))])

    n_kb = int(len(df) * config.KB_FRAC)
    kb = df.iloc[:n_kb].copy()
    test = df.iloc[n_kb:].copy()

    n_train = int(len(kb) * (1 - config.VAL_FRAC_OF_KB))
    kb_train_ids = kb["ticket_id"].iloc[:n_train].tolist()
    val_ids = kb["ticket_id"].iloc[n_train:].tolist()
    kb["split"] = ["kb_train"] * n_train + ["val"] * (len(kb) - n_train)

    for name, got, want in (
        ("kb", len(kb), config.EXPECTED_KB),
        ("test", len(test), config.EXPECTED_TEST),
        ("val", len(val_ids), config.EXPECTED_VAL),
    ):
        if got != want:
            log.warning("%s has %d rows, plan expected %d", name, got, want)
    return Split(kb=kb, test=test, val_ids=val_ids, kb_train_ids=kb_train_ids)


# --------------------------------------------------------------------------- save
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_split(s: Split, report: CleanReport, out_dir: Path = config.PROCESSED_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "kb": out_dir / "kb.parquet",
        "val_ids": out_dir / "val_ids.json",
        "kb_train_ids": out_dir / "kb_train_ids.json",
        "test_inputs": out_dir / "test_inputs.parquet",
        "test_labels": out_dir / _TEST_LABELS_FILE,
    }
    s.kb.to_parquet(paths["kb"], index=False)
    paths["val_ids"].write_text(json.dumps(s.val_ids))
    paths["kb_train_ids"].write_text(json.dumps(s.kb_train_ids))
    s.test[INPUT_COLS].to_parquet(paths["test_inputs"], index=False)
    label_cols = ["ticket_id", *TARGETS, "language", "answer", *TAG_COLS]
    s.test[label_cols].to_parquet(paths["test_labels"], index=False)

    manifest = {
        "source": config.DATA_FILE,
        "seed": config.SEED,
        "clean_report": report.__dict__,
        "counts": {
            "kb": len(s.kb), "kb_train": len(s.kb_train_ids),
            "val": len(s.val_ids), "test": len(s.test),
        },
        "id_ranges": {
            "kb": [s.kb["ticket_id"].iloc[0], s.kb["ticket_id"].iloc[-1]],
            "test": [s.test["ticket_id"].iloc[0], s.test["ticket_id"].iloc[-1]],
        },
        "sha256": {k: _sha256(p) for k, p in paths.items()},
    }
    config.MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


# --------------------------------------------------------------------- loaders
def load_kb() -> pd.DataFrame:
    return pd.read_parquet(config.KB_PATH)


def load_index_rows() -> pd.DataFrame:
    """KB rows that are useful precedents (non-empty answer). For P3's index."""
    kb = load_kb()
    return kb[kb["answer"].fillna("").str.strip() != ""].reset_index(drop=True)


def load_val_ids() -> list[str]:
    return json.loads(config.VAL_IDS_PATH.read_text())


def load_kb_train_ids() -> list[str]:
    return json.loads((config.PROCESSED_DIR / "kb_train_ids.json").read_text())


def load_test_inputs() -> pd.DataFrame:
    df = pd.read_parquet(config.TEST_INPUTS_PATH)
    assert list(df.columns) == INPUT_COLS, f"test_inputs has extra columns: {list(df.columns)}"
    return df