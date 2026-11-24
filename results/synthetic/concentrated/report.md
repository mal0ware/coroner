# Coroner report: concentrated.csv

## Verdict

400 trades made 20,000.00 net, a mean of 50.00 per trade with a t-statistic of 2.40, which is more than two standard errors from zero. The best ten trades carry 99% of the profit, against a median of 51% for logs drawn from a Normal with the same mean and spread (p = 0.1184), and the best eleven would have to go before the total reached zero. The first half of the trades made 13,176.52 and the second half made 6,823.48. The 09:00-10:00 window holds 60 trades for a median of 3.2 minutes and accounts for 97% of the profit.

## Input

File `concentrated.csv`: 400 trades, first entry 2025-01-02 10:42, last exit 2025-12-30 15:51.

Clock: timezone-aware timestamps, wall-clock time as written in the file. Trades are ordered by exit time.

Starting capital 100,000.00 (set with `--capital`). Percentage drawdowns, the ulcer index and the Martin ratio depend on it.

## Per-trade result

The t-statistic is mean / standard deviation x sqrt(number of trades), with the n - 1 standard deviation. It treats trades as independent draws.

The clustered t-statistics use a cluster-robust standard error: trades that exit on the same day (or in the same month) may be correlated in any way, and the days (months) are taken as independent. With few clusters the clustered standard error is itself noisy.

|  | Trades | Total | Mean | Std dev | t-statistic |
|:--|--:|--:|--:|--:|--:|
| Net | 400 | 20,000.00 | 50.00 | 416.46 | 2.40 |
| Gross | 400 | 23,899.11 | 59.75 | 416.49 | 2.87 |

| Net, t-statistic | Clusters | t-statistic |
|:--|--:|--:|
| Trades independent | 400 | 2.40 |
| Clustered by exit day | 202 | 2.51 |
| Clustered by exit month | 12 | 2.90 |

![Cumulative net result with and without the best ten trades](figures/equity.png)

## Without the best trades

Trades are ranked by net result and the best are removed. Share of profit is the removed trades' total over the total of all trades.

Smallest number of best trades whose removal takes the total to zero or below: **11** of 400.

|  | Removed | Removed total | Share of profit | Remaining total | Remaining mean | Remaining t |
|:--|--:|--:|--:|--:|--:|--:|
| All trades | 0 | 0.00 | 0.0% | 20,000.00 | 50.00 | 2.40 |
| Without best 10 | 10 | 19,800.00 | 99.0% | 200.00 | 0.51 | 0.04 |
| Without best 5% | 20 | 26,212.43 | 131.1% | -6,212.43 | -16.35 | -1.25 |

## Is that more concentrated than chance?

Each row draws 2,000 logs of 400 trades under a null and computes the same two numbers. The Normal null keeps the mean and standard deviation and has thin tails and no skew. The reflected null resamples these trades and flips each one about the mean with a random sign, which keeps the tails and removes the skew. p is one-sided: the share of draws at least as concentrated as this log, counting the log itself.

A draw whose total is zero or below counts as fully concentrated. Normal, same mean and std dev: 13 such draws; Trades resampled and reflected about the mean: 22 such draws.

|  | Share in best 10 | 95th pct | p | Trades to zero | 5th pct | p |
|:--|--:|--:|--:|--:|--:|--:|
| This log | 99.0% |  |  | 11 |  |  |
| Normal, same mean and std dev | 50.8% | 151.1% | 0.1184 | 23 | 7 | 0.1339 |
| Trades resampled and reflected about the mean | 67.8% | 190.6% | 0.1859 | 21 | 4 | 0.2034 |

## First half against second half

Trades in exit-time order, split by count: the first n // 2 and the rest.

|  | Trades | Total | Mean | Std dev | t-statistic |
|:--|--:|--:|--:|--:|--:|
| First half | 200 | 13,176.52 | 65.88 | 464.07 | 2.01 |
| Second half | 200 | 6,823.48 | 34.12 | 363.15 | 1.33 |

## Time of day

Buckets of 60 minutes by entry time.

A bucket is flagged when its median hold is under 5 minutes and it has at least 20 trades. Results from trades held that briefly depend heavily on the fill and cost assumptions behind them.

Permutation test, time-of-day labels shuffled 2,000 times across 7 buckets: p = 0.0005. A small p means results differ across buckets more than chance would give.

