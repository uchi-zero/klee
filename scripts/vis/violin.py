# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "matplotlib",
#     "pandas",
#     "seaborn",
# ]
# ///
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

klee_stats_file = "lua-1.csv"
query_stats_file = "z3-lua.csv"
time_bucket_size = "30min"

# read query stats
# expected columns: timestamp (seconds since epoch), status (e.g. SAT/UNSAT), span (microseconds)
query_stats = pd.read_csv(query_stats_file, header=None, names=["timestamp", "status", "span"])

# convert microsecond to millisecond
query_stats["span"] = query_stats["span"] / 1_000.0

# convert the timestamp to datetime and floor to 30-minute bin
query_stats["datetime"] = pd.to_datetime(query_stats["timestamp"], unit="s")
query_stats["time_bucket"] = query_stats["datetime"].dt.floor(time_bucket_size)

# map the time buckets to the index (0,1,2,...)
time_buckets = sorted(query_stats["time_bucket"].unique())
bin_index_map = {t: i for i, t in enumerate(time_buckets)}
query_stats["bucket_index"] = query_stats["time_bucket"].map(bin_index_map)

# count the samples of each bucket (used for the bar)
counts = (
    query_stats.groupby("bucket_index")
    .size()
    .reindex(range(len(time_buckets)), fill_value=0)
    .values
)

# prepare labels for x-axis
bin_labels = [t.strftime("%Y-%m-%d %H:%M") for t in time_buckets]

# violin + bar
plt.figure(figsize=(18, 6))
ax = plt.gca()

# --- violin ---
# Use bucket_index as categorical x; dodge=True will place hue categories side-by-side
sns.violinplot(
    data=query_stats,
    x="bucket_index",
    y="span",
    hue="status",
    split=True,      # we want side-by-side violins (not half/half)
    dodge=True,       # ensures hue levels are placed side-by-side
    inner="quartile", # show median and quartiles
    scale="width",
    width=0.8,
    cut=0,
    ax=ax,
)

ax.set_xlabel(f"Time Buckets {time_bucket_size}")
ax.set_yscale("log")  # log scale for span
ax.set_ylabel("Query Time (millisecond)")

# x axis ticks/labels
n_bins = len(time_buckets)
ax.set_xticks(np.arange(n_bins))
ax.set_xticklabels(np.arange(n_bins))

# If there are too many ticks, thin them out to at most max_ticks
max_ticks = 20
if n_bins > max_ticks:
    step = max(1, n_bins // max_ticks)
    thin_positions = np.arange(0, n_bins, step)
    ax.set_xticks(thin_positions)
    ax.set_xticklabels([bin_labels[i] for i in thin_positions], rotation=45, ha="right")

# --- bar (counts) on secondary y-axis ---
ax2 = ax.twinx()
x_pos = np.arange(n_bins)
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

plt.title("Lua: query counts (bar) + SAT/UNSAT violin of query Time")
plt.tight_layout()
plt.savefig("violin.png")
plt.close()
