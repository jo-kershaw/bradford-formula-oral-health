
# Analysis decisions

This records the main choices in the current analysis. The study population, exposure and outcome settings are defined in `analysis_settings.py`.

## Study definitions

- **Exposure:** qualifying specialist-formula prescriptions are identified using the project medication-name lookup. Prescribing occasions can be counted as distinct child–date combinations; the minimum number and age window are configurable.
- **Outcome:** dental general anaesthetic (GA) is assessed within configurable child-age windows. Child-level outcomes count each child once, separately from counts of GA records.
- **Analysis:** the study population, follow-up requirements and adjustment variables (including ethnicity, deprivation and birth year) are specified through the settings file. The 2+ prescribing-date definition has also been tested as a sensitivity analysis.

## Data and reporting

- **Two execution modes:** `run_analysis.py` uses the secure Bradford environment; `run_synthetic.py` generates fabricated examples for demonstrations and automated tests.
- **Separate outputs:** each run has a timestamped results folder. `analysis` figures follow the selected settings; `data_overview` figures describe the source extracts, including some explicitly fixed historical definitions.
- **Population comparisons:** the specialist-formula extract is part of the Bradford population, so ethnicity and IMD proportions use the population denominator without adding the formula group twice. The two groups are classified consistently.
- **External reference:** published OHID statistics and their citation are stored separately from Bradford analysis data.

## Repository

The repository contains reusable code, tests and approved reference material. Generated data and results remain outside version control. The repository is currently private; future ownership, licensing and wider release can be agreed separately.
