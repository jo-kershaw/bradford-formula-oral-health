# Specialist Formula Prescribing and Childhood Dental General Anaesthesia in Bradford

Python code for studying the association between prescribed low-allergy infant formula and dental general anaesthetic (GA) in childhood, using linked health records from Bradford.

## Running the analysis

Study definitions, including birth dates, prescription requirements and GA age windows, can be changed in `analysis_settings.py`.

Run the analysis within the Bradford secure environment:

```bash
python run_analysis.py
```

Generate example figures and tables using synthetic data:

```bash
python run_synthetic.py
```

## Outputs

Each run creates a timestamped folder in `results/secure/` or `results/synthetic/`.

Results include:

- **Data overview:** prescribing trends, dental GA records, ethnicity and deprivation.
- **Analysis:** cohort comparisons and adjusted statistical models.
- **External reference:** published OHID statistics for Bradford and England.

Tables are saved in CSV and Markdown formats, alongside the figures.

## Testing

Install the development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run the automated tests:

```bash
python -m pytest -q
```
