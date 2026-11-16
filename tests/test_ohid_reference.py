"""Tests for external OHID data and plot"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import matplotlib
matplotlib.use("Agg")
from plots_external_reference import read_ohid_reference, write_ohid_reference, FIGURE_NAME


def test_ohid_reference_is_an_index_with_expected_years():
    table = read_ohid_reference()
    assert table.financial_year_ending.tolist() == list(range(2019, 2026))
    assert table.loc[table.financial_year_ending == 2021, "bradford_index"].iloc[0] == 14.0
    assert table.loc[table.financial_year_ending == 2021, "england_index"].iloc[0] == 39.8
    assert table.loc[table.financial_year_ending == 2025, "bradford_index"].iloc[0] == 87.8
    assert table.loc[table.financial_year_ending == 2025, "england_index"].iloc[0] == 98.2
    for name in ["bradford_index", "england_index"]:
        assert table.loc[table.financial_year_ending.isin([2019, 2020]), name].mean() == 100


def test_ohid_outputs_are_external_not_secure_or_synthetic(tmp_path):
    plot = write_ohid_reference(tmp_path)
    assert plot.name == FIGURE_NAME
    assert plot.exists() and plot.stat().st_size > 1000
    folder = tmp_path / "tables" / "external_reference"
    csv = folder / "csv" / "ohid_bradford_england_all_index.csv"
    md = folder / "markdown" / "ohid_bradford_england_all_index.md"
    source = folder / "markdown" / "OHID_SOURCE.md"
    assert csv.exists() and md.exists() and source.exists()
    assert "EXTERNAL PUBLISHED REFERENCE" in md.read_text(encoding="utf-8")
    assert "2026" in source.read_text(encoding="utf-8")
    assert pd.read_csv(csv).shape == (7, 3)
    assert not plot.name.startswith(("SECURE_", "SYNTHETIC_"))


def test_ohid_figure_does_not_depend_on_study_settings(tmp_path):
    a = write_ohid_reference(tmp_path / "synthetic_run")
    b = write_ohid_reference(tmp_path / "secure_run")
    assert a.read_bytes() == b.read_bytes()
