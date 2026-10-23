import logging
from datetime import datetime
from typing import Any, Dict, Optional
import pandas as pd

from cron.settings_utils import get_setting
from .basic_lstm import BasicLSTMConfig, BasicLSTMForecaster
from .correlation_analyzer import CorrelationAnalyzer
from .dwd_data_fetcher import DWDDataFetcher
from .raspi_data_fetcher import RaspiDataFetcher

logger = logging.getLogger(__name__)


class ForecastEngine:
    """
    Generates forecasts for missing Raspberry Pi weather data using DWD correlations.

    This engine combines:
    1. Historical correlations between Raspberry Pi and DWD data
    2. Current DWD measurements
    3. Historical statistics for both stations

    To estimate missing Raspberry Pi values using linear regression.
    """

    def __init__(
        self,
        raspi_fetcher: RaspiDataFetcher,
        dwd_fetcher: DWDDataFetcher,
        training_period_days: int = 30,
        fallback_config: Optional[Any] = None,
    ):
        """
        Initialize the forecast engine.

        Args:
            raspi_fetcher: RaspiDataFetcher instance
            dwd_fetcher: DWDDataFetcher instance
            training_period_days: Days to use for correlation training
        """
        self.raspi_fetcher = raspi_fetcher
        self.dwd_fetcher = dwd_fetcher
        self.correlation_analyzer = CorrelationAnalyzer(training_period_days)
        self.training_period_days = training_period_days
        self.correlations: Dict[str, float] = {}
        self.raspi_stats: Dict[str, Dict] = {}
        self.dwd_stats: Dict[str, Dict] = {}
        self.raspi_history = pd.DataFrame()
        self.dwd_history = pd.DataFrame()
        self.last_forecast_metadata: Dict[str, Dict[str, Any]] = {}
        self._lstm_prediction_cache: Optional[Dict[str, float]] = None

        # Basic LSTM is the preferred strategy when a verified artifact and
        # optional TensorFlow runtime are present.  Missing artifacts are a
        # normal deployment state and intentionally do not fail the cronjob.
        config = fallback_config if fallback_config is not None else get_setting("fallback", None)
        self.primary_strategy = str(
            self._config_value(config, "primary", "basic_lstm")
        ).lower()
        if self.primary_strategy not in {"basic_lstm", "linear"}:
            logger.warning("Unknown fallback.primary '%s'; using linear", self.primary_strategy)
            self.primary_strategy = "linear"
        self.lstm_enabled = (
            self.primary_strategy == "basic_lstm"
            and bool(self._config_value(config, "basic_lstm.enabled", True))
        )
        self.plausibility_enabled = bool(
            self._config_value(config, "plausibility.enabled", True)
        )
        self.plausibility_margin = float(
            self._config_value(config, "plausibility.margin", 10.0)
        )
        self.basic_lstm: Optional[BasicLSTMForecaster] = None
        if self.lstm_enabled:
            lstm_config = BasicLSTMConfig(
                sequence_length=int(
                    self._config_value(config, "basic_lstm.sequence_length", 48)
                ),
                min_history_rows=int(
                    self._config_value(config, "basic_lstm.min_history_rows", 72)
                ),
            )
            model_path = self._config_value(
                config, "basic_lstm.model_path", "./config/models/basic_lstm.keras"
            )
            metadata_path = self._config_value(config, "basic_lstm.metadata_path", None)
            self.basic_lstm = BasicLSTMForecaster(model_path, metadata_path, lstm_config)
            if not self.basic_lstm.available:
                logger.info(
                    "Basic LSTM is configured as primary but unavailable (%s); "
                    "linear correlation fallback remains active",
                    self.basic_lstm.load_error,
                )

    @staticmethod
    def _config_value(config: Any, key: str, default: Any) -> Any:
        """Read dotted keys from Settings objects or plain dictionaries."""
        if config is None:
            return default
        value = config
        for part in key.split("."):
            if isinstance(value, dict):
                if part not in value:
                    return default
                value = value[part]
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return default
        return value

    def prepare_forecast(self) -> bool:
        """
        Prepare forecast by computing correlations and statistics.

        Returns:
            True if preparation successful, False otherwise
        """
        try:
            logger.info("Starting forecast preparation...")

            # Load historical data
            logger.info(f"Loading {self.training_period_days}-day historical data...")
            raspi_data = self.raspi_fetcher.get_recent_data(
                hours=self.training_period_days * 24
            )

            if raspi_data.empty:
                logger.error("No Raspberry Pi historical data available")
                return False
            self.raspi_history = raspi_data.copy()

            # Get corresponding DWD data
            start_date = raspi_data['timestamp'].min()
            end_date = raspi_data['timestamp'].max()
            dwd_data = self.dwd_fetcher.get_hourly_data(start_date, end_date)

            if dwd_data.empty:
                logger.error("No DWD historical data available")
                return False
            self.dwd_history = dwd_data.copy()

            # Calculate correlations
            logger.info("Calculating correlations...")
            self.correlations = self.correlation_analyzer.calculate_correlations(
                raspi_data, dwd_data
            )

            # Calculate historical statistics
            logger.info("Calculating historical statistics...")
            self._calculate_statistics(raspi_data, dwd_data)

            lstm_ready = bool(self.basic_lstm and self.basic_lstm.available)
            if not self.correlations and not lstm_ready:
                logger.error("No valid correlations and no usable Basic LSTM artifact")
                return False

            logger.info(
                "Forecast preparation complete (primary=%s)",
                "basic_lstm" if lstm_ready else "linear_correlation",
            )
            return True

        except Exception as e:
            logger.error(f"Error preparing forecast: {e}")
            return False

    def forecast_missing_fields(self) -> Dict[str, float]:
        """
        Forecast values for fields detected as missing in Raspberry Pi data.

        Returns:
            Dictionary mapping field names to forecasted values
        """
        try:
            # Detect data gaps
            gaps = self.raspi_fetcher.detect_data_gap(threshold_hours=2)
            logger.info(f"Detected data gaps: {gaps}")

            if not any(gaps.values()):
                logger.info("No data gaps detected, no forecasting needed")
                return {}

            # Get current DWD data
            dwd_current = self.dwd_fetcher.get_real_time_data()

            if dwd_current.empty:
                logger.error("Cannot forecast: no current DWD data available")
                return {}

            # Generate forecasts for missing fields
            forecasts = {}
            self.last_forecast_metadata = {}
            self._lstm_prediction_cache = None
            for field, has_gap in gaps.items():
                if has_gap and field in self.raspi_stats:
                    forecast_value = self._forecast_field(field, dwd_current)
                    if forecast_value is not None:
                        forecasts[field] = forecast_value
                        logger.info(f"Forecasted {field}: {forecast_value:.2f}")

            return forecasts

        except Exception as e:
            logger.error(f"Error forecasting missing fields: {e}")
            return {}

    def _forecast_field(self, raspi_field: str, dwd_current: pd.DataFrame) -> Optional[float]:
        """
        Forecast a single field value.

        Args:
            raspi_field: Raspberry Pi field name (e.g., 'temperature')
            dwd_current: Current DWD measurements DataFrame

        Returns:
            Forecasted value or None if unable to forecast
        """
        try:
            # Basic LSTM is the primary fallback.  A failed load, inference
            # error, or implausible output immediately selects the linear path.
            if self.lstm_enabled and self.basic_lstm and self.basic_lstm.available:
                try:
                    if self._lstm_prediction_cache is None:
                        self._lstm_prediction_cache = self.basic_lstm.predict(
                            self.raspi_history, self.dwd_history, dwd_current
                        )
                    lstm_predictions = self._lstm_prediction_cache
                    lstm_value = lstm_predictions.get(raspi_field)
                    if lstm_value is not None and self._is_plausible(raspi_field, lstm_value):
                        self.last_forecast_metadata[raspi_field] = {
                            "model": "basic_lstm",
                            "model_version": self.basic_lstm.version,
                            "reason": "primary_model",
                            "plausibility": "passed",
                        }
                        return float(lstm_value)
                    logger.warning("Basic LSTM output for %s failed plausibility check", raspi_field)
                except Exception as exc:
                    logger.warning("Basic LSTM prediction failed for %s: %s", raspi_field, exc)

            # Find matching DWD field for the deterministic linear fallback.
            dwd_field = CorrelationAnalyzer.FIELD_MAPPINGS.get(raspi_field)
            if not dwd_field:
                logger.warning(f"No DWD mapping for field: {raspi_field}")
                return None

            # Check if we have correlation data
            correlation_key = f"{raspi_field}_vs_{dwd_field}"
            if correlation_key not in self.correlations:
                logger.warning(f"No correlation data for: {correlation_key}")
                return None

            correlation = self.correlations[correlation_key]

            # Check correlation strength
            if abs(correlation) < CorrelationAnalyzer.MIN_CORRELATION_THRESHOLD:
                logger.warning(
                    f"Correlation too weak for {correlation_key}: {correlation:.3f}"
                )
                return None

            # Get DWD current value
            if dwd_field not in dwd_current.columns:
                logger.warning(f"DWD field not available: {dwd_field}")
                return None

            dwd_value = dwd_current[dwd_field].iloc[0]

            if pd.isna(dwd_value):
                logger.warning(f"Current DWD value is NaN for: {dwd_field}")
                return None

            # Get statistics
            raspi_stats = self.raspi_stats.get(raspi_field)
            dwd_stats = self.dwd_stats.get(dwd_field)

            if not raspi_stats or not dwd_stats:
                logger.warning(f"Missing statistics for {raspi_field} or {dwd_field}")
                return None

            # Estimate value using correlation
            estimated_value = self.correlation_analyzer.estimate_value(
                dwd_value=float(dwd_value),
                raspi_dwd_correlation=correlation,
                dwd_historical_mean=dwd_stats['mean'],
                dwd_historical_std=dwd_stats['std'],
                raspi_historical_mean=raspi_stats['mean'],
                raspi_historical_std=raspi_stats['std']
            )

            if not self._is_plausible(raspi_field, estimated_value):
                logger.warning("Linear fallback output for %s failed plausibility check", raspi_field)
                self.last_forecast_metadata[raspi_field] = {
                    "model": "linear_correlation",
                    "model_version": "builtin",
                    "reason": "plausibility_rejected",
                    "plausibility": "failed",
                }
                return None

            self.last_forecast_metadata[raspi_field] = {
                "model": "linear_correlation",
                "model_version": "builtin",
                "reason": "lstm_unavailable_or_rejected",
                "plausibility": "passed",
            }
            return estimated_value

        except Exception as e:
            logger.error(f"Error forecasting field {raspi_field}: {e}")
            return None

    def _is_plausible(self, field: str, value: float) -> bool:
        """Reject non-finite or physically implausible fallback values."""
        try:
            value = float(value)
        except (TypeError, ValueError):
            return False
        if not pd.notna(value) or not (-100.0 <= value <= 150.0):
            return False
        if not self.plausibility_enabled:
            return True

        # Hard physical bounds protect against corrupt model artifacts.
        hard_bounds = {
            "temperature": (-50.0, 70.0),
            "humidity": (0.0, 100.0),
            "water_temperature": (-10.0, 60.0),
        }
        lower, upper = hard_bounds.get(field, (-100.0, 150.0))
        stats = self.raspi_stats.get(field)
        if stats and stats.get("count", 0) > 0:
            lower = max(lower, float(stats["min"]) - self.plausibility_margin)
            upper = min(upper, float(stats["max"]) + self.plausibility_margin)
        return lower <= value <= upper

    def _calculate_statistics(self, raspi_data: pd.DataFrame, dwd_data: pd.DataFrame) -> None:
        """
        Calculate historical statistics for all available fields.

        Args:
            raspi_data: Raspberry Pi historical data
            dwd_data: DWD historical data
        """
        try:
            # Raspberry Pi statistics
            for field in CorrelationAnalyzer.FIELD_MAPPINGS.keys():
                if field in raspi_data.columns:
                    values = raspi_data[field].dropna()
                    if len(values) > 0:
                        self.raspi_stats[field] = {
                            'mean': float(values.mean()),
                            'std': float(values.std()) if len(values) > 1 else 0.0,
                            'min': float(values.min()),
                            'max': float(values.max()),
                            'count': len(values)
                        }
                        logger.info(
                            f"Raspi {field} stats: mean={self.raspi_stats[field]['mean']:.2f}, "
                            f"std={self.raspi_stats[field]['std']:.2f}"
                        )

            # DWD statistics
            for raspi_field, dwd_field in CorrelationAnalyzer.FIELD_MAPPINGS.items():
                if dwd_field in dwd_data.columns:
                    values = dwd_data[dwd_field].dropna()
                    if len(values) > 0:
                        self.dwd_stats[dwd_field] = {
                            'mean': float(values.mean()),
                            'std': float(values.std()) if len(values) > 1 else 0.0,
                            'min': float(values.min()),
                            'max': float(values.max()),
                            'count': len(values)
                        }
                        logger.info(
                            f"DWD {dwd_field} stats: mean={self.dwd_stats[dwd_field]['mean']:.2f}, "
                            f"std={self.dwd_stats[dwd_field]['std']:.2f}"
                        )

        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")

    def get_forecast_metadata(self) -> Dict:
        """
        Get metadata about the forecast model.

        Returns:
            Dictionary with correlation info, statistics, and quality metrics
        """
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'training_period_days': self.training_period_days,
            'correlations': self.correlations,
            'raspi_statistics': self.raspi_stats,
            'dwd_statistics': self.dwd_stats,
            'reliable_correlations': self.correlation_analyzer.get_reliable_correlations(),
            'fallback_strategy': f'{self.primary_strategy}_primary_linear_fallback',
            'basic_lstm': {
                'enabled': self.lstm_enabled,
                'available': bool(self.basic_lstm and self.basic_lstm.available),
                'model_version': self.basic_lstm.version if self.basic_lstm else 'disabled',
                'load_error': self.basic_lstm.load_error if self.basic_lstm else None,
            },
            'last_forecasts': self.last_forecast_metadata,
        }
