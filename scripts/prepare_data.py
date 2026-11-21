"""Download, clean and split the dataset into data/processed/. Owner: P1.

Usage: python -m scripts.prepare_data
"""
from sentineldesk import config, data


def main() -> None:
    df = data.clean(data.load_raw())
    kb, test = data.split(df)
    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    kb.to_parquet(config.KB_PATH, index=False)
    test.to_parquet(config.TEST_PATH, index=False)
    print(f"KB: {len(kb):,} rows -> {config.KB_PATH}")
    print(f"Test: {len(test):,} rows -> {config.TEST_PATH}")


if __name__ == "__main__":
    main()
