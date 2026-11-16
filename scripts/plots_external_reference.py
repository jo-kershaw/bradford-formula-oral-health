"""Make the public OHID reference figure.

The figure reads only the publicly sourced indexed OHID reference table.
"""
from pathlib import Path
import math
import pandas as pd
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent.parent
DATA_FILE = HERE / "reference_data" / "ohid_bradford_england_all_index.csv"
SOURCE_FILE = HERE / "reference_data" / "OHID_SOURCE.md"
TABLE_STEM = "ohid_bradford_england_all_index"
FIGURE_NAME = "ohid_bradford_england_all_improved.png"


def read_ohid_reference():
    """Load and sanity-check the bundled public index (no database connection)."""
    table = pd.read_csv(DATA_FILE)
    cols = ["financial_year_ending", "bradford_index", "england_index"]
    if list(table.columns) != cols:
        raise ValueError("Unexpected OHID reference CSV columns")
    if table.isna().any().any():
        raise ValueError("OHID reference has missing values")
    if table["financial_year_ending"].tolist() != list(range(2019, 2026)):
        raise ValueError("OHID years should run from FY ending 2019 through 2025")
    if not all(math.isfinite(float(v)) and float(v) >= 0 for v in table[cols[1:]].to_numpy().flat):
        raise ValueError("OHID indices must be nonnegative finite values")
    for col in ("bradford_index", "england_index"):
        baseline = table.loc[table.financial_year_ending.isin([2019, 2020]), col].mean()
        if abs(baseline - 100.0) > 0.2:
            raise ValueError(f"{col} baseline mean should be 100 (got {baseline})")
    return table


def _markdown_table(table):
    cols = table.columns.tolist()
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for row in table.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(lines) + "\n"


def write_ohid_reference(run_folder):
    """Write public reference CSV, Markdown, source and plot into this run.

    Filenames use neither SECURE_ nor SYNTHETIC_: this table is external OHID data
    in *both* run modes. Does not depend on any analysis setting.
    """
    run_folder = Path(run_folder)
    tables = run_folder / "tables" / "external_reference"
    plots = run_folder / "plots" / "external_reference"
    # TABLE_FORMAT_SUBFOLDERS_V14
    tables_csv = tables / "csv"
    tables_markdown = tables / "markdown"
    tables_csv.mkdir(parents=True, exist_ok=True)
    tables_markdown.mkdir(parents=True, exist_ok=True)
    plots.mkdir(parents=True, exist_ok=True)
    reference = read_ohid_reference()
    reference.to_csv(tables_csv / f"{TABLE_STEM}.csv", index=False)
    heading = (
        "# OHID: all hospital tooth extractions, Bradford vs England\n\n"
        "**EXTERNAL PUBLISHED REFERENCE — neither secure Bradford nor synthetic data.**\n\n"
        "Financial years ending March; mean index for FY ending 2019–20 = 100.\n"
        "Values transcribed from the project's October 2026 OHID comparison; "
        "see `OHID_SOURCE.md` for the source and limitations.\n\n"
    )
    (tables_markdown / f"{TABLE_STEM}.md").write_text(
        heading + _markdown_table(reference), encoding="utf-8"
    )
    (tables_markdown / "OHID_SOURCE.md").write_text(SOURCE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    plot_ohid_bradford_england_all(reference, plots / FIGURE_NAME)
    return plots / FIGURE_NAME


def plot_ohid_bradford_england_all(data, path):
    """Line comparison of indexed OHID extraction activity, not dental GA."""
    fig, ax = plt.subplots(figsize=(10, 5.7))
    years = data["financial_year_ending"]
    ax.axhline(100, color="0.45", lw=1, linestyle="--", alpha=0.8)
    ax.axvspan(2020.5, 2021.5, color="0.5", alpha=0.1)
    ax.plot(years, data["bradford_index"], "o-", lw=2.2, ms=6, label="Bradford")
    ax.plot(years, data["england_index"], "s-", lw=2.2, ms=5, label="England")
    ax.set_xticks(years)
    ax.set_xlim(2018.75, 2025.25)
    ax.set_ylim(0, max(150, float(data[["bradford_index", "england_index"]].max().max()) * 1.12))
    ax.set_xlabel("Financial year ending March")
    ax.set_ylabel("Hospital extraction episodes (index; 2019–20 mean = 100)")
    ax.set_title("Hospital tooth extractions in children and young people aged 0–19\nBradford versus England (OHID)")
    ax.legend(frameon=False, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(2021, 146, "COVID-era\ndisruption", ha="center", va="top", fontsize=9, color="0.35")
    fig.text(
        0.12, 0.025,
        "Source: OHID (2026), hospital tooth-extraction episodes, ages 0–19. "
        "Financial-year indices from project notes; not dental GA counts.",
        ha="left", fontsize=8, color="0.35"
    )
    fig.tight_layout(rect=(0, 0.075, 1, 1))
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