| Entry time | Trades | Net | Mean | Share of profit | Winners | Median hold (min) | Flag |
|:--|--:|--:|--:|--:|--:|--:|--:|
| 09:00-10:00 | 60 | 19,432.24 | 323.87 | 97.2% | 58.3% | 3.2 | short hold |
| 10:00-11:00 | 57 | 696.81 | 12.22 | 3.5% | 43.9% | 38.1 |  |
| 11:00-12:00 | 60 | -3,921.65 | -65.36 | -19.6% | 40.0% | 39.0 |  |
| 12:00-13:00 | 46 | 906.60 | 19.71 | 4.5% | 52.2% | 49.2 |  |
| 13:00-14:00 | 69 | 2,277.33 | 33.00 | 11.4% | 55.1% | 51.1 |  |
| 14:00-15:00 | 72 | 2,192.80 | 30.46 | 11.0% | 58.3% | 46.5 |  |
| 15:00-16:00 | 36 | -1,584.13 | -44.00 | -7.9% | 44.4% | 37.7 |  |

![Net result by entry time of day](figures/time_of_day.png)

## Weekday

By weekday of entry.

Permutation test, weekday labels shuffled 2,000 times across 5 buckets: p = 0.7616. A small p means results differ across buckets more than chance would give.

| Weekday | Trades | Net | Mean | Share of profit | Winners | Median hold (min) | Flag |
|:--|--:|--:|--:|--:|--:|--:|--:|
| Monday | 69 | 6,918.55 | 100.27 | 34.6% | 50.7% | 29.6 |  |
| Tuesday | 89 | 3,520.45 | 39.56 | 17.6% | 46.1% | 34.0 |  |
| Wednesday | 80 | 5,644.89 | 70.56 | 28.2% | 60.0% | 37.6 |  |
| Thursday | 71 | 1,419.51 | 19.99 | 7.1% | 52.1% | 39.7 |  |
| Friday | 91 | 2,496.60 | 27.44 | 12.5% | 47.3% | 45.1 |  |

![Net result by weekday of entry](figures/weekday.png)

## Costs

Cost is gross minus net, summed over all trades. Cost share is cost over gross.

|  | Amount |
|:--|--:|
| Gross result | 23,899.11 |
| Cost | 3,899.11 |
| Net result | 20,000.00 |
| Cost share of gross | 16.3% |

## Drawdown

The ulcer index and Martin ratio use end-of-day equity on every calendar day from the first exit to the last. Maximum drawdown, time under water and recovery factor use the trade-by-trade equity curve.

The annualised return is compound, on 365.25 days a year, and is not computed for logs shorter than 30 days.

Recovery factor is net profit over maximum drawdown. It is a trading-platform convention, not a statistic from the literature.

|  | Value |
|:--|--:|
| Ulcer index (%) | 0.961 |
| Annualised return (%) | 20.18 |
| Martin ratio | 21.00 |
| Maximum drawdown | 3,841.39 |
| Maximum drawdown (% of peak) | 3.68 |
| Longest time under water | 49 days 2 h (not recovered) |
| Recovery factor | 5.21 |

![Percentage drawdown of end-of-day equity](figures/drawdown.png)

## Positive periods

Net result by exit date. Only periods with at least one closed trade are counted.

|  | Positive | Total | Share |
|:--|--:|--:|--:|
| Days | 100 | 202 | 49.5% |
| Months | 9 | 12 | 75.0% |
| Quarters | 4 | 4 | 100.0% |

## Target before loss limit

Target +10,000.00, loss limit -10,000.00, horizon 400 trades. Trades are resampled into paths and each path's running total is followed until it reaches a barrier or the horizon ends.

The closed form uses the per-trade mean and standard deviation and has no horizon, so it gives no weight to paths that reach neither barrier.

Resampling assumes future trades look like these ones, including the best of them arriving as often as they did here.

|  | Target first | Loss limit first | Neither | Paths |
|:--|--:|--:|--:|--:|
| i.i.d. bootstrap | 92.1% | 0.1% | 7.8% | 10,000 |
| Stationary bootstrap, mean block 10 | 93.1% | 0.0% | 6.9% | 10,000 |
| i.i.d. bootstrap without best 10 | 6.8% | 5.9% | 87.4% | 10,000 |
| Brownian closed form, no horizon | 99.7% | 0.3% |  |  |

## Settings

coroner 0.1.0. Seed 0, 2,000 permutation draws, 10,000 bootstrap paths, best-n 10, risk-free rate 0% a year. The same file and settings give the same report.
