"""Artificial event-level records for testing PUBLIC code without private data.

All numbers, probabilities, names and distributions are arbitrary; i.e., not
calibrated to or derived from Bradford patient records.
"""
from collections import Counter
from datetime import timedelta

import numpy as np
import pandas as pd

from configuration import add_months


def make_synthetic_people(n=3200, seed=101, start_date=None, end_date=None):
    rng = np.random.default_rng(seed)
    start = pd.Timestamp(start_date or "2012-01-01")
    end = pd.Timestamp(end_date or "2020-12-31") + pd.Timedelta(days=1)
    days = int((end - start).days)
    if days < 1:
        raise ValueError("Synthetic DOB interval is empty")
    dates = [start.date() + timedelta(days=int(x)) for x in rng.integers(0, days, n)]
    ethn = rng.choice(["White British", "Pakistani", "Other ethnicities", "Unknown"],
                      size=n, p=[.45, .30, .19, .06])
    depr = rng.choice(["1-3 More deprived", "4-6 Middle", "7-10 Less deprived"],
                      size=n, p=[.55, .30, .15])
    return pd.DataFrame({"person_id": range(1, n+1), "dob": dates,
                         "birth_year": [d.year for d in dates], "ethnicity": ethn,
                         "deprivation": depr})


def make_synthetic_events(people, seed=102):
    rng = np.random.default_rng(seed)
    rx, ga = [], []
    for row in people.itertuples(index=False):
        # Deliberately arbitrary, with a mixture of no, one and repeat prescriptions.
        p = 0.18 + (0.08 if row.deprivation == "7-10 Less deprived" else 0)
        if rng.random() < p:
            n = int(rng.choice([1, 2, 4, 8], p=[.35, .30, .23, .12]))
            for j in range(n):
                d = add_months(row.dob, int(rng.integers(1, 11))) + timedelta(days=int(rng.integers(0, 8)))
                rx.append((row.person_id, d, "SYNTHETIC EXAMPLE FORMULA"))
                if j == 0 and rng.random() < .25:
                    rx.append((row.person_id, d, "SYNTHETIC EXAMPLE FORMULA"))
        # An entirely artificial illustration, not a research estimate.
        prob_ga = .045 if row.deprivation == "1-3 More deprived" else .022
        if rng.random() < prob_ga:
            month = int(rng.integers(18, 102))
            d = add_months(row.dob, month) + timedelta(days=int(rng.integers(0, 5)))
            ga.append((row.person_id, d))
            if rng.random() < .05:
                ga.append((row.person_id, add_months(row.dob, min(105, month+10))))
    return (pd.DataFrame(rx, columns=["person_id", "rx_date", "medication_name"]),
            pd.DataFrame(ga, columns=["person_id", "ga_date"]))


