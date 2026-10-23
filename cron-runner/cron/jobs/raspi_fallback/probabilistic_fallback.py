"""
CRPS-Optimized Fallback System Integration
Integrates probabilistic LSTM forecasting with fallback correlation-based approach

This module combines:
1. Primary: LSTM with CRPS for probabilistic forecasting
2. Fallback: Correlation-based estimation for when LSTM unavailable
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class ProbabilisticFallbackPredictor:
    """
    Hybrid predictor combining LSTM (CRPS) and correlation-based approaches
    """

    def __init__(self, lstm_model=None, correlation_analyzer=None):
        """
        Args:
            lstm_model: Trained LSTM model (outputs μ, σ for each variable)
            correlation_analyzer: Fallback correlation analyzer
        """
        self.lstm_model = lstm_model
        self.correlation_analyzer = correlation_analyzer
        self.fallback_used = False

    def predict_with_uncertainty(
        self,
        raspi_history: pd.DataFrame,
        dwd_current: Dict[str, float],
        dwd_history: pd.DataFrame,
        use_lstm: bool = True
    ) -> Dict[str, Dict[str, float]]:
        """
        Generate probabilistic forecast with uncertainty quantification

        Args:
            raspi_history: Past 30 days of Raspi data
            dwd_current: Current DWD measurements
            dwd_history: Past 30 days of DWD data
            use_lstm: Try LSTM first, fall back to correlation

        Returns:
            Dictionary with predictions and uncertainty:
            {
                'temperature': {
                    'mean': 16.5,
                    'std': 0.8,
                    'ci_lower_95': 14.93,
                    'ci_upper_95': 18.07,
                    'confidence': 0.95,
                    'method': 'lstm_crps'
                },
                ...
            }
        """

        self.fallback_used = False
        predictions = {}

        # Try LSTM first if available
        if use_lstm and self.lstm_model is not None:
            try:
                predictions = self._predict_lstm_crps(
                    raspi_history, dwd_current, dwd_history
                )
                logger.info("✓ LSTM CRPS prediction successful")
                return predictions
            except Exception as e:
                logger.warning(f"LSTM prediction failed, using fallback: {e}")
                self.fallback_used = True

        # Fallback: Correlation-based with uncertainty estimation
        predictions = self._predict_correlation_based(
            raspi_history, dwd_current, dwd_history
        )

        return predictions

    def _predict_lstm_crps(
        self,
        raspi_history: pd.DataFrame,
        dwd_current: Dict[str, float],
        dwd_history: pd.DataFrame
    ) -> Dict[str, Dict[str, float]]:
        """
        LSTM CRPS prediction with probabilistic outputs
        """
        import tensorflow as tf

        # Prepare features (same as training)
        features = self._prepare_lstm_features(
            raspi_history, dwd_current, dwd_history
        )

        # Get raw model output: [μ_t, σ_t, μ_h, σ_h, μ_w, σ_w]
        raw_pred = self.lstm_model.predict(features)  # Shape: (1, 6)

        # Extract and denormalize
        means = raw_pred[0, [0, 2, 4]]      # [μ_temp, μ_humid, μ_water]
        stds = raw_pred[0, [1, 3, 5]]       # [σ_temp, σ_humid, σ_water]

        # Ensure stds > 0
        stds = np.maximum(stds, 1e-6)

        # Denormalize (if using scaler)
        means_denorm, stds_denorm = self._denormalize_predictions(means, stds)

        # Compute 95% Confidence Intervals
        z_95 = 1.96

        predictions = {
            'temperature': {
                'mean': float(means_denorm[0]),
                'std': float(stds_denorm[0]),
                'ci_lower_95': float(means_denorm[0] - z_95 * stds_denorm[0]),
                'ci_upper_95': float(means_denorm[0] + z_95 * stds_denorm[0]),
                'confidence': 0.95,
                'method': 'lstm_crps'
            },
            'humidity': {
                'mean': float(means_denorm[1]),
                'std': float(stds_denorm[1]),
                'ci_lower_95': float(means_denorm[1] - z_95 * stds_denorm[1]),
                'ci_upper_95': float(means_denorm[1] + z_95 * stds_denorm[1]),
                'confidence': 0.95,
                'method': 'lstm_crps'
            },
            'water_temperature': {
                'mean': float(means_denorm[2]),
                'std': float(stds_denorm[2]),
                'ci_lower_95': float(means_denorm[2] - z_95 * stds_denorm[2]),
                'ci_upper_95': float(means_denorm[2] + z_95 * stds_denorm[2]),
                'confidence': 0.95,
                'method': 'lstm_crps'
            }
        }

        return predictions

    def _predict_correlation_based(
        self,
        raspi_history: pd.DataFrame,
        dwd_current: Dict[str, float],
        dwd_history: pd.DataFrame
    ) -> Dict[str, Dict[str, float]]:
        """
        Fallback: Correlation-based prediction with estimated uncertainty
        """

        # Calculate correlations
        correlations = self.correlation_analyzer.calculate_correlations(
            raspi_history, dwd_history
        )

        # Get historical statistics for uncertainty estimation
        raspi_stats = self._compute_statistics(raspi_history)
        dwd_stats = self._compute_statistics(dwd_history)

        predictions = {}

        # Temperature
        temp_corr = correlations.get('temperature_vs_temperature', 0.7)
        temp_est = self.correlation_analyzer.estimate_value(
            dwd_value=dwd_current.get('temperature', 15.0),
            raspi_dwd_correlation=temp_corr,
            dwd_historical_mean=dwd_stats['temperature']['mean'],
            dwd_historical_std=dwd_stats['temperature']['std'],
            raspi_historical_mean=raspi_stats['temperature']['mean'],
            raspi_historical_std=raspi_stats['temperature']['std']
        )

        # Estimate uncertainty from residuals
        temp_uncertainty = raspi_stats['temperature']['std'] * (1 - abs(temp_corr))

        predictions['temperature'] = {
            'mean': float(temp_est),
            'std': float(temp_uncertainty),
            'ci_lower_95': float(temp_est - 1.96 * temp_uncertainty),
            'ci_upper_95': float(temp_est + 1.96 * temp_uncertainty),
            'confidence': 0.95,
            'method': 'correlation_based',
            'correlation': float(temp_corr)
        }

        # Similar for humidity
        humid_corr = correlations.get('humidity_vs_humidity', 0.6)
        humid_est = self.correlation_analyzer.estimate_value(
            dwd_value=dwd_current.get('humidity', 70.0),
            raspi_dwd_correlation=humid_corr,
            dwd_historical_mean=dwd_stats['humidity']['mean'],
            dwd_historical_std=dwd_stats['humidity']['std'],
            raspi_historical_mean=raspi_stats['humidity']['mean'],
            raspi_historical_std=raspi_stats['humidity']['std']
        )

        humid_uncertainty = raspi_stats['humidity']['std'] * (1 - abs(humid_corr))

        predictions['humidity'] = {
            'mean': float(humid_est),
            'std': float(humid_uncertainty),
            'ci_lower_95': float(humid_est - 1.96 * humid_uncertainty),
            'ci_upper_95': float(humid_est + 1.96 * humid_uncertainty),
            'confidence': 0.95,
            'method': 'correlation_based',
            'correlation': float(humid_corr)
        }

        # Water temperature (estimate from Raspi history)
        water_mean = raspi_stats['water_temperature']['mean']
        water_uncertainty = raspi_stats['water_temperature']['std']

        predictions['water_temperature'] = {
            'mean': float(water_mean),
            'std': float(water_uncertainty),
            'ci_lower_95': float(water_mean - 1.96 * water_uncertainty),
            'ci_upper_95': float(water_mean + 1.96 * water_uncertainty),
            'confidence': 0.95,
            'method': 'correlation_based'
        }

        logger.info("✓ Correlation-based fallback prediction")

        return predictions

    def _prepare_lstm_features(
        self,
        raspi_history: pd.DataFrame,
        dwd_current: Dict[str, float],
        dwd_history: pd.DataFrame
    ) -> np.ndarray:
        """
        Prepare features for LSTM model (same as training)
        """
        # Should match training preprocessing
        # Returns shape (1, 720, 7)

        # Placeholder - implement based on your actual preprocessing
        raise NotImplementedError("Implement based on your training setup")

    def _denormalize_predictions(
        self,
        means: np.ndarray,
        stds: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Denormalize LSTM outputs using training scalers
        """
        # Placeholder - implement based on your scalers
        return means, stds

    def _compute_statistics(
        self,
        data: pd.DataFrame
    ) -> Dict[str, Dict[str, float]]:
        """
        Compute mean and std for each variable
        """
        stats = {}

        for col in ['temperature', 'humidity', 'water_temperature']:
            if col in data.columns:
                values = data[col].dropna()
                stats[col] = {
                    'mean': float(values.mean()),
                    'std': float(values.std()),
                    'count': len(values)
                }

        return stats


