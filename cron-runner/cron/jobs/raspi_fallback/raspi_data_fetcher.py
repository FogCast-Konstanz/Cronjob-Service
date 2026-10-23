"""
InfluxDB data fetcher for retrieving Raspberry Pi weather station data.
Queries the WeatherData bucket for historical and current measurements.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
from influxdb_client import InfluxDBClient

logger = logging.getLogger(__name__)


class RaspiDataFetcher:
    """
    Fetches Raspberry Pi weather station data from InfluxDB.

    Retrieves both real-time and historical measurements from the WeatherData bucket.
    """

    INFLUX_BUCKET = "WeatherData"
    MEASUREMENT_NAME = "weather_station"

    # Field mappings for Raspberry Pi data
    FIELD_MAPPINGS = {
        'temperature': 'temperature',
        'humidity': 'humidity',
        'water_temperature': 'water_temperature',
    }

    def __init__(self, influx_client: InfluxDBClient, org: str):
        """
        Initialize the Raspberry Pi data fetcher.

        Args:
            influx_client: InfluxDBClient instance
            org: InfluxDB organization name
        """
        self.client = influx_client
        self.org = org
        self.query_api = influx_client.query_api()

    def get_data(
        self,
        start: datetime,
        stop: datetime,
        fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Fetch Raspberry Pi weather data from InfluxDB.

        Args:
            start: Start datetime (inclusive)
            stop: Stop datetime (exclusive)
            fields: List of field names to retrieve (default: all)

        Returns:
            DataFrame with columns: timestamp, temperature, humidity, water_temperature
        """
        if fields is None:
            fields = list(self.FIELD_MAPPINGS.keys())

        try:
            # Build Flux query
            flux_query = self._build_query(start, stop, fields)
            result = self.query_api.query(query=flux_query, org=self.org)

            # Convert result to DataFrame
            df = self._convert_result_to_dataframe(result)

            if not df.empty:
                logger.info(f"Retrieved {len(df)} Raspberry Pi records from {start} to {stop}")
            else:
                logger.warning(f"No Raspberry Pi data found from {start} to {stop}")

            return df

        except Exception as e:
            logger.error(f"Error fetching Raspberry Pi data: {e}")
            return pd.DataFrame()

    def get_recent_data(self, hours: int = 24, fields: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Fetch recent Raspberry Pi weather data.

        Args:
            hours: Number of hours to look back
            fields: List of field names to retrieve (default: all)

        Returns:
            DataFrame with recent measurements
        """
        stop = datetime.utcnow()
        start = stop - timedelta(hours=hours)
        return self.get_data(start, stop, fields)

    def get_last_measurement(self, field: str = 'temperature') -> Optional[Dict]:
        """
        Get the most recent measurement for a specific field.

        Args:
            field: Field name to retrieve

        Returns:
            Dictionary with 'timestamp', 'value', and 'field' keys, or None if not found
        """
        try:
            flux_query = f'''
            from(bucket: "{self.INFLUX_BUCKET}")
              |> range(start: -7d)
              |> filter(fn: (r) => r["_measurement"] == "{self.MEASUREMENT_NAME}")
              |> filter(fn: (r) => r["_field"] == "{field}")
              |> sort(columns: ["_time"], desc: true)
              |> limit(n: 1)
            '''

            result = self.query_api.query(query=flux_query, org=self.org)

            if result and len(result) > 0 and len(result[0].records) > 0:
                record = result[0].records[0]
                return {
                    'timestamp': record.get_time(),
                    'value': record.get_value(),
                    'field': field
                }
            return None

        except Exception as e:
            logger.error(f"Error fetching last measurement for {field}: {e}")
            return None

    def detect_data_gap(
        self,
        threshold_hours: int = 2,
        fields: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Detect if there is a data gap for any field.

        Args:
            threshold_hours: Gap is detected if no data for this many hours
            fields: Fields to check (default: all)

        Returns:
            Dictionary mapping field names to boolean indicating gap presence
        """
        if fields is None:
            fields = list(self.FIELD_MAPPINGS.keys())

        gaps = {}
        for field in fields:
            last_measurement = self.get_last_measurement(field)

            if last_measurement is None:
                gaps[field] = True
                logger.warning(f"No data found for field: {field}")
            else:
                time_since_last = datetime.utcnow() - last_measurement['timestamp'].replace(tzinfo=None)
                has_gap = time_since_last > timedelta(hours=threshold_hours)
                gaps[field] = has_gap

                if has_gap:
                    logger.warning(
                        f"Data gap detected for {field}: "
                        f"{time_since_last.total_seconds()/3600:.1f} hours since last measurement"
                    )

        return gaps

    def _build_query(self, start: datetime, stop: datetime, fields: List[str]) -> str:
        """
        Build a Flux query for InfluxDB.

        Args:
            start: Start datetime
            stop: Stop datetime
            fields: List of field names

        Returns:
            Flux query string
        """
        # Convert to RFC3339 format
        start_rfc = start.isoformat() + 'Z' if start.tzinfo is None else start.isoformat()
        stop_rfc = stop.isoformat() + 'Z' if stop.tzinfo is None else stop.isoformat()

        field_filter = '|> filter(fn: (r) => ' + ' or '.join([
            f'r["_field"] == "{field}"' for field in fields
        ]) + ')'

        query = f'''
        from(bucket: "{self.INFLUX_BUCKET}")
          |> range(start: {start_rfc}, stop: {stop_rfc})
          |> filter(fn: (r) => r["_measurement"] == "{self.MEASUREMENT_NAME}")
          {field_filter}
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"])
        '''
        return query

    def _convert_result_to_dataframe(self, result) -> pd.DataFrame:
        """
        Convert InfluxDB query result to pandas DataFrame.

        Args:
            result: InfluxDB query result

        Returns:
            Formatted DataFrame
        """
        try:
            data = []
            for table in result:
                for record in table.records:
                    row = {'timestamp': record.get_time()}
                    for key, value in record.values.items():
                        if key not in ['_measurement', '_start', '_stop', 'result', 'table']:
                            row[key] = value
                    data.append(row)

            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            return df.sort_values('timestamp')

        except Exception as e:
            logger.error(f"Error converting InfluxDB result to DataFrame: {e}")
            return pd.DataFrame()

    def get_historical_statistics(
        self,
        field: str,
        days: int = 30
    ) -> Dict[str, float]:
        """
        Calculate statistics for a field over historical period.

        Args:
            field: Field name
            days: Number of historical days to analyze

        Returns:
            Dictionary with 'mean', 'std', 'min', 'max', 'count' keys
        """
        try:
            end = datetime.utcnow()
            start = end - timedelta(days=days)

            df = self.get_data(start, end, [field])

            if df.empty or field not in df.columns:
                logger.warning(f"No historical data for field: {field}")
                return {
                    'mean': None,
                    'std': None,
                    'min': None,
                    'max': None,
                    'count': 0
                }

            values = df[field].dropna()

            return {
                'mean': float(values.mean()),
                'std': float(values.std()),
                'min': float(values.min()),
                'max': float(values.max()),
                'count': int(len(values))
            }

        except Exception as e:
            logger.error(f"Error calculating historical statistics for {field}: {e}")
            return {
                'mean': None,
                'std': None,
                'min': None,
                'max': None,
                'count': 0
            }

