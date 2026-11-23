"""Charts for the report, rendered to PNG bytes with matplotlib."""

from __future__ import annotations

import io
from collections.abc import Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from coroner.analysis import Analysis
from coroner.checks import BucketRow
from coroner.verdict import count_word

BLUE = "#2a78d6"
ORANGE = "#eb6834"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
SURFACE = "#ffffff"


def _style(ax: Axes) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    ax.title.set_color(INK)


def _thousands(ax: Axes) -> None:
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))


def _png(fig: Figure) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=130, facecolor=SURFACE, metadata={"Software": None})
    plt.close(fig)
    return buffer.getvalue()


def _equity_axes(ax: Axes, a: Analysis, title: str) -> None:
    removed = a.leave_n.removed
    ax.step(a.exit_times, a.cumulative, where="post", color=BLUE, linewidth=1.8, label="All trades")
    ax.step(
        a.exit_times,
        a.cumulative_without_best,
        where="post",
        color=ORANGE,
        linewidth=1.8,
        linestyle="--",
        label=f"Without the best {count_word(removed)}",
    )
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.set_title(title, fontsize=11, loc="left")
    ax.set_ylabel("Cumulative net result")
    ax.set_xlabel("Exit time")
    _style(ax)
    _thousands(ax)
    for label in ax.get_xticklabels():
        label.set_rotation(30)
        label.set_horizontalalignment("right")


def equity_chart(a: Analysis) -> bytes:
    """Cumulative net result, with and without the best N trades."""
    fig, ax = plt.subplots(figsize=(8, 3.8), layout="constrained")
    _equity_axes(ax, a, "Cumulative net result")
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    return _png(fig)


def bucket_chart(rows: Sequence[BucketRow], title: str, xlabel: str, flag_label: str) -> bytes:
    """Net result per bucket. Flagged buckets are hatched and drawn in orange."""
    fig, ax = plt.subplots(figsize=(8, 3.4), layout="constrained")
    labels = [r.label for r in rows]
    totals = np.array([r.total for r in rows])
    flagged = np.array([r.short_hold for r in rows])
    positions = np.arange(len(rows))
    ax.bar(positions[~flagged], totals[~flagged], width=0.7, color=BLUE, label="Net result")
    if flagged.any():
        ax.bar(
            positions[flagged],
            totals[flagged],
            width=0.7,
            color=ORANGE,
            hatch="//",
            edgecolor=SURFACE,
            label=flag_label,
        )
        ax.legend(frameon=False, fontsize=9)
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.set_xticks(
        positions,
        labels,
        rotation=30 if len(rows) > 7 else 0,
        ha="right" if len(rows) > 7 else "center",
    )
    ax.set_title(title, fontsize=11, loc="left")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Net result")
    _style(ax)
    _thousands(ax)
    return _png(fig)


def drawdown_chart(a: Analysis) -> bytes:
    """Percentage drawdown of end-of-day equity from its running maximum."""
    fig, ax = plt.subplots(figsize=(8, 3.0), layout="constrained")
    ax.fill_between(a.daily_dates, -a.daily_drawdown_pct, 0, step="post", color=BLUE, alpha=0.35)
    ax.step(a.daily_dates, -a.daily_drawdown_pct, where="post", color=BLUE, linewidth=1.2)
    ax.set_title("Drawdown from the running maximum, end of day", fontsize=11, loc="left")
    ax.set_ylabel("Drawdown (% of peak equity)")
    ax.set_xlabel("Date")
    _style(ax)
    for label in ax.get_xticklabels():
        label.set_rotation(30)
        label.set_horizontalalignment("right")
    return _png(fig)


def headline_chart(panels: Sequence[tuple[str, Analysis]]) -> bytes:
    """Cumulative net result for several logs side by side, on one y-scale."""
    fig, axes = plt.subplots(
        1, len(panels), figsize=(5.0 * len(panels), 3.9), sharey=True, layout="constrained"
    )
    axes_list = [axes] if len(panels) == 1 else list(axes)
    for i, (ax, (title, a)) in enumerate(zip(axes_list, panels, strict=True)):
        _equity_axes(ax, a, title)
        if i > 0:
            ax.set_ylabel("")
    axes_list[0].legend(frameon=False, fontsize=9, loc="upper left")
    return _png(fig)
