# /// script
# requires-python = "==3.12"
# dependencies = [
#     "matplotlib",
#     "pandas",
#     "seaborn",
#     "click",
# ]
# ///
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import click

klee_stats_file = "lua-1.csv"
query_stats_file = "z3-lua.csv"
time_bucket_size = "30min"


@click.group()
def cli():
    """Main CLI."""
    pass


@cli.command()
@click.option("--time-bucket-size", type=str, default="30min")
@click.argument("query_stats_file", type=click.Path(exists=True))
def stats(query_stats_file, time_bucket_size):
    query_stats = pd.read_csv(
        query_stats_file, header=None, names=["timestamp", "status", "span"]
    )

    # convert the timestamp to datetime and floor to time bucket size
    query_stats["datetime"] = pd.to_datetime(query_stats["timestamp"], unit="s")
    query_stats["time_bucket"] = query_stats["datetime"].dt.floor(time_bucket_size)

    # count the samples of each bucket
    counts = query_stats.groupby("time_bucket", sort=False).size().values

    # print time buckets and their counts
    time_buckets = query_stats["time_bucket"].unique()
    for bucket, count in zip(time_buckets, counts):
        print(f"Time bucket: {bucket}, Count: {count}")


@cli.command()
@click.option("--time-bucket-size", type=str, default="30min")
@click.argument("query_stats_file", type=click.Path(exists=True))
@click.argument("output_file", type=click.Path(exists=False))
def violin(query_stats_file, time_bucket_size, output_file):
    query_stats = pd.read_csv(
        query_stats_file, header=None, names=["timestamp", "status", "span"]
    )

    # convert the timestamp to datetime and floor to time bucket size
    query_stats["datetime"] = pd.to_datetime(query_stats["timestamp"], unit="s")
    query_stats["time_bucket"] = query_stats["datetime"].dt.floor(time_bucket_size)

    num_time_buckets = len(query_stats["time_bucket"].unique())

    # count the samples of each bucket
    counts = query_stats.groupby("time_bucket", sort=False).size().values

    # violin + bar
    plt.figure(figsize=(18, 6))
    ax = plt.gca()

    # --- violin ---
    # Use bucket_index as categorical x; dodge=True will place hue categories side-by-side
    sns.violinplot(
        data=query_stats,
        x="time_bucket",
        y=query_stats["span"] / 1000.0,
        hue="status",
        split=True,
        dodge=True,
        inner="quartile",
        scale="width",
        width=0.8,
        cut=0,
        ax=ax,
    )

    ax.set_xlabel(f"Time Buckets {time_bucket_size}")
    ax.set_yscale("log")  # log scale for span
    ax.set_ylabel("Query Time (millisecond)")

    # x axis ticks/labels
    ax.set_xticks(np.arange(num_time_buckets))
    ax.set_xticklabels(np.arange(num_time_buckets))

    # If there are too many ticks, thin them out to at most max_ticks
    # max_ticks = 20
    # if n_bins > max_ticks:
    #     step = max(1, n_bins // max_ticks)
    #     thin_positions = np.arange(0, n_bins, step)
    #     ax.set_xticks(thin_positions)
    #     ax.set_xticklabels([bin_labels[i] for i in thin_positions], rotation=45, ha="right")

    # --- bar (counts) on secondary y-axis ---
    ax2 = ax.twinx()
    x_pos = np.arange(num_time_buckets)
    bar_width = 0.6
    ax2.bar(x_pos, counts, width=bar_width, alpha=0.25, color="gray", zorder=0)
    ax2.set_ylabel("#Queries")

    # Keep a single legend for the violin hue
    # seaborn often creates its own legend; we collect legend handles from the violin axis
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(handles, labels, title="status", loc="upper right")
    else:
        # fallback: let matplotlib place the default legend
        ax.legend(title="status", loc="upper right")

    plt.title("Query counts (bar) + SAT/UNSAT violin of query Time")
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()


if __name__ == "__main__":
    cli()
