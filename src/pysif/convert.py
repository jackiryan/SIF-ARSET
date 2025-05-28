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

import json
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import numpy as np
import os
import rasterio
from rasterio.plot import show
from rasterio.windows import from_bounds, Window
from rasterio.windows import bounds as window_bounds


def convert_geotiff_to_png(
    geotiff_path: str,
    output_png_path: str,
    vmin: int | None = None,
    vmax: int | None = None,
    bounds: dict[str, float] | None = None,
    scale_factor: float = 1,
    threshold: int | None = None,
    verbose: bool = True,
) -> bool:
    """
    This function is intended to convert geotiff to PNG for the purposes of this training, it should
    not be construed to be a general purpose conversion function. That purpose is better handled by
    something like: https://github.com/nasa/harmony-browse-image-generator
    This code specifically handles single-banded grayscale geotiffs and converts them to colormapped
    PNG files.

    Arguments:
        geotiff_path (str): Source geotiff file, usually a GOSIF granule.
        output_png_path (str): Desired output filename for the PNG image.
        vmin (int | None): Optionally specify a min value (unscaled) for the colormap.
        vmax (int | None): Optionally specify a max value (unscaled) for the colormap.
        bounds (dict | None): Optionally provide a bounding box as a dict of
            { "left": lon_min, "bottom": lat_min, "right": lon_max, "top": lat_max }
        scale_factor (float): Provide a scaling factor for the input data, this will
            be included in the metadata to tell the plotting widget how to convert the pixel
            values to units.
        threshold (int | None): Threshold value above which should be considered nodata. The
            nodata value in the geotiff will be used by default.
        verbose (bool): If True, print information about file output.

    Returns:
        A bool True or False on success or failure to convert the image.
    """
    png_dir = os.path.dirname(output_png_path)
    os.makedirs(png_dir, exist_ok=True)
    # Automatically determine the metadata name, since it should match the png
    fname_noext = os.path.splitext(output_png_path)[0]
    output_metadata_path = fname_noext + "_metadata.json"

    with rasterio.open(geotiff_path) as src:
        data = src.read(1)  # Read the first band
        src_width = src.width
        src_height = src.height
        src_crs = src.crs.to_string()
        src_bounds = src.bounds._asdict()

        if bounds:
            # Validate the bounds are within or equal to the source bounds
            if (
                bounds["left"] < src_bounds["left"]
                or bounds["bottom"] < src_bounds["bottom"]
                or bounds["right"] > src_bounds["right"]
                or bounds["top"] > src_bounds["top"]
            ):
                print(
                    f"Error: Requested bounds {bounds} are outside the source bounds {src_bounds}."
                )
                return False

            try:
                # Create a window from the geographic bounds
                window = from_bounds(
                    bounds["left"],
                    bounds["bottom"],
                    bounds["right"],
                    bounds["top"],
                    src.transform,
                )
                data = src.read(1, window=window)

                # Get the actual bounds of the window (might differ slightly due to pixel alignment)
                actual_bounds = window_bounds(window, src.transform)

                # Update width and height based on the window
                width = window.width
                height = window.height

                # Update bounds to the actual window bounds
                dst_bounds = {
                    "left": actual_bounds[0],
                    "bottom": actual_bounds[1],
                    "right": actual_bounds[2],
                    "top": actual_bounds[3],
                }

                # Read the default mask (derived from nodata value),
                # overwritten if using threshold
                mask = src.read_masks(1, window=window) == 0
            except Exception as e:
                print(f"Error processing bounds: {e}")
                return False
        else:
            width = src_width
            height = src_height
            dst_bounds = src_bounds
            # Read the default mask (derived from nodata value),
            # overwritten if using threshold
            mask = src.read_masks(1) == 0

    # The threshold is a value above which we consider value to be nodata.
    # In the case of GOSIF, this is BOTH 32766 (snow/ice) and 32767 (water)
    if threshold:
        mask = data > threshold

    valid_data = np.ma.masked_array(data, mask)

    range_min = vmin or np.nanmin(valid_data)
    range_max = vmax or np.nanmax(valid_data)
    norm_data = colors.Normalize(vmin=range_min, vmax=range_max)

    dpi = 360
    width_inches = width / dpi
    height_inches = height / dpi

    # Create a masked version where values > threshold will be transparent
    cmap = plt.cm.viridis.copy()
    cmap.set_bad(alpha=0)  # Set masked values to be transparent

    fig = plt.figure(figsize=(width_inches, height_inches), dpi=dpi)
    ax = plt.Axes(fig, (0, 0, 1, 1))  # No margins
    ax.set_axis_off()
    fig.add_axes(ax)
    ax.imshow(
        valid_data, cmap=cmap, norm=norm_data, interpolation="nearest", aspect="auto"
    )
    plt.savefig(
        output_png_path, dpi=dpi, bbox_inches="tight", pad_inches=0, transparent=True
    )
    plt.close(fig)

    # Get metadata for georeferencing and colormapping
    metadata = {
        "bounds": dst_bounds,
        "width": width,
        "height": height,
        "crs": src_crs,
        "dataRange": {
            "min": round(scale_factor * range_min, ndigits=5),
            "max": round(scale_factor * range_max, ndigits=5),
        },
    }

    # Save the metadata as JSON
    with open(output_metadata_path, "w") as f:
        json.dump(metadata, f)

    if verbose:
        print(
            f"Converted {geotiff_path} to {output_png_path} with metadata at {output_metadata_path}"
        )
    return True
