# PVSiteAPI
Site specific API for SBRI project


# pytest tests
```
export PYTHONPATH=${PYTHONPATH}:./src
pytest
```

# Setup and Run
```
pip install -r requirements.txt
cd src && uvicorn main:app --reload
```