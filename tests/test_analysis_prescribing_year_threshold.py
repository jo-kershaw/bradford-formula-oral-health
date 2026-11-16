"""Tests for annual ANALYSIS prescribing plot (artificial data only)."""
from dataclasses import replace
from datetime import date
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from configuration import load_settings
from sql_backend import build_queries
from synthetic_backend import aggregate_synthetic
from plots import _cohort_caption


def example():
    dob = date(2015, 1, 1)
    people = pd.DataFrame({
        "person_id": [1, 2, 3], "dob": [dob] * 3,
        "birth_year": [2015] * 3,
        "ethnicity": ["Pakistani"] * 3,
        "deprivation": ["1-3 More deprived"] * 3,
    })
    rx = pd.DataFrame({
        "person_id": [1, 1, 1, 2],
        "rx_date": [date(2015, 2, 1), date(2015, 2, 1),
                    date(2015, 3, 1), date(2015, 2, 1)],
        "medication_name": ["FORMULA"] * 4,
    })
    ga = pd.DataFrame({"person_id": [3], "ga_date": [date(2018, 1, 1)]})
    return people, rx, ga


def test_sql_counts_only_exposed_child_dates():
    cfg = load_settings("analysis_settings")
    query = build_queries(cfg)[0]["prescriptions_by_year"]
    assert "JOIN formula_ids f ON f.person_id = daily.person_id" in query
    assert "SELECT DISTINCT person_id, rx_date FROM rx_events" in query
    assert ":min_rx" in query  # The common CTE selects who qualifies.


def test_synthetic_yearly_counts_change_with_minimum_prescription_dates():
    people, rx, ga = example()
    base = replace(load_settings("analysis_settings"), min_rx=1, rx_mode="distinct_dates")
    one = aggregate_synthetic(people, rx, ga, base)["prescriptions_by_year"]
    two = aggregate_synthetic(people, rx, ga, replace(base, min_rx=2))["prescriptions_by_year"]
    assert one["n_prescribing_dates"].sum() == 3  # 2 dates for child 1, 1 for child 2
    assert one["n_children"].sum() == 2
    assert two["n_prescribing_dates"].sum() == 2  # Only child 1 is exposed
    assert two["n_children"].sum() == 1


def test_exposure_threshold_counts_records_but_chart_counts_distinct_dates():
    people, rx, ga = example()
    cfg = replace(load_settings("analysis_settings"), min_rx=3, rx_mode="records")
    data = aggregate_synthetic(people, rx, ga, cfg)
    assert data["cohort"].loc[data["cohort"].formula == 1, "n_children"].sum() == 1
    assert data["prescriptions_by_year"]["n_prescribing_dates"].sum() == 2


def test_chart_caption_reflects_threshold():
    cfg = replace(load_settings("analysis_settings"), min_rx=2, rx_mode="distinct_dates")
    caption = _cohort_caption(cfg)
    assert "2+ distinct prescription dates" in caption
