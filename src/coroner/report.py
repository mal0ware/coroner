"""Build the report once, then render it as markdown and as self-contained HTML."""

from __future__ import annotations

import base64
import html
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from coroner import __version__, charts
from coroner.analysis import Analysis
from coroner.barrier import BarrierResult
from coroner.checks import BucketRow, TradeStats
from coroner.verdict import count_word, money, verdict


@dataclass(frozen=True)
class Table:
    """A table of preformatted cells. The first column is left-aligned."""

    header: list[str]
    rows: list[list[str]]


@dataclass(frozen=True)
class Figure:
    """A PNG chart with its file name and alternative text."""

    name: str
    alt: str
    png: bytes


@dataclass(frozen=True)
class Section:
    """A titled block: paragraphs, then tables, then an optional figure."""

    title: str
    paragraphs: list[str] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    figure: Figure | None = None


@dataclass(frozen=True)
class Report:
    """The whole report, independent of output format."""

    title: str
    verdict: list[str]
    sections: list[Section]


# ---- formatting -----------------------------------------------------------


def _num(value: float, digits: int = 2) -> str:
    return "n/a" if math.isnan(value) else f"{value:,.{digits}f}"


def _pct(fraction: float, digits: int = 1) -> str:
    if math.isinf(fraction):
        return "total not positive"
    return "n/a" if math.isnan(fraction) else f"{100 * fraction:.{digits}f}%"


def _duration(delta: np.timedelta64) -> str:
    seconds = int(delta / np.timedelta64(1, "s"))
    days, rest = divmod(seconds, 86_400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days:,} days {hours} h"
    if hours:
        return f"{hours} h {minutes} min"
    return f"{minutes} min"


def _stamp(t: np.datetime64) -> str:
    return str(t.astype("datetime64[m]")).replace("T", " ")


def _stats_row(label: str, s: TradeStats) -> list[str]:
    return [label, f"{s.n:,}", money(s.total), _num(s.mean), _num(s.sd), _num(s.t_stat)]


def _bucket_table(rows: list[BucketRow], first: str, flag: bool) -> Table:
    header = [first, "Trades", "Net", "Mean", "Share of profit", "Winners", "Median hold (min)"]
    if flag:
        header.append("Flag")
    body = []
    for r in rows:
        cells = [
            r.label,
            f"{r.n:,}",
            money(r.total),
            _num(r.mean),
            _pct(r.share),
            _pct(r.win_rate),
            _num(r.median_hold_minutes, 1),
        ]
        if flag:
            cells.append("short hold" if r.short_hold else "")
        body.append(cells)
    return Table(header, body)


def _barrier_row(label: str, r: BarrierResult) -> list[str]:
    return [label, _pct(r.p_target), _pct(r.p_loss), _pct(r.p_neither), f"{r.paths:,}"]


# ---- assembly --------------------------------------------------------------


