import pandas as pd
from openmeteo_sdk.WeatherApiResponse import WeatherApiResponse


def toDataFrame(response: WeatherApiResponse, hourly_fields: list[str]):
    hourly = response.Hourly()
    if hourly is None:
        raise Exception
    dates = pd.date_range(
        start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
        end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=hourly.Interval()),
        inclusive="left",
        tz="UTC",
    )
    dates = dates.map(lambda x: x.strftime("%Y-%m-%dT%H:%M:%SZ"))
    hourly_data = {"date": dates}

    for i, variable_key in enumerate(hourly_fields):
        variable = hourly.Variables(i).ValuesAsNumpy()  # type: ignore
        hourly_data[variable_key] = variable.tolist()

    df = pd.DataFrame(data=hourly_data)
    return df


def extract_model_data(response: WeatherApiResponse, hourly_fields: list[str]):
    df = toDataFrame(response, hourly_fields)
    # Cut the dataframe when the most important values are not forecasted anymore (NaN)
    df = df.dropna(
        subset=["temperature_2m", "relative_humidity_2m", "dew_point_2m"])
    return df
