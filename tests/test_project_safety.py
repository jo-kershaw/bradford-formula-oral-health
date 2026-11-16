"""Synthetic-only regression checks.
These tests don't use fixed settings values, so users can change
analysis_settings.py and still use the tests.
"""

from dataclasses import replace
from datetime import date
from pathlib import Path
import sys

import pandas as pd
import pytest

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from configuration import add_months, load_settings
from synthetic_backend import aggregate_synthetic, load_aggregates
from analysis_stats import two_by_two, validate_aggregates


def test_settings_load_and_have_valid_primary_window():
    cfg = load_settings("analysis_settings")
    assert cfg.min_rx >= 1
    assert cfg.primary in cfg.windows
    assert cfg.birth_start <= cfg.birth_end


def test_calendar_month_arithmetic():
    assert add_months(date(2020, 2, 29), 12) == date(2021, 2, 28)
    assert add_months(date(2016, 12, 31), 96) == date(2024, 12, 31)


def test_invalid_birth_dates_rejected():
    cfg = load_settings("analysis_settings")
    impossible = replace(cfg, birth_start=date(2030, 1, 1), birth_end=date(2020, 1, 1))
    with pytest.raises(ValueError, match="birth_start"):
        impossible.validate()


def test_distinct_prescribing_dates_not_duplicate_rows():
    cfg = load_settings("analysis_settings")
    # Synthetic example births/ages are chosen to match the user-editable
    # exposure window and one outcome window.
    dob = date(cfg.birth_start.year, cfg.birth_start.month, min(cfg.birth_start.day, 28))
    person = pd.DataFrame({
        "person_id": [1, 2],
        "dob": [dob, dob],
        "birth_year": [dob.year, dob.year],
        "ethnicity": ["White British", "Pakistani"],
        "deprivation": ["1-3 More deprived", "4-6 Middle"],
    })
    first_date = add_months(dob, cfg.exposure_age_start)
    second_date = add_months(first_date, 1)
    # If the exposure window is too narrow for two distinct dates, the test
    # uses two adjacent days rather than assuming a one-month window.
    if second_date >= add_months(dob, cfg.exposure_age_end):
        from datetime import timedelta
        second_date = first_date + timedelta(days=1)
    if second_date >= add_months(dob, cfg.exposure_age_end):
        pytest.skip("Exposure window does not contain two prescribing dates")
    rx = pd.DataFrame({
        "person_id": [1, 1, 1, 2, 2],
        "rx_date": [first_date, first_date, second_date, first_date, first_date],
        "medication_name": ["FORMULA"] * 5,
    })
    ga = pd.DataFrame({"person_id": [1], "ga_date": [add_months(dob, cfg.primary.start_months)]})
    two_dates = replace(cfg, min_rx=2, rx_mode="distinct_dates")
    one_date = replace(cfg, min_rx=1, rx_mode="distinct_dates")
    by_two = aggregate_synthetic(person, rx, ga, two_dates)["cohort"]
    by_one = aggregate_synthetic(person, rx, ga, one_date)["cohort"]
    assert int(by_two.loc[by_two.formula == 1, "n_children"].sum()) == 1
    assert int(by_one.loc[by_one.formula == 1, "n_children"].sum()) == 2


def test_synthetic_counts_are_internally_consistent():
    cfg = load_settings("analysis_settings")
    data = load_aggregates(cfg, n=350)
    cohort = validate_aggregates(data["cohort"], cfg)
    assert int(cohort.n_children.sum()) == 350
    summary = two_by_two(cohort, cfg)
    assert (summary.ga_yes + summary.ga_no == summary.n_children).all()
    for window in cfg.windows:
        section = summary[summary.ga_window == window.name]
        assert int(section.n_children.sum()) == 350


def test_csv_and_markdown_pair_do_not_mix_sources(tmp_path):
    from analysis_runner import write_table_pair
    sample = pd.DataFrame({"group": ["A|B"], "n_children": [3]})
    for mode, prefix in [("synthetic", "SYNTHETIC"), ("secure", "SECURE")]:
        write_table_pair(sample, "test_output", tmp_path, mode)
        csv = tmp_path / "csv" / f"{prefix}_test_output.csv"
        md = tmp_path / "markdown" / f"{prefix}_test_output.md"
        assert csv.exists() and md.exists()
        assert "A\\|B" in md.read_text(encoding="utf-8")
        assert ("SYNTHETIC DATA" in md.read_text(encoding="utf-8")) == (mode == "synthetic")


def test_separate_timestamped_output_directories(tmp_path, monkeypatch):
    import analysis_runner
    monkeypatch.setattr(analysis_runner, "RESULTS_ROOT", tmp_path)
    a = analysis_runner.create_run_folders("synthetic")
    b = analysis_runner.create_run_folders("synthetic")
    c = analysis_runner.create_run_folders("secure")
    assert len({a, b, c}) == 3
    assert a.parent == b.parent == tmp_path / "synthetic"
    assert c.parent == tmp_path / "secure"
    assert (a / "RUN_INCOMPLETE.txt").exists()
