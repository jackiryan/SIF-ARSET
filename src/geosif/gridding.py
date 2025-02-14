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

from datetime import datetime, timedelta
from netCDF4 import Dataset, date2num, Variable
import numpy as np
import numpy.typing as npt
from tqdm.notebook import tqdm
from typing import TypeVar

from . import GesDiscDownloader

DatasetType = TypeVar("DatasetType")


def get_variable_array(
    granule: DatasetType, variable: str, dd: bool = False
) -> npt.NDArray[np.float32]:
    data = np.array(granule[variable].data[:], dtype=np.float32)
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


# This function subdivides a line between (lat1,lon1) and (lat2,lon2) into n points,
# writing the results into points[j, :, :]
def div_line(lat1, lon1, lat2, lon2, n, points, j):
    dLat = (lat2 - lat1) / (2.0 * n)
    dLon = (lon2 - lon1) / (2.0 * n)
    startLat = lat1 + dLat
    startLon = lon1 + dLon
    for i in range(n):
        points[j, i, 0] = startLat + 2 * i * dLat
        points[j, i, 1] = startLon + 2 * i * dLon


# For the first baseline run: subdivide the line into n points and store in lats and lons
def div_line2(lat1, lon1, lat2, lon2, n, lats, lons):
    dLat = (lat2 - lat1) / (2.0 * n)
    dLon = (lon2 - lon1) / (2.0 * n)
    startLat = lat1 + dLat
    startLon = lon1 + dLon
    for i in range(n):
        lats[i] = startLat + 2 * i * dLat
        lons[i] = startLon + 2 * i * dLon


# Divide the polygon edges into grid points using the two subdivided edges
def get_points(points, vert_lat, vert_lon, n, lats_0, lons_0, lats_1, lons_1):
    # Note: Julia indexes 1:4; here we assume vert_lat and vert_lon are length-4 arrays.
    div_line2(vert_lat[0], vert_lon[0], vert_lat[1], vert_lon[1], n, lats_0, lons_0)
    div_line2(vert_lat[3], vert_lon[3], vert_lat[2], vert_lon[2], n, lats_1, lons_1)
    for i in range(n):
        div_line(lats_0[i], lons_0[i], lats_1[i], lons_1[i], n, points, i)


def favg_all(
    arr,
    weight_arr,
    lat,
    lon,
    inp,
    s,
    s2,
    n,
    points,
):
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
) -> str:
    dl = GesDiscDownloader()

    dates: list[datetime] = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date)
        current_date += timedelta(days=1)

    data_range = dl.get_dataset_timerange(dataset)
    if start_date < data_range[0] or end_date > data_range[1]:
        raise ValueError(
            f"requested date range ({start_date.strftime('%Y-%m-%d')} to"
            f"{end_date.strftime('%Y-%m-%d')}) is outside the available "
            f"time range for {dataset}"
        )

    n_time = len(dates)  # number of time slices
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
        print(f"Gridding {d.strftime('%Y-%m-%d')} ({t_ndx + 1}/{n_time})")

        try:
            # Get a pydap client connection to the granule for this day
            granule = dl.get_granule_by_date(dataset, d)
            lat_granule = get_variable_array(granule, "Latitude")
            lon_granule = get_variable_array(granule, "Longitude")
            if np.any(
                (lat_granule > lat_min)
                & (lat_granule < lat_max)
                & (lon_granule > lon_min)
                & (lon_granule < lon_max)
            ):
                lat_in_ = get_variable_array(
                    granule, "Geolocation_footprint_latitude_vertices", dd=True
                )
                lon_in_ = get_variable_array(
                    granule, "Geolocation_footprint_longitude_vertices", dd=True
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
                # Build a counter of conditions (True=1, False=0)
                bool_add = (
                    (min_lat_in > lat_min).astype(int)
                    + (max_lat_in < lat_max).astype(int)
                    + (min_lon_in > lon_min).astype(int)
                    + (max_lon_in < lon_max).astype(int)
                    + (((max_lon_in - min_lon_in) < 50).astype(int))
                )
                b_counter = 5

                # Not implementing additional filter conditions for now

                idx = np.where(bool_add == b_counter)[0]
                if idx.size > 0:
                    n_pixels = lat_in_.shape[0]
                    mat_in = np.zeros((n_pixels, n_vars), dtype=np.float32)
                    col = 0
                    for var in variables:
                        mat_in[:, col] = get_variable_array(granule, var)
                        col += 1
                    # Compute grid indices (scale the pixel bounds to the output grid)
                    # Note: we subtract 1 to convert to 0-indexing.
                    iLat_ = np.floor(
                        ((lat_in_[idx, :] - lat_min) / (lat_max - lat_min))
                        * len(lat_vals)
                    ).astype(int)
                    iLon_ = np.floor(
                        ((lon_in_[idx, :] - lon_min) / (lon_max - lon_min))
                        * len(lon_vals)
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
            print(
                f"Error adding granule for {d.strftime('%Y-%m-%d')} to grid, caught: {e}"
            )

        if np.max(mat_data_weights) > 0:
            ds_n[t_ndx, :, :] = mat_data_weights
            ds_time[t_ndx] = date2num(d, units=ds_time.units)
            col = 0
            for var in variables:
                da = np.round(mat_data[:, :, col], 6)
                da[mat_data_weights < 1e-10] = -999
                nc_dict[var][t_ndx, :, :] = da
                col += 1
        else:
            ds_n[t_ndx, :, :] = 0
            ds_time[t_ndx] = date2num(d, units=ds_time.units)

        # Reset the temporary arrays for the next time slice
        mat_data.fill(0.0)
        mat_data_weights.fill(0.0)

    ds_out.close()


if __name__ == "__main__":
    create_gridded_raster(
        datetime(2020, 4, 1),
        datetime(2020, 4, 30),
        "OCO3_L2_Lite_SIF.11r",
        ["Daily_SIF_757nm"],
        "data/apr_2020_sif.nc4",
    )
