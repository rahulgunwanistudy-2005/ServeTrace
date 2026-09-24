"""The one figure in this eval: how CONTRADICTED holds up as the data gets worse.

matplotlib is a dev dependency and lives only here. Nothing under `app/` imports this
module, it is not in the runtime image, and the product never plots anything — the
Methodology page renders its own numbers from `published.json`.

Three panels, because the three sweeps ask different questions of the same engine and
putting them on one axis would imply a shared unit they do not have. The first two share
an axis on purpose, though: same displacements, same scale, and the only difference
between them is whether the phone reported the error it was making.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - import cost, not behaviour
    from eval.robustness import RobustnessReport, Sweep

# Matched to the product's own palette so the figure does not look like it came from
# somewhere else. Read off `frontend/src/app.css` as sRGB rather than imported, because a
# PNG has no design tokens.
INK = "#1c1917"
MUTED = "#78716c"
STRONG_LINE = "#b91c1c"
MODERATE_LINE = "#a8a29e"
GRID = "#e7e5e4"


def _series(sweep: Sweep, block: str, metric: str) -> tuple[list[float], list[float]]:
    xs: list[float] = []
    ys: list[float] = []
    for level in sweep.levels:
        value = getattr(level, block).get(metric)
        if value is None:
            continue
        xs.append(level.value)
        ys.append(value * 100.0)
    return xs, ys


def _floor(report: RobustnessReport) -> float:
    """Where to start the y-axis.

    A 0-100 axis on data that never leaves the high nineties draws four flat lines and
    says nothing. The figure exists to show *how much* the engine gives up, so the axis is
    scaled to the range that is actually in play, with the zero point stated in the caption
    so nobody reads a zoomed axis as a cliff.
    """
    values = [
        value
        for sweep in report.sweeps
        for level in sweep.levels
        for block in (level.strong, level.strong_or_moderate)
        for value in (block["precision"], block["recall"])
        if value is not None
    ]
    lowest = min(values, default=1.0) * 100.0
    return min(99.0, max(0.0, lowest - 1.5))


def _panel(axis: Any, sweep: Sweep, xlabel: str) -> None:
    for block, colour, label, style in (
        ("strong", STRONG_LINE, "STRONG only", "-"),
        ("strong_or_moderate", MODERATE_LINE, "STRONG + MODERATE", "--"),
    ):
        for metric, marker, suffix in (("precision", "o", "precision"), ("recall", "s", "recall")):
            xs, ys = _series(sweep, block, metric)
            if not xs:
                continue
            axis.plot(
                xs,
                ys,
                style,
                color=colour,
                marker=marker,
                markersize=4,
                linewidth=1.4,
                alpha=1.0 if metric == "precision" else 0.55,
                label=f"{label} — {suffix}",
            )

    axis.set_xlabel(xlabel, color=INK, fontsize=9)
    axis.grid(True, color=GRID, linewidth=0.6)
    axis.set_axisbelow(True)
    for spine in ("top", "right"):
        axis.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        axis.spines[spine].set_color(GRID)
    axis.tick_params(colors=MUTED, labelsize=8)


def write_robustness_png(report: RobustnessReport, path: Path) -> Path:
    """Draw all three sweeps and write the PNG. Returns the path it wrote."""
    import matplotlib

    # No display on a build machine, and none wanted on a laptop either.
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 3, figsize=(12.5, 3.9), dpi=160, sharey=True)
    left, middle, right = axes

    _panel(left, report.jitter, "GPS jitter, sigma (m)\nerror not reported")
    _panel(middle, report.jitter_reported, "GPS jitter, sigma (m)\nerror reported, as a phone does")
    _panel(right, report.gaps, "sampling gap (minutes)")
    floor = _floor(report)
    left.set_ylim(floor, 100 + (100 - floor) * 0.06)
    left.set_ylabel("percent", color=INK, fontsize=9)

    figure.suptitle(
        "CONTRADICTED under measurement noise",
        color=INK,
        fontsize=11,
        x=0.02,
        ha="left",
        y=0.985,
    )
    figure.text(
        0.02,
        0.9,
        f"{report.n_cases} synthetic cases per level, scored against unperturbed ground "
        f"truth. Axis starts at {_floor(report):.0f}%, not 0.",
        color=MUTED,
        fontsize=8,
        ha="left",
    )
    handles, labels = left.get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=8,
        labelcolor=MUTED,
        bbox_to_anchor=(0.5, -0.02),
    )
    figure.tight_layout(rect=(0, 0.06, 1, 0.88))

    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(figure)
    return path
