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

from datetime import datetime
import earthaccess
import gzip
import math
from netCDF4 import Dataset
import os
import requests
import shutil
from tqdm.notebook import tqdm
from urllib.parse import urljoin


def granule_date(granule: earthaccess.DataGranule) -> datetime:
    """
    Get the date of a daily granule from its metadata in NASA's Common Metadata
    Repository (CMR). OCO-2 and OCO-3 Lite granules each cover one UTC day starting
    at midnight, so the beginning of the granule's time range is the date of its data.

    Arguments:
        granule (DataGranule): A search result returned by earthaccess.search_data

    Returns:
        datetime: Midnight at the start of the day covered by the granule
    """
    begin = granule["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"]
    return datetime.strptime(begin[:10], "%Y-%m-%d")


def open_granule_in_memory(granule: earthaccess.DataGranule) -> Dataset:
    """
    Stream a granule from NASA Earthdata into memory and open it with netCDF4, without
    saving the file to disk. Call earthaccess.login() before using this function.

    Arguments:
        granule (DataGranule): A search result returned by earthaccess.search_data

    Returns:
        Dataset: An in-memory netCDF4 Dataset. Close it when you are done with it.

    Raises:
        RuntimeError: If the granule could not be opened, e.g. when not logged in
    """
    try:
        files = earthaccess.open([granule], show_progress=False)
    except AttributeError as e:
        # earthaccess does not set up its file store until you log in
        raise RuntimeError("Call earthaccess.login() before opening granules") from e
    if not files:
        raise RuntimeError(f"Unable to open granule {granule.data_links()}")

    remote_file = files[0]
    try:
        contents = remote_file.read()
    finally:
        remote_file.close()
    filename = os.path.basename(granule.data_links()[0])
    return Dataset(filename, mode="r", memory=contents)


def download_file(url: str, output_path: str, verbose: bool = False):
    """
    Download a file from the specified URL to the output path. This does not use an
    authenticated session, so it is only suitable for publicly available data.

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
