from datetime import datetime
import pytz
import os
from pathlib import Path

import pandas as pd
from influxdb_client.client.influxdb_client import InfluxDBClient
from influxdb_client.domain.write_precision import WritePrecision
from influxdb_client.client.write.point import Point
from influxdb_client.client.write_api import SYNCHRONOUS

from cron.settings_utils import get_data_dir, get_influx_config, get_coordinates


def main():
    data_dir = get_data_dir()
    influx_config = get_influx_config()
    latitude, longitude = get_coordinates()

    directories = os.listdir(data_dir)

    client = InfluxDBClient(
        url=influx_config['url'],
        token=influx_config['token'],
        org=influx_config['org']
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)

    for directory in directories:
        utc_time = directory
        try:
            utc_time = datetime.strptime(utc_time, "%Y-%m-%dT%H-%M-%SZ")
        except ValueError:
            print(f"Skipping query due to old date format: {utc_time}")
            continue

        models = os.listdir(os.path.join(data_dir, directory))
        for model in models:
            df = pd.read_csv(os.path.join(data_dir, directory, model))
            influx_data = []
            model_name = Path(model).stem

            for index, row in df.iterrows():
                point = Point("forecast")
                point.time(utc_time, WritePrecision.S)
                point.tag("model", model_name)
                point.tag("latitude", latitude)
                point.tag("longitude", longitude)
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

            write_api.write(
                bucket=influx_config['bucket'], org="FogCast", record=influx_data)
        print(">>> Wrote", len(models), "models for", directory)
    write_api.close()


if __name__ == "__main__":
    main()
