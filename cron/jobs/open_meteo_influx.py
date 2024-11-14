from datetime import datetime, timezone
import openmeteo_requests

import requests_cache
import pandas as pd
from retry_requests import retry
import influxdb_client
from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from cron.jobs.cronjob_base import CronjobBase
from cron.jobs.toDataFrame import toDataFrame
from cron.settings import settings


class OpenMeteoInfluxCronjob(CronjobBase):
    def __init__(self):
        super().__init__()
        self._lastDataDirectory = None

        models_df = pd.read_csv(settings.model_ids_path)
        self._models = {row['id']: row['name'] for _, row in models_df.iterrows()}

        hourly_fields_df = pd.read_csv(settings.hourly_fields_path)
        self._hourly_fields = [row['field'] for _, row in hourly_fields_df.iterrows()]

        self.client = influxdb_client.InfluxDBClient(url=settings.influx.url, token=settings.influx.token, org=settings.influx.org)

    def start(self, dt: datetime) -> bool:
        cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
        retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
        openmeteo = openmeteo_requests.Client(session = retry_session)

        # Make sure all required weather variables are listed here
        # The order of variables in hourly or daily is important to assign them correctly below
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": settings.latitude,
            "longitude": settings.longitude,
            "hourly": self._hourly_fields,
            "timezone": "Europe/Berlin",
            "models": self._models.values()
        }
        responses = openmeteo.weather_api(url, params=params)
        
        timestamp = datetime.now(timezone.utc)
        
        write_api = self.client.write_api(write_options=SYNCHRONOUS)

        for (i, response) in enumerate(responses):
            model_id = response.Model()
            model = self._models[model_id]
            df = toDataFrame(response)

            influx_data = []

            for index, row in df.iterrows():
                point = Point("forecast")
                point.time(timestamp, WritePrecision.S)
                point.tag("model", model)
                point.tag("latitude", settings.latitude)
                point.tag("longitude", settings.longitude)
                point.tag("forecast_date", row["date"])

                row = row.drop("date")

                is_nan = row.isna()
                if is_nan.sum() == len(row):
                    # if all values are NaN, skip this row
                    # this can happen if the forecast is too far in the future 
                    # and the model does not provide data yet
                    continue

                for key, value in row.items():
                    if pd.isna(value):
                        # skip NaN values
                        # this can happen if the model does not provide data for this field
                        continue
                    point.field(key, value)

                influx_data.append(point)
                
            write_api.write(bucket=settings.influx.bucket, org="FogCast", record=influx_data)
            print("Wrote", len(influx_data), "rows for", model)

    def cleanUpAfterError(self):
        pass
