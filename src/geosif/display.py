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

import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import numpy as np
import numpy.typing as npt


def plot_samples(
    samples: npt.NDArray[np.float64],
    lat: npt.NDArray[np.float64],
    lon: npt.NDArray[np.float64],
    cmap: str = "viridis",
    point_size: int = 20,
    vmin: float | None = None,
    vmax: float | None = None,
    title: str | None = None,
    label: str | None = None,
) -> None:
    """
    Plots sample values at the corresponding latitude and longitude coordinates
    on a world map.

    Args:
        samples (np.ndarray): 1D array of sample values
        lat (np.ndarray): 1D array of latitude values (in degrees)
        lon (np.ndarray): 1D array of longitude values (in degrees)
        cmap (str): Matplotlib colormap for the sample values, default is viridis
        point_size (int): Marker size for the scatter plot
        vmin (float): Lower bound for the colormap. Defaults to None (automatic)
        vmax (float): Upper bound for the colormap. Defaults to None (automatic)
        title (str): Optionally provide a title for the plot
        label (str): Optionally provide a name and unit for the sample quantities

    Returns:
        None

    Raises:
        ValueError: If the data arrays are not all the same length
    """
    if not (len(samples) == len(lat) == len(lon)):
        raise ValueError("samples, lat, and lon must all have the same length.")

    fig, ax = plt.subplots(
        subplot_kw={"projection": ccrs.PlateCarree()}, figsize=(10, 5)
    )

    # Add coastlines and other geographic features
    ax.set_global()
    ax.coastlines()
    ax.add_feature(cfeature.BORDERS, linewidth=0.5, edgecolor="black")
    ax.add_feature(cfeature.LAND, facecolor="lightgray")
    ax.add_feature(cfeature.OCEAN, facecolor="white")
    ax.set_extent([-180, 180, -90, 90], crs=ccrs.PlateCarree())

    # Plot the data as a scatter plot
    scatter = ax.scatter(
        lon,
        lat,
        c=samples,
        cmap=cmap,
        s=point_size,
        vmin=vmin,
        vmax=vmax,
        transform=ccrs.PlateCarree(),
    )

    cbar = plt.colorbar(
        scatter, ax=ax, orientation="horizontal", pad=0.05, fraction=0.05
    )
    if label:
        cbar.set_label(label)
    else:
        cbar.set_label("Sample values")

    if title:
        ax.set_title(title)

    plt.show()
