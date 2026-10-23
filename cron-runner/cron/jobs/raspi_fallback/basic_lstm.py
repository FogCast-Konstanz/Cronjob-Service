"""Production-safe Basic-LSTM artifact handling for the Raspberry-Pi fallback.

TensorFlow is deliberately imported lazily.  The cronjob can therefore run in
the small default container without a model artifact or the optional ML
runtime; in that case :class:`BasicLSTMForecaster` reports itself unavailable
and the caller can use the linear fallback.

The artifact consists of a Keras model and a JSON sidecar containing the
feature order, scalers, training configuration and a SHA-256 checksum.  The
same feature builder is used for training and inference to prevent silent
model/input drift.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TARGET_COLUMNS = ("temperature", "humidity", "water_temperature")
DWD_COLUMNS = ("temperature", "humidity")
SEQUENCE_FEATURES = (
    "raspi_temperature",
    "raspi_humidity",
    "raspi_water_temperature",
    "dwd_temperature",
    "dwd_humidity",
    "hour_sin",
    "hour_cos",
    "day_sin",
    "day_cos",
)
CURRENT_FEATURES = (
    "dwd_temperature",
    "dwd_humidity",
    "hour_sin",
    "hour_cos",
    "day_sin",
    "day_cos",
)


@dataclass(frozen=True)
class BasicLSTMConfig:
    """Parameters shared by training and inference."""

    sequence_length: int = 48
    lstm_units: int = 32
    dropout_rate: float = 0.15
    learning_rate: float = 0.001
    epochs: int = 30
    batch_size: int = 32
    seed: int = 42
    min_history_rows: int = 72


def _normalise_timestamps(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a sorted copy with a UTC ``timestamp`` column."""
    if frame is None or frame.empty:
        return pd.DataFrame()
    result = frame.copy()
    if "timestamp" not in result.columns:
        if isinstance(result.index, pd.DatetimeIndex):
            result = result.reset_index()
            if "timestamp" not in result.columns:
                result = result.rename(columns={result.columns[0]: "timestamp"})
        else:
            raise ValueError("weather data requires a timestamp column or DatetimeIndex")
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True, errors="coerce")
    result = result.dropna(subset=["timestamp"]).sort_values("timestamp")
    return result.drop_duplicates(subset=["timestamp"], keep="last").reset_index(drop=True)


