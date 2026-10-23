"""
Cronjob for handling missing Raspberry Pi weather data through DWD-based forecasting.
Detects data gaps and generates fallback predictions.
"""

import logging
from datetime import datetime
from typing import Dict, Optional
import pandas as pd
from influxdb_client import InfluxDBClient, Point

from cron.jobs.cronjob_base import CronjobBase
from cron.settings_utils import get_setting
from .dwd_data_fetcher import DWDDataFetcher
from .raspi_data_fetcher import RaspiDataFetcher
from .forecast_engine import ForecastEngine

logger = logging.getLogger(__name__)


class RaspiDWDFallbackCronjob(CronjobBase):
    """
    Cronjob to generate fallback weather data for Raspberry Pi when it fails to send data.

    This job:
    1. Detects if Raspberry Pi data is missing
    2. Analyzes historical correlations with DWD data
    3. Generates forecasts based on current DWD measurements
    4. Stores forecasted data in InfluxDB with quality flags
    """

    # Configuration constants
    DATA_GAP_THRESHOLD_HOURS = 2
    FORECAST_TRAINING_PERIOD_DAYS = 30
    INFLUX_BUCKET_WEATHER_DATA = "WeatherData"
    INFLUX_BUCKET_FORECAST = "WeatherForecast"
    INFLUX_ORG = "FogCast"

    def __init__(self):
        """Initialize the fallback cronjob."""
        super().__init__()
        self.influx_client = self._initialize_influx()
        self.org = self.INFLUX_ORG

        if self.influx_client is None:
            logger.error("Failed to initialize InfluxDB client")
            raise RuntimeError("InfluxDB initialization failed")

        self.raspi_fetcher = RaspiDataFetcher(self.influx_client, self.org)
        self.dwd_fetcher = DWDDataFetcher()
        self.forecast_engine = ForecastEngine(
            self.raspi_fetcher,
            self.dwd_fetcher,
            self.FORECAST_TRAINING_PERIOD_DAYS,
            fallback_config=get_setting("fallback", None),
        )

    def _initialize_influx(self) -> Optional[InfluxDBClient]:
        """Initialize InfluxDB client from settings."""
        try:
            url = get_setting('influx.url', 'http://localhost:8086')
            token = get_setting('influx.token', '')
            org = self.INFLUX_ORG

            if not token:
                logger.error("InfluxDB token not configured")
                return None

            return InfluxDBClient(
                url=url,
                token=token,
                org=org,
                timeout=120_000
            )
        except Exception as e:
            logger.error(f"Error initializing InfluxDB: {e}")
            return None

    def shouldStart(self, local_dt: datetime) -> bool:
        """
        Check if this job should run.

        Args:
            local_dt: Current datetime

        Returns:
            True if job should execute
        """
        # Run every 30 minutes
        return local_dt.minute % 30 == 0

    def start(self, local_dt: datetime) -> bool:
        """
        Execute the fallback forecast job.

        Args:
            local_dt: Current datetime

        Returns:
            True if successful, False if job handled error gracefully
        """
        try:
            logger.info("Starting Raspi DWD Fallback Cronjob")

            # Check for data gaps
            gaps = self.raspi_fetcher.detect_data_gap(
                threshold_hours=self.DATA_GAP_THRESHOLD_HOURS
            )

            if not any(gaps.values()):
                logger.info("No data gaps detected, job completed successfully")
                return True

            logger.warning(f"Data gaps detected: {gaps}")

            # Prepare forecast model
            if not self.forecast_engine.prepare_forecast():
                logger.error("Failed to prepare forecast model")
                return False

            # Generate forecasts
            forecasts = self.forecast_engine.forecast_missing_fields()

            if not forecasts:
                logger.warning("No forecasts generated")
                return False

            # Store forecasts in InfluxDB
            success = self._store_forecasts(forecasts, local_dt)

            if success:
                logger.info(f"Successfully stored {len(forecasts)} forecast values")
                self._send_notification(forecasts, gaps)

            return success

        except Exception as e:
            logger.exception("Critical error in Raspi DWD Fallback Cronjob")
            return False

    def _store_forecasts(self, forecasts: Dict[str, float], timestamp: datetime) -> bool:
        """
        Store forecasted values in InfluxDB.

        Args:
            forecasts: Dictionary mapping field names to forecasted values
            timestamp: Timestamp for the forecast

        Returns:
            True if successful
        """
        try:
            write_api = self.influx_client.write_api()
            points = []
            forecast_metadata = self.forecast_engine.last_forecast_metadata

            for field, value in forecasts.items():
                metadata = forecast_metadata.get(field, {})
                point = Point(measurement="weather_station") \
                    .field(field, float(value)) \
                    .field("is_fallback", True) \
                    .field("forecast_quality", "estimated") \
                    .tag("forecast_model", str(metadata.get("model", "unknown"))) \
                    .tag("model_version", str(metadata.get("model_version", "unknown"))) \
                    .tag("forecast_reason", str(metadata.get("reason", "unknown"))) \
                    .tag("plausibility", str(metadata.get("plausibility", "unknown"))) \
                    .time(timestamp)

                points.append(point)

            if points:
                write_api.write(
                    bucket=self.INFLUX_BUCKET_WEATHER_DATA,
                    org=self.org,
                    records=points
                )
                logger.info(f"Wrote {len(points)} forecast records to InfluxDB")
                return True

            return False

        except Exception as e:
            logger.error(f"Error storing forecasts in InfluxDB: {e}")
            return False

    def _send_notification(self, forecasts: Dict[str, float], gaps: Dict[str, bool]) -> None:
        """
        Send Discord notification about forecasts.

        Args:
            forecasts: Generated forecasts
            gaps: Detected data gaps
        """
        try:
            if not self._webhook:
                return

            gap_list = ", ".join([k for k, v in gaps.items() if v])
            forecast_list = "\n".join([
                f"• {k}: {v:.2f}" for k, v in forecasts.items()
            ])

            message = (
                f"🌡️ **Raspberry Pi Fallback Forecast Generated**\n"
                f"**Time:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                f"**Detected Gaps:** {gap_list}\n\n"
                f"**Generated Forecasts:**\n{forecast_list}\n\n"
                f"**Training Period:** {self.FORECAST_TRAINING_PERIOD_DAYS} days\n"
                f"**Data Freshness:** Uses DWD data from Konstanz station"
            )

            self._webhook.send(message)

        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")

    def cleanUpAfterError(self) -> None:
        """Cleanup after job error."""
        try:
            if self.influx_client:
                self.influx_client.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
