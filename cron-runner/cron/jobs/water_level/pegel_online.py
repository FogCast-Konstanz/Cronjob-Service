import requests
from enum import Enum
import pandas as pd

class PegelOnline:
    """
    Represents a system to interact with Pegel Online services.

    This class is designed to retrieve and process data from Pegel Online, a platform
    that provides water level and related hydrological information. The class includes
    methods for fetching and parsing data.
    """
    
    class Station(Enum):
        """
        Represents Pegel Online stations.
        """
        KONSTANZ_RHEIN = "e020e651-e422-46d3-ae28-34887c5a4a8e"
        KONSTANZ_BODENSEE = "aa9179c1-17ef-4c61-a48a-74193fa7bfdf"

    class Period(Enum):
        """
        Represents ISO_8601 periods.
        """
        last_24_hours = "P1D"
        last_31_days = "P31D"

    def get_water_level_measurements(self, period: Period, station: Station):
        """
        Fetches water level measurement data for a specified time period.

        This method retrieves a list of measurement records corresponding to the given
        time period.

        Args:
            period (str): The time period for which measurements are to be retrieved.
            station_uuid (str): The UUID of the station for which measurements are to be retrieved.

        Returns:
            list: A list of measurement records for the specified time period.

        Raises:
            ValueError: If the provided period format is incorrect or unrecognized.
        """
        base_url = f"https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations/{station.value}/W/measurements.json?"
        url = base_url + f"start={period.value}"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            df['value'] = df['value'].astype(int)
            df['date'] = pd.to_datetime(df['timestamp'], format='%Y-%m-%dT%H:%M:%S%z').dt.tz_convert('UTC').dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            return df
        else:
            raise ValueError(f"Failed to retrieve data for period {period}. Status code: {response.status_code}")