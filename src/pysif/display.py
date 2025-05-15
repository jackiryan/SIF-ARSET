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
    fig_size: tuple[int, int] = (16, 8),
    vmin: float | None = None,
    vmax: float | None = None,
    extents: list[float] = [-180, 180, -90, 90],
    title: str | None = None,
    label: str | None = None,
    outfile: str | None = None,
) -> None:
    """
    Plots sample values at the corresponding latitude and longitude coordinates
    on a world map.

    Arguments:
        samples (np.ndarray): 1D array of sample values
        lat (np.ndarray): 1D array of latitude values (in degrees)
        lon (np.ndarray): 1D array of longitude values (in degrees)
        cmap (str): Matplotlib colormap for the sample values, default is viridis
        point_size (int): Marker size for the scatter plot
        fig_size (tuple[int, int]): Size of the matplotlib figure (default 16, 8)
        vmin (float): Lower bound for the colormap. Defaults to None (automatic)
        vmax (float): Upper bound for the colormap. Defaults to None (automatic)
        title (str): Optionally provide a title for the plot
        label (str): Optionally provide a name and unit for the sample quantities
        outfile (str): Optionally save the plot as an image

    Returns:
        None

    Raises:
        ValueError: If the data arrays are not all the same length
    """
    _plot_map(
        False,
        samples,
        lat,
        lon,
        cmap=cmap,
        point_size=point_size,
        fig_size=fig_size,
        vmin=vmin,
        vmax=vmax,
        extents=extents,
        title=title,
        label=label,
        outfile=outfile,
    )


def plot_gridded(
    grid_data: npt.NDArray[np.float32],
    lat2d: npt.NDArray[np.float32],
    lon2d: npt.NDArray[np.float32],
    cmap: str = "viridis",
    fig_size: tuple[int, int] = (16, 8),
    vmin: float | None = None,
    vmax: float | None = None,
    extents: list[float] = [-180, 180, -90, 90],
    title: str | None = None,
    label: str | None = None,
    outfile: str | None = None,
) -> None:
    """
    Plots 2-D gridded data on a lat/lon coordinate system overlayed on a world map.

    Arguments:
        grid_data (np.ndarray): 2D array of sample values
        lat (np.ndarray): 2D array of latitude values (in degrees)
        lon (np.ndarray): 2D array of longitude values (in degrees)
        cmap (str): Matplotlib colormap for the sample values, default is viridis
        fig_size (tuple[int, int]): Size of the matplotlib figure (default 16, 8)
        vmin (float): Lower bound for the colormap. Defaults to None (automatic)
        vmax (float): Upper bound for the colormap. Defaults to None (automatic)
        title (str): Optionally provide a title for the plot
        label (str): Optionally provide a name and unit for the sample quantities
        outfile (str): Optionally save the plot as an image

    Returns:
        None

    Raises:
        ValueError: If the data arrays are not all the same length
    """
    _plot_map(
        True,
        grid_data,
        lat2d,
        lon2d,
        cmap=cmap,
        fig_size=fig_size,
        vmin=vmin,
        vmax=vmax,
        extents=extents,
        title=title,
        label=label,
        outfile=outfile,
    )


def _plot_map(
    is_grid: bool,
    data: npt.NDArray[np.float32],
    lat: npt.NDArray[np.float32],
    lon: npt.NDArray[np.float32],
    cmap: str = "viridis",
    point_size: int = 20,
    fig_size: tuple[int, int] = (16, 8),
    vmin: float | None = None,
    vmax: float | None = None,
    extents: list[float] = [-180, 180, -90, 90],
    title: str | None = None,
    label: str | None = None,
    outfile: str | None = None,
) -> None:
    if not (len(data) == len(lat) == len(lon)):
        raise ValueError("samples, lat, and lon must all have the same length.")

    fig, ax = plt.subplots(
        subplot_kw={"projection": ccrs.PlateCarree()}, figsize=fig_size
    )

    ax.set_global()
    ax.add_feature(cfeature.LAND, facecolor="lightgray")
    ax.add_feature(cfeature.OCEAN, facecolor="white")
    # Renders coastlines and borders underneath data
    ax.coastlines(linewidth=0.5, zorder=-1)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5, edgecolor="black", zorder=-1)
    ax.set_extent(extents, crs=ccrs.PlateCarree())

    if is_grid:
        # Matplotlib pcolormesh displays the gridded data as a pixel-like grid
        # Note vmax is lower here than in the previous example, SIF can vary seasonally.
        chart = ax.pcolormesh(
            lon,
            lat,
            data,
            vmin=vmin,
            vmax=vmax,
            cmap=cmap,
            transform=ccrs.PlateCarree(),
        )
    else:
        # Plot the data as a scatter plot
        chart = ax.scatter(
            lon,
            lat,
            c=data,
            cmap=cmap,
            s=point_size,
            vmin=vmin,
            vmax=vmax,
            transform=ccrs.PlateCarree(),
        )

    cbar = plt.colorbar(chart, ax=ax, orientation="horizontal", pad=0.05, fraction=0.05)

    if label:
        cbar.set_label(label)
    else:
        cbar.set_label("Sample values")

    if title:
        plt.title(title)

    if outfile:
        plt.savefig(outfile, bbox_inches="tight", dpi=300)
        print(f"Plot saved to {outfile}")

    plt.show()
