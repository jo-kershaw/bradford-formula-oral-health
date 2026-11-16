"""Smoke test: adjusted model completes on entirely artificial grouped counts."""
from types import SimpleNamespace

import pandas as pd

from analysis_stats import fit_adjusted


def test_adjusted_model_produces_predictions_and_intervals():
    # A small balanced, fabricated grouped dataset, independent of Bradford.
    rows = []
    for birth_year in (2015, 2016):
        for ethnicity in ("White British", "Pakistani"):
            for deprivation in ("More deprived", "Less deprived"):
                for formula in (0, 1):
                    cases = 3 + formula + (ethnicity == "Pakistani") + (birth_year == 2016)
                    rows.append({
                        "birth_year": birth_year,
                        "ethnicity": ethnicity,
                        "deprivation": deprivation,
                        "formula": formula,
                        "n_children": 100,
                        "ga_18_84": cases,
                    })
    cfg = SimpleNamespace(
        primary=SimpleNamespace(key="ga_18_84"),
        adjust_for=["ethnicity", "deprivation", "birth_year"],
        seed=123,
        ci_draws=150,
    )
    result, reason = fit_adjusted(pd.DataFrame(rows), cfg)
    assert reason is None, reason
    assert result is not None
    assert result["converged"] is True
    assert result["children"] == 1600
    assert 0 < result["formula_pct"] < 100
    assert 0 < result["other_pct"] < 100
    assert len(result["difference_pp_ci"]) == 2
