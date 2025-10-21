#!/bin/bash
conda env create -f environment.yml
source activate sif-arset
python -m ipykernel install --user --name=sif-arset --display-name "Python (sif-arset)"
jupyter lab notebooks/1_exploration.ipynb