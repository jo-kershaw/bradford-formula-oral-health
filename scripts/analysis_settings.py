"""EDIT THIS FILE to choose the children, prescriptions and GA outcomes.

The analysis runs without editing any SQL or statistical calculations.
All ages are in MONTHS, with the start included and end excluded:
  0 to 12 months = from birth until the first birthday (not including age 1).
  18 to 84 months = from age 18 months until the seventh birthday.
"""

# 1. Birth dates (both endpoints INCLUDED).
name = "Age 18 months to under 7: July 2014–December 2017 births"
birth_start = "2014-07-01"
birth_end = "2017-12-31"

# 2. Formula exposure: child must have enough qualifying medication records
# during this AGE range (in months, upper endpoint excluded).
exposure_age_start_months = 0
exposure_age_end_months = 12
min_prescriptions = 1              # Change to 2, 5, 10, etc.
prescription_count_mode = "distinct_dates"  # or "records"

# Optional medicine-name exclusions from the existing Bradford lookup.
# These exclude any name containing the given text (case-insensitive).
# Leave as [] to use all names in the supplied lookup, as in the original.
exclude_medication_name_contains = []

# 3. Dental GA age windows: (label, starting age in months, ending age in months).
# Each child is counted once per window, even if they have several procedures.
# A child may appear in different windows if they had GAs at different ages.
ga_windows = [
    ("18–under 40 months", 18, 40),
    ("40–under 62 months", 40, 62),
    ("62–under 84 months", 62, 84),
    ("18–under 84 months (overall)", 18, 84),
]

# Choose which GA window the adjusted model uses; must match a label above.
primary_ga_window = "18–under 84 months (overall)"

# 4. Calendar years of GA records to count (both dates INCLUDED).
# Narrowing this range counts GAs in those years ONLY, even if the age window
# extends beyond them; it is not the child's lifetime risk of GA.
ga_calendar_start = "2016-01-01"
ga_calendar_end = "2024-12-31"

# 5. Adjustment variables in the binomial logistic regression.
# Remove any names that you do not want in the model.
adjust_for = ["ethnicity", "deprivation", "birth_year"]

# 6. Data coverage checks. These describe the years in the source tables.
# Do not extend these unless the source data exists.
prescription_source_start = "2010-01-01"
prescription_source_end = "2023-12-31"
ga_source_start = "2016-01-01"
ga_source_end = "2024-12-31"

# Stop if children in the chosen birth cohort cannot all reach the selected
# GA ages in the available data. Recommended: True.
require_complete_coverage = True

# 7. Reproducibility. Output folders are created automatically for every run.
ci_draws = 2500                     # Simulation draws for model confidence intervals
random_seed = 20261112             # Reproducible synthetic demo / CI simulation
