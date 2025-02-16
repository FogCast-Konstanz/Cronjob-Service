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
    queries = os.listdir(settings.data_dir)

    for query in queries:
        local_time = query
        try:
            local_time = datetime.strptime(local_time, "%Y-%m-%dT%H-%M-%S")
        except ValueError:
            print(f"Skipping query due to invalid date format: {local_time}")
            continue
        
        berlin = pytz.timezone("CET")
        local_time.replace(tzinfo=berlin)
        utc_time = local_time.astimezone(pytz.utc)

        models = os.listdir(os.path.join(settings.data_dir, query))
        for model in models:
            df = pd.read_csv(os.path.join(settings.data_dir, query, model))
            

            
            write_api.write(bucket=settings.influx.bucket, org="FogCast", record=influx_data)
            print("Wrote", len(influx_data), "rows for", model_name)
        print(">>> Wrote", len(models), "models for", query)
    write_api.close()