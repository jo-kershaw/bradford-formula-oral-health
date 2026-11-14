
# Getting started

Run these commands from the repository folder using a suitable Python environment.

## Synthetic demonstration and tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python run_synthetic.py
```

The synthetic run generates example tables and figures without connecting to Bradford.

## Bradford analysis

Within the Bradford secure environment, review the study definitions in `analysis_settings.py`, then run:

```bash
python run_analysis.py
```

Bradford's database connection configuration must be available in that environment. To use a different database schema, adapt the source-data queries in `sql_backend.py`.

## Finding results

Each run creates `results/secure/<timestamp>/` or `results/synthetic/<timestamp>/`. Figures are under `plots/`; tables are organised under `tables/` by analysis type, with separate `csv/` and `markdown/` folders. `RUN_INFO.txt` records the run settings.
