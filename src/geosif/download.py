from bs4 import BeautifulSoup, Tag
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from pathlib import Path
from pydap.client import open_url
import re
import requests
import requests_cache
from urllib.parse import urljoin


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
        load_dotenv()
        self.token = os.getenv("NASA_EARTHDATA_TOKEN")
        if not self.token:
            raise ValueError(
                "NASA_EARTHDATA_TOKEN not found in environment variables. "
                "Please ensure you have a .env file with your token."
            )
        self.session = requests.Session()
        self.session.headers = {"Authorization": f"Bearer {self.token}"}

        # cache responses in an SQLite database with a TTL of 300 seconds (5 minutes)
        requests_cache.install_cache(
            "gesdisc_cache", backend="sqlite", expire_after=300
        )

        # list the available datasets on initialization to reference later
        self.datasets = {ds: GesDiscDataset(ds) for ds in self.list_datasets()}

    def list_directory(self, url: str) -> tuple[list[str], list[int]]:
        """
        List the contents of a directory URL on an OpenDAP portal, e.g.,
        https://oco2.gesdisc.eosdis.nasa.gov/opendap/

        Args:
            url (str): The URL of the directory on the OpenDAP portal

        Returns:
            A tuple of:
            list[str]: List of the contents of the directory in OpenDAP
            list[int]: List of the sizes (in bytes) of the files in the directory

        Raises:
            requests.exceptions.RequestException: If the directory listing fails
        """
        try:
            response = self.session.get(url)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error accessing GES DISC directory: {str(e)}")
            raise

        soup = BeautifulSoup(response.text, "html.parser")

        # OpenDAP directories use table rows to denote contents
        # Directory tables have a DataCatalog itemtype, files have a Dataset itemtype
        table = soup.find("table", itemtype="http://schema.org/DataCatalog")
        if type(table) != Tag:
            return ([], [])

        contents: list[str] = []
        filesizes: list[int] = []
        for row in table.find_all_next("tr"):
            if type(row) != Tag:
                continue
            tds = row.find_all("td")
            if len(tds) < 3:
                continue  # not enough columns
            # First column contains the filename
            link: Tag = tds[0].find("a")
            if not link:
                continue
            href = str(link.get("href"))
            if href.startswith("http://") or href.startswith("https://"):
                content_url = href
            else:
                # href is a relative URL, so prepend the parent URL
                content_url = urljoin(url, href)
            contents.append(content_url)

            # Third column has the filename
            if row.attrs.get("itemtype") == "http://schema.org/Dataset":
                filesizes.append(int(tds[2].get_text(strip=True)))
            else:
                filesizes.append(0)

        return (contents, filesizes)

    def list_datasets(self) -> list[str]:
        """
        List all datasets available on the OCO-2/3 GES DISC.

        Returns:
            list[str]: List of available datasets

        Raises:
            requests.exceptions.RequestException: If the directory listing fails
        """
        dataset_urls, _ = self.list_directory(self.oco2_gesdisc_url)
        datasets = [
            ds.split("/")[-2] for ds in dataset_urls if ds.split("/")[-2] != "test"
        ]
        return datasets

    def _get_date_extreme(
        self, year_url: str, year: int, find_min: bool = True
    ) -> tuple[datetime, bool]:
        # Year directories for a dataset will either be DOY directories or a flat
        # directory of netCDF files and metadata

        year_contents, _ = self.list_directory(year_url)
        available_doy: list[int] = []
        for link in year_contents:
            match = self.doy_pattern.search(link)
            if match:
                # Shouldn't cause TypeError due to the regex
                available_doy.append(int(match.group(1)))

        # a list of date strings in the format YYMMDD parsed from the
        # filename in the link
        available_nc4: list[str] = []
        for link in year_contents:
            match = self.nc4_pattern.search(link)
            if match:
                available_nc4.append(str(match.group(2)))

        if len(available_doy) > 0:
            date_objects = [year_doy_to_datetime(year, doy) for doy in available_doy]
            is_daily = False
        elif len(available_nc4) > 0:
            date_objects = [datetime.strptime(date, "%y%m%d") for date in available_nc4]
            is_daily = True
        else:
            return (datetime.fromtimestamp(0), False)

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
        dir_contents, _ = self.list_directory(dataset_url)

        # Brittle way of checking that a link in an OpenDAP directory points to a
        # directory, but should be okay as long as OpenDAP format is stable

        available_years: dict[int, str] = {}
        for link in dir_contents:
            match = self.year_pattern.search(link)
            if match:
                available_years[int(match.group(1))] = link.replace("contents.html", "")

        if not available_years:
            print(f"Dataset {dataset} is doc-only or had no available products.")
            return (datetime.fromtimestamp(0), datetime.fromtimestamp(0))

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

    def _check_inputs(self, dataset: str) -> None:
        """Helper function to perform initial checks on queries arriving from Jupyter notebooks."""
        if dataset not in self.datasets.keys():
            raise ValueError(
                f"{dataset} is not a dataset available on OCO-2/3 GES DISC"
            )

        # As a side effect, adds this dataset's timerange to the cached time ranges
        # stored in this class.
        if (
            self.datasets[dataset].startdate is None
            or self.datasets[dataset].enddate is None
        ):
            print(f"Checking available dates on GES DISC for {dataset}")
            self.get_dataset_timerange(dataset)

        if not self.datasets[dataset].daily:
            raise NotImplementedError("subdaily datasets not implemented")

    def _get_granule_url_by_date(self, dataset: str, date: datetime) -> tuple[str, int]:
        """
        Internal helper to get the direct URL for a granule on a given date.
        Instead of returning a pydap dataset, it returns a tuple of the URL
        to the file and the size of the file in bytes.
        """
        # Assume all pre-checks on arguments have been done by the caller, this
        # function is "private"
        year_url = f"{self.oco2_gesdisc_url}{dataset}/{date.year}/"
        year_contents, file_sizes = self.list_directory(year_url)
        granules: dict[datetime, tuple[str, int]] = {}
        for link, size in zip(year_contents, file_sizes):
            match = self.nc4_pattern.search(link)
            if match:
                # Parse the date from the filename and use only the date part.
                granule_date = datetime.strptime(match.group(2), "%y%m%d")
                granules[granule_date] = (link, size)

        granule_info = granules.get(date)
        if granule_info is None:
            raise FileNotFoundError(
                f"No {dataset} granule found for {date.strftime('%Y-%m-%d')}"
            )

        target_granule, granule_size = granule_info
        # Remove the ".html" suffix to get the raw netCDF (.nc4) URL.
        granule_url = (
            target_granule[: -len(".html")]
            if target_granule.endswith(".html")
            else target_granule
        )
        return (granule_url, granule_size)

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
        # Will raise an error if there is an issue with the requested query
        self._check_inputs(dataset)

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

        granule_url = self._get_granule_url_by_date(dataset, date)
        return open_url(granule_url, session=self.session)

    def _download_file(self, url: str, outpath: Path) -> Path:
        """
        Internal helper to download a single file from a URL into the specified directory.
        Returns the Path to the downloaded file.
        """
        filename = url.split("/")[-1]
        file_path = outpath / filename
        try:
            with self.session.get(url, stream=True) as r:
                r.raise_for_status()
                with open(file_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        except Exception as e:
            raise RuntimeError(f"Failed to download {url}: {e}") from e
        return file_path

    def download_timerange(
        self,
        dataset: str,
        start_date: datetime,
        end_date: datetime,
        outpath: Path,
        parallel: bool = True,
    ) -> list[Path]:
        """
        Download a set of granules from a time range of dates, using multithreading by default.

        Arguments:
            dataset (str): The name of a dataset on the OCO-2/3 GES DISC OpenDAP portal
            start_date (datetime): The requested start date of the dataset
            end_date (datetime): The requested end date of the dataset
            outpath (Path): Directory to store the output files. It will be created if it does not exist.
            parallel (bool): Download files in parallel. Default behavior is True.

        Returns:
            list[Path]: A list of pathlib.Path objects referring to each file that was downloaded.

        Raises:
            ValueError: If the dataset does not exist
        """
        # Will raise an error if there is an issue with the requested query
        self._check_inputs(dataset)

        # Create the output directory if it does not exist.
        outpath.mkdir(parents=True, exist_ok=True)

        # Generate a list of dates (daily) from start_date to end_date inclusive.
        current_date = start_date
        dates: list[datetime] = []
        while current_date <= end_date:
            dates.append(current_date)
            current_date += timedelta(days=1)

        # The tuples are (date, granule_url)
        granule_urls: list[tuple[datetime, str]] = []
        total_size = 0  # in bytes

        for d in dates:
            try:
                url, size = self._get_granule_url_by_date(dataset, d)
                granule_urls.append((d, url))
                total_size += size
            except Exception as e:
                print(f"Skipping {d.strftime('%Y-%m-%d')}: {e}")

        if not granule_urls:
            print("No granules found in the specified date range.")
            return []

        total_mb = total_size / (1024 * 1024)
        print(
            f"After this operation, {int(total_mb)} MB of additional disk space will be used."
        )
        confirm = input("Do you want to continue? (y/N): ")
        if confirm.lower() not in ("y", "yes"):
            print("Download cancelled.")
            return []

        downloaded_files: list[Path] = []

        def download_task(url: str) -> Path:
            return self._download_file(url, outpath)

        if parallel:
            with ThreadPoolExecutor() as executor:
                futures = {
                    executor.submit(download_task, url): url for _, url in granule_urls
                }
                for future in as_completed(futures):
                    try:
                        file_path = future.result()
                        downloaded_files.append(file_path)
                    except Exception as e:
                        print(f"Failed to download a file: {e}")
        else:
            for _, url in granule_urls:
                try:
                    file_path = download_task(url)
                    downloaded_files.append(file_path)
                except Exception as e:
                    print(f"Failed to download {url}: {e}")

        return downloaded_files


if __name__ == "__main__":
    print("Gathering datasets on GES DISC...")
    dl = GesDiscDownloader()
    # dataset = "OCO2_L2_CO2Prior.10r"
    dataset = "OCO3_L2_Lite_SIF.11r"
    """
    print(f"Getting time range for {dataset} data...")
    timerange = dl.get_dataset_timerange(dataset)
    print(
        f"{dataset} has time range {timerange[0].strftime('%Y-%m-%d')} to {timerange[1].strftime('%Y-%m-%d')}"
    )
    granule = dl.get_granule_by_date(dataset, datetime(2019, 12, 1))
    print(granule["Latitude"].data[:])
    """
    downloaded = dl.download_timerange(
        dataset,
        datetime(2019, 12, 1),
        datetime(2019, 12, 10),
        outpath=Path("/Users/jryan/Documents/granules"),
    )
    print("Downloaded files:")
    for f in downloaded:
        print(f)
