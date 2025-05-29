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
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import numpy as np
import numpy.typing as npt


def plot_samples(
    samples: npt.NDArray[np.float32],
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

    _, ax = plt.subplots(
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

'''
def plot_two_years_comparison(
        doy_list: list[int],
        values_a: list[float],
        year_a: str | int, 
        values_b: list[float],
        year_b: str | int,
        ylabel="GOSIF",
        title=None):
    """
    Plot two time series from different years for comparison.
    
    Arguments:
        doy_list (list[int]): Day of year within the respective year
        values_a, values_b (list[float]):  Value arrays for each year
        year_a, year_b (str | int): Year labels for the legend
        ylabel (str):  Y-axis label
        title (str): Plot title (auto-generated if None)
    
    Returns:
        None
    """
    # Create the plot
    plt.figure(figsize=(12, 6))
    
    # Plot both time series
    plt.plot(doy_list, values_a, "b-", linewidth=2,
             label=str(year_a), alpha=0.8)
    plt.plot(doy_list, values_b, "r-", linewidth=2,
             label=str(year_b), alpha=0.8)
    
    # Set title if not provided
    if title is None:
        title = f"{ylabel} Comparison: {year_a} vs {year_b}"
    
    # Format the plot
    plt.title(title, fontsize=14, fontweight="bold")
    plt.ylabel(ylabel, fontsize=12)
    plt.xlabel("Day of Year", fontsize=12)
    
    # Format x-axis dates
    plt.xticks(rotation=45)
    
    # Add legend
    plt.legend(fontsize=11, loc="best")
    
    # Adjust layout
    plt.tight_layout()
    plt.show()
'''

def plot_two_years_comparison(
        doy_list: list[int],
        values_a: list[float],
        year_a: str | int, 
        values_b: list[float],
        year_b: str | int,
        ylabel: str = "GOSIF",
        title: str | None = None,
        highlight_start_idx: int | None = None,
        highlight_end_idx: int | None = None,
        marker_size: int = 8,
        label_offset: float = 0.02):
    """
    Plot two time series from different years for comparison with optional highlighting
    of divergent periods using markers and data labels.
    
    Arguments:
        doy_list (list[int]): Day of year within the respective year
        values_a, values_b (list[float]): Value arrays for each year
        year_a, year_b (str | int): Year labels for the legend
        ylabel (str): Y-axis label
        title (str): Plot title (auto-generated if None)
        highlight_start_idx (int): Start index for highlighting divergent period
        highlight_end_idx (int): End index for highlighting divergent period
        marker_size (int): Size of the markers in highlighted region
        label_offset (float): Vertical offset for data labels as fraction of y-range
    
    Returns:
        None
    """
    # Create the plot
    plt.figure(figsize=(12, 6))
    
    # Define colors for consistency
    color_a = 'blue'
    color_b = 'red'
    
    # Plot both time series
    line_a = plt.plot(doy_list, values_a, color=color_a, linewidth=2,
                      label=str(year_a), alpha=0.8)[0]
    line_b = plt.plot(doy_list, values_b, color=color_b, linewidth=2,
                      label=str(year_b), alpha=0.8)[0]
    
    # Add markers and labels for highlighted region if specified
    if highlight_start_idx is not None and highlight_end_idx is not None:
        start_idx = max(0, highlight_start_idx)
        end_idx = min(len(doy_list), highlight_end_idx + 1)
        
        if start_idx < end_idx:
            highlight_doy = doy_list[start_idx:end_idx]
            highlight_values_a = values_a[start_idx:end_idx]
            highlight_values_b = values_b[start_idx:end_idx]
            
            plt.plot(highlight_doy, highlight_values_a, 'o', 
                    color=color_a, markersize=marker_size, alpha=0.9)
            plt.plot(highlight_doy, highlight_values_b, 'o', 
                    color=color_b, markersize=marker_size, alpha=0.9)
            
            # Calculate label offset based on data range
            y_range = max(max(values_a), max(values_b)) - min(min(values_a), min(values_b))
            offset = y_range * label_offset

            x_range = max(doy_list) - min(doy_list)
            x_offset = x_range * 0.01  # 1% of x-range for horizontal shift
            
            # Add data labels for the highlighted region
            for i, (doy, val_a, val_b) in enumerate(zip(highlight_doy, highlight_values_a, highlight_values_b)):
                # Label for year A (positioned above the point)
                plt.text(doy - x_offset, val_a + offset, f'{val_a:.2f}', 
                        color=color_a, fontsize=9, ha='center', va='bottom')
                
                # Label for year B (positioned below the point)
                plt.text(doy + x_offset, val_b - offset, f'{val_b:.2f}', 
                        color=color_b, fontsize=9, ha='center', va='top')

            y_min, y_max = plt.ylim()
            y_range = y_max - y_min
            
            # Calculate additional space needed for labels
            label_space = y_range * label_offset * 2  # Double the offset for buffer
            
            # Expand y-axis limits
            plt.ylim(y_min - label_space, y_max + label_space)
    
    
    # Set title if not provided
    if title is None:
        title = f"{ylabel} Comparison: {year_a} vs {year_b}"

    def doy_to_month_label(doy):
        """Convert day of year to month name."""
        # Use a reference year (e.g., 2020 which is a leap year to handle DOY 366)
        date = datetime(2020, 1, 1) + timedelta(days=doy - 1)
        return date.strftime('%b')
    
    # Create month labels and positions for major ticks
    unique_months = []
    month_positions = []
    seen_months = set()
    
    for i, doy in enumerate(doy_list):
        month_label = doy_to_month_label(doy)
        if month_label not in seen_months:
            unique_months.append(month_label)
            month_positions.append(doy)
            seen_months.add(month_label)
    
    # Set x-axis ticks and labels
    plt.xticks(month_positions, unique_months, rotation=0)  # rotation=0 for horizontal
    
    # Add minor ticks for better granularity (optional)
    plt.gca().set_xticks(doy_list, minor=True)
    
    # Format the plot
    plt.title(title, fontsize=14, fontweight="bold")
    plt.ylabel(ylabel, fontsize=12)
    
    # Add legend
    plt.legend(fontsize=11, loc="best")
    
    # Add grid for better readability
    #plt.grid(True, alpha=0.3)
    
    # Adjust layout
    plt.tight_layout()
    plt.show()
