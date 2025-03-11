# GEOSIF-ARSET

This repository is intended to contain code for the upcoming ARSET training session on using OCO-3 SIF data to reproduce the technique described in the [GEOSIF](https://doi.org/10.1016/j.rse.2024.114284) paper by Jeong et al.

## Prerequisites

### Clone this Repository to your Computer

Open a new terminal window and navigate to the directory you would like to work in for this training. Once you are in that directory, enter the following command to download the repository:

```bash
git clone https://github.com/jackiryan/GEOSIF-ARSET
cd GEOSIF-ARSET
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

If you would like to just open the notebook on subsequent uses, assuming your environment is set up, simply run the following command from the `GEOSIF-ARSET` directory:

```bash
jupyter lab notebooks/exploration.ipynb
```