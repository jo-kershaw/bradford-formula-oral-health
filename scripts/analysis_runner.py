"""Run the analysis and save, labelled with timestamps. Previous outputs are not overwritten.

Every run gets its own directory, with tables and plots kept separately.
The user can changes study population definitions in analysis_settings.py.
"""
from datetime import datetime
from pathlib import Path
import math

import pandas as pd

from analysis_stats import analyse
from plots import create_plots
from plots_overview import (
    plot_calendar_coverage,
    plot_dental_ga_by_year,
    plot_formula_prescriptions_by_year,
    plot_children_prescribed_by_year,
    plot_formula_by_ethnicity,
    plot_formula_by_ethnicity_year,
    plot_ga_by_ethnicity_formula,
    plot_ga_by_imd_group,
    plot_formula_by_imd_decile
)


RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"


def create_run_folders(mode):
    """Create an exclusive new run folder."""
    if mode not in ("secure", "synthetic"):
        raise ValueError("mode must be 'secure' or 'synthetic'")

    parent = RESULTS_ROOT / mode
    parent.mkdir(parents=True, exist_ok=True)
    # Microseconds make ordinary consecutive runs distinct; exclusive mkdir
    # prevents accidental overwrite.
    folder = parent / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    folder.mkdir(exist_ok=False)
    # Separate the new data-overview outputs from the analysis.
    # Keep both CSV and Markdown tables.
    for kind in ("tables", "plots"):
        for section in ("data_overview", "analysis"):
            (folder / kind / section).mkdir(parents=True)
    (folder / "plots" / "external_reference").mkdir()
    (folder / "RUN_INCOMPLETE.txt").write_text(
        "This run did not finish. Do not use the files in this folder.\n",
        encoding="utf-8",
    )
    return folder


