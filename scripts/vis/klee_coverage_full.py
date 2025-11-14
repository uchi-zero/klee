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
# -*- coding: utf-8 -*-
#
# klee_coverage_full.py
#
# Combined script:
#   1) Replays KLEE ktests into llvm-profraw, incrementally merges via llvm-profdata,
#      and writes group-only coverage_by_group.csv with all llvm-cov summary metrics.
#   2) Resamples coverage_by_group.csv onto a fixed time grid and writes per-kind
#      coverage CSVs (function/line/region/branch/inst).
#
# Outputs under <outdir>/coverage/:
#   - coverage_by_group.csv
#   - coverage.profdata
#   - profraw/
#   - resampled/
#       function_coverage.csv
#       line_coverage.csv
#       region_coverage.csv
#       branch_coverage.csv
#       inst_coverage.csv
#
# Resampling semantics (LOCF):
#   - Grid every --resample-step seconds (default 1200s = 20 min) from 0 to
#     ceil(max_elapsed/step)*step.
#   - elapsed_sec = 0 always uses the earliest row (baseline).
#   - For T > 0, we use the most recent row with elapsed_sec <= T.
#   - If no such row exists (shouldn’t happen if baseline exists), we use the earliest row.
#
# ------------------------------------------------------------------------------

import argparse
import csv
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------- generic helpers ----------