def aggregate_synthetic(people, rx, ga, cfg):
    """Independent person-level Python reference for cross-checking SQL outcomes.
    """
    eligible = people.loc[(people.dob >= cfg.birth_start) & (people.dob <= cfg.birth_end)].copy()
    cohort_ids = set(eligible.person_id)
    rx = rx.loc[rx.person_id.isin(cohort_ids)].copy()
    ga = ga.loc[ga.person_id.isin(cohort_ids)].copy()
    birth = dict(zip(eligible.person_id, eligible.dob))
    if cfg.excluded_terms and len(rx):
        bad = rx.medication_name.str.upper().apply(
            lambda x: any(t.upper() in x for t in cfg.excluded_terms))
        rx = rx.loc[~bad]
    if len(rx):
        rx = rx.loc[rx.apply(lambda x:
            add_months(birth[x.person_id], cfg.exposure_age_start) <= x.rx_date <
            add_months(birth[x.person_id], cfg.exposure_age_end), axis=1)]
    n_rx = (rx.groupby("person_id").rx_date.nunique() if cfg.rx_mode == "distinct_dates"
            else rx.groupby("person_id").size())
    eligible["formula"] = eligible.person_id.map(n_rx).fillna(0).ge(cfg.min_rx).astype(int)
    ga = ga.loc[(ga.ga_date >= cfg.ga_calendar_start) & (ga.ga_date <= cfg.ga_calendar_end)].copy()
    for w in cfg.windows:
        per_person = ga.loc[ga.apply(lambda x:
            add_months(birth[x.person_id], w.start_months) <= x.ga_date <
            add_months(birth[x.person_id], w.end_months), axis=1)].person_id.unique()
        eligible[w.key] = eligible.person_id.isin(per_person).astype(int)
    by = ["birth_year", "ethnicity", "deprivation", "formula"]
    result = (eligible.groupby(by, dropna=False, as_index=False)
              .agg(n_children=("person_id", "count"),
                   **{w.key: (w.key, "sum") for w in cfg.windows}))
    daily = rx.drop_duplicates(["person_id", "rx_date"]).copy()
    # Mirror the SQL: report prescribing dates only for exposed children.
    # A child qualifies across their entire selected exposure age window,
    # not separately for each calendar year.
    exposed_ids = set(eligible.loc[eligible["formula"] == 1, "person_id"])
    daily = daily.loc[daily["person_id"].isin(exposed_ids)].copy()
    if len(daily):
        daily["prescription_year"] = daily.rx_date.apply(lambda d: d.year)
        prescribing = (daily.groupby("prescription_year", as_index=False)
                       .agg(n_prescribing_dates=("rx_date", "size"),
                            n_children=("person_id", "nunique")))
    else:
        prescribing = pd.DataFrame(columns=["prescription_year", "n_prescribing_dates", "n_children"])
    w = cfg.primary
    if len(ga):
        primary = ga.loc[ga.apply(lambda x:
            add_months(birth[x.person_id], w.start_months) <= x.ga_date <
            add_months(birth[x.person_id], w.end_months), axis=1)].copy()
        primary["ga_year"] = primary.ga_date.apply(lambda d: d.year)
        primary = primary.merge(eligible[["person_id", "formula"]], on="person_id", validate="many_to_one")
        ga_year = (primary.groupby(["ga_year", "formula"], as_index=False)
                   .agg(n_ga_records=("ga_date", "size"),
                        n_children_with_ga=("person_id", "nunique")))
    else:
        ga_year = pd.DataFrame(columns=["ga_year", "formula", "n_ga_records", "n_children_with_ga"])
    # First GA in the PRIMARY selected window, per formula-exposed child.
    # This follows the same definition as SQL first_ga_by_year.
    if len(ga_year):
        first_events = (primary.loc[primary.formula == 1]
                        .groupby("person_id", as_index=False)
                        .agg(first_ga_date=("ga_date", "min")))
        first_events["first_ga_year"] = first_events.first_ga_date.apply(lambda d: d.year)
        first_ga_by_year = (first_events.groupby("first_ga_year", as_index=False)
                            .agg(n_children=("person_id", "size")))
    else:
        first_ga_by_year = pd.DataFrame(columns=["first_ga_year", "n_children"])

    freq = eligible.person_id.map(n_rx).fillna(0).astype(int)
    bands = pd.cut(freq, [-1, 0, 1, 4, 9, 19, 49, np.inf],
                   labels=["0", "1", "2-4", "5-9", "10-19", "20-49", "50+"])
    frequency = (bands.value_counts().rename_axis("frequency_band")
                 .reset_index(name="n_children"))
    if len(rx):
        products = (rx.groupby("medication_name", as_index=False)
                    .agg(n_children=("person_id", "nunique"), n_records=("rx_date", "size"))
                    .rename(columns={"medication_name": "product"}))
    else:
        products = pd.DataFrame(columns=["product", "n_children", "n_records"])
    return {"cohort": result, "prescriptions_by_year": prescribing,
            "ga_by_year": ga_year, "first_ga_by_year": first_ga_by_year, "prescription_frequency": frequency,
            "products_by_name": products}


def load_aggregates(cfg, n=3200):
    ppl = make_synthetic_people(n=n, seed=cfg.seed,
                                start_date=cfg.birth_start, end_date=cfg.birth_end)
    rx, ga = make_synthetic_events(ppl, seed=cfg.seed + 1)
    return aggregate_synthetic(ppl, rx, ga, cfg)
