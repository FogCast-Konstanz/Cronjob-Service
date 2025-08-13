from datetime import datetime, timezone
import os

from cron.jobs.open_meteo.open_meteo_cronjob import OpenMeteoCronjob
from cron.jobs.toDataFrame import extract_model_data
from cron.settings_utils import get_data_dir


class OpenMeteoCsvCronjob(OpenMeteoCronjob):

    def __init__(self):
        super().__init__()

    def start(self, local_dt: datetime) -> bool:
        utc_dt = local_dt.astimezone(timezone.utc)
        data_dir = get_data_dir()
        data_directory = os.path.join(
            data_dir, utc_dt.strftime("%Y-%m-%dT%H-%M-%SZ"))
        if not os.path.exists(data_directory):
            os.makedirs(data_directory)

        all_responses = self.get_data_for_all_models()
        for response in all_responses:
            model = response.model
            df = extract_model_data(response.response, self._hourly_fields)
            df.to_csv("{}/{}.csv".format(data_directory, model), index=False)

        self._lastDataDirectory = data_directory
        return True

    def cleanUpAfterError(self):
        if self._lastDataDirectory is not None:
            os.rmdir(self._lastDataDirectory)
