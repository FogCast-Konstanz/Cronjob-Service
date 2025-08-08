from datetime import datetime
import pandas as pd
import pytz
from influxdb_client.client.influxdb_client import InfluxDBClient
from influxdb_client.client.write.point import Point
from influxdb_client.client.write_api import SYNCHRONOUS

from cron.jobs.water_level.pegel_online import PegelOnline
from cron.jobs.cronjob_base import CronjobBase
from cron.settings_utils import get_influx_config


class PegelOnlineCronjob(CronjobBase):

    def __init__(self):
        super().__init__()
        self.pegel_online = PegelOnline()
        self.KONSTANZ_RHEIN = (
            PegelOnline.Station.KONSTANZ_RHEIN, 3329, "Konstanz Rhein")
        self.KONSTANZ_BODENSEE = (
            PegelOnline.Station.KONSTANZ_BODENSEE, 906, "Konstanz Bodensee")

        influx_config = get_influx_config()
        self.client = InfluxDBClient(
            url=influx_config["url"], token=influx_config["token"], org=influx_config["org"])
        self.bucket = influx_config["bucket"]

    def start(self, local_dt: datetime) -> bool:
        try:
            df_rhein = self.pegel_online.get_water_level_measurements(
                PegelOnline.Period.last_24_hours, self.KONSTANZ_RHEIN[0])
            df_bodensee = self.pegel_online.get_water_level_measurements(
                PegelOnline.Period.last_24_hours, self.KONSTANZ_BODENSEE[0])

            # write to database
            self.write_data_to_influxdb(df_rhein, self.KONSTANZ_RHEIN)
            self.write_data_to_influxdb(df_bodensee, self.KONSTANZ_BODENSEE)
            return True
        except BaseException as e:
            print(f"Error: {e}")
            return False

    def cleanUpAfterError(self):
        pass

    def write_data_to_influxdb(self, df: pd.DataFrame, station_infos: tuple):
        with self.client.write_api(write_options=SYNCHRONOUS) as write_api:
            for index, row in df.iterrows():
                point = Point("water_level") \
                    .field("value", row["value"]) \
                    .tag("unit", "cm") \
                    .tag("station_id", station_infos[1]) \
                    .tag("station_name", station_infos[2]) \
                    .time(datetime.strptime(row["date"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.UTC))
                write_api.write(bucket=self.bucket,
                                org="FogCast", record=point)