def build_report(a: Analysis, source_name: str) -> Report:
    """Turn an :class:`Analysis` into a :class:`Report`."""
    s = a.settings
    best = count_word(a.leave_n.removed)
    sections: list[Section] = []

    input_lines = [
        f"File `{source_name}`: {a.n:,} trades, first entry {_stamp(a.first_entry)}, "
        f"last exit {_stamp(a.last_exit)}.",
        f"Clock: {a.clock}. Trades are ordered by exit time.",
        f"Starting capital {money(s.capital)} (set with `--capital`). Percentage drawdowns, "
        "the ulcer index and the Martin ratio depend on it.",
    ]
    if a.size_median is not None:
        input_lines.append(f"Median trade size {_num(a.size_median)}.")
    sections.append(Section("Input", input_lines))

    sections.append(
        Section(
            "Per-trade result",
            [
                "The t-statistic is mean / standard deviation x sqrt(number of trades), with "
                "the n - 1 standard deviation. It treats trades as independent draws.",
                "The clustered t-statistics use a cluster-robust standard error: trades that "
                "exit on the same day (or in the same month) may be correlated in any way, and "
                "the days (months) are taken as independent. With few clusters the clustered "
                "standard error is itself noisy.",
            ],
            [
                Table(
                    ["", "Trades", "Total", "Mean", "Std dev", "t-statistic"],
                    [_stats_row("Net", a.net), _stats_row("Gross", a.gross)],
                ),
                Table(
                    ["Net, t-statistic", "Clusters", "t-statistic"],
                    [["Trades independent", f"{a.n:,}", _num(a.net.t_stat)]]
                    + [
                        [f"Clustered by {c.period}", f"{c.clusters:,}", _num(c.t_stat)]
                        for c in a.clustered
                    ],
                ),
            ],
            Figure(
                "equity.png",
                f"Cumulative net result with and without the best {best} trades",
                charts.equity_chart(a),
            ),
        )
    )

    def leave_row(
        label: str, removed: int, removed_total: float, share: float, rest: TradeStats
    ) -> list[str]:
        return [
            label,
            f"{removed:,}",
            money(removed_total),
            _pct(share),
            money(rest.total),
            _num(rest.mean),
            _num(rest.t_stat),
        ]

    zero_line = (
        "The total is already zero or below with every trade included."
        if a.to_zero == 0
        else f"Smallest number of best trades whose removal takes the total to zero or below: "
        f"**{a.to_zero:,}** of {a.n:,}."
    )
    sections.append(
        Section(
            "Without the best trades",
            [
                "Trades are ranked by net result and the best are removed. Share of profit is "
                "the removed trades' total over the total of all trades.",
                zero_line,
            ],
            [
                Table(
                    [
                        "",
                        "Removed",
                        "Removed total",
                        "Share of profit",
                        "Remaining total",
                        "Remaining mean",
                        "Remaining t",
                    ],
                    [
                        leave_row(
                            "All trades", 0, 0.0, 0.0 if a.net.total > 0 else math.nan, a.net
                        ),
                        leave_row(
                            f"Without best {a.leave_n.removed}",
                            a.leave_n.removed,
                            a.leave_n.removed_total,
                            a.leave_n.share,
                            a.leave_n.rest,
                        ),
                        leave_row(
                            "Without best 5%",
                            a.leave_5pct.removed,
                            a.leave_5pct.removed_total,
                            a.leave_5pct.share,
                            a.leave_5pct.rest,
                        ),
                    ],
                )
            ],
        )
    )

    nulls = [x for x in (a.null_normal, a.null_symmetric) if x is not None]
    if nulls:
        null_names = {
            "normal": "Normal, same mean and std dev",
            "symmetric": "Trades resampled and reflected about the mean",
        }
        null_rows = [
            [
                "This log",
                _pct(a.leave_n.share),
                "",
                "",
                f"{a.to_zero:,}",
                "",
                "",
            ]
        ] + [
            [
                null_names[x.name],
                _pct(x.share_median),
                _pct(x.share_p95),
                f"{x.share_p:.4f}",
                _num(x.to_zero_median, 0),
                _num(x.to_zero_p05, 0),
                f"{x.to_zero_p:.4f}",
            ]
            for x in nulls
        ]
        sections.append(
            Section(
                "Is that more concentrated than chance?",
                [
                    f"Each row draws {nulls[0].draws:,} logs of {a.n:,} trades under a null and "
                    f"computes the same two numbers. The Normal null keeps the mean and standard "
                    "deviation and has thin tails and no skew. The reflected null resamples these "
                    "trades and flips each one about the mean with a random sign, which keeps the "
                    "tails and removes the skew. p is one-sided: the share of draws at least as "
                    "concentrated as this log, counting the log itself.",
                    "A draw whose total is zero or below counts as fully concentrated. "
                    + "; ".join(
                        f"{null_names[x.name]}: {x.not_positive:,} such draws" for x in nulls
                    )
                    + ".",
                ],
                [
                    Table(
                        [
                            "",
                            f"Share in best {a.leave_n.removed}",
                            "95th pct",
                            "p",
                            "Trades to zero",
                            "5th pct",
                            "p",
                        ],
                        null_rows,
                    )
                ],
            )
        )

    sections.append(
        Section(
            "First half against second half",
            ["Trades in exit-time order, split by count: the first n // 2 and the rest."],
            [
                Table(
                    ["", "Trades", "Total", "Mean", "Std dev", "t-statistic"],
                    [
                        _stats_row("First half", a.halves.first),
                        _stats_row("Second half", a.halves.second),
                    ],
                )
            ],
        )
    )

    flag_note = (
        f"A bucket is flagged when its median hold is under {s.short_hold_minutes:g} minutes and "
        f"it has at least {s.min_bucket_trades} trades. Results from trades held that briefly "
        "depend heavily on the fill and cost assumptions behind them."
    )

    def perm_note(name: str, p: float, groups: int) -> str:
        if math.isnan(p):
            return f"Permutation test: not run, all trades fall in one {name} bucket."
        return (
            f"Permutation test, {name} labels shuffled {s.draws:,} times across {groups} "
            f"buckets: p = {p:.4f}. A small p means results differ across buckets more than "
            "chance would give."
        )

    sections.append(
        Section(
            "Time of day",
            [
                f"Buckets of {s.bucket_minutes} minutes by entry time.",
                flag_note,
                perm_note("time-of-day", a.perm_time_of_day.p_value, a.perm_time_of_day.n_groups),
            ],
            [_bucket_table(a.time_of_day, "Entry time", flag=True)],
            Figure(
                "time_of_day.png",
                "Net result by entry time of day",
                charts.bucket_chart(
                    a.time_of_day,
                    "Net result by entry time of day",
                    "Entry time",
                    f"Median hold under {s.short_hold_minutes:g} min",
                ),
            ),
        )
    )
    sections.append(
        Section(
            "Weekday",
            [
                "By weekday of entry.",
                perm_note("weekday", a.perm_weekday.p_value, a.perm_weekday.n_groups),
            ],
            [_bucket_table(a.weekday, "Weekday", flag=True)],
            Figure(
                "weekday.png",
                "Net result by weekday of entry",
                charts.bucket_chart(
                    a.weekday,
                    "Net result by weekday of entry",
                    "Weekday",
                    f"Median hold under {s.short_hold_minutes:g} min",
                ),
            ),
        )
    )

    cost = a.cost
    share_text = (
        "not defined: the gross result is zero or negative, so there is no gross profit "
        "for costs to be a share of"
        if cost.share is None
        else _pct(cost.share)
    )
    sections.append(
        Section(
            "Costs",
            ["Cost is gross minus net, summed over all trades. Cost share is cost over gross."],
            [
                Table(
                    ["", "Amount"],
                    [
                        ["Gross result", money(cost.gross_total)],
                        ["Cost", money(cost.cost_total)],
                        ["Net result", money(cost.net_total)],
                        ["Cost share of gross", share_text],
                    ],
                )
            ],
        )
    )

    d = a.drawdown
    underwater = _duration(d.underwater) + ("" if d.underwater_recovered else " (not recovered)")
    sections.append(
        Section(
            "Drawdown",
            [
                "The ulcer index and Martin ratio use end-of-day equity on every calendar day "
                "from the first exit to the last. Maximum drawdown, time under water and "
                "recovery factor use the trade-by-trade equity curve.",
                "The annualised return is compound, on 365.25 days a year, and is not "
                "computed for logs shorter than 30 days.",
                "Recovery factor is net profit over maximum drawdown. It is a trading-platform "
                "convention, not a statistic from the literature.",
            ],
            [
                Table(
                    ["", "Value"],
                    [
                        ["Ulcer index (%)", _num(d.ulcer_index, 3)],
                        ["Annualised return (%)", _num(d.annual_return_pct)],
                        ["Martin ratio", _num(d.martin_ratio)],
                        ["Maximum drawdown", money(d.max_drawdown)],
                        ["Maximum drawdown (% of peak)", _num(d.max_drawdown_pct)],
                        ["Longest time under water", underwater],
                        ["Recovery factor", _num(d.recovery_factor)],
                    ],
                )
            ],
            Figure(
                "drawdown.png",
                "Percentage drawdown of end-of-day equity",
                charts.drawdown_chart(a),
            ),
        )
    )

    sections.append(
        Section(
            "Positive periods",
            ["Net result by exit date. Only periods with at least one closed trade are counted."],
            [
                Table(
                    ["", "Positive", "Total", "Share"],
                    [[p.name, f"{p.positive:,}", f"{p.total:,}", _pct(p.share)] for p in a.periods],
                )
            ],
        )
    )

    b = a.barrier
    barrier_rows = [
        _barrier_row("i.i.d. bootstrap", b.iid),
        _barrier_row(f"Stationary bootstrap, mean block {b.mean_block:g}", b.stationary),
    ]
    if b.iid_without_best is not None:
        barrier_rows.append(
            _barrier_row(f"i.i.d. bootstrap without best {a.leave_n.removed}", b.iid_without_best)
        )
    barrier_rows.append(
        ["Brownian closed form, no horizon", _pct(b.brownian), _pct(1 - b.brownian), "", ""]
    )
    sections.append(
        Section(
            "Target before loss limit",
            [
                f"Target +{money(b.target)}, loss limit -{money(b.loss_limit)}, horizon "
                f"{b.horizon:,} trades. Trades are resampled into paths and each path's running "
                "total is followed until it reaches a barrier or the horizon ends.",
                "The closed form uses the per-trade mean and standard deviation and has no "
                "horizon, so it gives no weight to paths that reach neither barrier.",
                "Resampling assumes future trades look like these ones, including the best of "
                "them arriving as often as they did here.",
            ],
            [Table(["", "Target first", "Loss limit first", "Neither", "Paths"], barrier_rows)],
        )
    )

    for title, rows, first in (
        ("By symbol", a.by_symbol, "Symbol"),
        ("By side", a.by_side, "Side"),
    ):
        if rows is None:
            continue
        notes = []
        if len(rows) > 20:
            notes.append(f"The 20 largest by net result of {len(rows)}.")
        sections.append(Section(title, notes, [_bucket_table(rows[:20], first, flag=False)]))

    sections.append(
        Section(
            "Settings",
            [
                f"coroner {__version__}. Seed {s.seed}, {s.draws:,} permutation draws, "
                f"{s.paths:,} bootstrap paths, best-n {s.best_n}, risk-free rate "
                f"{s.risk_free_pct:g}% a year. The same file and settings give the same report."
            ],
        )
    )
    return Report(f"Coroner report: {source_name}", verdict(a), sections)


