# Coroner

**Give it a list of trades. It tells you what the profit died of.**

## The result

Two synthetic trade logs each hold 400 trades and each made exactly 20,000.00 net. Their per-trade t-statistics are 3.98 and 2.40, so both pass the usual "more than two standard errors" check. In the first, the best ten trades carry 31.7% of the profit and 42 would have to go before the total reached zero. In the second, ten trades carry 99.0%, the other 390 made 200.00 between them, and 97.2% of the profit sits in one hour of the day where trades are held for a median of 3.2 minutes.

![Cumulative net result of the two sample logs, with and without the best ten trades](results/headline.png)

The verdict paragraph that opens each report, exactly as the tool wrote it:

| `samples/broad.csv` | `samples/concentrated.csv` |
|:--|:--|
| 400 trades made 20,000.00 net, a mean of 50.00 per trade with a t-statistic of 3.98, which is more than two standard errors from zero. The best ten trades carry 32% of the profit, and the best 42 would have to go before the total reached zero. The first half of the trades made 10,929.37 and the second half made 9,070.63. | 400 trades made 20,000.00 net, a mean of 50.00 per trade with a t-statistic of 2.40, which is more than two standard errors from zero. Ten trades carry 99% of the profit: the other 390 made 200.00 between them. The first half of the trades made 13,176.52 and the second half made 6,823.48. The 09:00-10:00 window holds 60 trades for a median of 3.2 minutes and accounts for 97% of the profit. |
| [full report](results/broad/report.md) | [full report](results/concentrated/report.md) |

The rest of the numbers, side by side (`results/summary.md`):

| | broad | concentrated |
|:--|--:|--:|
| Net total | 20,000.00 | 20,000.00 |
| t-statistic | 3.98 | 2.40 |
| Share of profit in the best 10 | 31.7% | 99.0% |
| Total without the best 10 | 13,658.48 | 200.00 |
| t-statistic without the best 10 | 2.93 | 0.04 |
| Total without the best 5% (20 trades) | 8,739.73 | -6,212.43 |
| Best trades to remove to reach zero | 42 | 11 |
| Permutation p, time of day | 0.9265 | 0.0005 |
| Permutation p, weekday | 0.5717 | 0.7616 |
| Short-hold buckets | none | 09:00-10:00 |
| Cost share of gross | 16.8% | 16.3% |
| Ulcer index (%) | 0.678 | 0.961 |
| Recovery factor | 6.98 | 5.21 |
| Positive months | 12 of 12 | 9 of 12 |
| Target first / loss limit first / neither, i.i.d. bootstrap | 98.6% / 0.0% / 1.4% | 92.1% / 0.1% / 7.8% |
| The same without the best 10 | 85.4% / 0.0% / 14.6% | 6.8% / 5.9% / 87.4% |

Two things in that table did not separate the logs. Cost share is the same by construction. The target-before-loss-limit odds are high for both, because resampling the concentrated log deals the ten large winners back in at the rate they occurred. The odds only fall apart once those ten are removed (6.8% against 85.4%). See Limits.

The samples are synthetic and were built to differ in this way, so the result shows that the report tells the two cases apart. It says nothing about any real strategy.

## Reproduce

```
uv sync
uv run python scripts/reproduce.py
uv run pytest
```

`reproduce.py` regenerates the two sample logs, both reports, the chart above and the tables in `results/`. It takes about ten seconds. `--fast` uses fewer paths and draws, for CI.

## Use it on your own trades

```
uv run coroner report trades.csv
```

This writes `trades-report/report.md`, `trades-report/report.html` and `trades-report/figures/`. The HTML file has its styles and charts embedded and needs nothing else. The verdict is also printed to the terminal.

The input is a CSV with one row per closed trade.

| Column | Required | Meaning |
|:--|:--|:--|
| `entry_time` | yes | ISO 8601, for example `2025-03-10T09:31:00-04:00` or `2025-03-10 09:31:00` |
| `exit_time` | yes | ISO 8601, not before `entry_time` |
| `gross` | yes | result before costs, in account currency |
| `net` | yes | result after costs |
| `symbol` | no | free text; adds a by-symbol table |
| `side` | no | `long` or `short` (`buy` and `sell` are accepted); adds a by-side table |
| `size` | no | positive number; the median is reported |

Column names are matched after trimming spaces and lower-casing, and other columns are ignored. Timestamps must all carry a UTC offset or all carry none. With offsets, the time of day is taken as written in the file, or converted with `--tz America/New_York`. Without offsets the times are used as written. Holding times always come from the true instants, so a daylight-saving change does not distort them. At least two trades are needed.

A file that breaks these rules is rejected with the row and the reason, for example `row 17: exit_time '2025-03-10T09:00:00' is before entry_time '2025-03-10T09:31:00'`, and the exit code is 2.

Options, with their defaults:

