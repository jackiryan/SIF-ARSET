# SIF-ARSET: Introduction to Solar-Induced Fluorescence (SIF) Data

This repository contains code for the upcoming ARSET training session on using solar-induced fluorescence (SIF) data from the OCO-2 and OCO-3 missions to study plant behavior and health at an ecosystem level. In this training we discuss:

1. **exploration.ipynb**: Methods for retrieving and spatially gridding SIF data to get a sense of the observational record. In this exercise we reproduce monthly gridded plots like those that are found in [Doughty et al., 2022](https://doi.org/10.5194/essd-14-1513-2022) 
2. **gosif.ipynb**: One way to look at SIF with consistent spatial coverage, and the limitations of such a technique. In this exercise we retrieve and discuss data from the Drs. Xing Li and Jingfeng Xiao's 2019 [GOSIF paper](https://doi.org/10.3390/rs11050517).
3. **oco3_sam.ipynb**: A discussion of the Snapshot Area Map (SAM) mode unique to OCO-3, its applications, and a comparison of this data with flux tower data collected from ground-based measurements. The analysis in this notebook is similar to the one found in [Pierrat et al., 2022](https://doi.org/10.1029/2021JG006588), which looked at tower-based SIF and GPP measurements of boreal forest.

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

## Citations

[1] Basilio, R., Bennett, M., Eldering, A., Lawson, P., and Rosenberg, R. (2019). Orbiting Carbon Observatory-3 (OCO-3), remote sensing from the International Space Station (ISS). Proceedings Volume 11151, Sensors, Systems, and Next-Generation Satellites XXIII, 11151. https://doi.org/10.1117/12.2534996

[2] Doughty, R., Kurosu, T. P., Parazoo, N., Köhler, P., Wang, Y., Sun, Y., and Frankenberg, C. (2022). Global GOSAT, OCO-2, and OCO-3 solar-induced chlorophyll fluorescence datasets. Earth Syst. Sci. Data, 14, 1513–1529. https://doi.org/10.5194/essd-14-1513-2022

[3] OCO Science Team/Michael Gunson, Annmarie Eldering (2024). OCO-3 level 2 bias-corrected solar-induced fluorescence and other select fields from the IMAP-DOAS algorithm aggregated as daily files, retrospective processing V11r. Greenbelt, MD, USA, Goddard Earth Sciences Data and Information Services Center (GES DISC). Accessed: 4 Jun 2025. https://doi.org/10.5067/HC776J71KV41

[4] OCO-2/OCO-3 Science Team, Vivienne Payne, Abhishek Chatterjee (2024). OCO-2 level 2 bias-corrected XCO2 and other select fields from the full-physics retrieval aggregated as daily files, retrospective processing V11.2r. Greenbelt, MD, USA, Goddard Earth Sciences Data and Information Services Center (GES DISC). Accessed: 4 Jun 2025. https://doi.org/10.5067/70K2B2W8MNGY

[5] Li, X. and Xiao, J. (2019). A global, 0.05-degree product of solar-induced chlorophyll fluorescence derived from OCO-2, MODIS, and reanalysis data. Remote Sensing, 11, 517. https://doi.org/10.3390/rs11050517

[6] Yin, Y., Byrne, B., Liu, J., Wennberg, P., Davis, K. J., Magney, T., et al. (2020). Cropland carbon uptake delayed and reduced by 2019 midwest floods. AGU Advances, 1, e2019AV000140. https://doi.org/10.1029/2019AV000140

[7] Pierrat, Z., Magney, T., Parazoo, N. C., Grossmann, K., Bowling, D. R., Seibt, U., et al. (2022). Diurnal and seasonal dynamics of solar-induced chlorophyll fluorescence, vegetation indices, and gross primary productivity in the boreal forest. Journal of Geophysical Research: Biogeosciences, 127, e2021JG006588. https://doi.org/10.1029/2021JG006588

[8] Law, B. (2025). AmeriFlux BASE US-Me2 metolius mature ponderosa pine, Ver. 21-5. AmeriFlux AMP. Accessed: 4 Jun 2025. https://doi.org/10.17190/AMF/1246076

## Data Sources and Attributions

**GOSIF Dataset:** Used with permission from the author (permission pending).

**MapTiler Base Layer:** Used under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/) with contributions from OpenStreetMap contributors.

**Esri Global Imagery:** Base layer tiles used under the [Esri Master License Agreement](https://www.esri.com/content/dam/esrisites/en-us/media/legal/ma-full/ma-full.pdf). All map tiles are ©Esri.

**AmeriFlux BASE Dataset:** Used under [CC-BY-4.0 License](https://ameriflux.lbl.gov/sites/siteinfo/US-Me2#data-citation).