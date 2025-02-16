from datetime import datetime
import pytz
import os
from pathlib import Path

import pandas as pd
import influxdb_client
from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from cron.settings import settings

if __name__ == "__main__":
    directories = os.listdir(settings.data_dir)

    client = influxdb_client.InfluxDBClient(url=settings.influx.url, token=settings.influx.token, org=settings.influx.org)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    for directory in directories:
        utc_time = directory
        try:
            utc_time = datetime.strptime(utc_time, "%Y-%m-%dT%H-%M-%SZ")
        except ValueError:
            print(f"Skipping query due to old date format: {utc_time}")
            continue

        models = os.listdir(os.path.join(settings.data_dir, directory))
        for model in models:
            df = pd.read_csv(os.path.join(settings.data_dir, directory, model))
            influx_data = []
            model_name = Path(model).stem

            for index, row in df.iterrows():
                point = Point("forecast")
                point.time(utc_time, WritePrecision.S)
                point.tag("model", model_name)
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
            print("Wrote", len(influx_data), "rows for", model_name)
        print(">>> Wrote", len(models), "models for", directory)
    write_api.close()