# Create conda environment from environment.yml
conda env create -f environment.yml

# Activate the environment  
conda activate sif-arset

# Install the kernel for Jupyter
python -m ipykernel install --user --name=sif-arset --display-name "Python (sif-arset)"

# Launch Jupyter Lab with the first notebook
jupyter lab notebooks\1_exploration.ipynb
