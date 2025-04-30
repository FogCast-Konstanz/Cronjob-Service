from datetime import datetime, timezone

import pandas as pd
import influxdb_client
from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from cron.jobs.open_meteo_cronjob import OpenMeteoCronjob
from cron.jobs.toDataFrame import extract_model_data
from cron.settings import settings


class OpenMeteoInfluxCronjob(OpenMeteoCronjob):
    def __init__(self):
        super().__init__()
        self.client = influxdb_client.InfluxDBClient(url=settings.influx.url, token=settings.influx.token, org=settings.influx.org)

    def start(self, local_dt: datetime) -> bool:
        utc_dt = local_dt.astimezone(timezone.utc)        
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
                point.tag("latitude", settings.latitude)
                point.tag("longitude", settings.longitude)
                point.tag("forecast_date", row["date"])

                row = row.drop("date")

                for key, value in row.items():
                    if pd.isna(value):
                        # skip NaN values
                        # this can happen if the model does not provide data for this field
                        continue
                    point.field(key, value)

                influx_data.append(point)
                
            write_api.write(bucket=settings.influx.bucket, org="FogCast", record=influx_data)
            print("Wrote", len(influx_data), "rows for", model)
        write_api.close()

    def cleanUpAfterError(self):
        pass
