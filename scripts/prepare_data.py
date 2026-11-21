"""Download + clean + split -> data/processed/   (P1)

    python -m scripts.prepare_data                 # from HF URL (cached to data/raw/)
    python -m scripts.prepare_data --csv path.csv  # from a local copy
"""
from __future__ import annotations

import argparse
import json
import logging

from sentineldesk import config, data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None, help="local CSV path (default: cache or HF URL)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    raw = data.load_raw(args.csv)
    df, report = data.clean(raw)
    s = data.split(df)
    manifest = data.save_split(s, report)

    print(json.dumps({"clean_report": manifest["clean_report"], "counts": manifest["counts"]}, indent=2))
    print(f"\nWrote files to {config.PROCESSED_DIR}")


if __name__ == "__main__":
    main()