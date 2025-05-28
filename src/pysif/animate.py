#!/usr/bin/env python3
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
import os
import io
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.image import imread
import matplotlib.colors as colors
from matplotlib.colorbar import ColorbarBase
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from PIL import Image
import imageio
from tqdm.notebook import tqdm

from . import convert_geotiff_to_png

def create_gosif_comparison_animation(
    year_left: int,
    year_right: int,
    gosif_files: list[str],
    output_dir: str,
    temp_dir: str = "data/temp",
    bbox: dict[str, float] = None,
    vmin: float = 0.0,
    vmax: float = 0.8,
    threshold: int = 32765,
    scale_factor: float = 0.0001,
    speed: float = 1.0
) -> None:
    """
    Create an animated GIF comparing GOSIF data between two years.

    Arguments:
        year_left (int): The first year to compare
        year_right (int): The second year to compare
        gosif_files (list[str]): List of GOSIF files to use in the animation
        output_dir (str): Directory to save the combined images
        temp_dir (str): Directory for temporary files (default: "temp")
        bbox (dict[str, float]): Bounding box coordinates with keys "left", 
            "right", "bottom", "top" (default: US corn belt region)
        vmin (float): Minimum value for colorbar (default: 0.0)
        vmax (float): Maximum value for colorbar (default: 0.8)
        speed (float): Animation speed in frames per second

    Returns:
        str: path to the output gif
    """
    # Set default bbox if not provided
    if bbox is None:
        bbox = {"left": -102, "bottom": 31, "right": -80.5, "top": 49}

    if scale_factor == 0.0:
        raise ValueError("scale factor cannot be 0")
    
    # Create output directories
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)
    
    # This loop converts all geotiffs to colormapped PNGs and gets extracts the
    # date information from the filenames. This is highly dependent on the file
    # naming convention since that information is not present in the TIFF metadata.
    # Annual:  GOSIF_20xx.tif
    # Monthly: GOSIF_20xx.Myy.tif
    # 8day:    GOSIF_20xxzzz.tif
    files_left: list[tuple[str, datetime]] = []
    files_right: list[tuple[str, datetime]] = []
    for file in tqdm(gosif_files, desc="Exporting geotiffs as PNG"):
        bname = os.path.basename(file)
        year = int(bname[6:10])
        
        # Handle case where out-of-range files may be present
        if str(year) not in [year_left, year_right]:
            continue

        bname_noext = os.path.splitext(bname)[0]
        gpng = os.path.join(temp_dir, bname_noext + ".png")
        convert_geotiff_to_png(
            file,
            gpng,
            vmin=vmin/scale_factor,
            vmax=vmax/scale_factor,
            bounds=bbox,
            threshold=threshold,
            scale_factor=scale_factor,
            verbose=False
        )

        if "M" in bname:
            month = int(bname[12:14])
            date = datetime(year, month, 1)
        elif len(bname) > 15:
            # i.e., the basename is longer than just an annual filename
            doy = int(bname[10:13])
            date = datetime(year, 1, 1) + timedelta(days=doy-1)
        else:
            date = datetime(year, 1, 1)
        
        if str(year) == year_left:
            files_left.append((gpng, date))
        else:
            files_right.append((gpng, date))

    files_left.sort(key=lambda x: x[1])
    files_right.sort(key=lambda x: x[1])
    assert len(files_left) == len(files_right), f"Found {len(files_left)} files from {year_left}, but {len(files_right)} from {year_right}"
    animation_frames = []
    
    # Process each time step
    n = 0
    for lt, rt in tqdm(zip(files_left, files_right), total=len(files_left), desc="Creating animation frames"):
        file_left = lt[0]
        date_left = lt[1]
        month_left = date_left.strftime("%B")
        file_right = rt[0]
        date_right = rt[1]
        month_right = date_right.strftime("%B")

        output_file = f"{output_dir}/frame_{date_left.strftime("%m%d")}.png"
            
        # Create a figure with two subplots and horizontal colorbar below
        fig = plt.figure(figsize=(10, 6))
        
        # Define grid for the subplots and colorbar
        gs = fig.add_gridspec(2, 2, height_ratios=[20, 1], width_ratios=[1, 1])
        
        # Create the map subplots
        ax1 = fig.add_subplot(gs[0, 0], projection=ccrs.PlateCarree())
        ax2 = fig.add_subplot(gs[0, 1], projection=ccrs.PlateCarree())
        
        # Create the colorbar axis spanning both columns
        cax = fig.add_subplot(gs[1, :])
        
        # First subplot - left (typically earlier) year
        img_left = imread(file_left)
        extent = [bbox["left"], bbox["right"], bbox["bottom"], bbox["top"]]
        ax1.imshow(img_left, extent=extent, origin="upper")
        ax1.add_feature(cfeature.STATES.with_scale("10m"), linewidth=0.5, edgecolor="black")
        ax1.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=1, edgecolor="black")
        ax1.set_title(f"{month_left} {year_left}")
        
        # Second subplot - right (typically subsequent) year
        img_right = imread(file_right)
        ax2.imshow(img_right, extent=extent, origin="upper")
        ax2.add_feature(cfeature.STATES.with_scale("10m"), linewidth=0.5, edgecolor="black")
        ax2.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=1, edgecolor="black")
        ax2.set_title(f"{month_right} {year_right}")
        
        # Add horizontal colorbar
        norm = colors.Normalize(vmin=vmin, vmax=vmax)
        cmap = plt.cm.viridis
        
        # Create the colorbar
        cb = ColorbarBase(cax, cmap=cmap, norm=norm, orientation="horizontal")
        cb.set_label("GOSIF (W/m$^2$/sr/μm)")
        
        # Save the figure
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0)
        pil_image = Image.open(buf)
        animation_frames.append(pil_image.copy())  # Make a copy since we'll close the buffer
        buf.close()

        plt.savefig(output_file, format="png", dpi=150, bbox_inches="tight")
        plt.close()
        
        n += 1
    
    # Create animated GIF if any combined files were created
    if animation_frames:
        gif_path = os.path.join(output_dir, f"GOSIF_comparison_{year_left}v{year_right}.gif")
        with imageio.get_writer(gif_path, mode="I", fps=speed, optimize=False, loop=0) as writer:
            for frame in animation_frames:
                frame_data = np.array(frame)
                writer.append_data(frame_data)
        print(f"Created animated GIF: {gif_path} with {len(animation_frames)} frames")
        return gif_path
    else:
        print("No matching file pairs found to create GIF")
        return ""
