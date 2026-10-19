"""Charts for the comparison. Every input here comes from the checker's report or from
rows built from it (see compare.py), never from a method's own numbers.

Colors are the validated default palette of the dataviz guidance: categorical slots in
fixed order, and an ordinal blue ramp when there are more jobs than categorical slots.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write files only; no window, same behavior on every machine
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, to_rgb  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
# Ordinal blue ramp, steps 250 to 700 (lightest step still clears 2:1 on the surface).
ORDINAL_BLUE = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
                "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
METHOD_COLORS = {"rule": CATEGORICAL[0], "ig": CATEGORICAL[1]}
METHOD_LABELS = {"rule": "Rule to beat (EDD)", "ig": "Iterated Greedy"}


def fmt(value: float) -> str:
    """A measure for a label: thousands separators, never scientific notation, and up to
    9 decimals (beyond the 0.001 that decides whether a method beats the rule)."""
    v = float(value)
    if v.is_integer():
        return f"{int(v):,}"
    return f"{v:,.9f}".rstrip("0").rstrip(".")


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(TEXT_SECONDARY)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=8)


def _luminance(color: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in to_rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _label_color(fill: str) -> str:
    """Dark or white text, whichever contrasts more with the bar."""
    lum = _luminance(fill)
    return TEXT if (lum + 0.05) / (_luminance(TEXT) + 0.05) >= 1.05 / (lum + 0.05) else "white"


def _short_id(job_id: str) -> str:
    """Display only: the digits of an id without leading zeros (J012 -> 12), else the id."""
    digits = job_id.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_-")
    return digits.lstrip("0") or job_id if digits.isdigit() else job_id


def job_colors(sequence: list[str]) -> dict[str, str]:
    """One color per job, by position in the sequence, the same at every stage."""
    n = len(sequence)
    if n <= len(CATEGORICAL):
        return {job: CATEGORICAL[i] for i, job in enumerate(sequence)}
    ramp = LinearSegmentedColormap.from_list("ordinal_blue", ORDINAL_BLUE)
    return {job: matplotlib.colors.to_hex(ramp(i / (n - 1))) for i, job in enumerate(sequence)}


def gantt(report: dict, title: str):
    """One row per stage (in stages.csv order, first at the top), one bar per operation."""
    stages, sequence, ops = report["stages"], report["sequence"], report["operations"]
    colors = job_colors(sequence)
    row = {s: i for i, s in enumerate(stages)}
    span = max(op["completion"] for op in ops) - min(0, min(op["start"] for op in ops))

    width_in = 13 if len(sequence) > 8 else 10
    fig, ax = plt.subplots(figsize=(width_in, 0.55 * len(stages) + 1.8), facecolor=SURFACE)
    _style(ax)
    units_per_inch = span / (width_in * 0.8)
    for op in ops:
        fill = colors[op["job_id"]]
        length = op["completion"] - op["start"]
        y = row[op["stage_id"]]
        ax.barh(y, length, left=op["start"], height=0.72, color=fill, edgecolor=SURFACE, linewidth=1.0)
        # The full job id when it fits inside the bar, else its number (J012 -> 12).
        for label in (op["job_id"], _short_id(op["job_id"])):
            if length / units_per_inch >= 0.06 * len(label) + 0.04:
                ax.text(op["start"] + length / 2, y, label, ha="center", va="center",
                        fontsize=7, color=_label_color(fill))
                break

    ax.set_yticks(range(len(stages)), stages)
    ax.set_ylim(len(stages) - 0.5, -0.5)
    ax.set_xlim(left=0)
    ax.set_xlabel("Time (minutes)", color=TEXT_SECONDARY, fontsize=9)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    measures = report["measures"]
    ax.set_title(f"{title}\nweighted tardiness {fmt(measures['total_weighted_tardiness'])}, "
                 f"waiting {fmt(measures['total_waiting'])}, makespan {fmt(measures['makespan'])} "
                 "(times verified by the checker)", loc="left", fontsize=10, color=TEXT)
    handles = [Patch(facecolor=colors[j], label=j) for j in sequence]
    note = "Jobs in sequence order" + (" (color darkens along the sequence)" if len(sequence) > 8 else "")
    note += "\nNarrow bars show the job number only"
    ax.legend(handles=handles, title=note, title_fontsize=8, fontsize=7, frameon=False,
              loc="upper left", bbox_to_anchor=(1.01, 1.0), ncol=1 if len(sequence) <= 8 else 2,
              labelcolor=TEXT)
    fig.tight_layout()
    return fig, ax


def save_gantt(report: dict, title: str, path: Path) -> None:
    fig, _ = gantt(report, title)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def comparison_bars(rows: list[dict], methods: list[str], instances: list[str]):
    """Small multiples: one panel per instance and measure, each with its own axis."""
    measures = [("total_weighted_tardiness", "Total weighted tardiness"),
                ("total_waiting", "Total waiting between stages")]
    value = {(r["method"], r["instance"], m): r[m] for r in rows if r["feasible"] for m, _ in measures}
    fig, axes = plt.subplots(len(measures), len(instances), squeeze=False,
                             figsize=(2.6 * len(instances) + 0.6, 2.4 * len(measures) + 1.0), facecolor=SURFACE)
    for i, (key, label) in enumerate(measures):
        for j, instance in enumerate(instances):
            ax = axes[i][j]
            _style(ax)
            for k, method in enumerate(methods):
                v = value.get((method, instance, key))
                if v is None or v == "":
                    ax.text(k, 0, "n/a", ha="center", va="bottom", fontsize=8, color=TEXT_SECONDARY)
                    continue
                ax.bar(k, v, width=0.6, color=METHOD_COLORS.get(method, CATEGORICAL[k % 2]),
                       edgecolor=SURFACE, linewidth=1.0)
                ax.text(k, v, fmt(v),
                        ha="center", va="bottom", fontsize=8, color=TEXT)
            ax.set_xticks(range(len(methods)), [m for m in methods], fontsize=8)
            ax.set_xlim(-0.6, len(methods) - 0.4)
            ax.set_ylim(bottom=0, top=max([float(value.get((m, instance, key)) or 0) for m in methods] + [1]) * 1.18)
            ax.grid(axis="y", color=GRID, linewidth=0.8)
            ax.set_axisbelow(True)
            if i == 0:
                ax.set_title(instance, fontsize=9, color=TEXT)
            if j == 0:
                ax.set_ylabel(label, fontsize=8, color=TEXT_SECONDARY)
    if len(methods) >= 2:
        fig.legend(handles=[Patch(facecolor=METHOD_COLORS.get(m, CATEGORICAL[k % 2]), label=METHOD_LABELS.get(m, m))
                            for k, m in enumerate(methods)],
                   loc="upper right", ncol=len(methods), frameon=False, fontsize=8, labelcolor=TEXT)
    title = "Rule to beat vs Iterated Greedy" if len(methods) >= 2 else f"{METHOD_LABELS.get(methods[0], methods[0])} only"
    fig.suptitle(f"{title} (measures recomputed by the checker; each panel has its own scale)",
                 x=0.01, ha="left", fontsize=10, color=TEXT)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return fig, axes


def save_comparison_bars(rows: list[dict], methods: list[str], instances: list[str], path: Path) -> None:
    fig, _ = comparison_bars(rows, methods, instances)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
