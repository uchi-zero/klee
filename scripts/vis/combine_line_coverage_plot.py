#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "click>=8.1",
#   "matplotlib>=3.8",
#   "seaborn>=0.13",
#   "pandas>=2.2",
#   "numpy>=1.26",
# ]
# ///
"""
combine_line_coverage_plot.py — connected scatterplot for KLEE line coverage.

Modes
-----
1) Single-run mode (one CSV per series, no shading):

   python scripts/vis/combine_line_coverage_plot.py \
       --title "make — DFS Symbolon vs DFS Baseline: Line coverage" \
       --out make_line.png \
       --labels "DFS Symbolon,DFS Baseline" \
       sym_line_coverage.csv \
       base_line_coverage.csv

2) Multi-run mode with shaded min–max envelopes + mean line:

   python scripts/vis/combine_line_coverage_plot.py \
       --title "make — DFS Symbolon vs DFS Baseline: Line coverage" \
       --out make_line.png \
       --setting "DFS Symbolon:sym_run1.csv,sym_run2.csv,sym_run3.csv" \
       --setting "DFS Baseline:base_run1.csv,base_run2.csv,base_run3.csv"

Each CSV must have columns:
    elapsed_sec, line_covered, line_total[, line_percent]

If line_percent is missing, it is computed as:
    100 * line_covered / line_total
"""

from pathlib import Path
from typing import List, Tuple

import click
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


# ------------------ data loading helpers ------------------ #

def load_line_csv(path: Path) -> pd.DataFrame:
    """Load one line_coverage.csv and normalize columns."""
    df = pd.read_csv(path)
    required = {"elapsed_sec", "line_covered", "line_total"}
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing columns {missing}")

    if "line_percent" not in df.columns:
        line_total = df["line_total"].replace(0, pd.NA)
        df["line_percent"] = (df["line_covered"] / line_total * 100).fillna(0.0)

    # Sort by time, drop duplicate timestamps (keep most recent)
    df = df.sort_values("elapsed_sec").drop_duplicates(
        subset=["elapsed_sec"], keep="last"
    )
    return df


def align_runs(dfs: List[pd.DataFrame]) -> Tuple[np.ndarray, List[pd.DataFrame]]:
    """
    Align multiple runs on a common elapsed_sec grid using LOCF (ffill).

    Returns:
        grid: np.ndarray of elapsed_sec values
        aligned: list of dataframes indexed by the grid
    """
    all_ts = sorted({float(t) for df in dfs for t in df["elapsed_sec"].values})
    grid = pd.Index(all_ts, name="elapsed_sec")

    aligned = []
    for df in dfs:
        d = df.set_index("elapsed_sec").sort_index()
        d = d.reindex(grid).ffill()
        aligned.append(d)

    return grid.to_numpy(dtype=float), aligned


def aggregate_setting(label: str, paths: List[Path]):
    """
    For one setting (e.g., DFS Symbolon), aggregate multiple runs:
    - Align all runs to a common time grid
    - Compute mean / min / max line_covered
    - Compute mean line_percent
    """
    dfs = [load_line_csv(p) for p in paths]
    if not dfs:
        raise ValueError(f"Setting {label} has no CSVs")

    grid, aligned = align_runs(dfs)

    vals_cov = np.stack([
        d["line_covered"].to_numpy(dtype=float) for d in aligned
    ])
    mean_cov = vals_cov.mean(axis=0)
    min_cov = vals_cov.min(axis=0)
    max_cov = vals_cov.max(axis=0)

    vals_pct = np.stack([
        d["line_percent"].to_numpy(dtype=float) for d in aligned
    ])
    mean_pct = vals_pct.mean(axis=0)

    # assume line_total is constant across runs & time (how llvm-cov behaves)
    line_total = aligned[0]["line_total"].to_numpy(dtype=float)

    return {
        "label": label,
        "elapsed_sec": grid,
        "mean_cov": mean_cov,
        "min_cov": min_cov,
        "max_cov": max_cov,
        "mean_pct": mean_pct,
        "line_total": line_total,
    }


# ------------------ plotting & style ------------------ #

