#!/usr/bin/env python3
import os
import glob
import subprocess
from datetime import datetime, timedelta
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.image import imread
import matplotlib.colors as colors
from matplotlib.colorbar import ColorbarBase
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from PIL import Image

# Function to convert day of year to month name
def get_month_name(year, doy):
    date = datetime(year, 1, 1) + timedelta(days=doy-1)
    return date.strftime("%B")

# Directories
input_dir = "."
output_dir = "combined"
temp_dir = "temp_frames"
os.makedirs(output_dir, exist_ok=True)
os.makedirs(temp_dir, exist_ok=True)

# Bounding box coordinates
bbox = {"left": -102, "bottom": 31, "right": -80.5, "top": 49}

# Get all unique days of year from 2018 files
doy_list = []
for file in glob.glob(f"{input_dir}/GOSIF_2018???.png"):
    doy = file[-7:-4]
    doy_list.append(doy)

doy_list.sort()
combined_files = []

# Process each day of year
for doy in doy_list:
    file_2018 = f"{input_dir}/GOSIF_2018{doy}.png"
    file_2019 = f"{input_dir}/GOSIF_2019{doy}.png"
    
    if os.path.exists(file_2018) and os.path.exists(file_2019):
        month_2018 = get_month_name(2018, int(doy))
        month_2019 = get_month_name(2019, int(doy))
        
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
        
        # First subplot - 2018
        img_2018 = imread(file_2018)
        extent = [bbox["left"], bbox["right"], bbox["bottom"], bbox["top"]]
        ax1.imshow(img_2018, extent=extent, origin='upper')
        ax1.add_feature(cfeature.STATES.with_scale('10m'), linewidth=0.5, edgecolor='black')
        ax1.add_feature(cfeature.BORDERS.with_scale('10m'), linewidth=1, edgecolor='black')
        ax1.set_title(f"{month_2018} 2018")
        
        # Second subplot - 2019
        img_2019 = imread(file_2019)
        ax2.imshow(img_2019, extent=extent, origin='upper')
        ax2.add_feature(cfeature.STATES.with_scale('10m'), linewidth=0.5, edgecolor='black')
        ax2.add_feature(cfeature.BORDERS.with_scale('10m'), linewidth=1, edgecolor='black')
        ax2.set_title(f"{month_2019} 2019")
        
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
        
        print(f"Created combined image for DOY {doy} ({month_2018}/{month_2019})")
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