"""Introductory plots describing source datasets.
"""
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


def plot_calendar_coverage(coverage, plots_dir, source_mode="secure"):
    """Plot actual min/max dates from the three principal source tables.

    `coverage` must have columns dataset, start_date, end_date.
    The date ranges are for the source tables.
    """
    required = {"dataset", "start_date", "end_date"}
    if not required.issubset(coverage.columns):
        raise ValueError("Coverage table needs dataset, start_date and end_date columns")

    coverage = coverage.copy()
    coverage["start_date"] = pd.to_datetime(coverage["start_date"], errors="raise")
    coverage["end_date"] = pd.to_datetime(coverage["end_date"], errors="raise")
    if coverage[["start_date", "end_date"]].isna().any().any():
        raise ValueError("One of the source datasets has no valid coverage dates")
    if (coverage["start_date"] > coverage["end_date"]).any():
        raise ValueError("A source dataset ends before it starts")

    # Horizontal bar per dataset with exact endpoint dates.
    ranges = {
        row.dataset: (row.start_date, row.end_date)
        for row in coverage.itertuples(index=False)
    }
    fig, ax = plt.subplots(figsize=(12, 5))
    labels = list(ranges.keys())

    for y, label in enumerate(labels):
        start, end = ranges[label]
        ax.barh(
            y,
            (end - start).days,
            left=mdates.date2num(start),
            height=0.45,
        )
        ax.text(
            start, y + 0.27, start.strftime("%Y-%m-%d"),
            ha="left", va="bottom", fontsize=8,
        )
        ax.text(
            end, y + 0.27, end.strftime("%Y-%m-%d"),
            ha="right", va="bottom", fontsize=8,
        )

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_ylim(-0.7, len(labels) - 0.27)
    ax.xaxis_date()
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    ax.set_xlabel("Calendar year")
    ax.set_title("Calendar coverage of the principal datasets")

    # Auto-scale to actual data coverage.
    ax.set_xlim(
        min(s for s, _ in ranges.values()) - pd.DateOffset(years=1),
        max(e for _, e in ranges.values()) + pd.DateOffset(years=1),
    )
    if source_mode == "synthetic":
        fig.text(0.5, 0.01, "SYNTHETIC DATA",
                 ha="center", va="bottom", fontsize=10, weight="bold")

    plots_dir = Path(plots_dir)
    plots_dir.mkdir(parents=True, exist_ok=True)
    prefix = "SYNTHETIC_" if source_mode == "synthetic" else "SECURE_"
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(
        plots_dir / f"{prefix}calendar_coverage_datasets.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(fig)


# ============================================================
# BAR PLOTS: YEARLY SOURCE-DATA OVERVIEW
# The input tables are calculated by
# load_source_yearly_overview() in sql_backend.py.
# ============================================================

def _save_overview_bar(fig, plots_dir, filename, source_mode):
    plots_dir = Path(plots_dir)
    plots_dir.mkdir(parents=True, exist_ok=True)
    prefix = "SYNTHETIC_" if source_mode == "synthetic" else "SECURE_"
    if source_mode == "synthetic":
        fig.text(0.5, 0.01, "SYNTHETIC DATA",
                 ha="center", va="bottom", fontsize=10, weight="bold")
    fig.tight_layout()
    fig.savefig(plots_dir / (prefix + filename), dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_dental_ga_by_year(ga_by_year, plots_dir, source_mode="secure"):
    """GA records per calendar year, all ages in the source GA extract."""
    fig, ax = plt.subplots(figsize=(9, 5))

    ax.bar(ga_by_year["ga_year"], ga_by_year["n_ga"])
    ax.set_title("Dental general anaesthetics by year")
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of GA records")
    ax.set_xticks(ga_by_year["ga_year"])
    ax.tick_params(axis="x", rotation=45)

    _save_overview_bar(fig, plots_dir, "dental_ga_by_year_simple_bar.png", source_mode)


def plot_formula_prescriptions_by_year(prescriptions_by_year, plots_dir,
                                      source_mode="secure"):
    """Distinct prescribing dates per calendar year in the formula extract."""
    fig, ax = plt.subplots(figsize=(9, 5))

    ax.bar(prescriptions_by_year["year"], prescriptions_by_year["n_prescriptions"])
    ax.set_title("Low-allergy formula prescriptions by year")
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of prescription dates")
    ax.set_xticks(prescriptions_by_year["year"])
    ax.tick_params(axis="x", rotation=45)

    _save_overview_bar(fig, plots_dir,
                       "formula_prescriptions_by_year_simple_bar.png", source_mode)


def plot_children_prescribed_by_year(children_prescribed_by_year, plots_dir,
                                     source_mode="secure"):
    """Unique children receiving formula prescriptions within each calendar year."""
    fig, ax = plt.subplots(figsize=(9, 5))

    ax.bar(children_prescribed_by_year["year"], children_prescribed_by_year["n_children"])
    ax.set_title("Children receiving low-allergy formula prescriptions by year")
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of children")
    ax.set_xticks(children_prescribed_by_year["year"])
    ax.tick_params(axis="x", rotation=45)

    _save_overview_bar(fig, plots_dir,
                       "children_prescribed_formula_by_year_simple_bar.png", source_mode)

def plot_formula_by_ethnicity(plot_data, plots_dir, source_mode="secure"):
    import matplotlib.pyplot as plt

    plot_data = plot_data.sort_values(
        "provisional_formula_pct",
        ascending=False
    )

    fig, ax = plt.subplots(figsize=(9, 4.5))

    bars = ax.barh(
        plot_data["ethnic_group"],
        plot_data["provisional_formula_pct"],
    )

    ax.invert_yaxis()

    ax.bar_label(bars, fmt="%.2f%%", padding=5)

    ax.set_xlabel("Provisional formula proportion (%)")
    ax.set_title(
        "Specialist formula prescribing by ethnicity\n"
        "Bradford children born 2012–2018"
    )

    ax.set_xlim(0, 7.5)
    ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    fig.savefig(
        plots_dir / f"{source_mode.upper()}_formula_by_ethnicity.png",
        dpi=300,
        bbox_inches="tight"
    )

    plt.close(fig)

def plot_formula_by_ethnicity_year(
    ethnicity_by_year, plots_dir, source_mode="secure"
):
    import numpy as np
    import matplotlib.pyplot as plt

    # One column for each ethnic group
    plot_data = ethnicity_by_year.pivot(
        index="birth_year",
        columns="ethnic_group",
        values="provisional_formula_pct"
    ).sort_index()

    years = plot_data.index
    x = np.arange(len(years))
    width = 0.36

    fig, ax = plt.subplots(figsize=(10, 5))

    bars1 = ax.bar(
        x - width / 2,
        plot_data["White British"],
        width,
        label="White British"
    )

    bars2 = ax.bar(
        x + width / 2,
        plot_data["Pakistani"],
        width,
        label="Pakistani"
    )

    ax.set_xticks(x, years)
    ax.set_xlabel("Birth year")
    ax.set_ylabel("Provisional formula proportion (%)")
    ax.set_title(
        "Specialist formula prescribing by ethnicity and birth year\n"
        "Bradford children born 2012–2018"
    )

    ax.bar_label(bars1, fmt="%.1f", padding=3, fontsize=9)
    ax.bar_label(bars2, fmt="%.1f", padding=3, fontsize=9)

    ax.set_ylim(0, 9)
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()

    fig.savefig(
        plots_dir / f"{source_mode.upper()}_formula_by_ethnicity_year.png",
        dpi=300,
        bbox_inches="tight"
    )

    plt.close(fig)

def plot_ga_by_ethnicity_formula(
    ga_ethnicity, plots_dir, source_mode="secure"
):
    import matplotlib.pyplot as plt

    plot_data = ga_ethnicity.sort_values(
        "ga_pct", ascending=False
    )

    fig, ax = plt.subplots(figsize=(9, 4.5))

    bars = ax.barh(
        plot_data["ethnic_group"],
        plot_data["ga_pct"]
    )

    ax.invert_yaxis()
    ax.bar_label(bars, fmt="%.2f%%", padding=5)

    ax.set_xlabel("Children with dental GA (%)")
    ax.set_title(
        "Dental GA by ethnicity among children prescribed specialist formula\n"
        "Bradford births 2015–2018; GA ages 1–under 6"
    )

    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlim(0, max(plot_data["ga_pct"]) * 1.2)

    fig.tight_layout()
    fig.savefig(
        plots_dir / f"{source_mode.upper()}_ga_by_ethnicity_formula.png",
        dpi=300,
        bbox_inches="tight"
    )

    plt.close(fig)

def plot_ga_by_imd_group(
    ga_by_imd, plots_dir, source_mode="secure"
):

    # Preserve the original three deprivation groups
    group_order = [
        "1–3 More deprived",
        "4–6 Middle",
        "7–10 Less deprived"
    ]

    plot_data = (
        ga_by_imd
        .set_index("deprivation_group")
        .reindex(group_order)
        .dropna(subset=["ga_pct"])
        .reset_index()
    )

    fig, ax = plt.subplots(figsize=(8, 5))

    bars = ax.bar(
        plot_data["deprivation_group"],
        plot_data["ga_pct"],
        width=0.6
    )

    ax.bar_label(bars, fmt="%.2f%%", padding=5)

    ax.set_ylabel("Children undergoing dental GA (%)")
    ax.set_xlabel("IMD 2019 deprivation group")
    ax.set_title(
        "Dental GA by deprivation among specialist formula recipients\n"
        "Bradford births 2015–2018; GA ages 1–under 6"
    )

    # Keep original scale, but allow for different results
    ax.set_ylim(0, max(3.5, plot_data["ga_pct"].max() * 1.2))

    ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    fig.savefig(
        plots_dir / f"{source_mode.upper()}_ga_by_imd_group.png",
        dpi=300,
        bbox_inches="tight"
    )

    plt.close(fig)

def plot_formula_by_imd_decile(
    imd_comparison, plots_dir, source_mode="secure"
):
    import matplotlib.pyplot as plt

    plot_data = imd_comparison.sort_values("imd_decile")

    fig, ax = plt.subplots(figsize=(10, 5))

    bars = ax.bar(
        plot_data["imd_decile"].astype(str),
        plot_data["provisional_formula_pct"]
    )

    ax.bar_label(bars, fmt="%.2f%%", padding=4, fontsize=9)

    ax.set_xlabel(
        "IMD 2019 decile (1 = most deprived, 10 = least deprived)"
    )
    ax.set_ylabel("Provisional formula proportion (%)")
    ax.set_title(
        "Specialist formula prescribing by deprivation\n"
        "Bradford children born 2012–2018"
    )

    ax.set_ylim(
        0,
        max(9, plot_data["provisional_formula_pct"].max() * 1.2)
    )

    ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    fig.savefig(
        plots_dir / f"{source_mode.upper()}_formula_by_imd_decile.png",
        dpi=300,
        bbox_inches="tight"
    )

    plt.close(fig)

def plot_formula_prescriptions_by_year_ga_children(
    ga_children_prescriptions_by_year, plots_dir, source_mode="secure"
):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(ga_children_prescriptions_by_year["year"],
           ga_children_prescriptions_by_year["n_prescriptions"])
    ax.set_title("Formula prescriptions by year among children who had a dental GA")
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of prescription dates")
    ax.set_xticks(ga_children_prescriptions_by_year["year"])
    ax.tick_params(axis="x", rotation=45)
    _save_overview_bar(fig, plots_dir,
                       "formula_prescriptions_by_year_ga_children_simple.png",
                       source_mode)

def plot_children_prescribed_by_year_ga_children(
    ga_children_prescribed_by_year, plots_dir, source_mode="secure"
):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(ga_children_prescribed_by_year["year"],
           ga_children_prescribed_by_year["n_children"])
    ax.set_title("Children with a dental GA receiving formula prescriptions by year")
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of children")
    ax.set_xticks(ga_children_prescribed_by_year["year"])
    ax.tick_params(axis="x", rotation=45)
    _save_overview_bar(fig, plots_dir,
                       "children_prescribed_formula_by_year_ga_children.png",
                       source_mode)