def configure_paper_style():
    """Configure matplotlib rcParams to approximate the paper-style plot."""
    sns.set_theme(style="whitegrid", context="talk")

    plt.rcParams["font.family"] = "serif"
    plt.rcParams["font.serif"] = ["Times New Roman", "DejaVu Serif", "CMU Serif"]
    plt.rcParams["mathtext.fontset"] = "cm"
    plt.rcParams["font.size"] = 16

    plt.rcParams["axes.linewidth"] = 1.2
    plt.rcParams["grid.color"] = "#C0C0C0"
    plt.rcParams["grid.linewidth"] = 1.0
    plt.rcParams["grid.alpha"] = 0.5

    plt.rcParams["lines.linewidth"] = 2.2
    plt.rcParams["lines.markersize"] = 5


def place_end_labels(ax, endings, y_span, x_max_for_labels):
    """
    endings: list of (label, x_end, y_end, p_end, color)
    y_span: overall y-span of data
    x_max_for_labels: rightmost data-based x (used to position text near right edge)

    Returns (y_min_text, y_max_text) to help expand y-limits.
    """
    # Collision-avoidance: enforce a minimum vertical gap between labels
    min_dy = 0.04 * y_span
    endings_sorted = sorted(endings, key=lambda e: e[2])  # sort by y_end
    placed = []
    last_y = None

    for label, x_end, y_end, p_end, color in endings_sorted:
        y_text = y_end
        if last_y is not None and y_text - last_y < min_dy:
            y_text = last_y + min_dy
        placed.append((label, x_end, y_end, p_end, color, y_text))
        last_y = y_text

    all_y = []
    for label, x_end, y_end, p_end, color, y_text in placed:
        # ~2% padding from the right edge (based on max data time, not padded xlim)
        x_text = x_max_for_labels * 1.02
        ax.text(
            x_text,
            y_text,
            f"{p_end:.2f}%",
            color=color,
            va="center",
            ha="left",
            fontsize=12,
        )
        all_y.extend([y_end, y_text])

    return min(all_y), max(all_y)


def mark_origin(ax, color):
    """Draw a visible dot at the origin (0,0) with given color."""
    ax.scatter([0], [0], s=40, color=color, zorder=6)


# ------------------ CLI ------------------ #

