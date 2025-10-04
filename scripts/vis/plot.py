# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "matplotlib",
#     "pandas",
# ]
# ///

# this script takes a csv file as input and plots it

import matplotlib.pyplot as plt
import pandas as pd

klee_stats_file = "lua-1.csv"
query_stats_file = "z3-lua.csv"
time_bucket_size = "30min"

klee_stats = pd.read_csv(klee_stats_file)
klee_stats = klee_stats.iloc[1::2].copy() # every 30 mins

# calculate delta columns
klee_stats["DeltaSolverQueries"] = klee_stats["SolverQueries"].diff()
klee_stats["DeltaTerminationSolverError"] = klee_stats["TerminationSolverError"].diff()
klee_stats["DeltaTerminationProgramError"] = klee_stats["TerminationProgramError"].diff()

# add delta columns
first_idx = klee_stats.index[0]
klee_stats.loc[first_idx, "DeltaSolverQueries"] = klee_stats.loc[first_idx, "SolverQueries"]
klee_stats.loc[first_idx, "DeltaTerminationSolverError"] = klee_stats.loc[first_idx, "TerminationSolverError"]
klee_stats.loc[first_idx, "DeltaTerminationProgramError"] = klee_stats.loc[first_idx, "TerminationProgramError"]

# add coverage column
klee_stats["InstructionCoverage"] = klee_stats["CoveredInstructions"] / (klee_stats["CoveredInstructions"] + klee_stats["UncoveredInstructions"])
klee_stats["BranchCoverage"] = klee_stats["FullBranches"] / klee_stats["NumBranches"]

query_stats = pd.read_csv(query_stats_file, header=None, names=["timestamp", "status", "span"])

# convert the timestamp to datetime and floor to 30-minute bin
query_stats["datetime"] = pd.to_datetime(query_stats["timestamp"], unit="s")
query_stats["time_bucket"] = query_stats["datetime"].dt.floor(time_bucket_size)

# map the time buckets to the index (0,1,2,...)
time_buckets = sorted(query_stats["time_bucket"].unique())
bin_index_map = {t: i for i, t in enumerate(time_buckets)}
query_stats["bucket_index"] = query_stats["time_bucket"].map(bin_index_map)

klee_stats["DeltaSATQueries"] = (
    query_stats[query_stats["status"] == "sat"]
    .groupby("bucket_index")
    .size()
    .reindex(range(len(klee_stats)), fill_value=0)
    .values
)

# --- 绘图 ---
x = list(range(len(klee_stats)))
fig, ax1 = plt.subplots(figsize=(12, 6))
ax2 = ax1.twinx()
width = 0.6

# 四段堆叠柱：solver_err, prog_err, sat, unsat
solver_err = klee_stats["DeltaTerminationSolverError"].values
prog_err = klee_stats["DeltaTerminationProgramError"].values
sat = klee_stats["DeltaSATQueries"].values
unsat = (klee_stats["DeltaSolverQueries"] - klee_stats["DeltaTerminationSolverError"] - klee_stats["DeltaTerminationProgramError"] - klee_stats["DeltaSATQueries"]).values

b1 = ax1.bar(x, solver_err, width, label="TerminationSolverError")
b2 = ax1.bar(x, prog_err, width, bottom=solver_err, label="TerminationProgramError")
bottom_2 = solver_err + prog_err
b3 = ax1.bar(x, sat, width, bottom=bottom_2, label="Sat")
bottom_3 = bottom_2 + sat
b4 = ax1.bar(x, unsat, width, bottom=bottom_3, label="Unsat")

ax1.set_xlabel("Time buckets")
ax1.set_ylabel("#Queries")

# 右轴 coverage 折线
inscov = klee_stats["InstructionCoverage"].values
brcov = klee_stats["BranchCoverage"].values
l1, = ax2.plot(x, inscov, marker="o", linewidth=2, label="InstructionCoverage")
l2, = ax2.plot(x, brcov, marker="s", linewidth=2, label="BranchCoverage")
ax2.set_ylabel("Coverage")

# 合并图例
handles = [b1, b2, b3, b4, l1, l2]
labels = ["Timeout", "ProgramError", "Sat", "Unsat", "InstructionCoverage", "BranchCoverage"]
ax1.legend(handles, labels, loc="upper left")

ax1.set_xticks(x)

plt.title("Stacked solver queries (bars) and coverage (lines)")
plt.tight_layout()
plt.savefig("plot.png")
