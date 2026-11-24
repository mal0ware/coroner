# Coroner report: broad.csv

## Verdict

400 trades made 20,000.00 net, a mean of 50.00 per trade with a t-statistic of 3.98, which is more than two standard errors from zero. The best ten trades carry 32% of the profit, against a median of 32% for logs drawn from a Normal with the same mean and spread (p = 0.4968), and the best 42 would have to go before the total reached zero. The first half of the trades made 10,929.37 and the second half made 9,070.63.

## Input

File `broad.csv`: 400 trades, first entry 2025-01-02 12:45, last exit 2025-12-31 10:59.

Clock: timezone-aware timestamps, wall-clock time as written in the file. Trades are ordered by exit time.

Starting capital 100,000.00 (set with `--capital`). Percentage drawdowns, the ulcer index and the Martin ratio depend on it.

## Per-trade result

The t-statistic is mean / standard deviation x sqrt(number of trades), with the n - 1 standard deviation. It treats trades as independent draws.

The clustered t-statistics use a cluster-robust standard error: trades that exit on the same day (or in the same month) may be correlated in any way, and the days (months) are taken as independent. With few clusters the clustered standard error is itself noisy.

|  | Trades | Total | Mean | Std dev | t-statistic |
|:--|--:|--:|--:|--:|--:|
| Net | 400 | 20,000.00 | 50.00 | 251.33 | 3.98 |
| Gross | 400 | 24,048.79 | 60.12 | 251.35 | 4.78 |

| Net, t-statistic | Clusters | t-statistic |
|:--|--:|--:|
| Trades independent | 400 | 3.98 |
| Clustered by exit day | 211 | 3.99 |
| Clustered by exit month | 12 | 4.16 |

![Cumulative net result with and without the best ten trades](figures/equity.png)

## Without the best trades

Trades are ranked by net result and the best are removed. Share of profit is the removed trades' total over the total of all trades.

Smallest number of best trades whose removal takes the total to zero or below: **42** of 400.

|  | Removed | Removed total | Share of profit | Remaining total | Remaining mean | Remaining t |
|:--|--:|--:|--:|--:|--:|--:|
| All trades | 0 | 0.00 | 0.0% | 20,000.00 | 50.00 | 3.98 |
| Without best 10 | 10 | 6,341.52 | 31.7% | 13,658.48 | 35.02 | 2.93 |
| Without best 5% | 20 | 11,260.27 | 56.3% | 8,739.73 | 23.00 | 1.98 |

## Is that more concentrated than chance?

Each row draws 2,000 logs of 400 trades under a null and computes the same two numbers. The Normal null keeps the mean and standard deviation and has thin tails and no skew. The reflected null resamples these trades and flips each one about the mean with a random sign, which keeps the tails and removes the skew. p is one-sided: the share of draws at least as concentrated as this log, counting the log itself.

A draw whose total is zero or below counts as fully concentrated. Normal, same mean and std dev: 0 such draws; Trades resampled and reflected about the mean: 0 such draws.

|  | Share in best 10 | 95th pct | p | Trades to zero | 5th pct | p |
|:--|--:|--:|--:|--:|--:|--:|
| This log | 31.7% |  |  | 42 |  |  |
| Normal, same mean and std dev | 31.6% | 52.4% | 0.4968 | 42 | 22 | 0.5332 |
| Trades resampled and reflected about the mean | 29.8% | 50.2% | 0.4008 | 44 | 23 | 0.4478 |

## First half against second half

Trades in exit-time order, split by count: the first n // 2 and the rest.

|  | Trades | Total | Mean | Std dev | t-statistic |
|:--|--:|--:|--:|--:|--:|
| First half | 200 | 10,929.37 | 54.65 | 249.83 | 3.09 |
| Second half | 200 | 9,070.63 | 45.35 | 253.37 | 2.53 |

## Time of day

Buckets of 60 minutes by entry time.

A bucket is flagged when its median hold is under 5 minutes and it has at least 20 trades. Results from trades held that briefly depend heavily on the fill and cost assumptions behind them.

Permutation test, time-of-day labels shuffled 2,000 times across 7 buckets: p = 0.9265. A small p means results differ across buckets more than chance would give.

