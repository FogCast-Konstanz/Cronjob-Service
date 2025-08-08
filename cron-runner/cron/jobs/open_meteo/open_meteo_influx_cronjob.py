from datetime import datetime, timezone

import pandas as pd
from influxdb_client.client.influxdb_client import InfluxDBClient
from influxdb_client.client.write.point import Point
from influxdb_client.domain.write_precision import WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from cron.jobs.open_meteo.open_meteo_cronjob import OpenMeteoCronjob
from cron.jobs.toDataFrame import extract_model_data
from cron.settings_utils import get_influx_config, get_coordinates


class OpenMeteoInfluxCronjob(OpenMeteoCronjob):
    def __init__(self):
        super().__init__()
        influx_config = get_influx_config()
        self.client = InfluxDBClient(
            url=influx_config['url'],
            token=influx_config['token'],
            org=influx_config['org']
        )

    def start(self, local_dt: datetime) -> bool:
        utc_dt = local_dt.astimezone(timezone.utc)
        influx_config = get_influx_config()
        latitude, longitude = get_coordinates()

        write_api = self.client.write_api(write_options=SYNCHRONOUS)

        all_responses = self.get_data_for_all_models()
        for response in all_responses:
            model_id = response.Model()
            model = self._models[model_id]
            df = extract_model_data(response, self._hourly_fields)

            influx_data = []

            for index, row in df.iterrows():
                point = Point("forecast")
                point.time(utc_dt, WritePrecision.S)
                point.tag("model", model)
                point.tag("latitude", latitude)
                point.tag("longitude", longitude)
                point.tag("forecast_date", row["date"])

                row = row.drop("date")

                for key, value in row.items():
                    if pd.isna(value):
                        # skip NaN values
                        # this can happen if the model does not provide data for this field
                        continue
                    point.field(key, value)

                influx_data.append(point)

            write_api.write(
                bucket=influx_config['bucket'], org="FogCast", record=influx_data)
            print("Wrote", len(influx_data), "rows for", model)
        write_api.close()
        return True

    def cleanUpAfterError(self):
        pass
