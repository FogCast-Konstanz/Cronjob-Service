import warnings
import pandas as pd
import requests_cache
import openmeteo_requests
from retry_requests import retry
from datetime import datetime, timedelta, timezone
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client import Point
import influxdb_client
from cron.settings import settings

class BenchmarkingService:
    def __init__(self):
        # vs models currently not used because it is only one model
        # self.vs_models = ["gfs_hrrr"]

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
            timeout=300_000,
            verify_ssl=False,  # Disable SSL verification for self-signed certificates
            http_client_kwargs={"timeout": 300}
        )
        self.forecastBucket = 'WeatherForecast'
        self.benchmarkingBucket = "benchmark_score"
    
    def get_forecasts(self, start_time, end_time, models):
        
        models_flux_array = "[" + ", ".join(f'"{m}"' for m in models) + "]"

        query = f'''
        models = {models_flux_array}
        startForecast = time(v: {start_time.isoformat()})
        endForecast   = time(v: {end_time.isoformat()})
            from(bucket: "{self.forecastBucket}")
                |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
                |> filter(fn : (r) => r["_field"] == "temperature_2m"
                    or r["_field"] == "relative_humidity_2m"
                    or r["_field"] == "precipitation"
                    or r["_field"] == "cloud_cover"
                    or r["_field"] == "surface_pressure"
                    or r["_field"] == "dew_point_2m")
                |> filter(fn: (r) =>
                    time(v: r.forecast_date) >= startForecast and
                    time(v: r.forecast_date) <= endForecast
                ) |> filter(fn: (r) => contains(value: r.model, set: models) )
                |> keep(columns: ["_time","forecast_date", "model", "_value", "_field"])
        '''
        try:
            query_api = self.client.query_api()
            tables = query_api.query_data_frame(query)
            df = pd.DataFrame(tables)
        except Exception as e:
            print(f"Error running query: {e}")
            raise
        return df
    
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
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d")
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
        df_measured = pd.DataFrame(hourly_data)

        # Melt DataFrame to long format for merge
        df_measured = df_measured.melt(
            id_vars=["date"],
            var_name="_field",
            value_name="actual_value"
        )

        return df_measured
    
    def calculate_error(self, df_forecasts, df_measured, forecast_date, lead_time):
        #1 Merge df
        df_forecasts["forecast_date"] = pd.to_datetime(df_forecasts["forecast_date"], utc=True)
        df_measured["date"] = pd.to_datetime(df_measured["date"], utc=True)

        merged_df = df_forecasts.merge(
            df_measured,
            left_on=["forecast_date", "_field"],
            right_on=["date", "_field"],
            how="inner"
        )

        #2 Calculate error
        merged_df['abs_error'] = (merged_df['_value'] - merged_df['actual_value']).abs()
        merged_df['squared_error'] = (merged_df['_value'] - merged_df['actual_value']) ** 2

        error_df = merged_df.groupby(["model", "_field"]).agg(
            mae=('abs_error', 'mean'),
            mse=('squared_error', 'mean'),
            rmse=('squared_error', lambda x: (x.mean())**0.5),
        ).reset_index()

        error_df["selected_error"] = error_df.apply(
            lambda row: row["mae"] if row["_field"] in ["relative_humidity_2m", "cloud_cover"] 
                    else row["rmse"], 
            axis=1
        )

        # Structure as table to save as one row per model
        pivot_df = error_df.pivot_table(
            index=["model"],             
            columns="_field",          
            values="selected_error"       
        ).reset_index()

        pivot_df["lead_time"] = lead_time 
        pivot_df["forecast_date"] = forecast_date

        return pivot_df
    

    def write_data_to_influxdb(self, df: pd.DataFrame):
        
        batch = []
       
        write_api = self.client.write_api(write_options=SYNCHRONOUS)
        for _, row in df.iterrows():
            point = (
                Point("forecast_error")
                .tag("model", row["model"])
                .tag("lead_time", row["lead_time"])
                .field("forecast_date", row["forecast_date"].isoformat())
                .field("cloud_cover", float(row["cloud_cover"]))
                .field("relative_humidity_2m", float(row["relative_humidity_2m"]))
                .field("temperature_2m", float(row["temperature_2m"]))
                .field("surface_pressure", float(row["surface_pressure"]))
                .field("dew_point_2m", float(row["dew_point_2m"]))          
                .field("precipitation", float(row["precipitation"]))
            )
            batch.append(point)
        write_api.write(bucket=self.benchmarkingBucket, org="FogCast", record=batch)

    def generic_benchmark(self, models, end_time, daysback, lead_time):
        start_time = end_time - timedelta(days=daysback)

        print(f"Collecting data from {start_time} to {end_time} for models: {models}")
        df_forecasts = self.get_forecasts(start_time, end_time, models)

        print(f"Fetching the measured data for the same period.")
        measured_df = self.get_measured(start_time, end_time)

        print(f"Calculating error scores.")
        error_df = self.calculate_error(df_forecasts, measured_df, end_time, lead_time)
        print(error_df)

        print(f"Writing data to InfluxDB.")
        self.write_data_to_influxdb(error_df) 

    def run_benchmark(self):
        warnings.simplefilter("ignore")
        current_date = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        
        # Run benchmarks for different models and timeframes
        self.generic_benchmark(self.s_models, current_date, 3, "s")
        self.generic_benchmark(self.m_models, current_date, 7, "m")
        self.generic_benchmark(self.l_models, current_date, 15, "l")