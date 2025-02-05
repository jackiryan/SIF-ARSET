from bs4 import BeautifulSoup
from dataclasses import dataclass
from datetime import datetime
from dotenv import load_dotenv
import os
from pydap.client import open_url
import re
import requests


def year_doy_to_datetime(year: int, doy: int) -> datetime:
    """
    Convert an integer year and day of year (DOY) to a datetime object.

    Args:
        year (int): The year (e.g., 2024)
        doy (int): The day of the year (1-365 or 1-366 for leap years)

    Returns:
        datetime: A datetime object representing the date.
    """
    return datetime.strptime(f"{year}-{doy}", "%Y-%j")


@dataclass
class GesDiscDataset:
    name: str
    startdate: datetime | None = None
    enddate: datetime | None = None
    daily: bool = False


class GesDiscDownloader:

    # While this URL references OCO-2, it also contains OCO-3 datasets
    oco2_gesdisc_url = "https://oco2.gesdisc.eosdis.nasa.gov/opendap/"
    year_pattern = re.compile(r"/(\d{4})/contents\.html$")
    doy_pattern = re.compile(r"/(\d{3})/contents\.html$")
    nc4_pattern = re.compile(r"/([^/]*?)_(\d{6})_.*?\.nc4\.html$")

    def __init__(self):
        self.token = load_dotenv()
        self.token = os.getenv("NASA_EARTHDATA_TOKEN")
        if not self.token:
            raise ValueError(
                "NASA_EARTHDATA_TOKEN not found in environment variables. "
                "Please ensure you have a .env file with your token."
            )
        self.session = requests.Session()
        self.session.headers = {"Authorization": f"Bearer {self.token}"}
        # list the available datasets on initialization to reference later
        self.datasets = {ds: GesDiscDataset(ds) for ds in self.list_datasets()}

    def list_directory(self, url: str) -> list[str]:
        """
        List the contents of a directory URL on an OpenDAP portal, e.g.,
        https://oco2.gesdisc.eosdis.nasa.gov/opendap/

        Args:
            url (str): The URL of the directory on the OpenDAP portal

        Returns:
            list[str]: List of the contents of the directory in OpenDAP

        Raises:
            requests.exceptions.RequestException: If the directory listing fails
        """
        try:
            response = requests.get(url, headers=self.session.headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error accessing GES DISC directory: {str(e)}")
            raise

        soup = BeautifulSoup(response.text, "html.parser")

        # OpenDAP directories use a table element to hold the contents of a
        # directory, so return an empty list if one is not found
        dir_table = soup.find("table")
        if not dir_table:
            return []

        contents: list[str] = []
        for link in dir_table.find_all("a"):
            href = str(link.get("href"))
            # First element is self-referential, skip it
            if href == "#":
                continue
            elif href.startswith("https://") or href.startswith("http://"):
                content_url = href
            else:
                # href is a relative URL, so append the parent URL
                content_url = url + href
            contents.append(content_url)

        return contents

    def list_datasets(self) -> list[str]:
        """
        List all datasets available on the OCO-2/3 GES DISC.

        Returns:
            list[str]: List of available datasets

        Raises:
            requests.exceptions.RequestException: If the directory listing fails
        """
        dataset_urls = self.list_directory(self.oco2_gesdisc_url)
        datasets = [
            ds.split("/")[-2] for ds in dataset_urls if ds.split("/")[-2] != "test"
        ]
        return datasets

    def _get_date_extreme(
        self, year_url: str, year: int, find_min: bool = True
    ) -> tuple[datetime, bool]:
        # Year directories for a dataset will either be DOY directories or a flat
        # directory of netCDF files and metadata

        year_contents = self.list_directory(year_url)
        available_doy = [
            int(self.doy_pattern.search(link).group(1))
            for link in year_contents
            if self.doy_pattern.search(link)
        ]
        # actually a list of date strings in the format YYMMDD parsed from the
        # filename in the link
        available_nc4 = [
            str(self.nc4_pattern.search(link).group(2))
            for link in year_contents
            if self.nc4_pattern.search(link)
        ]
        if len(available_doy) > 0:
            date_objects = [year_doy_to_datetime(year, doy) for doy in available_doy]
            is_daily = False
        elif len(available_nc4) > 0:
            date_objects = [datetime.strptime(date, "%y%m%d") for date in available_nc4]
            is_daily = True
        else:
            return (datetime(), False)

        date_extreme = min(date_objects) if find_min else max(date_objects)
        return (date_extreme, is_daily)

    def get_dataset_timerange(self, dataset: str) -> tuple[datetime, datetime]:
        """
        List the beginning and end times of available products for a given dataset.

        Arguments:
            dataset (str): The name of a dataset on the OCO-2/3 GES DISC OpenDAP portal

        Returns:
            tuple[datetime, datetime]: A tuple of datetime objects with the beginning
                and end times of available data products

        Raises:
            ValueError: If the dataset does not exist
        """
        if dataset not in self.datasets.keys():
            raise ValueError(
                f"{dataset} is not a dataset available on OCO-2/3 GES DISC"
            )

        dataset_url = f"{self.oco2_gesdisc_url}{dataset}/"
        dir_contents = self.list_directory(dataset_url)

        # Brittle way of checking that a link in an OpenDAP directory points to a
        # directory, but should be okay as long as OpenDAP format is stable

        available_years = {
            int(self.year_pattern.search(link).group(1)): link.rstrip("contents.html")
            for link in dir_contents
            if self.year_pattern.search(link)
        }

        if not available_years:
            print(f"Dataset {dataset} is doc-only or had no available products.")
            return (datetime(), datetime())

        # Now search through the highest and lowest year directory to find the begin
        # and end dates.
        earliest_year = min(available_years)
        latest_year = max(available_years)

        earliest_date, is_daily = self._get_date_extreme(
            available_years[earliest_year], earliest_year
        )
        latest_date, _ = self._get_date_extreme(
            available_years[latest_year], latest_year, find_min=False
        )
        self.datasets[dataset].startdate = earliest_date
        self.datasets[dataset].enddate = latest_date
        self.datasets[dataset].daily = is_daily

        return (earliest_date, latest_date)

    def get_granule_by_date(self, dataset: str, date: datetime):
        """
        Get a pointer to the data from a given day for a dataset. Currently only daily
        datasets are supported.

        Arguments:
            dataset (str): The name of a dataset on the OCO-2/3 GES DISC OpenDAP portal
            date (datetime): The requested date of the data

        Returns:
            DatasetType: A pydap Dataset containing access to the variables in the netCDF

        Raises:
            FileNotFoundError: No data is available for the requested day in the dataset
            ValueError: If the dataset does not exist
        """
        if dataset not in self.datasets.keys():
            raise ValueError(
                f"{dataset} is not a dataset available on OCO-2/3 GES DISC"
            )

        if (
            self.datasets[dataset].startdate is None
            or self.datasets[dataset].enddate is None
        ):
            print(f"Checking available dates on GES DISC for {dataset}")
            self.get_dataset_timerange(dataset)

        if (
            date < self.datasets[dataset].startdate
            or date > self.datasets[dataset].enddate
        ):
            startdate_str = self.datasets[dataset].startdate.strftime("%Y-%m-%d")
            enddate_str = self.datasets[dataset].enddate.strftime("%Y-%m-%d")
            raise ValueError(
                f"{dataset} granules are not available on {date.strftime('%Y-%m-%d')}",
                f"\nAvailable dates: {startdate_str} to {enddate_str}",
            )

        if self.datasets[dataset].daily == False:
            raise NotImplementedError("subdaily datasets not implemented")

        year_url = f"{self.oco2_gesdisc_url}{dataset}/{date.year}/"
        year_contents = self.list_directory(year_url)
        granules = {
            datetime.strptime(
                str(self.nc4_pattern.search(link).group(2)), "%y%m%d"
            ): link
            for link in year_contents
            if self.nc4_pattern.search(link)
        }
        target_granule = granules.get(date)
        if target_granule is None:
            raise FileNotFoundError(
                f"No {dataset} granule found for {date.strftime('%Y-%m-%d')}"
            )

        # Remove .html from link to reference .nc4 data directly, which is the format
        # pydap expects
        pydap_url = target_granule.rstrip(".html")
        return open_url(pydap_url, session=self.session)


if __name__ == "__main__":
    print("Gathering datasets on GES DISC...")
    dl = GesDiscDownloader()
    # dataset = "OCO2_L2_CO2Prior.10r"
    dataset = "OCO3_L2_Lite_SIF.11r"
    print(f"Getting time range for {dataset} data...")
    timerange = dl.get_dataset_timerange(dataset)
    print(
        f"{dataset} has time range {timerange[0].strftime('%Y-%m-%d')} to {timerange[1].strftime('%Y-%m-%d')}"
    )
    granule = dl.get_granule_by_date(dataset, datetime(2019, 12, 1))
    print(granule["Latitude"].data[:])
