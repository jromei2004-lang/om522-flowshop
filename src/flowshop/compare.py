"""Deterministic comparison: pixi run compare

Runs every method on hand_checkable and the three development instances through the
same command the instructor uses (pixi run solve <input_dir> <output_dir> --method m),
checks every decision with pixi run check, and writes:

  results/comparison.csv            one row per method and instance
  results/runs/<method>/<instance>/ decision.json, summary.txt, check_report.json
  results/figures/                  Gantt charts and the method comparison bar chart

Every measure in the CSV and every time in the charts comes from the checker's report
(check_report.json), never from a method's own summary. The only value taken from
summary.txt is the computation time, which the checker cannot recompute.

A method that pixi run solve does not offer yet (for example ig before Iterated Greedy
is merged) is skipped with a message, and the comparison still succeeds.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

from flowshop import plots

METHODS = ["rule", "ig"]
INSTANCES = ["hand_checkable", "development_small", "development_medium", "development_large"]
GANTT_INSTANCES = ["hand_checkable", "development_small"]

COLUMNS = [
    "method", "instance", "jobs", "stages", "feasible",
    "total_weighted_tardiness", "total_waiting", "makespan", "runtime_s", "cpu", "note",
]
RUNTIME_LINE = re.compile(r"Computation time \(s\):\s*([0-9.eE+-]+)")
METHOD_CHOICES = re.compile(r"--method\s+\{([^}]*)\}")


def pixi(*args: str) -> subprocess.CompletedProcess:
    exe = shutil.which("pixi")
    if exe is None:
        raise SystemExit("pixi was not found on PATH; pixi run compare needs it to call solve and check.")
    return subprocess.run([exe, "run", *args], capture_output=True, text=True, encoding="utf-8")


def available_methods() -> set[str]:
    """The --method choices that pixi run solve accepts right now."""
    proc = pixi("solve", "--help")
    match = METHOD_CHOICES.search(proc.stdout)
    if proc.returncode != 0 or match is None:
        raise SystemExit(f"Could not read the --method choices from pixi run solve --help:\n{proc.stdout}{proc.stderr}")
    return {m.strip() for m in match.group(1).split(",")}


def cpu_name() -> str:
    """The processor's marketing name, read the way each platform exposes it."""
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                 capture_output=True, text=True, encoding="utf-8")
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        elif system == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        elif system == "Linux":
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine() or "unknown"


def instance_size(instance_dir: Path) -> tuple[int, int]:
    """(jobs, stages), counted from the CSV rows."""
    def rows(name: str) -> int:
        with (instance_dir / name).open(encoding="utf-8-sig", newline="") as f:
            return sum(1 for row in csv.reader(f) if row) - 1
    return rows("jobs.csv"), rows("stages.csv")


def run_one(method: str, instance: str, data_dir: Path, results_dir: Path, cpu: str) -> tuple[dict, dict | None]:
    """Solve and check one instance with one method. Returns (CSV row, checker report or None)."""
    inst_dir = data_dir / instance
    out_dir = results_dir / "runs" / method / instance
    jobs, stages = instance_size(inst_dir)
    row = {c: "" for c in COLUMNS} | {"method": method, "instance": instance, "jobs": jobs,
                                      "stages": stages, "cpu": cpu, "feasible": False}

    solved = pixi("solve", str(inst_dir), str(out_dir), "--method", method)
    decision = out_dir / "decision.json"
    if solved.returncode != 0 or not decision.is_file():
        row["note"] = f"solve exited {solved.returncode} without a decision.json"
        print(f"  {method} on {instance}: {row['note']}\n{solved.stderr}", file=sys.stderr)
        return row, None

    match = RUNTIME_LINE.search((out_dir / "summary.txt").read_text(encoding="utf-8"))
    row["runtime_s"] = float(match.group(1)) if match else ""

    report_path = out_dir / "check_report.json"
    checked = pixi("check", str(inst_dir), str(decision), "--report", str(report_path))
    if checked.returncode not in (0, 1) or not report_path.is_file():
        row["note"] = f"check exited {checked.returncode}: {checked.stderr.strip()}"
        print(f"  {method} on {instance}: {row['note']}", file=sys.stderr)
        return row, None
    with report_path.open(encoding="utf-8") as f:
        report = json.load(f)

    row["feasible"] = report["feasible"]
    if report["feasible"]:
        for key in ("total_weighted_tardiness", "total_waiting", "makespan"):
            row[key] = report["measures"][key]
    else:
        row["note"] = f"infeasible: {len(report['violations'])} violations (see check_report.json)"
    return row, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compare", description="Run, check, and compare every method")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--methods", nargs="+", default=METHODS)
    parser.add_argument("--instances", nargs="+", default=INSTANCES)
    args = parser.parse_args(argv)

    offered = available_methods()
    methods = []
    for m in args.methods:
        if m in offered:
            methods.append(m)
        else:
            print(f"Skipping {m}: pixi run solve does not offer --method {m} yet.")
    if not methods:
        print("No method to run.", file=sys.stderr)
        return 1

    cpu = cpu_name()
    print(f"CPU: {cpu}")
    rows, reports = [], {}
    for method in methods:
        for instance in args.instances:
            print(f"Running {method} on {instance} ...")
            row, report = run_one(method, instance, args.data_dir, args.results_dir, cpu)
            rows.append(row)
            if report is not None and report["feasible"]:
                reports[(method, instance)] = report

    args.results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.results_dir / "comparison.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {csv_path}")

    figures = args.results_dir / "figures"
    for (method, instance), report in reports.items():
        if instance in GANTT_INSTANCES:
            path = figures / f"gantt_{method}_{instance}.png"
            plots.save_gantt(report, f"{plots.METHOD_LABELS.get(method, method)} on {instance}", path)
            print(f"Wrote {path}")
    path = figures / "comparison_bars.png"
    plots.save_comparison_bars(rows, methods, args.instances, path)
    print(f"Wrote {path}")

    for row in rows:
        print(f"  {row['method']:>5} {row['instance']:<20} feasible={row['feasible']!s:<5} "
              f"TWT={row['total_weighted_tardiness']} waiting={row['total_waiting']} runtime_s={row['runtime_s']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
