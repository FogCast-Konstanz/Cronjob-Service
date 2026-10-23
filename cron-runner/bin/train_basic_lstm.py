from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from cron.jobs.raspi_fallback.basic_lstm import (
    BasicLSTMConfig,
    train_and_save_basic_lstm,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raspi-csv", required=True, type=Path)
    parser.add_argument("--dwd-csv", required=True, type=Path)
    parser.add_argument(
        "--model-path",
        type=Path,
        default=Path("./config/models/basic_lstm.keras"),
    )
    parser.add_argument("--metadata-path", type=Path, default=None)
    parser.add_argument("--sequence-length", type=int, default=48)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    metadata = train_and_save_basic_lstm(
        pd.read_csv(args.raspi_csv),
        pd.read_csv(args.dwd_csv),
        args.model_path,
        args.metadata_path,
        BasicLSTMConfig(
            sequence_length=args.sequence_length,
            epochs=args.epochs,
            seed=args.seed,
        ),
    )
    print(
        f"Basic-LSTM gespeichert: {args.model_path} "
        f"(Version {metadata['model_version']}, "
        f"{metadata['training_samples']} Trainingsfenster)"
    )


if __name__ == "__main__":
    main()
