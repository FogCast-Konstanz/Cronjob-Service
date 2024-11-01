import datetime
import os
import openmeteo_requests
import pathlib

import requests_cache
import pandas as pd
from retry_requests import retry


if __name__ == "__main__":

   
   script_dir = pathlib.Path(__file__).parent.resolve()
   base_path = os.path.join(script_dir.parent, "data")
   config_dir = os.path.join(script_dir.parent, "config")
   model_ids_path = os.path.join(config_dir, "models.csv")

   cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
   retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
   openmeteo = openmeteo_requests.Client(session = retry_session)

   models = [
      "ecmwf_ifs04", "ecmwf_ifs025", "ecmwf_aifs025", "cma_grapes_global", 
      "bom_access_global", "gfs_seamless", "gfs_global", "gfs_hrrr", 
      "ncep_nbm_conus", "gfs_graphcast025", "jma_seamless", "jma_msm", 
      "jma_gsm", "icon_seamless", "icon_global", "icon_eu", "icon_d2", 
      "gem_seamless", "gem_global", "gem_regional", "gem_hrdps_continental", 
      "meteofrance_seamless", "meteofrance_arpege_world", 
      "meteofrance_arpege_europe", "meteofrance_arome_france", 
      "meteofrance_arome_france_hd", "arpae_cosmo_seamless", 
      "arpae_cosmo_2i", "arpae_cosmo_5m", "metno_seamless", "metno_nordic", 
      "knmi_seamless", "knmi_harmonie_arome_europe", 
      "knmi_harmonie_arome_netherlands", "dmi_seamless", 
      "dmi_harmonie_arome_europe", "ukmo_seamless", 
      "ukmo_global_deterministic_10km", "ukmo_uk_deterministic_2km"
   ]

   model_ids = []

   for model_name in models:
      url = "https://api.open-meteo.com/v1/forecast"
      params = {
         "latitude": 47.67761561553788,
         "longitude": 9.190068339473479,
         "hourly": ["temperature_2m"],
         "timezone": "Europe/Berlin",
         "models": [model_name]
      }

      try:
         responses = openmeteo.weather_api(url, params=params)
      except Exception as e:
         continue

      assert len(responses) == 1

      model_id = responses[0].Model()
      
      model_ids.append({
         "name": model_name,
         "id": model_id
      })
   
   df = pd.DataFrame(model_ids)
   df.sort_values(by="id", inplace=True)
   df.to_csv(model_ids_path, index=False)