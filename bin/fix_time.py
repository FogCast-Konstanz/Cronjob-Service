from datetime import datetime
import pytz
import os

import pandas as pd

from cron.settings import settings

if __name__ == "__main__":
    directories = os.listdir(settings.data_dir)

    for directory in directories:
        local_time = directory
        try:
            local_time = datetime.strptime(local_time, "%Y-%m-%dT%H-%M-%S")
        except ValueError:
            print(f"Skipping query due to new date format: {local_time}")
            continue
        
        berlin = pytz.timezone("Europe/Berlin")
        local_time = berlin.localize(local_time)
        utc_time = local_time.astimezone(pytz.utc)

        os.mkdir(os.path.join(settings.data_dir, utc_time.strftime("%Y-%m-%dT%H-%M-%SZ")))

        models = os.listdir(os.path.join(settings.data_dir, directory))
        for model in models:
            df = pd.read_csv(os.path.join(settings.data_dir, directory, model))
            df["date"] = df["date"].apply(lambda x: berlin.localize(datetime.strptime(x, "%Y-%m-%d %H:%M:%S%z").replace(tzinfo=None)).astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
            df.to_csv(os.path.join(settings.data_dir, utc_time.strftime("%Y-%m-%dT%H-%M-%SZ"), model), index=False)
        