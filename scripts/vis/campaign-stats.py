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
import click

klee_stats_file = "lua-1.csv"
query_stats_file = "z3-lua.csv"
time_bucket_size = "30min"


def match_col_name(col_name: str) -> bool:
    if col_name == "SolverQueries":
        return True
    return False


@click.group()
def cli():
    """Main CLI."""
    pass


def preprocess(klee_stats_file: str, time_bucket_size: str):
    klee_stats = pd.read_csv(klee_stats_file)

    # convert the timestamp to datetime and floor to time bucket size
    klee_stats["WallTime"] = pd.to_timedelta(klee_stats["WallTime"], unit="us")
    klee_stats["TimeBucket"] = klee_stats["WallTime"].dt.floor(time_bucket_size)
    # For each time bucket, pick the row with the maximum WallTime (i.e., last in that bucket)
    last_idx = klee_stats.groupby("TimeBucket", sort=False)["WallTime"].idxmax()
    klee_stats = klee_stats.loc[last_idx]

    # Ensure continuous time buckets with no gaps
    min_bucket = klee_stats["TimeBucket"].min()
    max_bucket = klee_stats["TimeBucket"].max()
    all_buckets = pd.timedelta_range(
        start=min_bucket, end=max_bucket, freq=time_bucket_size
    )

    # Create a complete range of time buckets and reindex
    klee_stats = (
        klee_stats.set_index("TimeBucket").reindex(all_buckets).fillna(0).reset_index()
    )

    # Map time buckets to sequential numbers from 0
    klee_stats["TimeBucketNumber"] = range(len(klee_stats))
    # Create delta columns for columns matching pattern
    for col in klee_stats.columns:
        if match_col_name(col):
            delta_col_name = f"Delta{col}"
            klee_stats[delta_col_name] = klee_stats[col].diff()
            klee_stats.loc[0, delta_col_name] = klee_stats[col].iloc[0]

    print(klee_stats.head())

    return klee_stats


@cli.command()
@click.option("--time-bucket-size", type=str, default="30min")
@click.argument("klee_stats_file", type=click.Path(exists=True))
@click.argument("output_file", type=click.Path(exists=False))
def bar(klee_stats_file: str, time_bucket_size: str, output_file: str):
    klee_stats = preprocess(klee_stats_file, time_bucket_size)
    # Plot bar chart for each column matching pattern
    sns.barplot(x="TimeBucketNumber", y="DeltaSolverQueries", data=klee_stats)
    plt.xticks(rotation=-45)
    plt.savefig(output_file)


if __name__ == "__main__":
    cli()
