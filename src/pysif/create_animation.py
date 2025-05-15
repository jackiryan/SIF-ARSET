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
import glob
import subprocess
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.image import imread
import matplotlib.colors as colors
from matplotlib.colorbar import ColorbarBase
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# Function to convert day of year to month name
def get_month_name(year, doy):
    date = datetime(year, 1, 1) + timedelta(days=doy-1)
    return date.strftime("%B")

# Directories
input_dir = "./notebooks/data/gosif/animation/pngs"
output_dir = "./notebooks/data/gosif/animation/pngs/combined"
temp_dir = "./notebooks/data/gosif/animation/pngs/temp_frames"
os.makedirs(output_dir, exist_ok=True)
os.makedirs(temp_dir, exist_ok=True)

year_left = "2018"
year_right = "2019"

# Bounding box coordinates
bbox = {"left": -102, "bottom": 31, "right": -80.5, "top": 49}

# Get all unique days of year from left files
doy_list = []
for file in glob.glob(f"{input_dir}/GOSIF_{year_left}???.png"):
    doy = file[-7:-4]
    doy_list.append(doy)

doy_list.sort()
combined_files = []

# Process each day of year
for doy in doy_list:
    file_left = f"{input_dir}/GOSIF_{year_left}{doy}.png"
    file_right = f"{input_dir}/GOSIF_{year_right}{doy}.png"
    
    if os.path.exists(file_left) and os.path.exists(file_right):
        month_left = get_month_name(int(year_left), int(doy))
        month_right = get_month_name(int(year_right), int(doy))
        
        output_file = f"{output_dir}/combined_{doy}.png"
        combined_files.append(output_file)
        
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
        ax1.imshow(img_left, extent=extent, origin='upper')
        ax1.add_feature(cfeature.STATES.with_scale('10m'), linewidth=0.5, edgecolor='black')
        ax1.add_feature(cfeature.BORDERS.with_scale('10m'), linewidth=1, edgecolor='black')
        ax1.set_title(f"{month_left} {year_left}")
        
        # Second subplot - right (typically subsequent) year
        img_right = imread(file_right)
        ax2.imshow(img_right, extent=extent, origin='upper')
        ax2.add_feature(cfeature.STATES.with_scale('10m'), linewidth=0.5, edgecolor='black')
        ax2.add_feature(cfeature.BORDERS.with_scale('10m'), linewidth=1, edgecolor='black')
        ax2.set_title(f"{month_right} {year_right}")
        
        # Add horizontal colorbar
        norm = colors.Normalize(vmin=0.0, vmax=0.8)
        cmap = plt.cm.viridis
        
        # Create the colorbar
        cb = ColorbarBase(cax, cmap=cmap, norm=norm, orientation='horizontal')
        cb.set_label('SIF (W/m$^2$/sr/μm)')
        
        # Save the figure
        plt.tight_layout()
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"Created combined image for DOY {doy} ({month_left}/{month_right})")
    else:
        print(f"Skipping DOY {doy} - missing file(s)")

if combined_files:
    combined_files.sort()
    subprocess.run(["magick", "-delay", "30", "-loop", "0"] + combined_files + ["GOSIF_comparison.gif"])
    print(f"Created animated GIF: GOSIF_comparison.gif with {len(combined_files)} frames")
else:
    print("No matching file pairs found to create GIF")


# Create the GIF with optimization
'''
if combined_files:
    combined_files.sort()
    
    # First create a temporary optimized version of each frame
    optimized_files = []
    for i, file in enumerate(combined_files):
        temp_file = f"{temp_dir}/opt_{i:03d}.png"
        optimized_files.append(temp_file)
        
        # Convert to optimized PNG with reduced colors and size
        subprocess.run([
            "convert", 
            file, 
            "-resize", "800x", # Reduce resolution (adjust as needed)
            "-colors", "128",  # Reduce number of colors
            "-strip",          # Remove metadata
            "-quality", "85",  # Reduce quality slightly
            temp_file
        ])
    
    # Create the final optimized GIF
    subprocess.run([
        "convert", 
        "-delay", "30", 
        "-loop", "0",
        "-layers", "optimize",  # ImageMagick optimization
        "-fuzz", "2%",          # Allows for small color variations when optimizing
        "-dither", "None",      # Reduces file size by avoiding dithering
        *optimized_files, 
        "GOSIF_comparison.gif"
    ])
    
    # Get file size and report
    gif_size = os.path.getsize("GOSIF_comparison.gif") / (1024 * 1024)  # Size in MB
    print(f"Created optimized GIF: GOSIF_comparison.gif ({gif_size:.2f} MB) with {len(combined_files)} frames")
else:
    print("No matching file pairs found to create GIF")
'''

# Optional: Clean up temporary files
# import shutil
# shutil.rmtree(temp_dir)