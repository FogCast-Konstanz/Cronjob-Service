import warnings
import pandas as pd
import requests_cache
import openmeteo_requests
from retry_requests import retry
from datetime import datetime, timedelta, timezone
from influxdb_client.client.influxdb_client import InfluxDBClient
from influxdb_client.client.write.point import Point
from influxdb_client.client.write_api import SYNCHRONOUS
from cron.settings_utils import get_influx_config, get_coordinates


class BenchmarkingService:
    def __init__(self):
        # 24 hours
        self.s_models = [
            "ecmwf_ifs04", "ecmwf_ifs025", "ecmwf_aifs025", "cma_grapes_global", "bom_access_global", "gfs_seamless",
            "gfs_global", "ncep_nbm_conus", "gfs_graphcast025", "jma_seamless", "jma_msm", "jma_gsm", "icon_seamless",
            "icon_global", "icon_eu", "icon_d2", "gem_seamless", "gem_global", "gem_regional", "gem_hrdps_continental",
            "meteofrance_seamless", "meteofrance_arpege_world", "meteofrance_arpege_europe", "meteofrance_arome_france",
            "meteofrance_arome_france_hd", "metno_seamless", "metno_nordic", "knmi_seamless", "knmi_harmonie_arome_europe",
            "knmi_harmonie_arome_netherlands", "dmi_seamless", "dmi_harmonie_arome_europe", "ukmo_seamless",
            "ukmo_global_deterministic_10km", "ukmo_uk_deterministic_2km", "meteoswiss_icon_ch1", "meteoswiss_icon_ch2"
        ]
        # 3 days/72 hours
        self.m_models = [
            "ecmwf_ifs04", "ecmwf_ifs025", "ecmwf_aifs025", "cma_grapes_global", "bom_access_global", "gfs_seamless",
            "gfs_global", "ncep_nbm_conus", "gfs_graphcast025", "jma_seamless", "jma_msm", "jma_gsm", "icon_seamless",
            "icon_global", "icon_eu", "gem_seamless", "gem_global", "gem_regional", "meteofrance_seamless",
            "meteofrance_arpege_world", "meteofrance_arpege_europe", "ukmo_seamless", "ukmo_global_deterministic_10km", "meteoswiss_icon_ch2"
        ]
        # 7 days/168 hours
        self.l_models = [
            "ecmwf_ifs04", "ecmwf_ifs025", "ecmwf_aifs025", "cma_grapes_global", "bom_access_global", "gfs_seamless",
            "gfs_global", "ncep_nbm_conus", "gfs_graphcast025", "jma_seamless", "jma_gsm", "icon_seamless",
            "icon_global", "gem_seamless", "gem_global", "ukmo_seamless", "ukmo_global_deterministic_10km"
        ]

        # Get configuration
        influx_config = get_influx_config()
        self.latitude, self.longitude = get_coordinates()

        self.client = InfluxDBClient(
            url=influx_config["url"],
            token=influx_config["token"],
            org=influx_config["org"],
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
                    or r["_field"] == "dew_point_2m"
                    or r["_field"] == "wind_speed_10m")
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
        cache_session = requests_cache.CachedSession(
            '.cache', expire_after=3600)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        openmeteo = openmeteo_requests.Client(
            session=retry_session)  # type: ignore
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "hourly": [
                "temperature_2m", "surface_pressure", "cloud_cover",
                "precipitation", "relative_humidity_2m", "dew_point_2m", "wind_speed_10m"
            ],
            "timezone": "Europe/Berlin",
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d")
        }
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]
        hourly = response.Hourly()

        # Add type ignores for openmeteo API attributes
        hourly_data = {
            "date": pd.date_range(
                start=pd.to_datetime(
                    hourly.Time(), unit="s", utc=True),  # type: ignore
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", # type: ignore
                                   utc=True),  
                freq=pd.Timedelta(seconds=hourly.Interval()),  # type: ignore
                inclusive="left"
            ),
            "temperature_2m": hourly.Variables(0).ValuesAsNumpy(), # type: ignore
            "surface_pressure": hourly.Variables(1).ValuesAsNumpy(), # type: ignore
            "cloud_cover": hourly.Variables(2).ValuesAsNumpy(),  # type: ignore
            "precipitation": hourly.Variables(3).ValuesAsNumpy(), # type: ignore
            "relative_humidity_2m": hourly.Variables(4).ValuesAsNumpy(), # type: ignore
            "dew_point_2m": hourly.Variables(5).ValuesAsNumpy(),  # type: ignore
            "wind_speed_10m": hourly.Variables(6).ValuesAsNumpy()  # type: ignore
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
        """Calculate error metrics with improved error handling"""
        if df_forecasts.empty or df_measured.empty:
            print(
                f"Warning: Empty dataframes - forecasts: {len(df_forecasts)}, measured: {len(df_measured)}")
            return pd.DataFrame()

        # Ensure datetime columns are properly formatted
        df_forecasts["forecast_date"] = pd.to_datetime(
            df_forecasts["forecast_date"], utc=True)
        df_measured["date"] = pd.to_datetime(df_measured["date"], utc=True)

        # Merge dataframes
        merged_df = df_forecasts.merge(
            df_measured,
            left_on=["forecast_date", "_field"],
            right_on=["date", "_field"],
            how="inner"
        )

        if merged_df.empty:
            print("Warning: No matching data after merge")
            return pd.DataFrame()

        # Calculate error metrics
        merged_df['abs_error'] = (
            merged_df['_value'] - merged_df['actual_value']).abs()
        merged_df['squared_error'] = (
            merged_df['_value'] - merged_df['actual_value']) ** 2

        # Group by model and field to calculate error statistics
        error_df = merged_df.groupby(["model", "_field"]).agg(
            mae=('abs_error', 'mean'),
            mse=('squared_error', 'mean'),
            rmse=('squared_error', lambda x: (x.mean())**0.5),
        ).reset_index()

        # Select appropriate error metric per field
        error_df["selected_error"] = error_df.apply(
            lambda row: row["mae"] if row["_field"] in ["relative_humidity_2m", "cloud_cover"]
            else row["rmse"],
            axis=1
        )

        # Pivot to have one row per model with all field errors as columns
        pivot_df = error_df.pivot_table(
            index=["model"],
            columns="_field",
            values="selected_error"
        ).reset_index()

        # Add metadata
        pivot_df["lead_time"] = lead_time
        pivot_df["forecast_date"] = forecast_date

        return pivot_df

    def write_data_to_influxdb(self, df: pd.DataFrame):
        """Write benchmark data to InfluxDB with error handling"""
        write_api = self.client.write_api(write_options=SYNCHRONOUS)
        batch = []

        for _, row in df.iterrows():
            try:
                point = Point("forecast_error") \
                    .tag("model", str(row["model"])) \
                    .tag("lead_time", str(row["lead_time"])) \
                    .field("forecast_date", row["forecast_date"].isoformat())

                # Add fields with NaN checking
                for field in [
                    "cloud_cover", "relative_humidity_2m", "temperature_2m",
                    "surface_pressure", "dew_point_2m", "precipitation", "wind_speed_10m"
                ]:
                    value = row.get(field)
                    if pd.notna(value):  # Only add non-NaN values
                        point = point.field(field, float(value))

                batch.append(point)

            except Exception as e:
                print(
                    f"Error creating point for model {row.get('model', 'unknown')}: {e}")
                continue

        if batch:
            try:
                write_api.write(bucket=self.benchmarkingBucket,
                                org="FogCast", record=batch)
                print(f"Successfully wrote {len(batch)} points to InfluxDB")
            except Exception as e:
                print(f"Error writing to InfluxDB: {e}")
                raise
        else:
            print("No valid points to write to InfluxDB")

    def generic_benchmark(self, models, end_time, daysback, lead_time):
        """Run benchmark for specified models and time period with error handling"""
        start_time = end_time - timedelta(days=daysback)

        print(
            f"Collecting data from {start_time} to {end_time} for {len(models)} models")

        try:
            df_forecasts = self.get_forecasts(start_time, end_time, models)
            if df_forecasts.empty:
                print(
                    f"Warning: No forecast data found for time period {start_time} to {end_time}")
                return

        except Exception as e:
            print(f"Error fetching forecast data: {e}")
            return

        print(f"Fetching measured data for the same period")
        try:
            measured_df = self.get_measured(start_time, end_time)
            if measured_df.empty:
                print(
                    f"Warning: No measured data found for time period {start_time} to {end_time}")
                return

        except Exception as e:
            print(f"Error fetching measured data: {e}")
            return

        print(f"Calculating error scores")
        try:
            error_df = self.calculate_error(
                df_forecasts, measured_df, end_time, lead_time)
            if error_df.empty:
                print(
                    f"Warning: No error calculations possible for time period {start_time} to {end_time}")
                return

            print(f"Error calculations completed for {len(error_df)} models")

        except Exception as e:
            print(f"Error calculating error scores: {e}")
            return

        print(f"Writing data to InfluxDB")
        try:
            self.write_data_to_influxdb(error_df)

        except Exception as e:
            print(f"Error writing to InfluxDB: {e}")
            return

    def run_benchmark(self):
        """Run all benchmark calculations with proper error handling"""
        warnings.simplefilter("ignore")
        current_date = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0)

        print(f"Starting benchmark run at {current_date}")

        # Run benchmarks for different models and timeframes
        try:
            print("Running short-term benchmark (24 hours)")
            self.generic_benchmark(self.s_models, current_date, 1, "s")
        except Exception as e:
            print(f"Error in short-term benchmark: {e}")

        try:
            print("Running medium-term benchmark (3 days)")
            self.generic_benchmark(self.m_models, current_date, 3, "m")
        except Exception as e:
            print(f"Error in medium-term benchmark: {e}")

        try:
            print("Running long-term benchmark (7 days)")
            self.generic_benchmark(self.l_models, current_date, 7, "l")
        except Exception as e:
            print(f"Error in long-term benchmark: {e}")

        print("Benchmark run completed")