# ==============================================================================
# InfluxDB Integration for Probabilistic Forecasts
# ==============================================================================

def save_probabilistic_forecast(
    forecast_dict: Dict[str, Dict[str, float]],
    influx_client,
    bucket: str = "WeatherForecast"
):
    """
    Save probabilistic forecast (with μ, σ, CI) to InfluxDB

    Args:
        forecast_dict: Output from predict_with_uncertainty()
        influx_client: InfluxDB client
        bucket: Target bucket
    """
    from influxdb_client import Point
    from datetime import datetime

    write_api = influx_client.write_api()

    timestamp = datetime.utcnow().isoformat()

    for var_name, var_data in forecast_dict.items():
        point = Point("weather_forecast_crps") \
            .field(f"{var_name}_mean", var_data['mean']) \
            .field(f"{var_name}_std", var_data['std']) \
            .field(f"{var_name}_ci_lower_95", var_data['ci_lower_95']) \
            .field(f"{var_name}_ci_upper_95", var_data['ci_upper_95']) \
            .tag("variable", var_name) \
            .tag("model", var_data['method']) \
            .tag("confidence", str(var_data['confidence'])) \
            .time(timestamp)

        write_api.write(bucket=bucket, record=point)

    logger.info(f"✓ Saved probabilistic forecast to InfluxDB: {timestamp}")


def retrieve_probabilistic_forecast(
    influx_client,
    bucket: str = "WeatherForecast",
    time_range: str = "-1h"
) -> Dict[str, Dict[str, float]]:
    """
    Retrieve latest probabilistic forecast from InfluxDB
    """
    query_api = influx_client.query_api()

    query = f'''
    from(bucket: "{bucket}")
    |> range(start: {time_range})
    |> filter(fn: (r) => r["_measurement"] == "weather_forecast_crps")
    |> sort(columns: ["_time"], desc: true)
    |> limit(n: 100)
    '''

    result = query_api.query(query)

    forecasts = {}
    for table in result:
        for record in table.records:
            var = record.values.get("variable", "unknown")
            field = record.get_field()
            value = record.get_value()

            if var not in forecasts:
                forecasts[var] = {}

            forecasts[var][field] = value

    return forecasts

