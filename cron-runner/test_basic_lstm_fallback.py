import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from cron.jobs.raspi_fallback.basic_lstm import (
    BasicLSTMForecaster,
    SEQUENCE_FEATURES,
    build_feature_tables,
)
from cron.jobs.raspi_fallback.forecast_engine import ForecastEngine


class _Fetcher:
    pass


class BasicLSTMFallbackTests(unittest.TestCase):
    def _frames(self):
        timestamps = pd.date_range("2026-01-01", periods=80, freq="h", tz="UTC")
        raspi = pd.DataFrame(
            {
                "timestamp": timestamps,
                "temperature": np.linspace(5, 15, len(timestamps)),
                "humidity": np.linspace(90, 60, len(timestamps)),
                "water_temperature": np.linspace(8, 10, len(timestamps)),
            }
        )
        dwd = pd.DataFrame(
            {
                "timestamp": timestamps,
                "temperature": np.linspace(4, 14, len(timestamps)),
                "humidity": np.linspace(88, 58, len(timestamps)),
            }
        )
        return raspi, dwd

    def test_feature_builder_is_deterministic_and_ordered(self):
        raspi, dwd = self._frames()
        sequence, current = build_feature_tables(raspi, dwd)
        self.assertEqual(list(sequence.columns), list(SEQUENCE_FEATURES))
        self.assertEqual(len(sequence), len(current))
        np.testing.assert_allclose(
            sequence.iloc[10].to_numpy(),
            build_feature_tables(raspi, dwd)[0].iloc[10].to_numpy(),
        )

    def test_missing_artifact_is_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            forecaster = BasicLSTMForecaster(Path(directory) / "missing.keras")
            self.assertFalse(forecaster.available)
            with self.assertRaises(RuntimeError):
                forecaster.predict(*self._frames(), self._frames()[1].tail(1))

    def test_plausibility_rejects_invalid_humidity(self):
        engine = ForecastEngine(_Fetcher(), _Fetcher(), fallback_config={"basic_lstm": {"enabled": False}})
        engine.raspi_stats = {
            "humidity": {"min": 40.0, "max": 80.0, "count": 100}
        }
        self.assertTrue(engine._is_plausible("humidity", 75.0))
        self.assertFalse(engine._is_plausible("humidity", 120.0))
        self.assertFalse(engine._is_plausible("temperature", float("nan")))


if __name__ == "__main__":
    unittest.main()
