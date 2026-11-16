# Specialist Formula Prescribing and Childhood Dental General Anaesthesia in Bradford

Python code for studying the association between prescribed low-allergy infant formula and dental general anaesthetic (GA) in childhood, using linked health records from Bradford.

## Running the analysis

Study definitions, including birth dates, prescription requirements and GA age windows, can be changed in `scripts/analysis_settings.py`.

Run the analysis within the Bradford secure environment:

```bash
python scripts/run_analysis.py
```

Generate example figures and tables using synthetic data:

```bash
python scripts/run_synthetic.py
```

## Outputs

Each run creates a timestamped folder in `results/secure/` or `results/synthetic/`.

Results include:

- **Data overview:** prescribing trends, dental GA records, ethnicity and deprivation.
- **Analysis:** cohort comparisons and adjusted statistical models.
- **External reference:** published OHID statistics for Bradford and England.

Tables are saved in CSV and Markdown formats, alongside the figures.

### Dependencies

The project has three requirements files:

- `requirements.txt` — core Python packages used by the analysis.
- `requirements-dev.txt` — core packages plus pytest, for running the synthetic demonstration and tests.
- `requirements-secure.txt` — core packages plus `python-dotenv` and `pyodbc`, for connecting to the Bradford SQL database.

For work within the approved Bradford secure environment, install the secure dependencies using:

`python -m pip install -r requirements-secure.txt`

A compatible SQL Server ODBC driver and authorised database connection configuration are also required. These are managed separately from the Python requirements.

The synthetic demonstration does not require database access and can be run using `requirements-dev.txt`.

**Data security:** Database credentials, connection configuration containing secrets, and individual-level health records must not be committed to this repository.

## Testing

Install the development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run the automated tests:

```bash
python -m pytest -q
```
