"""Reproducible, study population-labelled figures."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _cohort_caption(cfg, *, threshold=True):
    """Build figure text from the settings."""
    births = (f"Births {cfg.birth_start:%d %b %Y}–"
              f"{cfg.birth_end:%d %b %Y}")
    age = (f"age {cfg.exposure_age_start}–under "
           f"{cfg.exposure_age_end} months")
    if threshold:
        unit = ("distinct prescription dates" if cfg.rx_mode == "distinct_dates"
                else "prescription records")
        exposure = f"Formula: {cfg.min_rx}+ {unit}, {age}"
    else:
        # The annual prescribing-date SQL currently counts all qualifying
        # formula records in the cohort, not just children above min_rx.
        exposure = f"All specialist formula prescribing dates, {age} (any count)"
    return births + "\n" + exposure


def _primary_ga_caption(cfg):
    """The configured primary GA age window AND calendar range."""
    w = cfg.primary
    return (f"GA age {w.start_months}–under {w.end_months} months; "
            f"{cfg.ga_calendar_start:%d %b %Y}–"
            f"{cfg.ga_calendar_end:%d %b %Y}")


def save_fig(fig, path, source_mode="secure"):
    if source_mode == "synthetic":
        fig.text(0.5, 0.01, "SYNTHETIC DATA — NOT STUDY RESULTS",
                 ha="center", va="bottom", fontsize=10, weight="bold")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_ga_age_windows(table, cfg, folder, source_mode="secure"):
    windows = [w.name for w in cfg.windows]
    exposed = table.loc[table.formula == 1].set_index("ga_window")
    other = table.loc[table.formula == 0].set_index("ga_window")
    x = np.arange(len(windows))
    fig, ax = plt.subplots(figsize=(max(8, len(windows) * 2.1), 4.7))
    ax.bar(x-0.2, exposed.loc[windows, "ga_percent"], width=.4, label="Formula")
    ax.bar(x+0.2, other.loc[windows, "ga_percent"], width=.4, label="Other children")
    ax.set_xticks(x, [f"{w.start_months}–<{w.end_months}m" for w in cfg.windows], rotation=18, ha="right")
    ax.set_ylabel("Children with recorded dental GA (%)")
    ax.set_title("Descriptive GA percentages by age window\n" + _cohort_caption(cfg), fontsize=10)
    ax.legend()
    save_fig(fig, folder / (("SYNTHETIC_" if source_mode == "synthetic" else "SECURE_") + "ga_percent_by_age_window.png"), source_mode=source_mode)


def plot_formula_by_birth_year(by_birth_year, cfg, folder, source_mode="secure"):
    years = sorted(by_birth_year.birth_year.unique())
    counts = by_birth_year.pivot_table(index="birth_year", columns="formula", values="n_children", fill_value=0)
    counts = counts.reindex(years, fill_value=0)
    formula = counts[1] if 1 in counts else np.zeros(len(years))
    total = counts.sum(axis=1)
    fig, ax = plt.subplots(figsize=(7.8, 4.5))
    ax.plot(years, 1000 * formula / total, "o-")
    ax.set_xlabel("Birth year")
    ax.set_ylabel("Formula recipients per 1,000 eligible children")
    ax.set_title("Qualifying formula prescriptions by birth year\n" + _cohort_caption(cfg), fontsize=10)
    ax.set_xticks(years)
    save_fig(fig, folder / (("SYNTHETIC_" if source_mode == "synthetic" else "SECURE_") + "formula_recipients_by_birth_year.png"), source_mode=source_mode)


def plot_ga_by_calendar_year(data, cfg, folder, source_mode="secure"):
    years = sorted(data.ga_year.unique()) if len(data) else []
    fig, ax = plt.subplots(figsize=(8.2, 4.5))
    for status, label in [(1, "Formula"), (0, "Other children")]:
        values = data.loc[data.formula == status].set_index("ga_year")["n_ga_records"] if len(data) else {}
        ax.plot(years, [values.get(y, 0) for y in years], "o-", label=label)
    ax.set_xlabel("Calendar year of dental GA")
    ax.set_ylabel("Recorded GA events (not unique children across years)")
    ax.set_title("Dental GA events by calendar year\n" + _cohort_caption(cfg) + "\n" + _primary_ga_caption(cfg), fontsize=9)
    ax.legend()
    save_fig(fig, folder / (("SYNTHETIC_" if source_mode == "synthetic" else "SECURE_") + "ga_events_by_calendar_year.png"), source_mode=source_mode)


def plot_rx_by_calendar_year(data, cfg, folder, source_mode="secure"):
    fig, ax = plt.subplots(figsize=(8.2, 4.5))
    if len(data):
        ax.bar(data.prescription_year, data.n_prescribing_dates)
        ax.set_xticks(sorted(data.prescription_year.unique()))
    ax.set_xlabel("Calendar year of qualifying formula record")
    ax.set_ylabel("Distinct child-prescription dates")
    ax.set_title("Specialist formula prescribing dates by year\n" + _cohort_caption(cfg), fontsize=10)
    save_fig(fig, folder / (("SYNTHETIC_" if source_mode == "synthetic" else "SECURE_") + "prescribing_dates_by_calendar_year.png"), source_mode=source_mode)


def plot_adjusted(model, cfg, folder, source_mode="secure"):
    if model is None:
        return
    vals = [model["formula_pct"], model["other_pct"]]
    cis = [model["formula_pct_ci"], model["other_pct_ci"]]
    err = np.array([[v-lo for v,(lo,hi) in zip(vals,cis)],
                    [hi-v for v,(lo,hi) in zip(vals,cis)]])
    fig, ax = plt.subplots(figsize=(6.0, 4.5))
    ax.bar([0,1], vals, yerr=err, capsize=5, width=.6)
    ax.set_xticks([0,1], ["Formula", "Other children"])
    ax.set_ylabel("Model-standardised probability of GA (%)")
    ax.set_title("Adjusted dental GA probabilities\n" + _cohort_caption(cfg) + "\n" + _primary_ga_caption(cfg), fontsize=9)
    save_fig(fig, folder / (("SYNTHETIC_" if source_mode == "synthetic" else "SECURE_") + "adjusted_ga_probabilities.png"), source_mode=source_mode)


def create_plots(tables, model, cfg, output_dir, source_mode="secure"):
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    plot_ga_age_windows(tables["two_by_two"], cfg, folder, source_mode=source_mode)
    plot_formula_by_birth_year(tables["by_birth_year"], cfg, folder, source_mode=source_mode)
    plot_ga_by_calendar_year(tables["ga_by_year"], cfg, folder, source_mode=source_mode)
    plot_first_ga_by_year_formula_children(
        tables["first_ga_by_year"], cfg, folder, source_mode=source_mode)
    plot_rx_by_calendar_year(tables["prescriptions_by_year"], cfg, folder, source_mode=source_mode)
    plot_adjusted(model, cfg, folder, source_mode=source_mode)

def plot_first_ga_by_year_formula_children(
    first_ga_by_year, cfg, folder, source_mode="secure"
):
    """First GA per qualifying formula child in the chosen primary GA window.
    Years count unique children exactly once, not all GA event records.
    """
    fig, ax = plt.subplots(figsize=(9, 5))
    if len(first_ga_by_year):
        ax.bar(first_ga_by_year["first_ga_year"],
               first_ga_by_year["n_children"])
        ax.set_xticks(first_ga_by_year["first_ga_year"])
    ax.tick_params(axis="x", rotation=45)
    ax.set_title("First GA by year among formula-prescribed children\n"
                 + _cohort_caption(cfg) + "\n" + _primary_ga_caption(cfg), fontsize=9)
    ax.set_xlabel("Year of first dental GA in selected age window")
    ax.set_ylabel("Number of children")
    path = folder / (("SYNTHETIC_" if source_mode == "synthetic" else "SECURE_")
                     + "first_ga_by_year_formula_children.png")
    save_fig(fig, path, source_mode=source_mode)