"""Load, clean and split the dataset. Owner: P1.

Leakage rule: the `answer` column may be read ONLY from the KB split.
"""
import pandas as pd

from . import config


def load_raw() -> pd.DataFrame:
    """Download the dataset from Hugging Face and return it as a DataFrame."""
    from datasets import load_dataset

    ds = load_dataset(config.DATASET_ID)
    return ds["train"].to_pandas()


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["subject"] = df["subject"].fillna("").astype(str).str.strip()
    df["body"] = df["body"].fillna("").astype(str).str.strip()
    df = df[df["body"] != ""]
    # TODO(P1): drop exact duplicates? normalise label casing? keep only en/de?
    return df


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fixed 80/20 split, as required by the challenge."""
    df = df.sample(frac=1.0, random_state=config.SEED).reset_index(drop=True)
    df["ticket_id"] = [f"TKT-{i:05d}" for i in range(len(df))]
    cut = int(len(df) * config.KB_FRACTION)
    return df.iloc[:cut].copy(), df.iloc[cut:].copy()


def load_kb() -> pd.DataFrame:
    return pd.read_parquet(config.KB_PATH)


def load_test_inputs() -> pd.DataFrame:
    """Holdout inputs only: no labels, no answers."""
    return pd.read_parquet(config.TEST_PATH, columns=["ticket_id", "subject", "body"])


def load_test_labels() -> pd.DataFrame:
    """Holdout labels, for scoring in evaluate.py only. Never pass these to the pipeline."""
    return pd.read_parquet(config.TEST_PATH, columns=["ticket_id", "type", "queue", "priority", "language"])