def markdown_cell(value):
    """Markdown table formatting without requiring 'tabulate' package."""
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        value = f"{value:.6g}"
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def write_table_pair(table, name, folder, mode):
    """Write the same table as both CSV (analysis) and Markdown (reading)."""
    if not isinstance(table, pd.DataFrame):
        raise TypeError(f"{name} is not a pandas table")
    prefix = "SYNTHETIC_" if mode == "synthetic" else "SECURE_"
    basename = prefix + name
    # TABLE_FORMAT_SUBFOLDERS_V14
    csv_folder = folder / "csv"
    markdown_folder = folder / "markdown"
    csv_folder.mkdir(parents=True, exist_ok=True)
    markdown_folder.mkdir(parents=True, exist_ok=True)
    table.to_csv(csv_folder / f"{basename}.csv", index=False)

    columns = [markdown_cell(col) for col in table.columns]
    lines = ["| " + " | ".join(columns) + " |",
             "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in table.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(markdown_cell(value) for value in row) + " |")
    heading = "# " + name.replace("_", " ").title()
    source = "**SYNTHETIC DATA — NOT STUDY RESULTS**" if mode == "synthetic" else "**BRADFORD SECURE DATA**"
    (markdown_folder / f"{basename}.md").write_text(
        heading + "\n\n" + source + "\n\n" + "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def adjusted_model_table(model, reason):
    """Record model output as an ordinary table, including failure explanation."""
    columns = ["measure", "estimate", "ci_lower", "ci_upper", "unit_or_note"]
    if model is None:
        return pd.DataFrame([["model_not_fitted", None, None, None, reason or "No model"]], columns=columns)
    measures = [
        ("formula_odds_ratio", model["odds_ratio"], *model["odds_ratio_ci"], "OR"),
        ("formula_p_value", model["p_value"], None, None, "p-value"),
        ("adjusted_GA_formula", model["formula_pct"], *model["formula_pct_ci"], "%"),
        ("adjusted_GA_other", model["other_pct"], *model["other_pct_ci"], "%"),
        ("adjusted_GA_difference", model["difference_pp"], *model["difference_pp_ci"], "percentage points"),
        ("relative_GA_difference", model["relative_difference_pct"], *model["relative_difference_ci"], "%"),
    ]
    return pd.DataFrame(measures, columns=columns)


def run_info(cfg, mode, tables, model, reason):
    source = ("BRADFORD DATA (secure environment)" if mode == "secure"
              else "SYNTHETIC DATA")
    lines = [
        "BRADFORD ANALYSIS — RUN INFORMATION",
        f"Data source: {source}",
        f"Completed: {datetime.now().isoformat(timespec='seconds')}",
        f"Analysis: {cfg.name}",
        f"Births: {cfg.birth_start} to {cfg.birth_end} (inclusive)",
        f"Exposure: {cfg.min_rx}+ {cfg.rx_mode}, age {cfg.exposure_age_start} to under {cfg.exposure_age_end} months",
        f"Medication exclusions: {', '.join(cfg.excluded_terms) if cfg.excluded_terms else 'none'}",
        "GA age windows: " + "; ".join(f"{w.name}: {w.start_months} to under {w.end_months} months" for w in cfg.windows),
        f"Primary GA outcome: {cfg.primary.name}",
        f"GA calendar dates: {cfg.ga_calendar_start} to {cfg.ga_calendar_end}",
        f"Adjustment variables: {', '.join(cfg.adjust_for) if cfg.adjust_for else 'none'}",
        f"Source prescription coverage (declared): {cfg.rx_source_start} to {cfg.rx_source_end}",
        f"Source GA coverage (declared): {cfg.ga_source_start} to {cfg.ga_source_end}",
        f"Require full source coverage: {cfg.require_complete_coverage}",
        f"Children in analysis: {int(tables['cohort'].n_children.sum())}",
        f"Qualifying formula recipients: {int(tables['cohort'].loc[tables['cohort'].formula == 1, 'n_children'].sum())}",
        f"Children with GA in primary window: {int(tables['cohort'][cfg.primary.key].sum())}",
        f"Adjusted model: {'fitted' if model else 'NOT FITTED: ' + (reason or 'unknown reason')}",
        f"Confidence interval draws: {cfg.ci_draws}; random seed: {cfg.seed}",
        "",
        "CSV tables: tables/<section>/csv/; readable tables: tables/<section>/markdown/.",
        "plots/analysis/ contains analysis plots; plots/data_overview/ contains source coverage and yearly overview plots.",
        "Yearly overview is unfiltered source activity: all GA ages and all formula-extract records.",
        "Formula prescribing dates are unique child-calendar-date combinations.",
        "Source coverage dates are unfiltered table ranges, not the selected study population.",
        "Synthetic runs omit source coverage because the demo has no observation-period data.",
        "plots/external_reference/ is for plots made from published external data.",
        "Secure outputs stay in the Bradford environment.",
    ]
    return "\n".join(lines) + "\n"


def run_pipeline(cfg, *, mode, engine=None, synthetic_children=3200):
    print("\nANALYSIS:", cfg.name)
    print("Births:", cfg.birth_start, "through", cfg.birth_end)
    print("Exposure:", cfg.min_rx, "or more", cfg.rx_mode, "in months",
          cfg.exposure_age_start, "to under", cfg.exposure_age_end)
    print("GA calendar filter:", cfg.ga_calendar_start, "through", cfg.ga_calendar_end)
    print("GA windows:", ", ".join(w.name for w in cfg.windows))

    if mode == "secure":
        if engine is None:
            raise RuntimeError("The Bradford setup must create the SQLAlchemy engine first")
        from sql_backend import (
            load_aggregates, load_source_coverage, load_source_yearly_overview, load_formula_by_ethnicity_overview,\
             load_ga_by_ethnicity_formula_overview, load_ga_by_imd_group_overview, load_formula_by_imd_decile_overview
        )
        data = load_aggregates(engine, cfg)
        source_coverage = load_source_coverage(engine)
        source_yearly = load_source_yearly_overview(engine)
        from sql_backend import load_source_ga_children_yearly_overview
        ga_children_yearly = load_source_ga_children_yearly_overview(engine)
        formula_ethnicity = load_formula_by_ethnicity_overview(engine)
        ga_ethnicity_formula = load_ga_by_ethnicity_formula_overview(engine)
        ga_imd_group = load_ga_by_imd_group_overview(engine)
        imd_comparison = load_formula_by_imd_decile_overview(engine)
    elif mode == "synthetic":
        from synthetic_backend import load_aggregates
        data = load_aggregates(cfg, n=synthetic_children)
        source_coverage = None  # Synthetic generator has no observation-period table.
        source_yearly = None  # Source-wide yearly figures are secure-only for now.
        ga_children_yearly = None
        formula_ethnicity = None
        ga_ethnicity_formula = None
        ga_imd_group = None
        imd_comparison = None
        print("SYNTHETIC DEMO: all people, prescriptions, GA events and distributions are fabricated.")
    else:
        raise ValueError("mode must be 'secure' or 'synthetic'")

    tables, model, reason = analyse(data, cfg)
    tables["adjusted_model"] = adjusted_model_table(model, reason)
    # First-GA plot must agree with the selected study cohort.
    exposed_ga = int(tables["cohort"].loc[
        tables["cohort"].formula == 1, cfg.primary.key].sum())
    first_ga_total = int(tables["first_ga_by_year"]["n_children"].sum())
    if first_ga_total != exposed_ga:
        raise ValueError("First GA totals disagree: "
                         f"{first_ga_total} versus {exposed_ga}")

    folder = create_run_folders(mode)
    for name, table in tables.items():
        write_table_pair(table, name, folder / "tables" / "analysis", mode)
    create_plots(tables, model, cfg, folder / "plots" / "analysis", source_mode=mode)
    if source_coverage is not None:
        write_table_pair(source_coverage, "calendar_coverage_datasets",
                         folder / "tables" / "data_overview", mode)
        plot_calendar_coverage(source_coverage,
                               folder / "plots" / "data_overview", source_mode=mode)
    if source_yearly is not None:
        # Original exploratory plots, now using annual SQL totals rather than
        # loading person-level medication or dental GA data into Python.
        for name, table in source_yearly.items():
            write_table_pair(table, name, folder / "tables" / "data_overview", mode)

        overview_plots = folder / "plots" / "data_overview"
        plot_dental_ga_by_year(source_yearly["dental_ga_by_year"], overview_plots,
                               source_mode=mode)
        plot_formula_prescriptions_by_year(
            source_yearly["formula_prescriptions_by_year"], overview_plots,
            source_mode=mode)
        plot_children_prescribed_by_year(
            source_yearly["children_prescribed_formula_by_year"], overview_plots,
            source_mode=mode)
        if formula_ethnicity is not None:
            for name, table in formula_ethnicity.items():
                write_table_pair(
                    table,
                    name,
                    folder / "tables" / "data_overview",
                    mode
                )
            plot_formula_by_ethnicity(
                formula_ethnicity["formula_by_ethnicity"],
                folder / "plots" / "data_overview",
                source_mode=mode
            )
            plot_formula_by_ethnicity_year(
                formula_ethnicity["formula_by_ethnicity_year"],
                folder / "plots" / "data_overview",
                source_mode=mode
            )
        if ga_ethnicity_formula is not None:
            for name, table in ga_ethnicity_formula.items():
                write_table_pair(
                    table,
                    name,
                    folder / "tables" / "data_overview",
                    mode
                )

            plot_ga_by_ethnicity_formula(
                ga_ethnicity_formula["ga_by_ethnicity_formula"],
                folder / "plots" / "data_overview",
                source_mode=mode
            )
        if ga_imd_group is not None:
            for name, table in ga_imd_group.items():
                write_table_pair(
                    table,
                    name,
                    folder / "tables" / "data_overview",
                    mode
                )

            plot_ga_by_imd_group(
                ga_imd_group["ga_by_imd_group"],
                folder / "plots" / "data_overview",
                source_mode=mode
            )
        if imd_comparison is not None:
            for name, table in imd_comparison.items():
                write_table_pair(
                    table,
                    name,
                    folder / "tables" / "data_overview",
                    mode
                )

            plot_formula_by_imd_decile(
                imd_comparison["formula_by_imd_decile"],
                folder / "plots" / "data_overview",
                source_mode=mode
            )
    if ga_children_yearly is not None:
        from plots_overview import (
            plot_formula_prescriptions_by_year_ga_children,
            plot_children_prescribed_by_year_ga_children,
        )
        for name, table in ga_children_yearly.items():
            write_table_pair(table, name,
                             folder / "tables" / "data_overview", mode)
        overview_plots = folder / "plots" / "data_overview"
        plot_formula_prescriptions_by_year_ga_children(
            ga_children_yearly["formula_prescriptions_by_year_ga_children"],
            overview_plots, source_mode=mode)
        plot_children_prescribed_by_year_ga_children(
            ga_children_yearly["children_prescribed_formula_by_year_ga_children"],
            overview_plots, source_mode=mode)

    # Published OHID reference:
    # Source and indexed numbers are in reference_data/ .
    from plots_external_reference import write_ohid_reference
    write_ohid_reference(folder)

    (folder / "RUN_INFO.txt").write_text(
        run_info(cfg, mode, tables, model, reason), encoding="utf-8"
    )
    (folder / "RUN_INCOMPLETE.txt").unlink()

    print("\nCOHORT: {:,} children, {:,} qualifying formula recipients, "
          "{:,} children with GA in primary age window".format(
              int(tables["cohort"].n_children.sum()),
              int(tables["cohort"].loc[tables["cohort"].formula == 1, "n_children"].sum()),
              int(tables["cohort"][cfg.primary.key].sum())))
    print("\n2x2 TABLES (children, not GA procedures):")
    print(tables["two_by_two"].to_string(index=False))
    if model:
        print("\nADJUSTED MODEL:", model["model_formula"])
        print("Formula OR: {:.3f} (95% CI {:.3f}–{:.3f}), p={:.4g}".format(
            model["odds_ratio"], *model["odds_ratio_ci"], model["p_value"]))
    else:
        print("\nNo adjusted model:", reason)
    print("\n", ("SECURE DATA" if mode == "secure" else "SYNTHETIC DATA"),
          "outputs saved under", folder.resolve())
    return folder