def run(cmd, check=True, env=None, capture=True, decode=True):
    """Run a command with flexible stdout/stderr handling."""
    kwargs = dict(check=False, env=env)
    if capture:
        if decode:
            kwargs.update(capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
        else:
            kwargs.update(capture_output=True)  # bytes
    else:
        kwargs.update(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    p = subprocess.run(cmd if isinstance(cmd, list) else cmd.split(), **kwargs)
    if check and p.returncode != 0:
        out = getattr(p, "stdout", "")
        err = getattr(p, "stderr", "")
        if isinstance(out, (bytes, bytearray)):
            try:
                out = out.decode("utf-8", "replace")
            except Exception:
                pass
        if isinstance(err, (bytes, bytearray)):
            try:
                err = err.decode("utf-8", "replace")
            except Exception:
                pass
        raise RuntimeError(f"cmd failed ({p.returncode}): {cmd}\nOUT:\n{out}\nERR:\n{err}")
    return p

def list_ktests(outdir: Path, skip_early: bool, ktest_suffix: str):
    """
    Return ktests matching test*.ktest<SUFFIX> (or exactly .ktest if SUFFIX='').
    Example: ktest_suffix='.A_data' -> matches 'testXXXXX.ktest.A_data'.
    """
    suf = (ktest_suffix or "")
    if suf and not suf.startswith("."):
        suf = "." + suf
    pattern = f"test*.ktest{suf}" if suf else "test*.ktest"
    keep = []
    for k in sorted(outdir.glob(pattern)):
        if skip_early:
            # works for plain .ktest names (testXXXXXX.early); if you use extra suffixes,
            # disable this flag.
            if k.with_suffix(".early").exists():
                continue
        keep.append(k)
    return keep

def mtime(path: Path) -> float:
    return path.stat().st_mtime

def nproc() -> int:
    return max(1, os.cpu_count() or 1)

def merge_prof_chunked(llvm_profdata: str, inputs, out: Path,
                       tmpdir: Path, chunk_size: int, threads: int):
    """
    Merge potentially many profile inputs by chunking to keep latency/memory reasonable.
    inputs: iterable of file Paths (e.g., .profraw or .profdata)
    Produces 'out'.
    """
    inputs = [str(x) for x in inputs]
    if not inputs:
        raise RuntimeError("merge_prof_chunked: empty inputs")

    tmpdir.mkdir(parents=True, exist_ok=True)
    if len(inputs) <= chunk_size:
        cmd = [llvm_profdata, "merge", "-sparse",
               f"--num-threads={threads}", *inputs, "-o", str(out)]
        run(cmd, check=True, capture=False)
        return

    # First-stage partials
    partials = []
    for i in range(0, len(inputs), chunk_size):
        part = tmpdir / f"part_{i // chunk_size:04d}.profdata"
        chunk = inputs[i:i + chunk_size]
        cmd = [llvm_profdata, "merge", "-sparse",
               f"--num-threads={threads}", *chunk, "-o", str(part)]
        run(cmd, check=True, capture=False)
        partials.append(str(part))

    # Merge partials into final
    cmd = [llvm_profdata, "merge", "-sparse",
           f"--num-threads={threads}", *partials, "-o", str(out)]
    run(cmd, check=True, capture=False)

def _mk_metric(d):
    return {
        "covered": int(d.get("covered", 0) or 0),
        "count":   int(d.get("count", 0) or 0),
        "percent": float(d.get("percent", 0.0) or 0.0),
    }

def export_summary_all(llvm_cov: str, target: Path, profdata: Path):
    """Return totals for functions/lines/regions/branches/(instantiations).

    If llvm-cov reports 'No coverage data found', we treat everything as zero
    and print a warning instead of throwing. This keeps the script running,
    but you should fix instrumentation/replay if you see this frequently.
    """
    def zero_totals():
        return {
            "functions":      {"covered": 0, "count": 0, "percent": 0.0},
            "lines":          {"covered": 0, "count": 0, "percent": 0.0},
            "regions":        {"covered": 0, "count": 0, "percent": 0.0},
            "branches":       {"covered": 0, "count": 0, "percent": 0.0},
            "instantiations": {"covered": 0, "count": 0, "percent": 0.0},
        }

    # --- JSON export (preferred) ---
    p = run(
        [llvm_cov, "export", "--summary-only",
         f"--instr-profile={profdata}", str(target)],
        check=False
    )

    if p.returncode == 0:
        data = json.loads(p.stdout)
        totals = (data.get("data") or [{}])[0].get("totals", {}) or {}
        return {
            "functions":      _mk_metric(totals.get("functions", {})),
            "lines":          _mk_metric(totals.get("lines", {})),
            "regions":        _mk_metric(totals.get("regions", {})),
            "branches":       _mk_metric(totals.get("branches", {})),
            "instantiations": _mk_metric(totals.get("instantiations", {})),
        }

    err_text = (p.stderr or "").strip()
    if "No coverage data found" in err_text:
        print(
            f"[warn] llvm-cov export: no coverage data found for {target} "
            f"with profile {profdata}; treating totals as zero.",
            file=sys.stderr,
        )
        return zero_totals()

    # --- Text summary fallback ---
    p = run(
        [llvm_cov, "report", "--summary-only",
         f"--instr-profile={profdata}", str(target)],
        check=False
    )
    if p.returncode == 0:
        rows = [ln.rstrip("\n") for ln in p.stdout.splitlines() if ln.strip()]
        hdr_idx = next((i for i, ln in enumerate(rows)
                        if "Filename" in ln and "Coverage" in ln), None)
        tot_idx = next((i for i, ln in enumerate(rows)
                        if ln.strip().startswith("TOTAL")), None)
        if hdr_idx is None or tot_idx is None:
            raise RuntimeError("Failed to parse llvm-cov report summary-only output")
        header = re.split(r"\s{2,}", rows[hdr_idx].strip())
        total_cols = re.split(r"\s{2,}", rows[tot_idx].strip())

        colmap = {}
        for h, v in zip(header[1:], total_cols[1:]):  # skip first column
            colmap[h] = v

        def parse_cov(s):
            m = re.search(r"\((\d+)\s*/\s*(\d+)\)", s or "")
            pctm = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", s or "")
            covered = int(m.group(1)) if m else 0
            count   = int(m.group(2)) if m else 0
            percent = float(pctm.group(1)) if pctm else (100.0 * covered / count if count else 0.0)
            return {"covered": covered, "count": count, "percent": percent}

        return {
            "functions":      parse_cov(colmap.get("Function Coverage", "")),
            "lines":          parse_cov(colmap.get("Line Coverage", "")),
            "regions":        parse_cov(colmap.get("Region Coverage", "")),
            "branches":       parse_cov(colmap.get("Branch Coverage", "")),
            "instantiations": parse_cov(colmap.get("Instantiation Coverage", "")),
        }

    err_text = (p.stderr or "").strip()
    if "No coverage data found" in err_text:
        print(
            f"[warn] llvm-cov report: no coverage data found for {target} "
            f"with profile {profdata}; treating totals as zero.",
            file=sys.stderr,
        )
        return zero_totals()

    # If we get here, it's some other llvm-cov failure
    raise RuntimeError(
        f"llvm-cov failed for {target} with profile {profdata}:\n{p.stderr}"
    )

# ---------- timeout helpers ----------

def find_timeout_bin():
    for name in ("timeout", "/usr/bin/timeout"):
        p = shutil.which(name) if name == "timeout" else (
            name if os.path.exists(name) else None
        )
        if p:
            return p
    return None

def replay_with_timeout(cmd, env, timeout_bin, timeout_sec, kill_after_sec):
    """
    Run klee-replay with either external 'timeout' (preferred) or Python fallback.
    Returns (returncode, timed_out: bool).
    """
    if timeout_bin:
        full = [
            timeout_bin,
            f"--kill-after={int(kill_after_sec)}s",
            f"{int(timeout_sec)}s",
            *cmd,
        ]
        p = subprocess.run(
            full, env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return p.returncode, (p.returncode in (124, 137))

    # Python fallback
    try:
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
        try:
            rc = proc.wait(timeout=timeout_sec)
            return rc, False
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except Exception:
                pass
            try:
                proc.wait(timeout=kill_after_sec)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except Exception:
                    pass
            return 124, True
    except Exception:
        return 1, False

# ---------- progress line ----------

def progress_line(done: int, total: int, current: str,
                  timeouts: int, failures: int):
    """Single-line progress like:
       [replay] 6282/15000 (41.9%)  test006282.ktest  timeouts=12 failed=3
    """
    pct = (100.0 * done / total) if total else 0.0
    cur = Path(current).name if current else ""
    msg = f"[replay] {done}/{total} ({pct:5.1f}%)  {cur}  timeouts={timeouts} failed={failures}"
    try:
        cols = shutil.get_terminal_size(fallback=(120, 20)).columns
    except Exception:
        cols = 120
    line = ("\r" + msg)[: max(1, cols - 1)]
    sys.stdout.write(line.ljust(cols - 1))
    sys.stdout.flush()

# ---------- resampling helpers (LOCF, csv-based) ----------

COVERAGE_KINDS = {
    "function": ("func_covered", "func_total", "func_percent"),
    "line":     ("line_covered", "line_total", "line_percent"),
    "region":   ("region_covered", "region_total", "region_percent"),
    "branch":   ("branch_covered", "branch_total", "branch_percent"),
    "inst":     ("inst_covered", "inst_total", "inst_percent"),
}

def _resample_locf_rows(rows, step: int):
    """LOCF resampling on elapsed_sec using a fixed grid.

    rows: list[dict] where dict["elapsed_sec"] is a float-ish string.
    step: grid step in seconds (int).

    Semantics:
    - We always keep the first row (baseline) at time 0.
    - For later grid points T > 0, we use the last row with elapsed_sec <= T.
    """
    if not rows:
        return []

    # Sort by elapsed_sec but keep original order for ties
    def _as_float(r):
        try:
            return float(r.get("elapsed_sec", 0.0))
        except Exception:
            return 0.0

    rows_sorted = sorted(rows, key=_as_float)
    max_t = max(_as_float(r) for r in rows_sorted)
    if step <= 0:
        raise ValueError("resample step must be > 0")

    # Grid: 0, step, 2*step, ..., ceil(max_t/step)*step
    last_grid = int(math.ceil(max_t / step) * step)
    grid_times = [0] + [t for t in range(step, last_grid + 1, step)]

    out_rows = []
    i = 0  # index into rows_sorted

    for idx_t, t in enumerate(grid_times):
        if idx_t == 0:
            # For time 0, force the *first* row (baseline),
            # even if there are multiple rows at elapsed_sec == 0.
            i = 0
        else:
            # For T > 0, advance i while next sample is still <= T (standard LOCF).
            while i + 1 < len(rows_sorted):
                next_t = _as_float(rows_sorted[i + 1])
                if next_t <= t + 1e-9:
                    i += 1
                else:
                    break

        base = rows_sorted[i]
        new = dict(base)
        new["elapsed_sec"] = f"{float(t):.6f}"
        out_rows.append(new)

    return out_rows

def resample_and_split(coverage_csv: Path, out_dir: Path, step: int):
    """Resample coverage_by_group.csv and write per-kind CSVs."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # Read all rows
    with coverage_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    if not rows:
        print("[resample] input coverage CSV is empty; nothing to do")
        return

    # Validate columns
    required = {"elapsed_sec"}
    for cols in COVERAGE_KINDS.values():
        required.update(cols)
    missing = [c for c in required if c not in fieldnames]
    if missing:
        raise RuntimeError(f"[resample] Missing required columns: {missing}")

    # Resample with LOCF
    resampled_rows = _resample_locf_rows(rows, step)

    outputs = {}

    for kind, cols in COVERAGE_KINDS.items():
        out_path = out_dir / f"{kind}_coverage.csv"
        with out_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["elapsed_sec", *cols])
            for r in resampled_rows:
                w.writerow([r["elapsed_sec"], r[cols[0]], r[cols[1]], r[cols[2]]])
        outputs[kind] = out_path

    print("[resample] wrote per-kind coverage CSVs:")
    for k, p in outputs.items():
        print(f"  {k:8s}: {p}")

    print("\n[resample] Approximation method:")
    print(f"- Fixed grid every {step} seconds.")
    print("- At each grid time T, use the most recent row with elapsed_sec <= T (LOCF).")
    print("- At time 0, we use the earliest row (baseline).")

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(
        description=(
            "KLEE coverage tracker:\n"
            "  - Replays ktests + merges profiles into coverage_by_group.csv\n"
            "  - Optionally resamples & splits into per-kind coverage CSVs"
        )
    )
    ap.add_argument("--target", required=True,
                    help="Instrumented native binary (-fprofile-instr-generate -fcoverage-mapping)")
    ap.add_argument("--outdir", required=True,
                    help="KLEE output dir containing test*.ktest")
    ap.add_argument("--group-sec", type=float, default=0.0,
                    help="Group ktests by this bucket size in seconds; 0 = one event per ktest.")
    ap.add_argument("--klee-replay", default="klee-replay")
    ap.add_argument("--llvm-profdata", default="llvm-profdata")
    ap.add_argument("--llvm-cov", default="llvm-cov")
    ap.add_argument("--skip-early-markers", action="store_true",
                    help="Skip ktests that have a sibling testXXXXXX.early marker.")
    ap.add_argument("--ktest-suffix", default="",
                    help="Additional suffix after .ktest to match (e.g., '.A_data'). Default: ''")

    # Latency knobs
    ap.add_argument("--per-test-timeout-sec", type=float, default=15.0,
                    help="Timeout per klee-replay (seconds).")
    ap.add_argument("--kill-after-sec", type=float, default=2.0,
                    help="SIGKILL after this many seconds if SIGTERM didn’t stop the replay.")
    ap.add_argument("--make-no-exec", action="store_true",
                    help="Set MAKEFLAGS='-n' during replay to avoid executing recipes.")
    ap.add_argument("--merge-chunk-size", type=int, default=5000,
                    help="Max inputs per llvm-profdata merge chunk.")
    ap.add_argument("--num-threads", type=int, default=0,
                    help="Threads for llvm-profdata merges (0 = use CPU count).")

    # Resampling knobs
    ap.add_argument("--no-resample", action="store_true",
                    help="Skip splitting/resampling coverage_by_group.csv.")
    ap.add_argument("--resample-step", type=int, default=1200,
                    help="Grid step in seconds for resampling (default 1200 = 20 min).")
    ap.add_argument("--resample-out", default=None,
                    help="Directory for per-kind resampled CSVs "
                         "(default: <outdir>/coverage/resampled).")

    args = ap.parse_args()

    target  = Path(args.target).resolve()
    outdir  = Path(args.outdir).resolve()
    covdir  = outdir / "coverage"
    profraw = covdir / "profraw"
    tmpdir  = covdir / "tmp"
    covdir.mkdir(exist_ok=True)
    profraw.mkdir(exist_ok=True)
    tmpdir.mkdir(exist_ok=True)

    # 1) Discover tests and t0
    tests = list_ktests(outdir, args.skip_early_markers, args.ktest_suffix)
    if not tests:
        print("[group] no ktests found")
        return 0

    tests = sorted(tests, key=mtime)
    asm = outdir / "assembly.ll"
    earliest_test_ts = tests[0].stat().st_mtime
    t0 = min(
        (asm.stat().st_mtime if asm.exists() else earliest_test_ts),
        earliest_test_ts
    )

    # 2) Build groups
    groups = []
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

    # Total count for progress
    total_tests = sum(len(ts) for _, ts in groups)
    print(f"[replay] starting replays into {profraw}")
    progress_line(0, total_tests, "", 0, 0)

    # 3) Incremental merge and CSV
    cum_prof = None
    csv_path = covdir / "coverage_by_group.csv"
    baseline_written = False
    timeout_bin = find_timeout_bin()
    threads = (nproc() if args.num_threads in (0, None) else max(1, args.num_threads))

    timed_out_log = profraw / ".timed_out"
    failed_log    = profraw / ".failed"

    total_replayed = 0
    total_timeouts = 0
    total_failed   = 0

    with csv_path.open("w", newline="", encoding="utf-8") as fcsv, \
         timed_out_log.open("w", encoding="utf-8") as tlog, \
         failed_log.open("w", encoding="utf-8") as flog:

        w = csv.writer(fcsv)
        w.writerow([
            "timestamp_iso","elapsed_sec",
            "func_covered","func_total","func_percent",
            "line_covered","line_total","line_percent",
            "region_covered","region_total","region_percent",
            "branch_covered","branch_total","branch_percent",
            "inst_covered","inst_total","inst_percent",
        ])

        for gi, (elapsed, ts) in enumerate(groups, 1):
            raws_this = []

            for t in ts:
                pat = str(profraw / f"{t.name}-%p.profraw")
                env = os.environ.copy()
                env["LLVM_PROFILE_FILE"] = pat
                if args.make_no_exec:
                    env["MAKEFLAGS"] = "-n"

                cmd = [args.klee_replay, str(target), str(t)]
                rc, to = replay_with_timeout(
                    cmd, env, timeout_bin,
                    args.per_test_timeout_sec,
                    args.kill_after_sec,
                )

                total_replayed += 1
                if to:
                    total_timeouts += 1
                    tlog.write(str(t) + "\n")
                    tlog.flush()
                elif rc != 0:
                    total_failed += 1
                    flog.write(f"{t} {rc}\n")
                    flog.flush()

                raws_this += sorted(profraw.glob(f"{t.name}-*.profraw"))

                # live progress
                progress_line(
                    total_replayed, total_tests,
                    t.name, total_timeouts, total_failed
                )

            print()  # newline after the single-line progress for this group

            if not raws_this:
                # nothing produced by this group
                continue

            # merge group's raw -> bucket.profdata (chunked)
            bucket_prof = tmpdir / f"bucket_{int(round(elapsed * 1e6))}.profdata"
            merge_prof_chunked(
                args.llvm_profdata, raws_this, bucket_prof,
                tmpdir / "bucket_parts",
                args.merge_chunk_size, threads,
            )

            # cumulative merge (small)
            if cum_prof is None:
                cum_prof = tmpdir / f"cum_{int(round(elapsed * 1e6))}.profdata"
                merge_prof_chunked(
                    args.llvm_profdata, [bucket_prof], cum_prof,
                    tmpdir / "cum_parts_init",
                    args.merge_chunk_size, threads,
                )
            else:
                new_cum = tmpdir / f"cum_{int(round(elapsed * 1e6))}.profdata"
                merge_prof_chunked(
                    args.llvm_profdata, [str(cum_prof), str(bucket_prof)], new_cum,
                    tmpdir / "cum_parts",
                    args.merge_chunk_size, threads,
                )
                cum_prof = new_cum

            # totals
            tot = export_summary_all(args.llvm_cov, target, cum_prof)

            # baseline row at t0 (true 0 coverage)
            if not baseline_written:
                w.writerow([
                    datetime.fromtimestamp(t0, timezone.utc).isoformat(),
                    f"{0.0:.6f}",
                    0, tot["functions"]["count"],      "0.00",
                    0, tot["lines"]["count"],          "0.00",
                    0, tot["regions"]["count"],        "0.00",
                    0, tot["branches"]["count"],       "0.00",
                    0, tot["instantiations"]["count"], "0.00",
                ])
                baseline_written = True

            ts_abs = t0 + elapsed
            w.writerow([
                datetime.fromtimestamp(ts_abs, timezone.utc).isoformat(),
                f"{elapsed:.6f}",
                tot["functions"]["covered"],      tot["functions"]["count"],      f"{tot['functions']['percent']:.2f}",
                tot["lines"]["covered"],          tot["lines"]["count"],          f"{tot['lines']['percent']:.2f}",
                tot["regions"]["covered"],        tot["regions"]["count"],        f"{tot['regions']['percent']:.2f}",
                tot["branches"]["covered"],       tot["branches"]["count"],       f"{tot['branches']['percent']:.2f}",
                tot["instantiations"]["covered"], tot["instantiations"]["count"], f"{tot['instantiations']['percent']:.2f}",
            ])
            fcsv.flush()
            print(
                f"[group {gi}/{len(groups)}] tests={len(ts)} "
                f"replayed_total={total_replayed} "
                f"timeouts={total_timeouts} failed={total_failed}",
                flush=True,
            )

    if cum_prof:
        try:
            os.replace(cum_prof, covdir / "coverage.profdata")
        except Exception:
            pass

    print(f"[group] wrote {csv_path}")

    # 4) Optional resampling/splitting
    if not args.no_resample:
        resample_out = (
            Path(args.resample_out).resolve()
            if args.resample_out is not None
            else (covdir / "resampled")
        )
        print(f"[resample] using output dir: {resample_out}")
        resample_and_split(csv_path, resample_out, step=args.resample_step)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