| Option | Default | Meaning |
|:--|:--|:--|
| `--out DIR` | `<file stem>-report` | output directory |
| `--tz ZONE` | none | convert timezone-aware timestamps to this zone |
| `--capital` | 100000 | starting equity; percentage drawdowns depend on it |
| `--best-n` | 10 | how many of the best trades to leave out |
| `--bucket-minutes` | 60 | width of time-of-day buckets |
| `--short-hold-minutes` | 5 | a bucket is flagged when its median hold is below this |
| `--min-bucket-trades` | 20 | and it has at least this many trades |
| `--target`, `--loss-limit` | 10% of capital each | the two barriers, as positive amounts |
| `--horizon` | number of trades in the file | trades per resampled path |
| `--paths` | 10000 | resampled paths |
| `--draws` | 2000 | permutation draws |
| `--block` | 10 | mean block length of the stationary bootstrap, in trades |
| `--risk-free` | 0 | percent a year, for the Martin ratio |
| `--seed` | 0 | the same file, settings and seed give the same report |

## What was built

Nine checks, each a pure function in `src/coroner/checks.py` or `src/coroner/barrier.py` with its own tests.

1. Per-trade mean, standard deviation (n - 1) and t-statistic, mean / sd x sqrt(n).
2. A label-shuffle permutation test. The statistic is the between-group sum of squares of net results grouped by time-of-day bucket, and again by weekday. Labels are shuffled 2,000 times with a fixed seed.
3. First half against second half, in exit-time order, split by count.
4. Profit by entry time-of-day bucket and by weekday, with the median holding time of each bucket and a flag for short holds.
5. Leave-out: total, mean and t-statistic without the best N trades and without the best 5%, the share of profit those trades carried, and the smallest number of best trades whose removal takes the total to zero or below.
6. Cost share: total cost over total gross result. When gross is zero or negative the share is reported as not defined.
7. Ulcer index, Martin ratio, maximum drawdown, longest time under water and recovery factor. Recovery factor (net profit over maximum drawdown) is a trading-platform convention. I found no source for it in the literature.
8. Share of days, months and quarters that ended positive, with counts. Only periods with a closed trade are counted.
9. The chance of reaching a profit target before a loss limit. Trades are resampled by the i.i.d. bootstrap and by the stationary bootstrap, each path's running total is followed, and paths that reach neither barrier are reported separately. The Brownian closed form is printed beside them.

### The verdict rules

The verdict is three to five sentences. Each comes from one fixed rule in `src/coroner/verdict.py`.

1. Headline, always: trade count, net total, mean and t-statistic, and whether |t| is at least 2.
2. Concentration, always. If the best N trades carry at least half the profit: "N trades carry X% of the profit" and what the others made. Otherwise the share they carry and the number that must go to reach zero. If the log lost money it says there is no profit to attribute.
3. Halves, always: what each half made or lost.
4. Time, only when triggered. If a time-of-day bucket is flagged for short holds, the flagged bucket with the largest absolute profit is named. Otherwise, if a permutation test has p below 0.01, that is stated.
5. Costs, only when triggered: costs are at least half of gross, or gross is not positive.

## Sources

- Peter G. Martin and Byron McCann, The Investor's Guide to Fidelity Funds, Wiley, 1989 (the ulcer index). I read Martin's own statement of the formula at tangotools.com/ui/ui.htm, not the book.
- Dimitris N. Politis and Joseph P. Romano, "The Stationary Bootstrap", Journal of the American Statistical Association 89(428), 1994, 1303-1313. The JASA text is paywalled. The algorithm was taken from the same authors' "Limit theorems for weakly dependent Hilbert space valued random variables with application to the stationary bootstrap", Statistica Sinica 4, 1994, Section 3.1.
- Karl Sigman, lecture notes on Brownian motion and on the gambler's ruin problem, Columbia University, for the two closed forms.

`PAPER.md` has each formula with its location in the source.

## Comparison with the sources

There is no paper result to replicate here. The comparison is between the barrier simulator and the closed forms it should agree with (`results/barrier_check.md`, 20,000 paths per row):

| Case | Exact | Simulated | Difference | z |
|:--|--:|--:|--:|--:|
| Fair +-1 walk, target 15, limit 10 | 0.4000 | 0.4001 | +0.0001 | +0.03 |
| +-1 walk, p = 0.55, target 10, limit 10 | 0.8815 | 0.8771 | -0.0043 | -1.90 |
| +-1 walk, p = 0.45, target 10, limit 10 | 0.1185 | 0.1123 | -0.0062 | -2.71 |
| Gaussian steps, sd 0.5, target 15, limit 10 | 0.5215 | 0.5265 | +0.0050 | +1.42 |
| Gaussian steps, sd 0.25, target 15, limit 10 | 0.5215 | 0.5219 | +0.0003 | +0.09 |

The third row is 2.7 standard errors low. I reran both biased walks at 200,000 paths with three other seeds each. The p = 0.45 walk came out at z = -1.66, -0.87 and -0.70, and the p = 0.55 walk at -0.55, -0.09 and +0.39. I found no cause in the code and read the row as a chance draw, but all four p = 0.45 runs are below the exact value and I have not ruled out a small bias. The committed table is the original run.

