"""Synthetic-only checks for figure captions from analysis_settings."""
from dataclasses import replace
from datetime import date
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from configuration import load_settings, Window
from plots import _cohort_caption, _primary_ga_caption


def test_caption_changes_with_birth_range_and_prescription_threshold():
    cfg = load_settings("analysis_settings")
    cfg = replace(cfg, birth_start=date(2015, 1, 1), birth_end=date(2016, 12, 31),
                  min_rx=2, rx_mode="distinct_dates", name="OLD TITLE NOT TO BE USED")
    label = _cohort_caption(cfg)
    assert "2015" in label and "2016" in label
    assert "2+ distinct prescription dates" in label
    assert "OLD TITLE" not in label


def test_calendar_prescribing_title_does_not_incorrectly_claim_minimum_threshold():
    cfg = replace(load_settings("analysis_settings"), min_rx=10)
    label = _cohort_caption(cfg, threshold=False)
    assert "any count" in label
    assert "10+" not in label


def test_primary_ga_caption_uses_actual_bounds_and_calendar_dates():
    cfg = load_settings("analysis_settings")
    cfg = replace(cfg, windows=[Window("stale name", 18, 96, "ga_18_96")],
                  primary_window="stale name", ga_calendar_end=date(2025, 12, 31))
    label = _primary_ga_caption(cfg)
    assert "18–under 96 months" in label
    assert "2025" in label
    assert "stale name" not in label
