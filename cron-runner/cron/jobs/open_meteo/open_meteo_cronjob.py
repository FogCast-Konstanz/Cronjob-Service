from dataclasses import dataclass
from datetime import datetime
import openmeteo_requests

from openmeteo_sdk.WeatherApiResponse import WeatherApiResponse

import requests_cache
import pandas as pd
from retry_requests import retry

from cron.jobs.cronjob_base import CronjobBase
from cron.settings_utils import get_setting, get_coordinates


@dataclass
class ModelResponse:
    model: str
    response: WeatherApiResponse


class OpenMeteoCronjob(CronjobBase):

    def __init__(self):
        super().__init__()
        self._lastDataDirectory = None

        model_ids_path = get_setting(
            'model_ids_path', './config/model_ids.csv')
        models_df = pd.read_csv(model_ids_path)
        self._models = [row['name'] for _, row in models_df.iterrows()]

        hourly_fields_path = get_setting(
            'hourly_fields_path', './config/hourly_fields.csv')
        hourly_fields_df = pd.read_csv(hourly_fields_path)
        self._hourly_fields = [row['field']
                               for _, row in hourly_fields_df.iterrows()]

    def get_data_for_all_models(self) -> list[ModelResponse]:
        all_responses = []
        latitude, longitude = get_coordinates()

        cache_session = requests_cache.CachedSession(
            '.cache', expire_after=3600)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        # Type ignore for the session type mismatch
        openmeteo = openmeteo_requests.Client(
            session=retry_session)  # type: ignore
        url = "https://api.open-meteo.com/v1/forecast"
        for model in self._models:
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "hourly": self._hourly_fields,
                "timezone": "GMT",
                "models": [model],
                "forecast_days": 16
            }

            try:
                responses = openmeteo.weather_api(url, params=params)
                single_response = responses[0]
                if single_response is None:
                    raise Exception
                res = ModelResponse(model, single_response)
                all_responses.append(res)
                print("Received data for model: {}".format(model))
            except Exception as e:
                print("Unable to request data for model ", model)
                error_message = (
                    f"**⚠️ Cronjob Warning**\n"
                    f"**Time:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
                    f"**Unable to request data for model `{model}`**\n"
                    f"**Error message:**\n"
                    f"```\n{str(e)}\n```"
                )
                if self._webhook is not None:
                    self._webhook.send(error_message)
                continue

        return all_responses