The ulcer index and the Martin ratio differ from Martin's statement in three small ways, listed in `PAPER.md`.

## Data

Any trade log with entry time, exit time, gross and net result. The two samples in `samples/` are random numbers from a seeded generator (`src/coroner/samples.py`). They use the weekdays of 2025 with no holiday calendar and contain no market data. Nothing is downloaded, and `scripts/fetch_data.py` only says so.

## How it is tested

127 tests, the maths first.

- Exact algebra on small hand-built inputs for every check, with the arithmetic written in a comment beside each expected value
- The ulcer index against the loop printed on Martin's page
- The barrier simulator against a/(a+b) for a fair +-1 walk, the gambler's ruin formula for a biased one, and the Brownian closed form for Gaussian steps
- The Brownian formula against its mu -> 0 limit, its reflection symmetry and the gambler's ruin formula at small drift
- The permutation test: mean p near 0.5 over 300 data sets whose labels carry no information, and the exact p of 2/70 on a case small enough to enumerate
- The stationary bootstrap: blocks follow on and wrap, block lengths have the stated mean, a mean block of 1 gives independent draws
- The loader: every rejection names its row; timezone handling across a daylight-saving change
- Each verdict rule against the exact sentence it must produce
- A six-trade file through the whole analysis with every number checked by hand
- Running `reproduce` twice gives byte-identical files, and the committed samples and summary table match what the code produces

## Layout

```
src/coroner/trades.py     read and validate the CSV
src/coroner/checks.py     checks 1 to 8
src/coroner/barrier.py    check 9 and the closed forms
src/coroner/analysis.py   runs every check
src/coroner/verdict.py    the verdict rules
src/coroner/report.py     markdown and HTML
src/coroner/charts.py     the figures
src/coroner/samples.py    the two synthetic logs
src/coroner/cli.py        the command line
tests/                    maths tests first
scripts/reproduce.py      one command rebuilds every figure and table
scripts/make_samples.py   rewrites samples/
scripts/fetch_data.py     nothing to fetch
samples/                  the two synthetic logs
results/                  committed reports, figures and tables
PAPER.md                  citations, formulas, differences from the sources
```

Dependencies are numpy, pandas and matplotlib. The command line uses `argparse` from the standard library.

## Roadmap

- [x] Project skeleton, CI, and the reproduce command
- [x] A command-line tool that reads a CSV of trades and writes an HTML and a markdown report
- [x] Per-trade t-statistic, and a label-shuffle permutation test
- [x] First half against second half
- [x] Profit by time of day and by weekday, with a flag for windows where trades are held only minutes
- [x] The result without the best N trades, and how many of the best trades must go before the total reaches zero
- [x] Cost as a share of gross profit
- [x] Ulcer index, recovery factor, and the share of days, months and quarters that ended positive
- [x] The odds of reaching a profit target before a loss limit, by resampling the trades
- [x] `PAPER.md` comparison with the sources
- [x] Results and limits written up at the top of this file

## Limits

- The headline is a demonstration on synthetic logs built to differ. It has not been run on a real trade log in this repository.
- The t-statistic did not catch the concentrated log: 2.40 with ten trades carrying 99% of the profit. It treats trades as independent draws from one distribution, and ten outliers in 400 still leave a mean 2.4 standard errors above zero.
- The barrier odds did not catch it either. Resampling gave the concentrated log a 92.1% chance of reaching +10,000 before -10,000, because the bootstrap assumes the ten large winners keep arriving at the same rate. Resampling assumes the future looks like the sample.
- The stationary bootstrap's mean block of 10 trades is a default I picked. It is not estimated from the data, and on these samples, which have no serial dependence by construction, it changed the odds by about a point.
- Percentage drawdowns, the ulcer index and the Martin ratio depend on `--capital`. The default of 100,000 is arbitrary. The Martin ratios of 29.73 and 21.00 above are that large because the samples lose little against that capital, and they mean nothing beyond the comparison.
- The ulcer index is computed on end-of-day equity over every calendar day, weekends included. Intraday drawdowns do not enter it. Maximum drawdown and time under water use the trade-by-trade curve and do see them.
- Equity moves only when a trade closes. Open-trade losses are invisible, so every drawdown figure is a lower bound.
- The short-hold flag uses fixed thresholds (median under 5 minutes, at least 20 trades). It marks a window to look at. It does not show that the fills were unrealistic.
- The permutation tests cover two labelings. With two tests the verdict uses p below 0.01, which is a rough allowance and not a formal correction.
- Positive-period shares count only periods with a closed trade.
- It judges the trades you give it. It cannot see the versions you tried and threw away; Procrustes is the tool for that.
- The checks came out of a private project, where they showed that a strategy with 202 trades owed 99% of its gain to 10 of them. That figure is the owner's and is not reproduced here.
- This is research code. It is not investment advice and it does not trade.

## The name

A coroner does not ask whether the patient looked healthy. A coroner finds the cause.

## Licence

MIT. See `LICENSE`.
