from __future__ import annotations

import argparse
import io
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests


DEFAULT_RASPI_API = "https://fogcast.in.htwg-konstanz.de/api"
DEFAULT_DWD_API = DEFAULT_RASPI_API
RASPI_COLUMNS = ["temperature", "humidity", "water_temperature"]
DWD_COLUMNS = ["temperature", "humidity"]


def _parse_timestamp(value: str) -> datetime:
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize("UTC")
    return parsed.tz_convert("UTC").to_pydatetime()


def _windows(start: datetime, stop: datetime, days: int) -> Iterable[tuple[datetime, datetime]]:
    current = start
    delta = timedelta(days=days)
    while current < stop:
        window_stop = min(current + delta, stop)
        yield current, window_stop
        current = window_stop


def _api_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_json(session: requests.Session, url: str, params: dict[str, str], timeout: int) -> list[dict]:
    response = session.get(url, params=params, timeout=timeout)
    if response.status_code == 500 and "['result', 'table'] not found in axis" in response.text:
        print(f"Skipping unavailable backend window: {response.url}")
        return []
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError(f"Expected a list from {response.url}, got {type(payload).__name__}")
    return payload


def fetch_hourly_raspi(
    session: requests.Session,
    api_base: str,
    start: datetime,
    stop: datetime,
    window_days: int,
    timeout: int,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    url = f"{api_base.rstrip('/')}/weatherstation"
    for window_start, window_stop in _windows(start, stop, window_days):
        records = _get_json(
            session,
            url,
            {
                "start": _api_timestamp(window_start),
                "stop": _api_timestamp(window_stop),
            },
            timeout,
        )
        if not records:
            continue
        frame = pd.DataFrame(records)
        timestamp_column = "time" if "time" in frame.columns else "timestamp"
        if timestamp_column not in frame.columns:
            raise ValueError("Raspi response has no time or timestamp column")
        frame["timestamp"] = pd.to_datetime(frame[timestamp_column], utc=True, errors="coerce")
        frame = frame.dropna(subset=["timestamp"])
        missing = [column for column in RASPI_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(f"Raspi response is missing columns: {missing}")
        frame = frame.set_index("timestamp")[RASPI_COLUMNS].apply(pd.to_numeric, errors="coerce")
        frames.append(frame.resample("1h").mean())
        print(f"Raspi {window_start.date()} - {window_stop.date()}: {len(records)} raw rows")

    if not frames:
        raise ValueError("No Raspi data was returned for the requested period")
    result = pd.concat(frames).sort_index()
    result = result[~result.index.duplicated(keep="last")].sort_index()
    hourly_index = pd.date_range(
        start=start.replace(minute=0, second=0, microsecond=0),
        end=(stop - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0),
        freq="1h",
        tz="UTC",
    )
    return result.reindex(hourly_index)


def fetch_hourly_dwd(
    session: requests.Session,
    api_base: str,
    start: datetime,
    stop: datetime,
    window_days: int,
    timeout: int,
) -> pd.DataFrame:
    del api_base, window_days
    base = (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
        "climate/hourly/air_temperature"
    )
    urls = [
        f"{base}/historical/stundenwerte_TU_02712_19710101_20251231_hist.zip",
        f"{base}/recent/stundenwerte_TU_02712_akt.zip",
    ]
    frames: list[pd.DataFrame] = []
    for url in urls:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = [name for name in archive.namelist() if "produkt" in name.lower() and name.endswith(".txt")]
            if not names:
                raise ValueError(f"DWD archive has no product file: {url}")
            raw = pd.read_csv(archive.open(names[0]), sep=";", low_memory=False)
        frame = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(
                    raw["MESS_DATUM"].astype(str), format="%Y%m%d%H", utc=True, errors="coerce"
                ),
                "temperature": pd.to_numeric(raw["TT_TU"], errors="coerce"),
                "humidity": pd.to_numeric(raw["RF_TU"], errors="coerce"),
            }
        )
        frames.append(frame)
        print(f"DWD archive downloaded: {url.rsplit('/', 1)[-1]} ({len(frame)} rows)")

    result = pd.concat(frames, ignore_index=True)
    result = result.dropna(subset=["timestamp"]).drop_duplicates("timestamp", keep="last")
    result = result.set_index("timestamp").sort_index()[DWD_COLUMNS]
    result = result.loc[(result.index >= start) & (result.index < stop)]
    return result.resample("1h").mean()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2025-07-24T00:00:00Z")
    parser.add_argument("--stop", default="2026-10-15T00:00:00Z")
    parser.add_argument("--raspi-api", default=DEFAULT_RASPI_API)
    parser.add_argument("--dwd-api", default=DEFAULT_DWD_API)
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./dev/training_data"),
    )
    args = parser.parse_args()

    if args.window_days < 1:
        raise ValueError("--window-days must be positive")
    start = _parse_timestamp(args.start)
    stop = _parse_timestamp(args.stop)
    if start >= stop:
        raise ValueError("--start must be before --stop")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with requests.Session() as session:
        raspi = fetch_hourly_raspi(
            session, args.raspi_api, start, stop, args.window_days, args.timeout
        )
        dwd = fetch_hourly_dwd(
            session, args.dwd_api, start, stop, args.window_days, args.timeout
        )

    raspi.index.name = "timestamp"
    dwd.index.name = "timestamp"
    raspi.reset_index().to_csv(args.output_dir / "raspi_hourly.csv", index=False)
    dwd.reset_index().to_csv(args.output_dir / "dwd_hourly.csv", index=False)
    summary = pd.DataFrame(
        {
            "dataset": ["raspi", "dwd"],
            "rows": [len(raspi), len(dwd)],
            "first_timestamp": [raspi.index.min(), dwd.index.min()],
            "last_timestamp": [raspi.index.max(), dwd.index.max()],
            "complete_rows": [
                int(raspi[RASPI_COLUMNS].notna().all(axis=1).sum()),
                int(dwd[DWD_COLUMNS].notna().all(axis=1).sum()),
            ],
        }
    )
    summary.to_csv(args.output_dir / "summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"Training data written to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
