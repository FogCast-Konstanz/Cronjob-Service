import influxdb_client
from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import os
import numpy as np
import pandas as pd
from cron.settings import settings
import warnings
from datetime import datetime, timedelta, timezone
import openmeteo_requests
import requests_cache
from retry_requests import retry
import itertools
import pytz
from time import time

class BenchmarkingService:
    def __init__(self):
        self.models = [
            "ecmwf_ifs04", "ecmwf_ifs025", "ecmwf_aifs025", "cma_grapes_global", "bom_access_global",
            "gfs_seamless", "gfs_global", "gfs_hrrr", "ncep_nbm_conus", "gfs_graphcast025",
            "jma_seamless", "jma_msm", "jma_gsm", "icon_seamless", "icon_global", "icon_eu", "icon_d2",
            "gem_seamless", "gem_global", "gem_regional", "gem_hrdps_continental",
            "meteofrance_seamless", "meteofrance_arpege_world", "meteofrance_arpege_europe",
            "meteofrance_arome_france", "meteofrance_arome_france_hd", "metno_seamless", "metno_nordic",
            "knmi_seamless", "knmi_harmonie_arome_europe", "knmi_harmonie_arome_netherlands",
            "dmi_seamless", "dmi_harmonie_arome_europe", "ukmo_seamless", "ukmo_global_deterministic_10km",
            "ukmo_uk_deterministic_2km"
        ]
        self.vs_models = ["gfs_hrrr"]
        self.s_models = [
            "icon_d2", "gem_regional", "gem_hrdps_continental", "meteofrance_arome_france",
            "meteofrance_arome_france_hd", "metno_seamless", "metno_nordic", "knmi_seamless",
            "knmi_harmonie_arome_europe", "knmi_harmonie_arome_netherlands", "dmi_seamless",
            "dmi_harmonie_arome_europe", "ukmo_uk_deterministic_2km"
        ]
        self.m_models = [
            "jma_msm", "icon_seamless", "icon_global", "icon_eu", "meteofrance_seamless",
            "meteofrance_arpege_world", "meteofrance_arpege_europe", "ukmo_seamless",
            "ukmo_global_deterministic_10km"
        ]
        self.l_models = [
            "ecmwf_ifs04", "ecmwf_ifs025", "ecmwf_aifs025", "cma_grapes_global", "bom_access_global",
            "gfs_seamless", "gfs_global", "ncep_nbm_conus", "gfs_graphcast025", "jma_seamless", "jma_gsm",
            "gem_seamless", "gem_global"
        ]
        self.client = influxdb_client.InfluxDBClient(
            url=settings.influx.url,
            token=settings.influx.token,
            org=settings.influx.org,
            timeout=120_000,
            verify_ssl=False,  # Disable SSL verification for self-signed certificates
            http_client_kwargs={"timeout": 300}
        )
        self.bucket = 'WeatherForecast'

    def get_forecasts(self, start_time, end_time):
        query = f'''
            from(bucket: "{self.bucket}") 
                |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
                |> filter(fn : (r) => r["_field"] == "temperature_2m"
                    or r["_field"] == "relative_humidity_2m"
                    or r["_field"] == "precipitation"
                    or r["_field"] == "cloud_cover"
                    or r["_field"] == "surface_pressure"
                    or r["_field"] == "dew_point_2m")
                |> keep(columns: ["_time", "forecast_date", "model", "_value", "_field"])
        '''
        try:
            query_api = self.client.query_api()
            tables = query_api.query_data_frame(query)
            df = pd.DataFrame(tables)
        except Exception as e:
            print(f"Error running query: {e}")
            raise
        return df
    
    def write_data_to_influxdb(self, df: pd.DataFrame, batch_size: int = 5000):
        total_rows = len(df)
        batch = []
        progress_bar = itertools.cycle(["|", "/", "-", "\\"])
        write_api = self.client.write_api(write_options=SYNCHRONOUS)
        for index, row in df.iterrows():
            point = Point("error_score") \
                .field("_value", float(row["_value"])) \
                .field("actual_value", float(row["actual_value"])) \
                .field("error", float(row["error"])) \
                .tag("feature", str(row["_field"])) \
                .tag("forecast_date", str(row["forecast_date"])) \
                .tag("_model", str(row["model"])) \
                .tag("forecast_horizon", str(row["forecast_horizon"])) \
                .time(
                    row["_time"].tz_convert('UTC') if row["_time"].tzinfo 
                    else row["_time"].tz_localize('UTC')
                )
            batch.append(point)
            if len(batch) == batch_size:
                write_api.write(bucket=self.bucket, org=settings.influx.org, record=batch)
                batch = []
            if index % 1000 == 0 or index == total_rows - 1:
                print(f"\rWriting {index + 1}/{total_rows} {next(progress_bar)}", end="")
        if batch:
            write_api.write(bucket=self.bucket, org=settings.influx.org, record=batch)
        print("\nMigration completed.")

    def get_measured(self, start_time, end_time):
        cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        openmeteo = openmeteo_requests.Client(session=retry_session)
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": 47.6952,
            "longitude": 9.1307,
            "hourly": [
                "temperature_2m", "surface_pressure", "cloud_cover",
                "precipitation", "relative_humidity_2m", "dew_point_2m"
            ],
            "timezone": "Europe/Berlin",
            "start_date": start_time.date(),
            "end_date": end_time.date(),
        }
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]
        hourly = response.Hourly()
        hourly_data = {
            "date": pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left"
            ),
            "temperature_2m": hourly.Variables(0).ValuesAsNumpy(),
            "surface_pressure": hourly.Variables(1).ValuesAsNumpy(),
            "cloud_cover": hourly.Variables(2).ValuesAsNumpy(),
            "precipitation": hourly.Variables(3).ValuesAsNumpy(),
            "relative_humidity_2m": hourly.Variables(4).ValuesAsNumpy(),
            "dew_point_2m": hourly.Variables(5).ValuesAsNumpy()
        }
        return pd.DataFrame(data=hourly_data)

    def calculate_error(self, df):
        df['actual_value'] = df.apply(
            lambda row: row[row['_field']] if row['_field'] in df.columns else np.nan,
            axis=1
        )
        def compute_error(row):
            if row['_field'] in ['cloud_cover', 'relative_humidity_2m']:
                return abs(row['_value'] - row['actual_value'])
            else:
                return (row['_value'] - row['actual_value']) ** 2
        df['error'] = df.apply(compute_error, axis=1)
        return df.drop(columns=[
            "temperature_2m", "relative_humidity_2m", "dew_point_2m",
            "cloud_cover", "surface_pressure", "precipitation",
            "date", "result", "table"
        ], errors='ignore')

    def run_benchmark(self):
        warnings.simplefilter("ignore")
        current_date = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        self._process_vs_error(current_date)
        self._process_s_error(current_date)
        self._process_m_error(current_date)
        self._process_l_error(current_date)

    def _process_vs_error(self, current_date):
        start_time = time()
        print("Method _process_vs_error started...")

        end_dt = datetime.fromisoformat(current_date).replace(tzinfo=pytz.UTC)
        start_dt = end_dt - timedelta(days=1)

        forecasts = self.get_forecasts(start_dt, end_dt)
        measured = self.get_measured(start_dt, end_dt)

        forecasts["_time"] = pd.to_datetime(forecasts["_time"]).dt.floor('S')
        measured["date"] = pd.to_datetime(measured["date"]).dt.floor('S')

        merged = forecasts.merge(measured, left_on="_time", right_on="date", how="inner")
        error_df = self.calculate_error(merged)
        error_df['forecast_horizon'] = 'very short'
        print(f"Writing {len(error_df)} very short error records to InfluxDB")
        self.write_data_to_influxdb(error_df)
        elapsed = time() - start_time
        print(f"Method _process_vs_error finished successfully in {elapsed:.2f} seconds.")
    
    def _process_s_error(self, current_date):
        start_time = time()
        print("Method _process_s_error started...")

        end_dt = datetime.fromisoformat(current_date).replace(tzinfo=pytz.UTC)
        start_dt = end_dt - timedelta(days=3)

        forecasts = self.get_forecasts(start_dt, end_dt)
        measured = self.get_measured(start_dt, end_dt)

        forecasts["_time"] = pd.to_datetime(forecasts["_time"]).dt.floor('S')
        measured["date"] = pd.to_datetime(measured["date"]).dt.floor('S')

        merged = forecasts.merge(measured, left_on="_time", right_on="date", how="inner")
        print(f"Merged records: {len(merged)}")

        error_df = self.calculate_error(merged)
        error_df['forecast_horizon'] = 'short'
        print(f"Writing {len(error_df)} short error records to InfluxDB")

        self.write_data_to_influxdb(error_df)
        elapsed = time() - start_time
        print(f"Method _process_s_error finished successfully in {elapsed:.2f} seconds.")


    def _process_m_error(self, current_date):
        start_time = time()
        print("Method _process_m_error started...")

        end_dt = datetime.fromisoformat(current_date).replace(tzinfo=pytz.UTC)
        start_dt = end_dt - timedelta(days=7)

        forecasts = self.get_forecasts(start_dt, end_dt)
        measured = self.get_measured(start_dt, end_dt)

        forecasts["_time"] = pd.to_datetime(forecasts["_time"]).dt.floor('S')
        measured["date"] = pd.to_datetime(measured["date"]).dt.floor('S')

        merged = forecasts.merge(measured, left_on="_time", right_on="date", how="inner")
        print(f"Merged records: {len(merged)}")

        error_df = self.calculate_error(merged)
        error_df['forecast_horizon'] = 'medium'
        print(f"Writing {len(error_df)} medium error records to InfluxDB")

        self.write_data_to_influxdb(error_df)
        elapsed = time() - start_time
        print(f"Method _process_m_error finished successfully in {elapsed:.2f} seconds.")


    def _process_l_error(self, current_date):
        start_time = time()
        print("Method _process_l_error started...")

        end_dt = datetime.fromisoformat(current_date).replace(tzinfo=pytz.UTC)
        start_dt = end_dt - timedelta(days=15)

        forecasts = self.get_forecasts(start_dt, end_dt)
        measured = self.get_measured(start_dt, end_dt)

        forecasts["_time"] = pd.to_datetime(forecasts["_time"]).dt.floor('S')
        measured["date"] = pd.to_datetime(measured["date"]).dt.floor('S')

        merged = forecasts.merge(measured, left_on="_time", right_on="date", how="inner")
        print(f"Merged records: {len(merged)}")

        error_df = self.calculate_error(merged)
        error_df['forecast_horizon'] = 'long'
        print(f"Writing {len(error_df)} long error records to InfluxDB")

        self.write_data_to_influxdb(error_df)
        elapsed = time() - start_time
        print(f"Method _process_l_error finished successfully in {elapsed:.2f} seconds.")
