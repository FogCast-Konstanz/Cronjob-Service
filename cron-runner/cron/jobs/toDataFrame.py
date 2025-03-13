import pandas as pd


def toDataFrame(response, hourly_fields: list[str]):
    hourly = response.Hourly()

    dates = pd.date_range(
      start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
      end = pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
      freq = pd.Timedelta(seconds = hourly.Interval()),
      inclusive = "left",
      tz="UTC",
    )
    dates = dates.map(lambda x: x.strftime("%Y-%m-%dT%H:%M:%SZ"))
    hourly_data = {"date": dates }

    for i, variable_key in enumerate(hourly_fields):
        variable = hourly.Variables(i).ValuesAsNumpy()
        hourly_data[variable_key] = variable

    df = pd.DataFrame(data = hourly_data)
    return df

def extract_model_data(response, hourly_fields: list[str]):
    df = toDataFrame(response, hourly_fields)

    # Determine forecast horizon by detecting a significant increase in missing forecast data.
    # Compute the number of NaNs in each row for forecast columns.
    nan_counts = df[hourly_fields].isnull().sum(axis=1)

    horizon_index = None
    diff_threshold = 10  # threshold for a significant jump in missing values
    for i in range(1, len(nan_counts)):
        diff = nan_counts.iloc[i] - nan_counts.iloc[i-1]
        if diff >= diff_threshold:
            horizon_index = df.index[i]
            break

    if horizon_index is not None:
        df = df.loc[:horizon_index-1]

    # Additionally, drop any row that is entirely NaN in the forecast columns.
    # Remove only trailing rows where all forecast columns are NaN
    for idx in df.index[::-1]:
        if df.loc[idx, hourly_fields].isnull().all():
            df = df.drop(idx)
        else:
            break
    
    return df