# ---- rendering -------------------------------------------------------------


def render_markdown(report: Report, figure_dir: str = "figures") -> str:
    """Markdown text. Figures are referenced as files under ``figure_dir``."""
    lines = [f"# {report.title}", "", "## Verdict", "", " ".join(report.verdict), ""]
    for section in report.sections:
        lines += [f"## {section.title}", ""]
        for paragraph in section.paragraphs:
            lines += [paragraph, ""]
        for table in section.tables:
            lines.append("| " + " | ".join(table.header) + " |")
            lines.append("|" + "|".join([":--"] + ["--:"] * (len(table.header) - 1)) + "|")
            lines += ["| " + " | ".join(row) + " |" for row in table.rows]
            lines.append("")
        if section.figure is not None:
            lines += [f"![{section.figure.alt}]({figure_dir}/{section.figure.name})", ""]
    return "\n".join(lines)


_CSS = """
body { font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; color: #0b0b0b;
       background: #ffffff; max-width: 920px; margin: 2rem auto; padding: 0 1rem; }
h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
h2 { font-size: 1.1rem; margin-top: 2.2rem; border-bottom: 1px solid #e4e3df;
     padding-bottom: 0.2rem; }
p { margin: 0.5rem 0; }
.verdict { border-left: 4px solid #2a78d6; background: #f5f7fa; padding: 0.8rem 1rem;
           font-size: 1.05rem; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; margin: 0.8rem 0; font-variant-numeric: tabular-nums; }
th, td { padding: 0.25rem 0.7rem; border-bottom: 1px solid #e4e3df; text-align: right;
         white-space: nowrap; }
th { color: #52514e; font-weight: 600; }
th:first-child, td:first-child { text-align: left; }
img { max-width: 100%; height: auto; }
code { background: #f1f0ec; padding: 0 0.2rem; }
"""