| Entry time | Trades | Net | Mean | Share of profit | Winners | Median hold (min) | Flag |
|:--|--:|--:|--:|--:|--:|--:|--:|
| 09:00-10:00 | 33 | 21.78 | 0.66 | 0.1% | 48.5% | 52.9 |  |
| 10:00-11:00 | 71 | 3,686.78 | 51.93 | 18.4% | 57.7% | 59.6 |  |
| 11:00-12:00 | 59 | 4,010.29 | 67.97 | 20.1% | 55.9% | 51.3 |  |
| 12:00-13:00 | 71 | 3,922.25 | 55.24 | 19.6% | 56.3% | 48.4 |  |
| 13:00-14:00 | 66 | 2,924.88 | 44.32 | 14.6% | 53.0% | 49.9 |  |
| 14:00-15:00 | 65 | 4,227.31 | 65.04 | 21.1% | 53.8% | 44.6 |  |
| 15:00-16:00 | 35 | 1,206.71 | 34.48 | 6.0% | 45.7% | 33.5 |  |

![Net result by entry time of day](figures/time_of_day.png)

## Weekday

By weekday of entry.

Permutation test, weekday labels shuffled 2,000 times across 5 buckets: p = 0.5717. A small p means results differ across buckets more than chance would give.

| Weekday | Trades | Net | Mean | Share of profit | Winners | Median hold (min) | Flag |
|:--|--:|--:|--:|--:|--:|--:|--:|
| Monday | 76 | 4,791.65 | 63.05 | 24.0% | 53.9% | 43.9 |  |
| Tuesday | 75 | 1,762.62 | 23.50 | 8.8% | 48.0% | 47.2 |  |
| Wednesday | 86 | 3,110.79 | 36.17 | 15.6% | 54.7% | 50.5 |  |
| Thursday | 80 | 3,281.74 | 41.02 | 16.4% | 51.2% | 50.1 |  |
| Friday | 83 | 7,053.20 | 84.98 | 35.3% | 61.4% | 46.8 |  |

![Net result by weekday of entry](figures/weekday.png)

## Costs

Cost is gross minus net, summed over all trades. Cost share is cost over gross.

|  | Amount |
|:--|--:|
| Gross result | 24,048.79 |
| Cost | 4,048.79 |
| Net result | 20,000.00 |
| Cost share of gross | 16.8% |

## Drawdown

The ulcer index and Martin ratio use end-of-day equity on every calendar day from the first exit to the last. Maximum drawdown, time under water and recovery factor use the trade-by-trade equity curve.

The annualised return is compound, on 365.25 days a year, and is not computed for logs shorter than 30 days.

Recovery factor is net profit over maximum drawdown. It is a trading-platform convention, not a statistic from the literature.

|  | Value |
|:--|--:|
| Ulcer index (%) | 0.678 |
| Annualised return (%) | 20.14 |
| Martin ratio | 29.73 |
| Maximum drawdown | 2,864.83 |
| Maximum drawdown (% of peak) | 2.64 |
| Longest time under water | 48 days 1 h |
| Recovery factor | 6.98 |

![Percentage drawdown of end-of-day equity](figures/drawdown.png)

## Positive periods

Net result by exit date. Only periods with at least one closed trade are counted.

|  | Positive | Total | Share |
|:--|--:|--:|--:|
| Days | 123 | 211 | 58.3% |
| Months | 12 | 12 | 100.0% |
| Quarters | 4 | 4 | 100.0% |

## Target before loss limit

Target +10,000.00, loss limit -10,000.00, horizon 400 trades. Trades are resampled into paths and each path's running total is followed until it reaches a barrier or the horizon ends.

The closed form uses the per-trade mean and standard deviation and has no horizon, so it gives no weight to paths that reach neither barrier.

Resampling assumes future trades look like these ones, including the best of them arriving as often as they did here.

|  | Target first | Loss limit first | Neither | Paths |
|:--|--:|--:|--:|--:|
| i.i.d. bootstrap | 98.6% | 0.0% | 1.4% | 10,000 |
| Stationary bootstrap, mean block 10 | 98.7% | 0.0% | 1.3% | 10,000 |
| i.i.d. bootstrap without best 10 | 85.4% | 0.0% | 14.6% | 10,000 |
| Brownian closed form, no horizon | 100.0% | 0.0% |  |  |

## Settings

coroner 0.1.0. Seed 0, 2,000 permutation draws, 10,000 bootstrap paths, best-n 10, risk-free rate 0% a year. The same file and settings give the same report.
