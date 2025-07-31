#!/bin/bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m ipykernel install --user --name=venv --display-name "Python (venv)"
jupyter lab notebooks/1_exploration.ipynb