#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib"]
# ///

"""
Incremental KLEE coverage (post-run), resampled to a fixed time grid.

Outputs under <outdir>/coverage/:
  - coverage_by_event.csv                    # one row per event (per ktest or group)
  - coverage_by_interval_<N>min.csv         # resampled every N minutes (default 20)
  - coverage_by_interval.png                # plot of the resampled series
  - coverage.profdata                       # final cumulative profile
  - profraw/                                # raw profiles produced during replay
"""

import argparse, csv, json, os, subprocess, sys, math
from datetime import datetime, timezone
from pathlib import Path

# ---------- helpers ----------

def run(cmd, check=True, env=None, capture=True, decode=True):
    """
    Run a command with flexible stdout/stderr handling.

    capture=True  -> collect stdout/stderr
    decode=True   -> return text (UTF-8, 'replace' errors)
    capture=False -> discard stdout/stderr (no decoding, faster)
    """
    kwargs = dict(check=False, env=env)
    if capture:
        if decode:
            kwargs.update(capture_output=True, text=True, encoding="utf-8", errors="replace")
        else:
            kwargs.update(capture_output=True)  # bytes in p.stdout/p.stderr
    else:
        kwargs.update(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    p = subprocess.run(cmd if isinstance(cmd, list) else cmd.split(), **kwargs)
    if check and p.returncode != 0:
        out = getattr(p, "stdout", b"")
        err = getattr(p, "stderr", b"")
        try: out = out.decode("utf-8", "replace") if isinstance(out, (bytes, bytearray)) else out
        except Exception: pass
        try: err = err.decode("utf-8", "replace") if isinstance(err, (bytes, bytearray)) else err
        except Exception: pass
        raise RuntimeError(f"cmd failed ({p.returncode}): {cmd}\nOUT:\n{out}\nERR:\n{err}")
    return p

def list_ktests(outdir: Path, skip_early: bool):
    keep = []
    for k in sorted(outdir.glob("test*.ktest")):
        # optionally skip early-termination markers (testXXXXXX.early)
        if skip_early and k.with_suffix(".early").exists():
            continue
        keep.append(k)
    return keep

def mtime(path: Path) -> float:
    return path.stat().st_mtime

def export_totals(llvm_cov: str, target: Path, profdata: Path):
    # Prefer JSON export when available
    p = run([llvm_cov, "export", f"--instr-profile={profdata}", str(target)], check=False)
    if p.returncode == 0:
        data = json.loads(p.stdout)
        lines = data.get("data", [{}])[0].get("totals", {}).get("lines", {})
        return dict(covered=int(lines.get("covered",0)),
                    count=int(lines.get("count",0)),
                    percent=float(lines.get("percent",0.0)))
    # Fallback: parse text table
    p = run([llvm_cov, "report", str(target), f"-instr-profile={profdata}"], check=True)
    total = next((ln for ln in p.stdout.splitlines() if ln.strip().startswith("TOTAL")), None)
    nums  = [x for x in total.replace('%','').split() if x.replace('.','',1).isdigit()]
    covered, total_lines, pct = map(float, nums[-3:])
    return dict(covered=int(covered), count=int(total_lines), percent=float(pct))

def merge_prof(llvm_profdata: str, inputs, out: Path):
    run([llvm_profdata, "merge", "-sparse", *map(str, inputs), "-o", str(out)], check=True)

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description="Incremental coverage + fixed-interval resample.")
    ap.add_argument("--target", required=True, help="Instrumented native binary (built with -fprofile-instr-generate -fcoverage-mapping)")
    ap.add_argument("--outdir", required=True, help="KLEE output dir containing test*.ktest")
    ap.add_argument("--group-sec", type=float, default=0.0,
                    help="Group ktests by this bucket size in seconds; 0 = one event per ktest.")
    ap.add_argument("--interval-min", type=float, default=20.0,
                    help="Resample interval in minutes for the final plot/CSV (default 20).")
    ap.add_argument("--klee-replay", default="klee-replay")
    ap.add_argument("--llvm-profdata", default="llvm-profdata")
    ap.add_argument("--llvm-cov", default="llvm-cov")
    ap.add_argument("--skip-early-markers", action="store_true",
                    help="If set, skip ktests that have a sibling testXXXXXX.early marker.")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()

    target  = Path(args.target).resolve()
    outdir  = Path(args.outdir).resolve()
    covdir  = outdir / "coverage"
    profraw = covdir / "profraw"
    covdir.mkdir(exist_ok=True); profraw.mkdir(exist_ok=True)

    # 1) Discover tests and choose t0 (assembly.ll or earliest test)
    tests = list_ktests(outdir, args.skip_early_markers)
    if not tests:
        print("[inc] no ktests found"); return
    tests = sorted(tests, key=mtime)
    asm = outdir / "assembly.ll"
    earliest_test_ts = tests[0].stat().st_mtime
    t0 = min((asm.stat().st_mtime if asm.exists() else earliest_test_ts), earliest_test_ts)

    # 2) Build groups: per-ktest or by time bucket
    groups = []  # list[(elapsed_sec, [tests...])]
    if args.group_sec <= 0.0:
        for t in tests:
            groups.append((mtime(t) - t0, [t]))
    else:
        from collections import defaultdict
        buckets = defaultdict(list)
        for t in tests:
            dt = mtime(t) - t0
            k  = math.floor(dt / args.group_sec) * args.group_sec
            buckets[k].append(t)
        for k in sorted(buckets.keys()):
            groups.append((k, buckets[k]))

    # 3) Incremental merge and event CSV
    tmp = covdir / "tmp"; tmp.mkdir(exist_ok=True)
    cum_prof = None
    event_csv = covdir / "coverage_by_event.csv"
    baseline_written = False

    with open(event_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_iso","elapsed_sec","covered_lines","total_lines","percent"])
        for elapsed, ts in groups:
            # replay ONLY the tests in this group; do NOT capture/decode output
            raws_this = []
            for t in ts:
                pat = str(profraw / f"{t.name}-%p.profraw")
                env = os.environ.copy(); env["LLVM_PROFILE_FILE"] = pat
                run([args.klee_replay, str(target), str(t)], check=False, env=env, capture=False)
                raws_this += sorted(profraw.glob(f"{t.name}-*.profraw"))
            if not raws_this:
                continue

            # merge group's raw -> bucket.profdata
            bucket_prof = tmp / f"bucket_{int(round(elapsed*1e6))}.profdata"
            merge_prof(args.llvm_profdata, raws_this, bucket_prof)

            # cumulative = merge(previous cumulative, bucket)
            if cum_prof is None:
                cum_prof = tmp / f"cum_{int(round(elapsed*1e6))}.profdata"
                merge_prof(args.llvm_profdata, [bucket_prof], cum_prof)
            else:
                new_cum = tmp / f"cum_{int(round(elapsed*1e6))}.profdata"
                merge_prof(args.llvm_profdata, [cum_prof, bucket_prof], new_cum)
                cum_prof = new_cum

            # coverage totals for this cumulative state
            totals = export_totals(args.llvm_cov, target, cum_prof)

            # baseline (0,0) at t0 in the event CSV
            if not baseline_written:
                w.writerow([
                    datetime.fromtimestamp(t0, timezone.utc).isoformat(),
                    f"{0.0:.6f}", 0, totals["count"], "0.00",
                ])
                baseline_written = True

            ts_abs = t0 + elapsed
            w.writerow([datetime.fromtimestamp(ts_abs, timezone.utc).isoformat(),
                        f"{elapsed:.6f}", totals["covered"], totals["count"],
                        f"{totals['percent']:.2f}"])

    if cum_prof:
        try: os.replace(cum_prof, covdir / "coverage.profdata")
        except Exception: pass

    # 4) RESAMPLE to fixed cadence (covered lines), appending a final sample at last_t
    step_sec = max(1.0, args.interval_min * 60.0)  # guard

    # Load event curve (elapsed_sec, covered_lines)
    events = []
    with open(event_csv, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            events.append((float(row["elapsed_sec"]), int(row["covered_lines"])))
    events.sort()

    # Sentinel baseline strictly before 0 so the first grid sample stays at 0
    EPS = 1e-6
    events.insert(0, (-EPS, 0))

    last_t = events[-1][0]
    # Grid: 0, step, 2*step, ..., floor(last_t/step)*step
    num_steps = int(math.floor(max(0.0, last_t) / step_sec))
    grid = [i * step_sec for i in range(num_steps + 1)]

    # Right-continuous step with strict '<' so t=0 samples 0, not an event at 0.0
    resampled = []
    j = 0
    cur_cov = 0
    for g in grid:
        while j < len(events) and events[j][0] < g - 1e-12:
            cur_cov = events[j][1]
            j += 1
        resampled.append((g, cur_cov))

    # Append a final sample at last_t if it's not exactly on the grid
    if not grid or last_t > grid[-1] + 1e-12:
        while j < len(events) and events[j][0] <= last_t + 1e-12:
            cur_cov = events[j][1]
            j += 1
        resampled.append((last_t, cur_cov))

    # Write resampled CSV (elapsed in hours)
    res_csv = covdir / f"coverage_by_interval_{int(args.interval_min)}min.csv"
    with open(res_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["elapsed_hours","covered_lines"])
        for g, cov in resampled:
            w.writerow([f"{g/3600.0:.6f}", cov])

    # 5) Plot (resampled)
    if not args.no_plot:
        try:
            import matplotlib; matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            xs_hr = [g/3600.0 for g,_ in resampled]
            ys_ln = [cov for _,cov in resampled]

            # ensure an explicit (0,0) in the plotted series
            if not xs_hr or xs_hr[0] > 0.0:
                xs_hr.insert(0, 0.0); ys_ln.insert(0, 0)

            plt.figure(figsize=(7,4))
            plt.step(xs_hr, ys_ln, where="post", linewidth=1.8)
            plt.scatter(xs_hr, ys_ln, s=14, zorder=3)

            xmax = max(xs_hr) if xs_hr else 0.0
            ymax = max(ys_ln) if ys_ln else 0
            # small padding so origin point is not glued to axes
            x_pad = max(0.05, 0.02 * (xmax if xmax > 0 else 1.0))   # hours
            y_pad = max(50, int(0.03 * (ymax if ymax > 0 else 1)))  # lines
            plt.xlim(left=-x_pad)
            plt.ylim(bottom=-y_pad)

            # X ticks: 0,2,4,6,... up to cover data
            tick_max = max(6.0, 2.0 * math.ceil((xmax if xmax > 0 else 0)/2.0))
            xticks = [2.0 * i for i in range(int(tick_max/2.0) + 1)]
            plt.xticks(xticks)

            # Y ticks: every 500 lines
            step = 500
            ytick_max = int(math.ceil(max(1, ymax) / step) * step)
            yticks = list(range(0, ytick_max + step, step))
            plt.yticks(yticks)

            plt.xlabel("Time (hour)")
            plt.ylabel("Covered Lines")
            plt.title(outdir.name)
            plt.grid(True, alpha=0.35)
            plt.tight_layout()
            plt.savefig(covdir / "coverage_by_interval.png")
            plt.close()
        except Exception as e:
            sys.stderr.write(f"[inc] WARN: plotting failed: {e}\n")

    print(f"[inc] wrote {event_csv} and {res_csv}")

if __name__ == "__main__":
    main()
