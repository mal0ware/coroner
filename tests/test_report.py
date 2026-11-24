"""End to end: a hand-built file through the analysis, the report and the CLI."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from conftest import WriteCsv
from coroner import cli, samples
from coroner.analysis import Settings, analyse
from coroner.report import build_report, render_html, render_markdown
from coroner.trades import load_trades
from coroner.verdict import verdict

ROOT = Path(__file__).resolve().parent.parent
FAST = Settings(paths=300, draws=100)

# Six trades over three days. Net: 100, -20, 30, -10, 50, -30 = 120. Cost 2 each.
HAND = [
    ["2025-03-10T09:30:00", "2025-03-10T09:32:00", "102", "100"],  # Monday
    ["2025-03-10T09:40:00", "2025-03-10T09:43:00", "-18", "-20"],
    ["2025-03-11T09:50:00", "2025-03-11T09:54:00", "32", "30"],  # Tuesday
    ["2025-03-11T14:00:00", "2025-03-11T15:00:00", "-8", "-10"],
    ["2025-03-12T14:10:00", "2025-03-12T15:10:00", "52", "50"],  # Wednesday
    ["2025-03-12T14:20:00", "2025-03-12T15:20:00", "-28", "-30"],
]


def test_hand_built_file_exact_numbers(write_csv: WriteCsv) -> None:
    settings = Settings(
        capital=1000.0, best_n=1, min_bucket_trades=3, paths=300, draws=100, target=50.0
    )
    a = analyse(load_trades(write_csv(HAND)), settings)

    assert (a.n, a.net.total, a.net.mean) == (6, 120.0, 20.0)
    # squared deviations from 20: 6400 + 1600 + 100 + 900 + 900 + 2500 = 12400
    assert a.net.sd == pytest.approx(math.sqrt(12400 / 5))
    assert a.net.t_stat == pytest.approx(20 / math.sqrt(2480) * math.sqrt(6))

    # halves: 100 - 20 + 30 = 110, then -10 + 50 - 30 = 10
    assert (a.halves.first.total, a.halves.second.total) == (110.0, 10.0)

    # best one is 100: 83.3% of 120. Remove 100 and 50 and the rest is -30.
    assert a.leave_n.share == pytest.approx(100 / 120)
    assert a.leave_n.rest.total == pytest.approx(20.0)
    assert a.leave_5pct.removed == 1
    assert a.to_zero == 2

    # 09:00 bucket: 100 - 20 + 30 = 110, holds 2, 3, 4 min: median 3, flagged at 3 trades
    morning, afternoon = a.time_of_day
    assert (morning.label, morning.n, morning.total) == ("09:00-10:00", 3, 110.0)
    assert morning.median_hold_minutes == 3.0 and morning.short_hold
    assert (afternoon.label, afternoon.total, afternoon.short_hold) == ("14:00-15:00", 10.0, False)
    assert [(r.label, r.total) for r in a.weekday] == [
        ("Monday", 80.0),
        ("Tuesday", 20.0),
        ("Wednesday", 20.0),
    ]

    # gross 132, cost 12
    assert a.cost.cost_total == pytest.approx(12.0)
    assert a.cost.share == pytest.approx(12 / 132)

    # trade-by-trade equity 1000, 1100, 1080, 1110, 1100, 1150, 1120:
    # drops of 20, 10 and 30, so the maximum drawdown is 30, 30/1150 of the peak
    assert a.drawdown.max_drawdown == pytest.approx(30.0)
    assert a.drawdown.max_drawdown_pct == pytest.approx(100 * 30 / 1150)
    assert a.drawdown.recovery_factor == pytest.approx(4.0)
    # longest spell under water: the 1110 peak (Tuesday 09:54) until 1150 (Wednesday 15:10)
    assert a.drawdown.underwater == np.timedelta64(29 * 60 + 16, "m")
    assert a.drawdown.underwater_recovered
    # daily closes 1000 (start), 1080, 1100, 1120: never below a previous close
    assert a.drawdown.ulcer_index == 0.0 and math.isnan(a.drawdown.martin_ratio)
    # three days is too short to annualise
    assert math.isnan(a.drawdown.annual_return_pct)

    assert [(p.positive, p.total) for p in a.periods] == [(3, 3), (1, 1), (1, 1)]

    # target 50, loss limit 10% of 1000 = 100, horizon 6 trades
    assert (a.barrier.target, a.barrier.loss_limit, a.barrier.horizon) == (50.0, 100.0, 6)
    for result in (a.barrier.iid, a.barrier.stationary):
        assert result.hit_target + result.hit_loss + result.neither == 300

    assert a.cumulative.tolist() == [100, 80, 110, 100, 150, 120]
    assert a.cumulative_without_best.tolist() == [0, -20, 10, 0, 50, 20]


def test_hand_built_verdict(write_csv: WriteCsv) -> None:
    a = analyse(load_trades(write_csv(HAND)), Settings(best_n=1, min_bucket_trades=3, paths=50))
    sentences = verdict(a)
    assert 3 <= len(sentences) <= 5
    # Six trades are too few for the share to stand out against a Normal null.
    assert sentences[1].startswith("The best trade carries 83% of the profit, against a median")
    assert sentences[1].endswith("and the best two would have to go before the total reached zero.")
    assert sentences[3].startswith("The 09:00-10:00 window holds 3 trades for a median of 3.0 min")


def test_settings_are_validated() -> None:
    for bad in (
        Settings(capital=0),
        Settings(best_n=0),
        Settings(bucket_minutes=7),
        Settings(target=-1),
        Settings(loss_limit=0),
        Settings(horizon=0),
        Settings(paths=0),
        Settings(mean_block=0.5),
    ):
        with pytest.raises(ValueError):
            bad.validate()


def test_optional_columns_add_sections(write_csv: WriteCsv) -> None:
    header = ["entry_time", "exit_time", "gross", "net", "symbol", "side", "size"]
    extra = [["ES", "long", "1"], ["ES", "short", "2"], ["NQ", "long", "1"]] * 2
    path = write_csv([[*r, *e] for r, e in zip(HAND, extra, strict=True)], header=header)
    a = analyse(load_trades(path), FAST)
    assert a.by_symbol is not None and a.by_side is not None
    # ES: 100 - 20 - 10 + 50 = 120; NQ: 30 - 30 = 0
    assert [(r.label, r.total) for r in a.by_symbol] == [("ES", 120.0), ("NQ", 0.0)]
    # long: 100 + 30 - 10 - 30 = 90; short: -20 + 50 = 30
    assert [(r.label, r.total) for r in a.by_side] == [("long", 90.0), ("short", 30.0)]
    text = render_markdown(build_report(a, "trades.csv"))
    assert "## By symbol" in text and "## By side" in text and "Median trade size" in text


def test_losing_log_has_defined_output(write_csv: WriteCsv) -> None:
    rows = [[r[0], r[1], str(-float(r[2])), str(-float(r[2]) - 2)] for r in HAND]
    a = analyse(load_trades(write_csv(rows)), FAST)
    assert a.cost.share is None and a.to_zero == 0 and math.isnan(a.leave_n.share)
    text = render_markdown(build_report(a, "trades.csv"))
    assert "not defined: the gross result is zero or negative" in text
    assert "The log did not make money" in text
    assert "costs cannot be stated as a share of gross profit" in text


def test_cli_writes_both_reports(write_csv: WriteCsv, tmp_path: Path) -> None:
    out = tmp_path / "out"
    code = cli.main(
        ["report", str(write_csv(HAND)), "--out", str(out), "--paths", "200", "--draws", "50"]
    )
    assert code == 0
    md = (out / "report.md").read_text(encoding="utf-8")
    page = (out / "report.html").read_text(encoding="utf-8")
    assert md.startswith("# Coroner report: trades.csv\n\n## Verdict\n\n6 trades made 120.00 net")
    for name in ("equity", "time_of_day", "weekday", "drawdown"):
        assert (out / "figures" / f"{name}.png").read_bytes().startswith(b"\x89PNG")
        assert f"figures/{name}.png" in md
    # self-contained: charts embedded, nothing fetched
    assert page.count("data:image/png;base64,") == 4
    for external in ("http://", "https://", "<script", "<link", 'src="figures'):
        assert external not in page
    assert "6 trades made 120.00 net" in page


def test_cli_default_output_directory(
    write_csv: WriteCsv, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert cli.main(["report", str(write_csv(HAND)), "--paths", "50", "--draws", "20"]) == 0
    assert (tmp_path / "trades-report" / "report.html").is_file()


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ([], "missing required column(s)"),
        (["--bucket-minutes", "7"], "bucket-minutes must divide 1440"),
    ],
)
def test_cli_reports_errors_and_exits_2(
    write_csv: WriteCsv,
    capsys: pytest.CaptureFixture[str],
    extra: list[str],
    message: str,
) -> None:
    path = write_csv([["1", "2"]], header=["a", "b"]) if not extra else write_csv(HAND)
    assert cli.main(["report", str(path), *extra]) == 2
    err = capsys.readouterr().err
    assert err.startswith("coroner: error:") and message in err


def test_same_input_same_report(write_csv: WriteCsv) -> None:
    path = write_csv(HAND)
    first = build_report(analyse(load_trades(path), FAST), "trades.csv")
    second = build_report(analyse(load_trades(path), FAST), "trades.csv")
    assert render_markdown(first) == render_markdown(second)
    assert render_html(first) == render_html(second)


def test_seed_changes_only_the_resampled_numbers(write_csv: WriteCsv) -> None:
    log = load_trades(write_csv(HAND))
    a = analyse(log, Settings(paths=400, draws=100, target=60, loss_limit=60, seed=1))
    b = analyse(log, Settings(paths=400, draws=100, target=60, loss_limit=60, seed=2))
    assert a.net == b.net and a.leave_n == b.leave_n and a.drawdown == b.drawdown
    assert a.barrier.iid != b.barrier.iid


# ---- the shipped samples ---------------------------------------------------


def test_committed_samples_match_the_generator(tmp_path: Path) -> None:
    for fresh in samples.write_samples(tmp_path):
        assert fresh.read_bytes() == (ROOT / "samples" / fresh.name).read_bytes()


def test_samples_have_the_same_total_and_different_causes() -> None:
    broad = analyse(load_trades(ROOT / "samples" / "broad.csv"), FAST)
    conc = analyse(load_trades(ROOT / "samples" / "concentrated.csv"), FAST)
    assert broad.n == conc.n == samples.N_TRADES
    assert broad.net.total == pytest.approx(samples.TOTAL, abs=1e-6)
    assert conc.net.total == pytest.approx(samples.TOTAL, abs=1e-6)

    # concentrated: ten trades carry 99% by construction, in a short-hold window
    assert conc.leave_n.share == pytest.approx(samples.BIG_SHARE, abs=1e-9)
    assert conc.to_zero == 11
    flagged = [r for r in conc.time_of_day if r.short_hold]
    assert [r.label for r in flagged] == ["09:00-10:00"]
    assert flagged[0].n == samples.N_OPEN and flagged[0].median_hold_minutes < 5

    # broad: no window is flagged and the best ten carry well under half
    assert not any(r.short_hold for r in broad.time_of_day)
    assert broad.leave_n.share < 0.5 and broad.to_zero > 30

    # The ten big trades inflate the standard deviation the Normal null is drawn
    # with, so at t = 2.4 the null's own best ten carry about half the profit and
    # 99% does not stand out (p > 0.05). The leave-out t and the time-of-day test
    # are what separate the two samples.
    assert conc.null_normal is not None and conc.null_normal.share_p > 0.05
    assert conc.leave_n.rest.t_stat < 0.1
    assert verdict(conc)[1].startswith("The best ten trades carry 99% of the profit")
    assert broad.null_normal is not None and broad.null_normal.share_p > 0.2
    assert verdict(broad)[1].startswith("The best ten trades carry")
    assert 3 <= len(verdict(broad)) <= 5 and 3 <= len(verdict(conc)) <= 5


def test_sample_timestamps_are_timezone_aware() -> None:
    log = load_trades(ROOT / "samples" / "broad.csv")
    assert "timezone-aware" in log.clock
    minutes = (log.entry_local - log.entry_local.astype("datetime64[D]")) / np.timedelta64(1, "m")
    assert minutes.min() >= 9 * 60 + 30 and minutes.max() < 15 * 60 + 30
