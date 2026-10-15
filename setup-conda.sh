#!/bin/bash
set -e

ENV_NAME=sif-arset

if ! command -v conda >/dev/null 2>&1; then
    echo "Error: conda was not found on your PATH." >&2
    echo "Install Miniconda (https://www.anaconda.com/docs/getting-started/miniconda/install)," >&2
    echo "open a new terminal window, and run this script again." >&2
    exit 1
fi

# Create the environment, or update it if an earlier run already created it.
if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    echo "Environment '$ENV_NAME' already exists; updating it from environment.yml."
    conda env update -n "$ENV_NAME" -f environment.yml
else
    conda env create -f environment.yml
fi

# Run commands inside the environment with `conda run` instead of activating it.
# `conda activate` / `source activate` are unreliable inside scripts, and if
# activation fails the kernel gets installed into the wrong Python.
conda run -n "$ENV_NAME" python -m ipykernel install --user --name="$ENV_NAME" --display-name "Python ($ENV_NAME)"
conda run -n "$ENV_NAME" --no-capture-output jupyter lab notebooks/1_exploration.ipynb