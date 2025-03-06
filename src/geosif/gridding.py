"""
Copyright (c) 2025 Jacqueline Ryan

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

"""
Code for creating gridded rasters from a time range of L2 granules. This code is based on
Christian Frankenberg's Julia code here: https://github.com/cfranken/gridding

As I attempted to be faithful to the original code when translating to Python, an idiosyncratic
aspect of the code is that output arrays are typically passed by reference as a function argument,
rather than returned from the function. Most functions with a return value of "None" are mutating
the values of an array as a side effect.
"""

from datetime import datetime, timedelta
from glob import glob
from netCDF4 import Dataset, date2num, Variable
import numpy as np
import numpy.typing as npt
import os
import re
from tqdm.notebook import tqdm
from typing import TypeVar

from . import GesDiscDownloader
from . import L2_SCHEMAS

DatasetType = TypeVar("DatasetType")

EQ_STRS = ["=", "==", "eq"]
GT_STRS = [">", "gt"]
LT_STRS = ["<", "lt"]


def get_variable_array(
    granule: DatasetType, variable: str, dd: bool = False, pydap: bool = True,
) -> npt.NDArray[np.float32]:
    """
    Retrieve a variable's data from a granule and return it as a numpy array of type float32.

    Arguments:
        granule (DatasetType): A pydap dataset containing the variable of interest.
        variable (str): The name of the variable to extract.
        dd (bool): Flag indicating whether to perform a reshape for footprint bounds. Default is False.
        pydap (bool): If False, use syntax for local netCDF data

    Returns:
        npt.NDArray[np.float32]: A numpy array of type float32 containing the variable data, reshaped if required.
    """
    if pydap:
        # pydap flattens all variables to the top level by joining group names with an underscore
        varname = variable.replace("/", "_")
        data = np.array(granule[varname].data[:], dtype=np.float32)
    else:
        if "/" in variable:
            group = variable.split("/")[0]
            varname = variable.split("/")[-1]
            data = np.array(granule[group][varname][:], dtype=np.float32)
        else:
            data = np.array(granule[variable][:], dtype=np.float32)
    # DD means there is a second index for footprint bounds of dimension 4
    if dd:
        if data.shape[0] == 4:
            # Reshape to (4, prod(si[1:])).T (mimicking Julia’s transpose)
            reshaped = np.reshape(data, (4, -1), order="F").T
            return reshaped
        elif data.shape[-1] == 4:
            reshaped = np.reshape(data, (-1, 4), order="F")
            return reshaped
    # If no reshaping is required, return as is
    return data


def get_granule_date(granule: DatasetType, pydap: bool) -> str:
    """extract the date metadata from an input netCDF."""
    if pydap:
        return granule.attributes["HDF5_GLOBAL"]["date_time_coverage"][0].split("T")[0]
    else:
        return granule.date_time_coverage[0].split("T")[0]


def div_line(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    n: int,
    points: npt.NDArray[np.float32],
    j: int,
) -> None:
    """
    Subdivide a line between two geographic coordinates into 'n' points and store the result in the provided array.

    Arguments:
        lat1 (float): Starting latitude.
        lon1 (float): Starting longitude.
        lat2 (float): Ending latitude.
        lon2 (float): Ending longitude.
        n (int): Number of subdivisions.
        points (npt.NDArray[np.float32]): Array to store the computed points.
        j (int): Index in the first dimension of 'points' where the result should be stored.

    Returns:
        None
    """
    dLat = (lat2 - lat1) / (2.0 * n)
    dLon = (lon2 - lon1) / (2.0 * n)
    startLat = lat1 + dLat
    startLon = lon1 + dLon
    for i in range(n):
        points[j, i, 0] = startLat + 2 * i * dLat
        points[j, i, 1] = startLon + 2 * i * dLon


# For the first baseline run: subdivide the line into n points and store in lats and lons
def div_line2(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    n: int,
    lats: npt.NDArray[np.float32],
    lons: npt.NDArray[np.float32],
) -> None:
    """
    Subdivide a line between two geographic coordinates into 'n' points and store the latitude and longitude separately.

    Arguments:
        lat1 (float): Starting latitude.
        lon1 (float): Starting longitude.
        lat2 (float): Ending latitude.
        lon2 (float): Ending longitude.
        n (int): Number of subdivisions.
        lats (npt.NDArray[np.float32]): Array to store computed latitude values.
        lons (npt.NDArray[np.float32]): Array to store computed longitude values.

    Returns:
        None
    """
    dLat = (lat2 - lat1) / (2.0 * n)
    dLon = (lon2 - lon1) / (2.0 * n)
    startLat = lat1 + dLat
    startLon = lon1 + dLon
    for i in range(n):
        lats[i] = startLat + 2 * i * dLat
        lons[i] = startLon + 2 * i * dLon


# Divide the polygon edges into grid points using the two subdivided edges
def get_points(
    points: npt.NDArray[np.float32],
    vert_lat: npt.NDArray[np.float32],
    vert_lon: npt.NDArray[np.float32],
    n: int,
    lats_0: npt.NDArray[np.float32],
    lons_0: npt.NDArray[np.float32],
    lats_1: npt.NDArray[np.float32],
    lons_1: npt.NDArray[np.float32],
):
    """
    Divide polygon edges into grid points using two subdivided edges.

    This function uses two subdivided lines from the polygon's vertices to generate a grid of points across the polygon.

    Arguments:
        points (npt.NDArray[np.float32]): Array to store the generated grid points.
        vert_lat (npt.NDArray[np.float32]): Array of vertex latitudes (expected length 4).
        vert_lon (npt.NDArray[np.float32]): Array of vertex longitudes (expected length 4).
        n (int): Number of subdivisions for each edge.
        lats_0 (npt.NDArray[np.float32]): Temporary array to store intermediate latitudes from first edge.
        lons_0 (npt.NDArray[np.float32]): Temporary array to store intermediate longitudes from first edge.
        lats_1 (npt.NDArray[np.float32]): Temporary array to store intermediate latitudes from second edge.
        lons_1 (npt.NDArray[np.float32]): Temporary array to store intermediate longitudes from second edge.

    Returns:
        None
    """
    # Note: Julia indexes 1:4; here we assume vert_lat and vert_lon are length-4 arrays.
    div_line2(vert_lat[0], vert_lon[0], vert_lat[1], vert_lon[1], n, lats_0, lons_0)
    div_line2(vert_lat[3], vert_lon[3], vert_lat[2], vert_lon[2], n, lats_1, lons_1)
    for i in range(n):
        div_line(lats_0[i], lons_0[i], lats_1[i], lons_1[i], n, points, i)


def favg_all(
    arr: npt.NDArray[np.float32],
    weight_arr: npt.NDArray[np.float32],
    lat: npt.NDArray[np.float32],
    lon: npt.NDArray[np.float32],
    inp: npt.NDArray[np.float32],
    s: int,
    s2: int,
    n: int,
    points: npt.NDArray[np.float32],
) -> None:
    """
    Aggregate and average input data onto a grid, updating the grid and weight arrays.

    This function calculates weighted averages for grid cells based on input data and updates the arrays that hold the
    accumulated values and weights. It also handles cases where the input data corresponds to a single pixel or spans a region.

    Arguments:
        arr (npt.NDArray[np.float32]): 3D array representing the grid data.
        weight_arr (npt.NDArray[np.float32]): 2D array of weights corresponding to the grid.
        lat (npt.NDArray[np.float32]): 2D array of latitudes (grid indices) for each pixel.
        lon (npt.NDArray[np.float32]): 2D array of longitudes (grid indices) for each pixel.
        inp (npt.NDArray[np.float32]): 2D array of input values for each pixel.
        s (int): Number of valid pixels.
        s2 (int): Number of variables per pixel.
        n (int): Grid subdivision factor.
        points (npt.NDArray[np.float32]): Temporary array used for subdividing pixel bounds.

    Returns:
        None
    """
    # Here, lat and lon are assumed to be 2D arrays (one row per pixel) holding grid indices.
    ix = np.zeros(n * n, dtype=np.int32)
    iy = np.zeros(n * n, dtype=np.int32)
    lats_0 = np.zeros(n, dtype=np.float32)
    lons_0 = np.zeros(n, dtype=np.float32)
    lats_1 = np.zeros(n, dtype=np.float32)
    lons_1 = np.zeros(n, dtype=np.float32)

    # Compute integer indices from lat, lon arrays
    iLon = np.floor(lon).astype(np.int32)
    iLat = np.floor(lat).astype(np.int32)
    # Minimum and maximum across each row (axis=1)
    minLat_arr = np.min(np.floor(lat).astype(np.int32), axis=1)
    maxLat_arr = np.max(np.floor(lat).astype(np.int32), axis=1)
    minLon_arr = np.min(np.floor(lon).astype(np.int32), axis=1)
    maxLon_arr = np.max(np.floor(lon).astype(np.int32), axis=1)
    distLon = maxLon_arr - minLon_arr
    dimLat = maxLat_arr - minLat_arr
    dimLon = maxLon_arr - minLon_arr
    fac = 1.0 / (n * n)

    for i in range(s):
        if (dimLat[i] == 0) and (dimLon[i] == 0):
            idx_lon = iLon[i, 0]
            idx_lat = iLat[i, 0]
            weight_arr[idx_lon, idx_lat] += 1
            for z in range(s2):
                mean_old = arr[idx_lon, idx_lat, z]
                w = weight_arr[idx_lon, idx_lat]
                arr[idx_lon, idx_lat, z] = mean_old + (1.0 / w) * (inp[i, z] - mean_old)
        elif distLon[i] < n:
            get_points(points, lat[i, :], lon[i, :], n, lats_0, lons_0, lats_1, lons_1)
            # Floor the subdivided points into indices
            ix_2d = np.floor(points[:, :, 0]).astype(np.int32)
            iy_2d = np.floor(points[:, :, 1]).astype(np.int32)
            ix = ix_2d.flatten()
            iy = iy_2d.flatten()
            for j in range(len(ix)):
                idx_lon = iy[j]
                idx_lat = ix[j]
                weight_arr[idx_lon, idx_lat] += fac
                for z in range(s2):
                    mean_old = arr[idx_lon, idx_lat, z]
                    w = weight_arr[idx_lon, idx_lat]
                    arr[idx_lon, idx_lat, z] = mean_old + (fac / w) * (
                        inp[i, z] - mean_old
                    )


def generate_dates(start_date: datetime, end_date: datetime) -> list[datetime]:
    """
    Generate a list of dates from start_date to end_date (inclusive).

    Arguments:
        start_date (datetime): The beginning date.
        end_date (datetime): The ending date.

    Returns:
        List[datetime]: List of dates between start_date and end_date.
    """
    dates: list[datetime] = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date)
        current_date += timedelta(days=1)
    return dates


def validate_date_range(
    dl: GesDiscDownloader, dataset: str, start_date: datetime, end_date: datetime
) -> None:
    """
    Validate that the requested date range is within the available dataset time range
    when using the pydap client for sourcing data.

    Arguments:
        dl (GesDiscDownloader): The downloader instance.
        dataset (str): The dataset identifier.
        start_date (datetime): The requested start date.
        end_date (datetime): The requested end date.

    Raises:
        ValueError: If the requested date range is outside the available time range for the dataset.
    """
    data_range = dl.get_dataset_timerange(dataset)
    if start_date < data_range[0] or end_date > data_range[1]:
        raise ValueError(
            f"requested date range ({start_date.strftime('%Y-%m-%d')} to "
            f"{end_date.strftime('%Y-%m-%d')}) is outside the available time range for {dataset}"
        )


def validate_local_dir(
    local_dir: str, dataset: str, start_date: datetime, end_date: datetime
) -> None:
    """
    Validate that the requested granules are available in the specified directory when
    sourcing data from disk.

    Arguments:
        local_dir (str): String path of the source granule directory.
        dataset (str): The dataset identifier, not the same as the one used in the OpenDAP portal.
        start_date (datetime): The requested start date.
        end_date (datetime): The requested end date.

    Raises:
        FileNotFoundError: If the requested date range is outside the available time range for the dataset.
    """
    assert os.path.exists(local_dir), "input granule directory not found"
    month_files = glob(
        os.path.join(local_dir, f"{dataset}*{start_date.strftime('%y%m')}*.nc*")
    )
    if len(month_files) == 0:
        raise FileNotFoundError(
            "No granules from the given month found in the provided input directory."
        )


def get_local_granule(local_dir: str, dataset: str, d: datetime) -> DatasetType:
    """
    Get the full path to a granule in the local directory for the specified date and
    dataset.

    Arguments:
        local_dir (str): String path of the source granule directory.
        dataset (str): The dataset identifier, not the same as the one used in the OpenDAP portal.
        d (datetime): The requested date.

    Returns:
        DatasetType: A netCDF Dataset object.

    Raises:
        FileNotFoundError: No data is available for the requested day in the dataset
    """
    found_files = glob(
        os.path.join(local_dir, f"{dataset}*{d.strftime('%y%m%d')}*.nc*")
    )
    if len(found_files) > 0:
        return Dataset(found_files[0], "r")
    else:
        raise FileNotFoundError(
            f"Unable to find a matching granule for {d.strftime('%y%m%d')}"
        )


def process_day_granule(
    granule: DatasetType,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    variables: list[str],
    lat_vals: npt.NDArray[np.float32],
    lon_vals: npt.NDArray[np.float32],
    n_vars: int,
    points: npt.NDArray[np.float32],
    mat_data: npt.NDArray[np.float32],
    mat_data_weights: npt.NDArray[np.float32],
    schema: dict[str, str],
    filters: dict[str, tuple[str, float]] | None = None,
    pydap: bool = True,
) -> None:
    """
    Process a single granule for a given date and update the grid data arrays.

    This function uses the GesDiscDownloader to retrieve the granule for the given date,
    extracts necessary variables, and aggregates them onto the grid.

    Arguments:
        dl (GesDiscDownloader): The downloader instance.
        dataset (str): Dataset identifier.
        d (datetime): Date for which the granule is to be processed.
        lat_min (float): Minimum latitude of the grid.
        lat_max (float): Maximum latitude of the grid.
        lon_min (float): Minimum longitude of the grid.
        lon_max (float): Maximum longitude of the grid.
        variables (List[str]): List of variable names to process.
        lat_vals (npt.NDArray[np.float32]): Array of latitude values for the grid.
        lon_vals (npt.NDArray[np.float32]): Array of longitude values for the grid.
        n_vars (int): Number of variables.
        points (npt.NDArray[np.float32]): Temporary array for subdividing pixel bounds.
        mat_data (npt.NDArray[np.float32]): 3D grid data array to update.
        mat_data_weights (npt.NDArray[np.float32]): 2D weight array to update.
        schema (dict[str, str]): A dictionary describing lat/lon key names in the granules.
        filters (dict[str, tuple[str, float]]): Optionally specify a list of filters
            where they key is the netCDF variable to filter on, and the values are a
            tuple of a comparator string (<, ==, etc.) and the threshold value
        pydap (bool): If True, handle the granule dataset using pydap syntax

    Returns:
        None
    """
    try:
        g_date = get_granule_date(granule, pydap)
    except:
        g_date = "unknown date"
    try:
        lat_granule = get_variable_array(granule, schema["lat"], pydap=pydap)
        lon_granule = get_variable_array(granule, schema["lon"], pydap=pydap)
        if np.any(
            (lat_granule > lat_min)
            & (lat_granule < lat_max)
            & (lon_granule > lon_min)
            & (lon_granule < lon_max)
        ):
            lat_in_ = get_variable_array(
                granule, schema["vertex_lat"], dd=True, pydap=pydap
            )
            lon_in_ = get_variable_array(
                granule, schema["vertex_lon"], dd=True, pydap=pydap
            )
            # If the first dimension is 4, transpose the arrays
            if lat_in_.shape[0] == 4:
                lat_in_ = lat_in_.T
                lon_in_ = lon_in_.T
            # Determine the bounding box per pixel
            min_lat_in = np.min(lat_in_, axis=1)
            max_lat_in = np.max(lat_in_, axis=1)
            min_lon_in = np.min(lon_in_, axis=1)
            max_lon_in = np.max(lon_in_, axis=1)
            bool_add = (
                (min_lat_in > lat_min).astype(int)
                + (max_lat_in < lat_max).astype(int)
                + (min_lon_in > lon_min).astype(int)
                + (max_lon_in < lon_max).astype(int)
                + (((max_lon_in - min_lon_in) < 50).astype(int))
            )
            b_counter = 5
            if filters:
                for key, val in filters.items():
                    comp = val[0]
                    thresh = val[1]
                    key_arr = get_variable_array(granule, key, pydap=pydap)
                    if comp in EQ_STRS:
                        bool_add += key_arr == thresh
                        b_counter += 1
                    elif comp in GT_STRS:
                        bool_add += key_arr > thresh
                        b_counter += 1
                    elif comp in LT_STRS:
                        bool_add += key_arr < thresh
                        b_counter += 1
                    else:
                        print(
                            f"Ignoring unprocessable filter: ds['{key}'] {comp} {thresh}"
                        )

            idx = np.where(bool_add == b_counter)[0]
            if idx.size > 0:
                n_pixels = lat_in_.shape[0]
                mat_in = np.zeros((n_pixels, n_vars), dtype=np.float32)
                for col, var in enumerate(variables):
                    mat_in[:, col] = get_variable_array(granule, var, pydap=pydap)
                iLat_ = np.floor(
                    ((lat_in_[idx, :] - lat_min) / (lat_max - lat_min)) * len(lat_vals)
                ).astype(int)
                iLon_ = np.floor(
                    ((lon_in_[idx, :] - lon_min) / (lon_max - lon_min)) * len(lon_vals)
                ).astype(int)
                iLat_ = np.clip(iLat_, 0, len(lat_vals) - 1)
                iLon_ = np.clip(iLon_, 0, len(lon_vals) - 1)
                s = idx.size
                s2 = mat_in.shape[1]
                favg_all(
                    mat_data,
                    mat_data_weights,
                    iLat_,
                    iLon_,
                    mat_in[idx, :],
                    s,
                    s2,
                    n_vars,
                    points,
                )
    except Exception as e:
        print(f"Error adding granule for {g_date} to grid, caught: {e}")


def create_gridded_raster(
    start_date: datetime,
    end_date: datetime,
    dataset: str,
    variables: list[str],
    out_file: str,
    lat_min: float = -90.0,
    lat_max: float = 90.0,
    lon_min: float = -180.0,
    lon_max: float = 180.0,
    lat_res: float = 1.0,
    lon_res: float = 1.0,
    local_dir: str | None = None,
    filters: dict[str, tuple[str, float]] | None = None,
) -> str:
    """
    Create a gridded raster netCDF file from a dataset over a specified date range.

    This function sets up the output grid and netCDF file, validates the date range,
    and then, for each day in the range, accesses the dataset using GesDiscDownloader,
    processes the granule, aggregates data onto the grid, and writes the results to file.

    Arguments:
        start_date (datetime): The start date for the data extraction.
        end_date (datetime): The end date for the data extraction.
        dataset (str): The dataset identifier to be processed.
        variables (List[str]): A list of variable names to extract from the dataset.
        out_file (str): Path to the output netCDF file.
        lat_min (float): Minimum latitude for the output grid. Default is -90.0.
        lat_max (float): Maximum latitude for the output grid. Default is 90.0.
        lon_min (float): Minimum longitude for the output grid. Default is -180.0.
        lon_max (float): Maximum longitude for the output grid. Default is 180.0.
        lat_res (float): Latitude resolution of the output grid. Default is 1.0.
        lon_res (float): Longitude resolution of the output grid. Default is 1.0.
        local_dir (str | None): If specified, use a local directory to source input
            granules instead of progressively downloading using pydap. This will also
            enable parallel processing.
        filters (dict[str, tuple[str, float]]): Optionally specify a list of filters
            where they key is the netCDF variable to filter on, and the values are a
            tuple of a comparator string (<, ==, etc.) and the threshold value

    Returns:
        str: The path to the output netCDF file.

    Raises:
        ValueError: If the requested date range is outside the available time range for the dataset.
        ValueError: If the requested dataset does not have a known schema describing its lat/lon variables.
    """
    dates = generate_dates(start_date, end_date)

    if local_dir is None:
        dl = GesDiscDownloader()
        validate_date_range(dl, dataset, start_date, end_date)
    else:
        validate_local_dir(local_dir, dataset, start_date, end_date)
    
    granule_schema: dict[str, str] | None = None
    for schema in L2_SCHEMAS:
        if re.match(schema["regex"], dataset):
            granule_schema = schema
        elif re.match(schema["file_regex"], dataset):
            granule_schema = schema
    if granule_schema is None:
        raise ValueError(f"unsupported dataset: {dataset}, add to L2_SCHEMAS in schemas.py if you know the variables to use.")

    n_time = len(dates)
    eps = lat_res / 100.0
    lat_vals = np.arange(
        lat_min + lat_res / 2.0,
        lat_max - lat_res / 2.0 + eps,
        lat_res,
        dtype=np.float32,
    )
    lon_vals = np.arange(
        lon_min + lon_res / 2.0,
        lon_max - lon_res / 2.0 + eps,
        lon_res,
        dtype=np.float32,
    )

    print("Output file dimension (time/lon/lat):")
    print(n_time, "/", len(lon_vals), "/", len(lat_vals))

    ds_out = Dataset(out_file, "w", format="NETCDF4")
    ds_out.createDimension("lat", len(lat_vals))
    ds_out.createDimension("lon", len(lon_vals))
    ds_out.createDimension("time", n_time)

    ds_lat = ds_out.createVariable("lat", np.float32, ("lat",))
    ds_lon = ds_out.createVariable("lon", np.float32, ("lon",))
    ds_time = ds_out.createVariable("time", np.float32, ("time",))

    ds_lat.units = "degrees_north"
    ds_lat.long_name = "Latitude"
    ds_lon.units = "degrees_east"
    ds_lon.long_name = "Longitude"
    ds_time.units = "days since 1970-01-01"
    ds_time.long_name = "Time (UTC), start of interval"

    ds_lat[:] = lat_vals
    ds_lon[:] = lon_vals
    ds_out.title = f"{start_date.strftime('%b %Y')} monthly average {dataset}"

    nc_dict: dict[str, Variable] = {}
    for var in variables:
        ds_var = ds_out.createVariable(
            var,
            np.float32,
            ("time", "lon", "lat"),
            zlib=True,
            complevel=4,
            fill_value=-999.0,
        )
        nc_dict[var] = ds_var
    ds_n = ds_out.createVariable(
        "n",
        np.float32,
        ("time", "lon", "lat"),
        zlib=True,
        complevel=4,
        fill_value=-999.0,
    )
    ds_n.units = ""
    ds_n.long_name = "Number of pixels in average"

    n_grid = 10
    points = np.zeros((n_grid, n_grid, 2), dtype=np.float32)

    n_vars = len(variables)
    mat_data = np.zeros((len(lon_vals), len(lat_vals), n_vars), dtype=np.float32)
    mat_data_weights = np.zeros((len(lon_vals), len(lat_vals)), dtype=np.float32)

    for t_ndx, d in enumerate(tqdm(dates, desc="Time slices")):
        try:
            if local_dir is None:
                granule = dl.get_granule_by_date(dataset, d)
            else:
                granule = get_local_granule(local_dir, dataset, d)

            print(f"Gridding {d.strftime('%Y-%m-%d')} ({t_ndx + 1}/{n_time})")
            process_day_granule(
                granule,
                lat_min,
                lat_max,
                lon_min,
                lon_max,
                variables,
                lat_vals,
                lon_vals,
                n_vars,
                points,
                mat_data,
                mat_data_weights,
                granule_schema,
                filters=filters,
                pydap=(local_dir is None),
            )

            if np.max(mat_data_weights) > 0:
                ds_n[t_ndx, :, :] = mat_data_weights
                ds_time[t_ndx] = date2num(d, units=ds_time.units)
                for col, var in enumerate(variables):
                    da = np.round(mat_data[:, :, col], 6)
                    da[mat_data_weights < 1e-10] = -999
                    nc_dict[var][t_ndx, :, :] = da
            else:
                ds_n[t_ndx, :, :] = 0
                ds_time[t_ndx] = date2num(d, units=ds_time.units)
        except FileNotFoundError:
            print(f"No data found for {d.strftime('%Y-%m-%d')}, skipping")
            granule = None
            ds_n[t_ndx, :, :] = 0
            ds_time[t_ndx] = date2num(d, units=ds_time.units)
        except Exception as e:
            print(f"Error processing granule for {d.strftime('%Y-%m-%d')}: {e}")
        finally:
            # Close the granule file if it's a netCDF Dataset
            if granule is not None and hasattr(granule, "close"):
                granule.close()

        # Reset temporary arrays for the next time slice
        mat_data.fill(0.0)
        mat_data_weights.fill(0.0)

    ds_out.close()
    return out_file


if __name__ == "__main__":
    create_gridded_raster(
        datetime(2020, 5, 1),
        datetime(2020, 5, 31),
        "OCO3_L2_Lite_SIF.11r",
        ["Daily_SIF_757nm"],
        "data/may_2020_sif.nc4",
        local_dir="data",
    )
