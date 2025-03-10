import pandas as pd


def toDataFrame(response):
    hourly = response.Hourly()
    hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
    hourly_relative_humidity_2m = hourly.Variables(1).ValuesAsNumpy()
    hourly_dew_point_2m = hourly.Variables(2).ValuesAsNumpy()
    hourly_apparent_temperature = hourly.Variables(3).ValuesAsNumpy()
    hourly_precipitation_probability = hourly.Variables(4).ValuesAsNumpy()
    hourly_precipitation = hourly.Variables(5).ValuesAsNumpy()
    hourly_rain = hourly.Variables(6).ValuesAsNumpy()
    hourly_showers = hourly.Variables(7).ValuesAsNumpy()
    hourly_snowfall = hourly.Variables(8).ValuesAsNumpy()
    hourly_snow_depth = hourly.Variables(9).ValuesAsNumpy()
    hourly_weather_code = hourly.Variables(10).ValuesAsNumpy()
    hourly_pressure_msl = hourly.Variables(11).ValuesAsNumpy()
    hourly_surface_pressure = hourly.Variables(12).ValuesAsNumpy()
    hourly_cloud_cover = hourly.Variables(13).ValuesAsNumpy()
    hourly_cloud_cover_low = hourly.Variables(14).ValuesAsNumpy()
    hourly_cloud_cover_mid = hourly.Variables(15).ValuesAsNumpy()
    hourly_cloud_cover_high = hourly.Variables(16).ValuesAsNumpy()
    hourly_visibility = hourly.Variables(17).ValuesAsNumpy()
    hourly_evapotranspiration = hourly.Variables(18).ValuesAsNumpy()
    hourly_et0_fao_evapotranspiration = hourly.Variables(19).ValuesAsNumpy()
    hourly_vapour_pressure_deficit = hourly.Variables(20).ValuesAsNumpy()
    hourly_wind_speed_10m = hourly.Variables(21).ValuesAsNumpy()
    hourly_wind_speed_80m = hourly.Variables(22).ValuesAsNumpy()
    hourly_wind_speed_120m = hourly.Variables(23).ValuesAsNumpy()
    hourly_wind_speed_180m = hourly.Variables(24).ValuesAsNumpy()
    hourly_wind_direction_10m = hourly.Variables(25).ValuesAsNumpy()
    hourly_wind_direction_80m = hourly.Variables(26).ValuesAsNumpy()
    hourly_wind_direction_120m = hourly.Variables(27).ValuesAsNumpy()
    hourly_wind_direction_180m = hourly.Variables(28).ValuesAsNumpy()
    hourly_wind_gusts_10m = hourly.Variables(29).ValuesAsNumpy()
    hourly_temperature_80m = hourly.Variables(30).ValuesAsNumpy()
    hourly_temperature_120m = hourly.Variables(31).ValuesAsNumpy()
    hourly_temperature_180m = hourly.Variables(32).ValuesAsNumpy()
    hourly_soil_temperature_0cm = hourly.Variables(33).ValuesAsNumpy()
    hourly_soil_temperature_6cm = hourly.Variables(34).ValuesAsNumpy()
    hourly_soil_temperature_18cm = hourly.Variables(35).ValuesAsNumpy()
    hourly_soil_temperature_54cm = hourly.Variables(36).ValuesAsNumpy()
    hourly_soil_moisture_0_to_1cm = hourly.Variables(37).ValuesAsNumpy()
    hourly_soil_moisture_1_to_3cm = hourly.Variables(38).ValuesAsNumpy()
    hourly_soil_moisture_3_to_9cm = hourly.Variables(39).ValuesAsNumpy()
    hourly_soil_moisture_9_to_27cm = hourly.Variables(40).ValuesAsNumpy()
    hourly_soil_moisture_27_to_81cm = hourly.Variables(41).ValuesAsNumpy()

    dates = pd.date_range(
      start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
      end = pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
      freq = pd.Timedelta(seconds = hourly.Interval()),
      inclusive = "left",
      tz="UTC",
    )
    dates = dates.map(lambda x: x.strftime("%Y-%m-%dT%H:%M:%SZ"))
    hourly_data = {"date": dates }
    hourly_data["temperature_2m"] = hourly_temperature_2m
    hourly_data["relative_humidity_2m"] = hourly_relative_humidity_2m
    hourly_data["dew_point_2m"] = hourly_dew_point_2m
    hourly_data["apparent_temperature"] = hourly_apparent_temperature
    hourly_data["precipitation_probability"] = hourly_precipitation_probability
    hourly_data["precipitation"] = hourly_precipitation
    hourly_data["rain"] = hourly_rain
    hourly_data["showers"] = hourly_showers
    hourly_data["snowfall"] = hourly_snowfall
    hourly_data["snow_depth"] = hourly_snow_depth
    hourly_data["weather_code"] = hourly_weather_code
    hourly_data["pressure_msl"] = hourly_pressure_msl
    hourly_data["surface_pressure"] = hourly_surface_pressure
    hourly_data["cloud_cover"] = hourly_cloud_cover
    hourly_data["cloud_cover_low"] = hourly_cloud_cover_low
    hourly_data["cloud_cover_mid"] = hourly_cloud_cover_mid
    hourly_data["cloud_cover_high"] = hourly_cloud_cover_high
    hourly_data["visibility"] = hourly_visibility
    hourly_data["evapotranspiration"] = hourly_evapotranspiration
    hourly_data["et0_fao_evapotranspiration"] = hourly_et0_fao_evapotranspiration
    hourly_data["vapour_pressure_deficit"] = hourly_vapour_pressure_deficit
    hourly_data["wind_speed_10m"] = hourly_wind_speed_10m
    hourly_data["wind_speed_80m"] = hourly_wind_speed_80m
    hourly_data["wind_speed_120m"] = hourly_wind_speed_120m
    hourly_data["wind_speed_180m"] = hourly_wind_speed_180m
    hourly_data["wind_direction_10m"] = hourly_wind_direction_10m
    hourly_data["wind_direction_80m"] = hourly_wind_direction_80m
    hourly_data["wind_direction_120m"] = hourly_wind_direction_120m
    hourly_data["wind_direction_180m"] = hourly_wind_direction_180m
    hourly_data["wind_gusts_10m"] = hourly_wind_gusts_10m
    hourly_data["temperature_80m"] = hourly_temperature_80m
    hourly_data["temperature_120m"] = hourly_temperature_120m
    hourly_data["temperature_180m"] = hourly_temperature_180m
    hourly_data["soil_temperature_0cm"] = hourly_soil_temperature_0cm
    hourly_data["soil_temperature_6cm"] = hourly_soil_temperature_6cm
    hourly_data["soil_temperature_18cm"] = hourly_soil_temperature_18cm
    hourly_data["soil_temperature_54cm"] = hourly_soil_temperature_54cm
    hourly_data["soil_moisture_0_to_1cm"] = hourly_soil_moisture_0_to_1cm
    hourly_data["soil_moisture_1_to_3cm"] = hourly_soil_moisture_1_to_3cm
    hourly_data["soil_moisture_3_to_9cm"] = hourly_soil_moisture_3_to_9cm
    hourly_data["soil_moisture_9_to_27cm"] = hourly_soil_moisture_9_to_27cm
    hourly_data["soil_moisture_27_to_81cm"] = hourly_soil_moisture_27_to_81cm

    df = pd.DataFrame(data = hourly_data)
    return df