def build_feature_tables(
    raspi_data: pd.DataFrame,
    dwd_data: pd.DataFrame,
    fill_missing_raspi: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Align weather data and build sequence/current feature tables.

    DWD values are matched to the nearest Raspberry-Pi timestamp within
    30 minutes.  ``fill_missing_raspi`` is only used for inference, where a
    short sensor gap must not turn the whole input window into NaNs.
    """
    raspi = _normalise_timestamps(raspi_data)
    dwd = _normalise_timestamps(dwd_data)
    required_raspi = ["timestamp", *TARGET_COLUMNS]
    required_dwd = ["timestamp", *DWD_COLUMNS]
    missing_raspi = [name for name in required_raspi if name not in raspi.columns]
    missing_dwd = [name for name in required_dwd if name not in dwd.columns]
    if missing_raspi or missing_dwd:
        raise ValueError(
            f"missing LSTM columns: raspi={missing_raspi}, dwd={missing_dwd}"
        )

    raspi = raspi[required_raspi].copy()
    dwd = dwd[required_dwd].rename(
        columns={
            "temperature": "dwd_temperature",
            "humidity": "dwd_humidity",
        }
    )
    # Training uses one row per hour.  InfluxDB normally returns raw Raspi
    # samples, so aggregate both inputs before aligning them with the model.
    raspi = (
        raspi.set_index("timestamp")[list(TARGET_COLUMNS)]
        .apply(pd.to_numeric, errors="coerce")
        .resample("1h")
        .mean()
        .reset_index()
    )
    dwd = (
        dwd.set_index("timestamp")[["dwd_temperature", "dwd_humidity"]]
        .apply(pd.to_numeric, errors="coerce")
        .resample("1h")
        .mean()
        .reset_index()
    )
    if fill_missing_raspi:
        for column in TARGET_COLUMNS:
            raspi[column] = pd.to_numeric(raspi[column], errors="coerce").ffill().bfill()

    merged = pd.merge_asof(
        raspi.sort_values("timestamp"),
        dwd.sort_values("timestamp"),
        on="timestamp",
        direction="nearest",
        tolerance=pd.Timedelta(minutes=30),
    )
    if merged.empty:
        return pd.DataFrame(), pd.DataFrame()

    timestamp = merged["timestamp"]
    hour = timestamp.dt.hour + timestamp.dt.minute / 60.0
    day = timestamp.dt.dayofyear
    sequence = pd.DataFrame(
        {
            "raspi_temperature": merged["temperature"].to_numpy(),
            "raspi_humidity": merged["humidity"].to_numpy(),
            "raspi_water_temperature": merged["water_temperature"].to_numpy(),
            "dwd_temperature": merged["dwd_temperature"].to_numpy(),
            "dwd_humidity": merged["dwd_humidity"].to_numpy(),
            "hour_sin": np.sin(2 * np.pi * hour.to_numpy() / 24),
            "hour_cos": np.cos(2 * np.pi * hour.to_numpy() / 24),
            "day_sin": np.sin(2 * np.pi * day.to_numpy() / 366),
            "day_cos": np.cos(2 * np.pi * day.to_numpy() / 366),
        },
        index=timestamp,
    )
    sequence.index.name = "timestamp"
    current = sequence[list(CURRENT_FEATURES)].copy()
    return sequence[list(SEQUENCE_FEATURES)], current


def _fit_scaler(values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    mean = np.asarray(values, dtype=np.float64).mean(axis=0)
    scale = np.asarray(values, dtype=np.float64).std(axis=0)
    scale[scale < 1e-8] = 1.0
    return mean, scale


def _scale(values: np.ndarray, mean: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return (values - mean) / scale


def _metadata_path(model_path: Path) -> Path:
    return model_path.with_suffix(".metadata.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BasicLSTMForecaster:
    """Load and execute a versioned Basic-LSTM artifact."""

    def __init__(
        self,
        model_path: str | Path,
        metadata_path: str | Path | None = None,
        config: BasicLSTMConfig | None = None,
    ):
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path) if metadata_path else _metadata_path(self.model_path)
        self.config = config or BasicLSTMConfig()
        self.model = None
        self.metadata: Dict[str, Any] = {}
        self.load_error: Optional[str] = None
        self._load()

    @property
    def available(self) -> bool:
        return self.model is not None

    @property
    def version(self) -> str:
        return str(self.metadata.get("model_version", "unavailable"))

    def _load(self) -> None:
        if not self.model_path.is_file() or not self.metadata_path.is_file():
            self.load_error = "model or metadata artifact is missing"
            return
        try:
            with self.metadata_path.open("r", encoding="utf-8") as handle:
                metadata = json.load(handle)
            if metadata.get("artifact_type") != "fogcast-basic-lstm":
                raise ValueError("unsupported LSTM artifact type")
            expected_hash = metadata.get("artifact_sha256")
            if expected_hash and expected_hash != _sha256(self.model_path):
                raise ValueError("model checksum does not match metadata")
            if int(metadata["sequence_length"]) < 2:
                raise ValueError("invalid sequence length in metadata")
            if list(metadata["sequence_features"]) != list(SEQUENCE_FEATURES):
                raise ValueError("sequence feature order does not match runtime")
            if list(metadata.get("current_features", [])) != list(CURRENT_FEATURES):
                raise ValueError("current feature order does not match runtime")
            if list(metadata.get("target_columns", [])) != list(TARGET_COLUMNS):
                raise ValueError("target column order does not match runtime")
            if len(metadata["sequence_scaler"]["mean"]) != len(SEQUENCE_FEATURES):
                raise ValueError("invalid sequence scaler in metadata")
            if len(metadata["current_scaler"]["mean"]) != len(CURRENT_FEATURES):
                raise ValueError("invalid current scaler in metadata")
            if len(metadata["target_scaler"]["mean"]) != len(TARGET_COLUMNS):
                raise ValueError("invalid target scaler in metadata")

            # TensorFlow is optional for the default linear-safe deployment.
            from tensorflow import keras  # type: ignore

            model = keras.models.load_model(self.model_path, compile=False)
            input_shapes = [tuple(input_tensor.shape) for input_tensor in model.inputs]
            expected_sequence_shape = (
                None,
                int(metadata["sequence_length"]),
                len(SEQUENCE_FEATURES),
            )
            expected_current_shape = (None, len(CURRENT_FEATURES))
            if input_shapes[:2] != [expected_sequence_shape, expected_current_shape]:
                raise ValueError("model input shapes do not match metadata")
            self.model = model
            self.metadata = metadata
            logger.info("Loaded Basic LSTM artifact %s (version %s)", self.model_path, self.version)
        except Exception as exc:
            self.load_error = str(exc)
            self.model = None
            logger.warning("Basic LSTM unavailable: %s", exc)

    def predict(
        self,
        raspi_history: pd.DataFrame,
        dwd_history: pd.DataFrame,
        dwd_current: pd.DataFrame,
    ) -> Dict[str, float]:
        """Predict the next Raspi values from historical and current DWD data."""
        if not self.available:
            raise RuntimeError(self.load_error or "Basic LSTM is not loaded")

        current = _normalise_timestamps(dwd_current)
        if current.empty:
            raise ValueError("current DWD data is empty")
        current = current.sort_values("timestamp").iloc[-1]
        if pd.isna(current.get("temperature")) or pd.isna(current.get("humidity")):
            raise ValueError("current DWD temperature/humidity is incomplete")

        last_raspi = _normalise_timestamps(raspi_history).iloc[-1]
        row = pd.DataFrame(
            [
                {
                    "timestamp": current["timestamp"],
                    "temperature": last_raspi["temperature"],
                    "humidity": last_raspi["humidity"],
                    "water_temperature": last_raspi["water_temperature"],
                }
            ]
        )
        current_dwd = pd.DataFrame(
            [
                {
                    "timestamp": current["timestamp"],
                    "temperature": current["temperature"],
                    "humidity": current["humidity"],
                }
            ]
        )
        appended_sequence, appended_current = build_feature_tables(
            pd.concat([_normalise_timestamps(raspi_history), row], ignore_index=True),
            pd.concat([_normalise_timestamps(dwd_history), current_dwd], ignore_index=True),
            fill_missing_raspi=True,
        )
        if len(appended_sequence) < int(self.metadata["sequence_length"]) + 1:
            raise ValueError("not enough aligned history for Basic LSTM inference")

        sequence_length = int(self.metadata["sequence_length"])
        sequence_values = appended_sequence.to_numpy(dtype=np.float32)
        current_values = appended_current.to_numpy(dtype=np.float32)
        sequence_mean = np.asarray(self.metadata["sequence_scaler"]["mean"], dtype=np.float32)
        sequence_scale = np.asarray(self.metadata["sequence_scaler"]["scale"], dtype=np.float32)
        current_mean = np.asarray(self.metadata["current_scaler"]["mean"], dtype=np.float32)
        current_scale = np.asarray(self.metadata["current_scaler"]["scale"], dtype=np.float32)
        target_mean = np.asarray(self.metadata["target_scaler"]["mean"], dtype=np.float32)
        target_scale = np.asarray(self.metadata["target_scaler"]["scale"], dtype=np.float32)
        x_sequence = _scale(
            sequence_values[-sequence_length - 1:-1], sequence_mean, sequence_scale
        )[None, ...]
        x_current = _scale(current_values[-1:], current_mean, current_scale)
        raw = self.model.predict([x_sequence, x_current], verbose=0)
        prediction = np.asarray(raw, dtype=np.float32).reshape(-1, len(TARGET_COLUMNS))[-1]
        prediction = prediction * target_scale + target_mean
        if not np.isfinite(prediction).all():
            raise ValueError("Basic LSTM returned non-finite values")
        return {name: float(value) for name, value in zip(TARGET_COLUMNS, prediction)}


def _create_training_samples(
    raspi_data: pd.DataFrame,
    dwd_data: pd.DataFrame,
    config: BasicLSTMConfig,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    sequence, current = build_feature_tables(raspi_data, dwd_data)
    clean = sequence.notna().all(axis=1) & current.notna().all(axis=1)
    sequence = sequence.loc[clean]
    current = current.loc[clean]
    targets = sequence[
        ["raspi_temperature", "raspi_humidity", "raspi_water_temperature"]
    ].to_numpy(dtype=np.float32)
    if len(sequence) <= config.sequence_length:
        raise ValueError(
            f"need more than {config.sequence_length} aligned rows, got {len(sequence)}"
        )
    sequence_values = sequence.to_numpy(dtype=np.float32)
    current_values = current.to_numpy(dtype=np.float32)
    X_sequence, X_current, y = [], [], []
    for idx in range(config.sequence_length, len(sequence_values)):
        X_sequence.append(sequence_values[idx - config.sequence_length:idx])
        X_current.append(current_values[idx])
        y.append(targets[idx])
    return (
        np.asarray(X_sequence, dtype=np.float32),
        np.asarray(X_current, dtype=np.float32),
        np.asarray(y, dtype=np.float32),
    )


def train_and_save_basic_lstm(
    raspi_data: pd.DataFrame,
    dwd_data: pd.DataFrame,
    model_path: str | Path,
    metadata_path: str | Path | None = None,
    config: BasicLSTMConfig | None = None,
) -> Dict[str, Any]:
    """Train a deterministic Basic LSTM and atomically write model + metadata.

    This function is the supported artifact-generation entry point.  It is
    intentionally not called by the cronjob: training belongs in CI/offline
    operations, never in a gap-recovery run.
    """
    config = config or BasicLSTMConfig()
    if config.sequence_length < 2 or config.epochs < 1:
        raise ValueError("invalid Basic LSTM training configuration")
    X_sequence, X_current, y = _create_training_samples(raspi_data, dwd_data, config)
    if len(X_sequence) < config.min_history_rows - config.sequence_length:
        raise ValueError("insufficient aligned training samples")

    # TensorFlow is imported only by the offline training path.
    try:
        os.environ.setdefault("TF_DETERMINISTIC_OPS", "1")
        import tensorflow as tf  # type: ignore
        from tensorflow import keras  # type: ignore
        from tensorflow.keras import layers  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "TensorFlow is required only for training; install cron[fallback-lstm]"
        ) from exc

    os.environ.setdefault("PYTHONHASHSEED", str(config.seed))
    random.seed(config.seed)
    np.random.seed(config.seed)
    tf.random.set_seed(config.seed)
    try:
        keras.utils.set_random_seed(config.seed)
    except AttributeError:
        pass

    split = max(1, int(len(X_sequence) * 0.8))
    if split >= len(X_sequence):
        split = len(X_sequence) - 1
    sequence_mean, sequence_scale = _fit_scaler(X_sequence[:split].reshape(-1, X_sequence.shape[-1]))
    current_mean, current_scale = _fit_scaler(X_current[:split])
    target_mean, target_scale = _fit_scaler(y[:split])
    X_sequence_scaled = _scale(X_sequence, sequence_mean, sequence_scale).astype(np.float32)
    X_current_scaled = _scale(X_current, current_mean, current_scale).astype(np.float32)
    y_scaled = _scale(y, target_mean, target_scale).astype(np.float32)

    sequence_input = keras.Input(
        shape=(config.sequence_length, len(SEQUENCE_FEATURES)), name="sequence_input"
    )
    current_input = keras.Input(shape=(len(CURRENT_FEATURES),), name="current_dwd_input")
    sequence_branch = layers.LSTM(
        config.lstm_units, dropout=config.dropout_rate, recurrent_dropout=0.0
    )(sequence_input)
    current_branch = layers.Dense(16, activation="relu")(current_input)
    merged = layers.Concatenate()([sequence_branch, current_branch])
    merged = layers.Dense(32, activation="relu")(merged)
    merged = layers.Dropout(config.dropout_rate)(merged)
    output = layers.Dense(len(TARGET_COLUMNS), name="targets")(merged)
    model = keras.Model(
        inputs=[sequence_input, current_input],
        outputs=output,
        name="basic_lstm_fallback",
    )
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=config.learning_rate),
        loss="mse",
        metrics=["mae"],
    )
    model.fit(
        [X_sequence_scaled[:split], X_current_scaled[:split]],
        y_scaled[:split],
        validation_data=(
            [X_sequence_scaled[split:], X_current_scaled[split:]],
            y_scaled[split:],
        ),
        epochs=config.epochs,
        batch_size=config.batch_size,
        shuffle=False,
        verbose=0,
        callbacks=[
            keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=5, restore_best_weights=True
            )
        ],
    )

    model_path = Path(model_path)
    metadata_path = Path(metadata_path) if metadata_path else _metadata_path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    # Keep the temporary filename Keras-compatible (.keras extension), then
    # atomically replace the previously deployed artifact.
    temporary_model = model_path.with_name(model_path.stem + ".new.keras")
    model.save(temporary_model)
    os.replace(temporary_model, model_path)

    metadata: Dict[str, Any] = {
        "artifact_type": "fogcast-basic-lstm",
        "model_version": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sequence_length": config.sequence_length,
        "sequence_features": list(SEQUENCE_FEATURES),
        "current_features": list(CURRENT_FEATURES),
        "target_columns": list(TARGET_COLUMNS),
        "lstm_units": config.lstm_units,
        "dropout_rate": config.dropout_rate,
        "tensorflow_version": str(tf.__version__),
        "seed": config.seed,
        "training_samples": int(len(X_sequence)),
        "sequence_scaler": {
            "mean": sequence_mean.tolist(),
            "scale": sequence_scale.tolist(),
        },
        "current_scaler": {
            "mean": current_mean.tolist(),
            "scale": current_scale.tolist(),
        },
        "target_scaler": {
            "mean": target_mean.tolist(),
            "scale": target_scale.tolist(),
        },
        "artifact_sha256": _sha256(model_path),
    }
    temporary_metadata = metadata_path.with_name(metadata_path.name + ".new")
    with temporary_metadata.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
        handle.write("\n")
    os.replace(temporary_metadata, metadata_path)
    return metadata