def _inline(text: str) -> str:
    """Escape, then turn the few markdown marks the report uses into HTML."""
    out = html.escape(text)
    for mark, tag in (("**", "strong"), ("`", "code")):
        parts = out.split(mark)
        if len(parts) % 2 == 1:
            out = "".join(
                part if i % 2 == 0 else f"<{tag}>{part}</{tag}>" for i, part in enumerate(parts)
            )
    return out


def render_html(report: Report) -> str:
    """One HTML file with styles and charts embedded; it needs nothing else."""
    out = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html.escape(report.title)}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        f"<h1>{html.escape(report.title)}</h1>",
        "<h2>Verdict</h2>",
        f'<p class="verdict">{_inline(" ".join(report.verdict))}</p>',
    ]
    for section in report.sections:
        out.append(f"<h2>{html.escape(section.title)}</h2>")
        out += [f"<p>{_inline(p)}</p>" for p in section.paragraphs]
        for table in section.tables:
            out.append('<div class="scroll"><table>')
            out.append(
                "<tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in table.header) + "</tr>"
            )
            for row in table.rows:
                out.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>")
            out.append("</table></div>")
        if section.figure is not None:
            data = base64.b64encode(section.figure.png).decode("ascii")
            alt = html.escape(section.figure.alt)
            out.append(f'<p><img alt="{alt}" src="data:image/png;base64,{data}"></p>')
    out += ["</body>", "</html>", ""]
    return "\n".join(out)


def write_report(report: Report, out_dir: Path) -> tuple[Path, Path]:
    """Write ``report.md``, ``report.html`` and ``figures/*.png`` into ``out_dir``."""
    figures = out_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    for section in report.sections:
        if section.figure is not None:
            (figures / section.figure.name).write_bytes(section.figure.png)
    md_path = out_dir / "report.md"
    html_path = out_dir / "report.html"
    md_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    html_path.write_text(render_html(report), encoding="utf-8", newline="\n")
    return md_path, html_path
