# SIF-ARSET: Introduction to Solar-Induced Fluorescence (SIF) Data

This repository contains code for the upcoming ARSET training session on using solar-induced fluorescence (SIF) data from the OCO-2 and OCO-3 missions to study plant behavior and health at an ecosystem level. In this training we discuss:

1. **exploration.ipynb**: Methods for retrieving and spatially gridding SIF data to get a sense of the observational record. In this exercise we reproduce monthly gridded plots like those that are found in [Doughty et al.](https://doi.org/10.5194/essd-14-1513-2022) 
2. **gosif.ipynb**: One way to look at SIF with consistent spatial coverage, and the limitations of such a technique. In this exercise we retrieve and discuss data from the Drs. Xing Li and Jingfeng Xiao's 2019 [GOSIF paper](https://doi.org/10.3390/rs11050517).
3. **ann-sif.ipynb** (not yet implemented): Another way to look at SIF over a wide area, this time being able to look at diurnal variation at the expense of spatial resolution. In this exercise we will reproduce and discuss results from [Zhang et al.](https://doi.org/10.1016/j.rse.2022.113383)

## Prerequisites

### Clone this Repository to your Computer

Open a new terminal window and navigate to the directory you would like to work in for this training. Once you are in that directory, enter the following command to download the repository:

```bash
git clone https://github.com/jackiryan/SIF-ARSET
cd SIF-ARSET
```

Alternatively, you may wish to use [GitHub Desktop](https://desktop.github.com/download/) which does not require the command line. In the GitHub Desktop app, you would click the "Current Repository" dropdown, then select "Add", then "Clone Repository..." (Shift+Cmd+O on MacOS) and select this repo (you may need to have it starred for it to appear in the list of options). 

### Getting an Earthdata Token

Before diving into the Jupyter Notebook in the notebooks/ directory, you will need to get an Access token from the NASA Earthdata site. First, head to [Earthdata Login](https://urs.earthdata.nasa.gov/) and create an account if you do not have one already. If you are logged in, this link will redirect to your user profile page. Next, navigate to the tab called "Generate Token" (see screenshot below if you can't find it).

![Earthdata login page](images/EarthData_Login.png)

If you have already generated a token and it hasn't expired, it will be listed on this page. Press the green button to generate a new token if you need a new one, or copy your existing token. Next you will want to copy the .env.example file and save it as .env in this directory with your copied token credential. You can edit the new .env file yourself in a text editor or use the commands below:

**On MacOS/Linux**
```bash
echo "NASA_EARTHDATA_TOKEN=<paste your token here>" > .env
```

**On Windows**
```powershell
Set-Content .env "NASA_EARTHDATA_TOKEN=<paste your token here>"
```

### Installing the necessary packages

The provided setup script will install the required packages **and open the notebook in a new browser tab**:

**On MacOS/Linux**
```bash
./setup.sh
```

**On Windows**
```powershell
.\setup.ps1
```

If you would like to just open the notebook on subsequent uses, assuming your environment is set up, simply run the following command from the `SIF-ARSET` directory:

```bash
jupyter lab notebooks/exploration.ipynb
```