@click.command()
@click.argument(
    "csvs",
    nargs=-1,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--title", required=True, help="Plot title")
@click.option(
    "--out",
    "out_path",
    default="line_compare.png",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Output PNG path",
)
@click.option(
    "--labels",
    default=None,
    help="Comma-separated legend labels (single-run mode only)",
)
@click.option(
    "--setting",
    "settings",
    multiple=True,
    help=(
        "Multi-run mode: setting definition of the form "
        "'Label:path1.csv,path2.csv,...'. "
        "Repeat --setting for multiple settings."
    ),
)
@click.option(
    "--colors",
    default=None,
    help="Comma-separated Matplotlib colors (e.g. 'red,blue,green').",
)
def main(csvs, title, out_path, labels, settings, colors):
    """
    Connected scatterplot for line coverage.

    Modes:
    - If --setting is provided: multi-run mode with shaded min–max envelopes.
    - Else: single-run mode using positional CSVs.
    """
    configure_paper_style()

    out_path = Path(out_path)
    multi_run_mode = len(settings) > 0

    if multi_run_mode and csvs:
        raise click.UsageError(
            "Provide either positional CSVs (single-run mode) OR --setting "
            "definitions (multi-run mode), but not both."
        )

    # ---------------- determine series count & palette ---------------- #
    if multi_run_mode:
        parsed_settings = []
        for s in settings:
            try:
                label, paths_str = s.split(":", 1)
            except ValueError:
                raise click.UsageError(
                    f"Invalid --setting '{s}'. Expected 'Label:path1.csv,path2.csv,...'"
                )
            label = label.strip()
            paths = [Path(p.strip()) for p in paths_str.split(",") if p.strip()]
            if not paths:
                raise click.UsageError(f"--setting '{s}' has no CSV paths")
            parsed_settings.append((label, paths))
        series_count = len(parsed_settings)
    else:
        if not csvs:
            raise click.UsageError(
                "Provide CSVs as positional arguments, or use --setting for multi-run mode."
            )
        series_count = len(csvs)

    # Colors
    if colors is not None:
        color_list = [c.strip() for c in colors.split(",") if c.strip()]
        if len(color_list) < series_count:
            extra = sns.color_palette("Set2", series_count - len(color_list))
            color_list = list(color_list) + list(extra)
    else:
        color_list = sns.color_palette("Set2", series_count)

    # ---------------- figure ---------------- #
    fig, ax = plt.subplots(figsize=(8, 4.5))

    endings = []  # (label, x_end_hours, y_end, p_end, color)
    max_hours = 0.0
    ymin, ymax = None, None

    # ---------------- multi-run mode ---------------- #
    if multi_run_mode:
        for (label, paths), color in zip(parsed_settings, color_list):
            agg = aggregate_setting(label, paths)
            x_hours = agg["elapsed_sec"] / 3600.0
            mean_cov = agg["mean_cov"]
            min_cov = agg["min_cov"]
            max_cov = agg["max_cov"]
            mean_pct = agg["mean_pct"]

            # shaded min–max envelope
            ax.fill_between(
                x_hours,
                min_cov,
                max_cov,
                color=color,
                alpha=0.18,
                linewidth=0,
            )

            # mean line + markers (connected scatterplot)
            ax.plot(
                x_hours,
                mean_cov,
                marker="o",
                linestyle="-",
                linewidth=2.2,
                markersize=5,
                color=color,
                label=label,
            )

            if x_hours.size > 0:
                max_hours = max(max_hours, float(x_hours.max()))
            if mean_cov.size > 0:
                cur_min = float(min_cov.min())
                cur_max = float(max_cov.max())
                ymin = cur_min if ymin is None else min(ymin, cur_min)
                ymax = cur_max if ymax is None else max(ymax, cur_max)

            if x_hours.size > 0:
                endings.append(
                    (
                        label,
                        float(x_hours[-1]),
                        float(mean_cov[-1]),
                        float(mean_pct[-1]),
                        color,
                    )
                )

    # ---------------- single-run mode ---------------- #
    else:
        if labels is not None:
            label_list = [s.strip() for s in labels.split(",") if s.strip()]
            if len(label_list) != len(csvs):
                raise click.UsageError(
                    f"--labels has {len(label_list)} entries but there are {len(csvs)} CSVs"
                )
        else:
            label_list = [p.stem for p in csvs]

        for path, label, color in zip(csvs, label_list, color_list):
            df = load_line_csv(path)
            x_hours = df["elapsed_sec"].astype(float) / 3600.0
            y = df["line_covered"].astype(float)

            ax.plot(
                x_hours,
                y,
                marker="o",
                linestyle="-",
                linewidth=2.2,
                markersize=5,
                color=color,
                label=label,
            )

            if not x_hours.empty:
                max_hours = max(max_hours, float(x_hours.max()))
            if not y.empty:
                ymin = float(y.min()) if ymin is None else min(ymin, float(y.min()))
                ymax = float(y.max()) if ymax is None else max(ymax, float(y.max()))

            last = df.iloc[-1]
            endings.append(
                (
                    label,
                    float(x_hours.iloc[-1]),
                    float(y.iloc[-1]),
                    float(last["line_percent"]),
                    color,
                )
            )

    # ---------------- axes / labels / legend ---------------- #
    if max_hours <= 0:
        max_hours = 1.0
    if ymin is None or ymax is None:
        ymin, ymax = 0.0, 1.0

    y_span = max(1.0, ymax - ymin)

    # x-axis: give room to the right for labels (15%), and ALSO a bit of room on the left
    x_max_for_labels = max_hours
    max_hours_with_text = max_hours * 1.15
    x_left = -0.05 * max_hours_with_text  # 5% of total width to the left of 0

    ax.set_title(title)
    ax.set_xlabel("Time (hour)")
    ax.set_ylabel("Covered Lines")

    ax.set_xlim(x_left, max_hours_with_text)
    ax.legend(loc="upper left", frameon=True)

    # Place end-of-series percentages with collision avoidance
    if endings:
        y_min_text, y_max_text = place_end_labels(
            ax, endings, y_span, x_max_for_labels
        )
        ymin_plot = min(ymin, y_min_text) - 0.05 * y_span
        ymax_plot = max(ymax, y_max_text) + 0.05 * y_span
        ax.set_ylim(ymin_plot, ymax_plot)
    else:
        ymin_plot, ymax_plot = ymin, ymax
        ax.set_ylim(ymin_plot, ymax_plot)

    # After setting final x/y limits, filter ticks so we only show non-negative values
    xticks = [t for t in ax.get_xticks() if t >= 0]
    if 0.0 not in xticks:
        xticks = [0.0] + xticks
    ax.set_xticks(xticks)

    yticks = [t for t in ax.get_yticks() if t >= 0]
    if 0.0 not in yticks:
        yticks = [0.0] + yticks
    ax.set_yticks(yticks)

    # Mark origin with the first series' color, now that it's inside the axes
    if endings:
        origin_color = endings[0][4]
        mark_origin(ax, origin_color)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    click.echo(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
