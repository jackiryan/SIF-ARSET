"""
Copyright (c) 2025, by the California Institute of Technology. ALL RIGHTS RESERVED.
United States Government Sponsorship acknowledged. Any commercial use must be 
negotiated with the Office of Technology Transfer at the California Institute 
of Technology.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from bs4 import BeautifulSoup, Tag
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from dotenv import load_dotenv
import gzip
import math
import os
from pathlib import Path
from pydap.client import open_url
# from pydap.cas.urs import setup_session
import pydap.lib
import re
import requests
import requests_cache
import shutil
from tqdm.notebook import tqdm
from urllib.parse import urljoin, urlparse
from urllib3.util.retry import Retry

os.makedirs("pydap-cache", exist_ok=True)
pydap.lib.CACHE = "pydap-cache/" # type: ignore


def year_doy_to_datetime(year: int, doy: int) -> datetime:
    """
    Convert an integer year and day of year (DOY) to a datetime object.

    Arguments:
        year (int): The year (e.g., 2024)
        doy (int): The day of the year (1-365 or 1-366 for leap years)

    Returns:
        datetime: A datetime object representing the date.
    """
    return datetime.strptime(f"{year}-{doy}", "%Y-%j")


@dataclass
class GesDiscDataset:
    name: str
    # Rather than handling possible None values, set the default
    # date range to somewhere far in the future if the timerange
    # fails to be found. This would cause granule requests to sub-
    # sequently fail (intended).
    startdate: datetime = datetime(2100, 1, 1)
    enddate: datetime = datetime(2100, 1, 2)
    daily: bool = False


def create_retry_session(
    username: str | None, password: str | None, retries: int = 5, backoff_factor: float = 1.0
) -> requests.Session:
    """
    When downloading data from the DAAC's direct data portal (not OpenDAP), the
    server can occasionally return error 503 (Unavailable) when handling too many
    client requests. This function attempts to mitigate that by retrying the request
    with a backoff factor.

    Arguments:
        username (str | None): Earthdata username. If not provided, uses the netrc
        password (str | None): Earthdata password
        retries (int): Number of retries to use for the request
        backoff_factor (float): increase in amount of time to space repeated requests

    Returns:
        requests.Session: A session object that will be used for subsequent HTTPS
            requests to the DAAC
    """
    session = requests.Session()
    if username and password:
        token_sess = requests.Session()
        token_sess.headers.update({"User-Agent": "earthaccess"})
        token_sess.auth = (username, password)
        auth_resp = token_sess.post(
            "https://urs.earthdata.nasa.gov/api/users/find_or_create_token",
            headers={
                "Accept": "application/json",
            },
            timeout=10,
        )
        
        if not auth_resp.ok:
            msg = f"Authentication with Earthdata Login failed with:\n{auth_resp.text}"
            raise ValueError(msg)

        token_data = auth_resp.json()
        if "access_token" in token_data:
            token = token_data["access_token"]
        else:
            # prints token to screen, potentially vulnerable
            raise ValueError(f"Could not find token in response: {token_data}")
            
        session.headers.update({"Authorization": f"Bearer {token}"})

    retry_strategy = Retry(
        total=retries,
        status_forcelist=[503],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        backoff_factor=backoff_factor,
        raise_on_status=False,
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


class GesDiscDownloader:
    # While this URL references OCO-2, it also contains OCO-3 datasets
    oco2_gesdisc_url = "https://oco2.gesdisc.eosdis.nasa.gov/opendap/"
    # OpenDAP is basically broken as far as I can tell, and does not allow downloads
    # Use the direct data portal as a backup until this is fixed.
    gesdisc_download_url = "https://oco2.gesdisc.eosdis.nasa.gov/data/"
    year_pattern = re.compile(r"/(\d{4})/contents\.html$")
    doy_pattern = re.compile(r"/(\d{3})/contents\.html$")
    nc4_pattern = re.compile(r"/([^/]*?)_(\d{6})_.*?\.nc4?(?:\.dmr)?\.html$")

    def __init__(self):
        load_dotenv()
        username = os.getenv("EARTHDATA_USERNAME")
        password = os.getenv("EARTHDATA_PASSWORD")
            
        self.session = create_retry_session(username, password)
        self.pydap_session = self.session

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

        Arguments:
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
            link: Tag | None = tds[0].find("a")
            if not link:
                continue
            href = str(link.get("href"))
            if href.startswith("http://") or href.startswith("https://"):
                content_url = href
            else:
                # href is a relative URL, so prepend the parent URL
                content_url = urljoin(url, href)
            contents.append(content_url.strip())

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

        # Short circuit the queries if we have already populated the values
        if (
            self.datasets[dataset].startdate != datetime(2100, 1, 1)
            and self.datasets[dataset].enddate != datetime(2100, 1, 2)
        ):
            return (self.datasets[dataset].startdate, self.datasets[dataset].enddate)

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
            self.datasets[dataset].startdate == datetime(2100, 1, 1)
            or self.datasets[dataset].enddate == datetime(2100, 1, 2)
        ):
            print(f"Checking available dates on GES DISC for {dataset}")
            self.get_dataset_timerange(dataset)

        if not self.datasets[dataset].daily:
            raise NotImplementedError("subdaily datasets not implemented")

    def _get_granule_url_by_date(self, dataset: str, date: datetime) -> str:
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

        target_granule, _ = granule_info
        # Replace https with dap4
        target_granule = target_granule.replace("https", "dap4")
        # Remove the ".html" suffix to get the raw netCDF (.nc4) URL.
        granule_url = (
            target_granule[: -len(".html")]
            if target_granule.endswith(".html")
            else target_granule
        )
        # Also now we should remove the .dmr suffix (new as far as I can tell)
        granule_url = (
            granule_url[: -len(".dmr")]
            if granule_url.endswith(".dmr")
            else granule_url
        )
        return granule_url

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
        # pydap session is used to get around transient errors where EDL_TOKEN causes 401 errors. 
        return open_url(granule_url, session=self.pydap_session)

    def _opendap_to_archive_url(self, dataset: str, url: str) -> str:
        # Rough heuristic for figuring out which archive directory to filter to
        if dataset.startswith("OCO2"):
            data_dir = "OCO2_DATA"
        else:
            data_dir = "OCO3_DATA"
        # Assumes product is daily (no doy dirs)
        year = url.split("/")[-2]
        filename = url.split("/")[-1]
        return urljoin(
            self.gesdisc_download_url, f"{data_dir}/{dataset}/{year}/{filename}"
        )

    def _download_file(self, url: str, outpath: Path) -> Path:
        """
        Internal helper to download a single file from a URL into the specified directory.
        Returns the Path to the downloaded file.
        """
        filename = os.path.basename(urlparse(url).path)
        file_path = outpath / filename
        if file_path.exists():
            # Skip downloading if the file exists
            # print(f"Skipping {file_path}, already downloaded...")
            return file_path
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
        outpath: str | Path,
        parallel: bool = True,
        yes: bool = False,
    ) -> tuple[list[Path], list[datetime], list[str]]:
        """
        Download a set of granules from a time range of dates, using multithreading by default.

        Arguments:
            dataset (str): The name of a dataset on the OCO-2/3 GES DISC OpenDAP portal
            start_date (datetime): The requested start date of the dataset
            end_date (datetime): The requested end date of the dataset
            outpath (Path): Directory to store the output files. It will be created
                if it does not exist.
            parallel (bool): Download files in parallel. Default behavior is True.
            yes (bool): Skip yes/no prompt before downloading.

        Returns:
            tuple[list[Path], list[datetime], list[str]]:
                - list of Paths referring to each file that was downloaded
                - list of dates for which no granule was found on the DAAC.
                - list of urls that failed to download, if any

        Raises:
            ValueError: If the dataset does not exist
        """
        # Will raise an error if there is an issue with the requested query
        self._check_inputs(dataset)
        if start_date > end_date:
            raise ValueError("start date is after the end date of requested time range")

        # Create the output directory if it does not exist.
        outpath = Path(outpath).resolve()
        outpath.mkdir(parents=True, exist_ok=True)

        # Generate a list of dates (daily) from start_date to end_date inclusive.
        current_date = start_date
        dates: list[datetime] = []
        while current_date <= end_date:
            dates.append(current_date)
            current_date += timedelta(days=1)
        dates_by_year: dict[int, list[datetime]] = {}
        for d in dates:
            dates_by_year.setdefault(d.year, []).append(d)

        # The tuples are (date, granule_url)
        granule_urls: list[tuple[datetime, str]] = []
        total_size = 0  # in bytes

        # Build up a list of all requested dates in case the request crosses a
        # year boundary
        all_requested_dates: list[datetime] = []

        for year, date_list in dates_by_year.items():
            all_requested_dates.extend(date_list)
            year_dir = f"{self.oco2_gesdisc_url}{dataset}/{year}/"
            try:
                directory_urls, file_sizes = self.list_directory(year_dir)
            except Exception as e:
                print(f"Error fetching directory for year {year}: {e}")
                continue

            for url, size in zip(directory_urls, file_sizes):
                match = self.nc4_pattern.search(url)
                if match:
                    date = datetime.strptime(match.group(2), "%y%m%d")
                    if date in date_list:
                        opendap_url = (
                            url[: -len(".html")] if url.endswith(".html") else url
                        )
                        # also remove the dmr suffix if present, this is a new thing
                        opendap_url = (
                            opendap_url[: -len(".dmr")] if opendap_url.endswith(".dmr") else opendap_url
                        )
                        archive_url = self._opendap_to_archive_url(dataset, opendap_url)
                        filename = os.path.basename(urlparse(archive_url).path)
                        file_path = outpath / Path(filename)
                        if not file_path.exists():
                            total_size += size
                        granule_urls.append((date, archive_url))

        found_dates = list(map(lambda x: x[0], granule_urls))
        notfound_dates = list(set(all_requested_dates) - set(found_dates))

        if not granule_urls:
            print("No granules found in the specified date range.")
            return ([], notfound_dates, [])

        total_mb = total_size / (1024 * 1024)
        if not yes:
            print(
                f"This action will add an additional {int(total_mb)} MB of data to {outpath}"
            )
            confirm = input("Do you want to continue? (y/N): ")
            if confirm.lower() not in ("y", "yes"):
                print("Download cancelled.")
                return ([], [], [])

        downloaded_files: list[Path] = []
        failed_downloads: list[str] = []

        def download_task(url: str) -> Path:
            return self._download_file(url, outpath)

        if parallel:
            # Setting max_workers to 3 as a default because more workers might be
            # causing issues server-side
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(download_task, url): url for _, url in granule_urls
                }
                for future in tqdm(
                    as_completed(futures), total=len(futures), desc="Downloading files"
                ):
                    try:
                        downloaded_files.append(future.result())
                    except Exception as e:
                        failed_url = futures[future]
                        print(f"Failed to download {failed_url}: {e}")
                        failed_downloads.append(failed_url)

        else:
            for _, url in tqdm(
                granule_urls, total=len(granule_urls), desc="Downloading files"
            ):
                try:
                    file_path = download_task(url)
                    downloaded_files.append(file_path)
                except Exception as e:
                    print(f"Failed to download {url}: {e}")
                    failed_downloads.append(url)

        return (downloaded_files, notfound_dates, failed_downloads)


def download_file(url: str, output_path: str, verbose: bool = False):
    """
    Download a file from the specified URL to the output path. Very similar to
    GesdiscDataDownloader._download_file, but does not rely on an authenticated
    session.

    Arguments:
        url (str): URL to download
        output_path (str): Path to save the downloaded file
        verbose (bool, optional): Enable verbose output

    Returns:
        bool: True if download was successful, False otherwise
    """
    try:
        if verbose:
            print(f"Downloading from {url}...")

        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an exception if not a 2xx response

        total_size = int(response.headers.get("content-length", 0))

        with open(output_path, "wb") as f:
            if verbose and total_size > 0:
                print(f"Total file size: {total_size / (1024 * 1024):.2f} MB")

            downloaded = 0

            for chunk in tqdm(
                response.iter_content(chunk_size=8192),
                total=round(total_size / 8192),
                desc="Downloading file",
            ):
                f.write(chunk)
                downloaded += len(chunk)

        if verbose:
            print(f"Successfully downloaded: {output_path}")
        return output_path
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return ""


def construct_unh_url(
        base_url: str,
        dataset: str,
        year: int,
        month: int | None = None,
        day: int | None = None,
        verbose: bool = False
) -> str:
    """
    Construct the appropriate URL on the UNH data store based on the provided parameters.

    Arguments:
        base_url (str): Base URL for the UNH server
        dataset (str): Dataset name (e.g., GOSIF_v2)
        year (int): Year to download data for
        month (int, optional): Month to download data for (1-12)
        day (int, optional): Day to download data for
        verbose (bool): Enable verbose output

    Returns:
        str: URL for the requested data file
    """
    # Base URL for the dataset
    dataset_url = urljoin(base_url, dataset + "/")

    # Remove "_v2" from dataset name if present for filename construction
    filename_dataset = dataset.replace("_v2", "")

    if month is None and day is None:
        # Annual data
        resolution_path = "Annual/"
        filename = f"{filename_dataset}_{year}.tif.gz"
        if verbose:
            print(f"Requesting annual data for {year}")
    elif month is not None and day is None:
        # Monthly data
        resolution_path = "Monthly/"
        filename = f"{filename_dataset}_{year}.M{month:02d}.tif.gz"
        if verbose:
            print(f"Requesting monthly data for {year}-{month:02d}")
    elif month is None and day is not None:
        # 8day data - since month is none assume day is doy
        resolution_path = "8day/"
        day_of_year = day

        # For 8-day data, find the nearest 8-day period
        # The 8-day periods are: 1-8, 9-16, 17-24, etc.
        # So the representative days are 1, 9, 17, 25, etc.
        nearest_8day = 1 + 8 * math.floor((day_of_year - 1) / 8)

        filename = f"{filename_dataset}_{year}{nearest_8day:03d}.tif.gz"
        if verbose:
            print(
                f"Requesting 8-day data for {year}-{nearest_8day:03d} (DOY {nearest_8day:03d})"
            )
    else:
        # 8day data - need to calculate day of year
        resolution_path = "8day/"
        month = month or 1
        day = day or 1
        date = datetime(year, month, day)
        day_of_year = int(date.strftime("%j"))  # Day of year as integer

        nearest_8day = 1 + 8 * math.floor((day_of_year - 1) / 8)

        filename = f"{filename_dataset}_{year}{nearest_8day:03d}.tif.gz"
        if verbose:
            print(
                f"Requesting 8-day data for {year}-{month:02d}-{day:02d} (DOY {nearest_8day:03d})"
            )

    file_url = urljoin(dataset_url, resolution_path + filename)

    return file_url


def download_gosif_granule(
    year: int,
    month: int | None = None,
    day: int | None = None,
    dataset: str = "GOSIF_v2",
    output_dir: str | None = None,
    verbose: bool = True,
) -> str:
    """
    Download a granule for the UNH global ecology data store, mostly for downloading
    GOSIF data.

    Arguments:
        year (int): Year of granule data. If no other date info is provided, will
            download the annual product.
        month (int): Month of granule data. If no day is provided, will download the
            Monthly product.
        day (int): Day of the granule data. Will find the closest match to the 8-day
            cadence. If no month is provided, day will be treated as a day of year.
        dataset (str): Specify the name of the dataset, default is GOSIF_v2
        output_dir (str): Path to store the downloaded granule. Default is cwd.
        verbose (bool): Print additional information. Default is True.

    Returns:
        str: Path of downloaded granule.
    """
    base_url = "https://data.globalecology.unh.edu/data/"
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    else:
        output_dir = os.getcwd()

    try:
        # Construct the URL
        url = construct_unh_url(base_url, dataset, year, month, day, verbose)

        # Determine the output filename
        output_filename = os.path.basename(url)
        output_path = os.path.join(output_dir, output_filename)

        if os.path.exists(output_path):
            return output_path
        granule_name = download_file(url, output_path, verbose)
    except Exception as e:
        print(f"Unexpected error: {e}")
        return ""

    return granule_name


def download_unpack_gosif(year: int,
                          month: int | None = None,
                          day: int | None = None,
                          dataset: str = "GOSIF_v2",
                          output_dir: str | None = None,
                          verbose: bool = True
) -> str:
    """
    Download and unzip a GOSIF granule from the UNH data store.

    Arguments:
        year (int): Year of granule data. If no other date info is provided, will
            download the annual product.
        month (int): Month of granule data. If no day is provided, will download the
            Monthly product.
        day (int): Day of the granule data. Will find the closest match to the 8-day
            cadence. If no month is provided, day will be treated as a day of year.
        dataset (str): Specify the name of the dataset, default is GOSIF_v2
        output_dir (str): Path to store the downloaded granule. Default is cwd.
        verbose (bool): Print additional information. Default is True.

    Returns:
        str: Path of downloaded granule.
    """
    # The file is a .gz (gzip) archive, so it will need to be extracted before we can use it
    gosif_gz = download_gosif_granule(year, month, day, dataset, output_dir, verbose)

    # Strip .gz file extension from the downloaded file to get the output (extracted) filename
    gosif_geotiff = os.path.splitext(gosif_gz)[0]
    with gzip.open(gosif_gz, "rb") as f_in:
        with open(gosif_geotiff, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    if verbose:
        print(f"Unpacked geotiff file: {gosif_geotiff}")
    return gosif_geotiff


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
        outpath=Path("data"),
        parallel=False,
    )
    print("Downloaded files:")
    for f in downloaded:
        print(f)
