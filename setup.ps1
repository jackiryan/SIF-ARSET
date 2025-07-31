# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# For PowerShell, use venv\Scripts\Activate
# For cmd, use venv\Scripts\activate.bat
venv\Scripts\Activate

# Install dependencies
pip install -r requirements.txt

python -m ipykernel install --user --name=venv --display-name "Python (venv)"

# Launch Jupyter Lab with the specified notebook
jupyter lab notebooks\1_exploration.ipynb
