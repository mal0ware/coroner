# Coroner report: market_ma200.csv

## Verdict

282 trades made 1,213,323.09 net, a mean of 4,302.56 per trade with a t-statistic of 4.87, which is more than two standard errors from zero. Ten trades carry 55% of the profit, against a median of 30% for logs drawn from a Normal with the same mean and spread (p = 0.0100): the other 272 made 551,084.03 between them. The first half of the trades made 663,943.80 and the second half made 549,379.29.

## Input

File `market_ma200.csv`: 282 trades, first entry 1927-03-03 16:00, last exit 2026-09-30 16:00.

Clock: timestamps without offset, used as written. Trades are ordered by exit time.

Starting capital 100,000.00 (set with `--capital`). Percentage drawdowns, the ulcer index and the Martin ratio depend on it.

## Per-trade result

The t-statistic is mean / standard deviation x sqrt(number of trades), with the n - 1 standard deviation. It treats trades as independent draws.

The clustered t-statistics use a cluster-robust standard error: trades that exit on the same day (or in the same month) may be correlated in any way, and the days (months) are taken as independent. With few clusters the clustered standard error is itself noisy.

|  | Trades | Total | Mean | Std dev | t-statistic |
|:--|--:|--:|--:|--:|--:|
| Net | 282 | 1,213,323.09 | 4,302.56 | 14,844.04 | 4.87 |
| Gross | 282 | 1,241,523.09 | 4,402.56 | 14,844.04 | 4.98 |

| Net, t-statistic | Clusters | t-statistic |
|:--|--:|--:|
| Trades independent | 282 | 4.87 |
| Clustered by exit day | 282 | 4.87 |
| Clustered by exit month | 186 | 4.86 |

![Cumulative net result with and without the best ten trades](figures/equity.png)

## Without the best trades

Trades are ranked by net result and the best are removed. Share of profit is the removed trades' total over the total of all trades.

Smallest number of best trades whose removal takes the total to zero or below: **31** of 282.

|  | Removed | Removed total | Share of profit | Remaining total | Remaining mean | Remaining t |
|:--|--:|--:|--:|--:|--:|--:|
| All trades | 0 | 0.00 | 0.0% | 1,213,323.09 | 4,302.56 | 4.87 |
| Without best 10 | 10 | 662,239.06 | 54.6% | 551,084.03 | 2,026.04 | 4.06 |
| Without best 5% | 15 | 866,092.12 | 71.4% | 347,230.97 | 1,300.49 | 3.36 |

## Is that more concentrated than chance?

Each row draws 2,000 logs of 282 trades under a null and computes the same two numbers. The Normal null keeps the mean and standard deviation and has thin tails and no skew. The reflected null resamples these trades and flips each one about the mean with a random sign, which keeps the tails and removes the skew. p is one-sided: the share of draws at least as concentrated as this log, counting the log itself.

A draw whose total is zero or below counts as fully concentrated. Normal, same mean and std dev: 0 such draws; Trades resampled and reflected about the mean: 0 such draws.

|  | Share in best 10 | 95th pct | p | Trades to zero | 5th pct | p |
|:--|--:|--:|--:|--:|--:|--:|
| This log | 54.6% |  |  | 31 |  |  |
| Normal, same mean and std dev | 30.0% | 44.8% | 0.0100 | 46 | 28 | 0.1024 |
| Trades resampled and reflected about the mean | 40.6% | 56.6% | 0.0670 | 73 | 40 | 0.0185 |

## First half against second half

Trades in exit-time order, split by count: the first n // 2 and the rest.

|  | Trades | Total | Mean | Std dev | t-statistic |
|:--|--:|--:|--:|--:|--:|
| First half | 141 | 663,943.80 | 4,708.82 | 16,732.40 | 3.34 |
| Second half | 141 | 549,379.29 | 3,896.31 | 12,726.33 | 3.64 |

## Time of day

Buckets of 60 minutes by entry time.

A bucket is flagged when its median hold is under 5 minutes and it has at least 20 trades. Results from trades held that briefly depend heavily on the fill and cost assumptions behind them.

Permutation test: not run, all trades fall in one time-of-day bucket.

| Entry time | Trades | Net | Mean | Share of profit | Winners | Median hold (min) | Flag |
|:--|--:|--:|--:|--:|--:|--:|--:|
| 16:00-17:00 | 282 | 1,213,323.09 | 4,302.56 | 100.0% | 29.1% | 10,800.0 |  |

![Net result by entry time of day](figures/time_of_day.png)

## Weekday

By weekday of entry.

Permutation test, weekday labels shuffled 2,000 times across 6 buckets: p = 0.2474. A small p means results differ across buckets more than chance would give.

| Weekday | Trades | Net | Mean | Share of profit | Winners | Median hold (min) | Flag |
|:--|--:|--:|--:|--:|--:|--:|--:|
| Monday | 43 | 369,757.63 | 8,599.01 | 30.5% | 34.9% | 34,560.0 |  |
| Tuesday | 56 | 147,881.72 | 2,640.74 | 12.2% | 25.0% | 9,360.0 |  |
| Wednesday | 57 | 318,790.58 | 5,592.82 | 26.3% | 42.1% | 21,600.0 |  |
| Thursday | 53 | 204,639.63 | 3,861.13 | 16.9% | 22.6% | 7,200.0 |  |
| Friday | 64 | 178,604.20 | 2,790.69 | 14.7% | 26.6% | 15,840.0 |  |
| Saturday | 9 | -6,350.67 | -705.63 | -0.5% | 0.0% | 5,760.0 |  |

![Net result by weekday of entry](figures/weekday.png)

## Costs

Cost is gross minus net, summed over all trades. Cost share is cost over gross.

|  | Amount |
|:--|--:|
| Gross result | 1,241,523.09 |
| Cost | 28,200.00 |
| Net result | 1,213,323.09 |
| Cost share of gross | 2.3% |

## Drawdown

The ulcer index and Martin ratio use end-of-day equity on every calendar day from the first exit to the last. Maximum drawdown, time under water and recovery factor use the trade-by-trade equity curve.

The annualised return is compound, on 365.25 days a year, and is not computed for logs shorter than 30 days.

Recovery factor is net profit over maximum drawdown. It is a trading-platform convention, not a statistic from the literature.

|  | Value |
|:--|--:|
| Ulcer index (%) | 2.102 |
| Annualised return (%) | 2.62 |
| Martin ratio | 1.25 |
| Maximum drawdown | 25,459.80 |
| Maximum drawdown (% of peak) | 12.50 |
| Longest time under water | 1,692 days 0 h |
| Recovery factor | 47.66 |

![Percentage drawdown of end-of-day equity](figures/drawdown.png)

## Positive periods

Net result by exit date. Only periods with at least one closed trade are counted.

|  | Positive | Total | Share |
|:--|--:|--:|--:|
| Days | 82 | 282 | 29.1% |
| Months | 74 | 186 | 39.8% |
| Quarters | 68 | 130 | 52.3% |

## Target before loss limit

Target +10,000.00, loss limit -10,000.00, horizon 282 trades. Trades are resampled into paths and each path's running total is followed until it reaches a barrier or the horizon ends.

The closed form uses the per-trade mean and standard deviation and has no horizon, so it gives no weight to paths that reach neither barrier.

Resampling assumes future trades look like these ones, including the best of them arriving as often as they did here.

|  | Target first | Loss limit first | Neither | Paths |
|:--|--:|--:|--:|--:|
| i.i.d. bootstrap | 86.9% | 13.2% | 0.0% | 10,000 |
| Stationary bootstrap, mean block 10 | 85.8% | 14.2% | 0.0% | 10,000 |
| i.i.d. bootstrap without best 10 | 80.3% | 19.7% | 0.0% | 10,000 |
| Brownian closed form, no horizon | 59.6% | 40.4% |  |  |

## By symbol

| Symbol | Trades | Net | Mean | Share of profit | Winners | Median hold (min) |
|:--|--:|--:|--:|--:|--:|--:|
| Market | 282 | 1,213,323.09 | 4,302.56 | 100.0% | 29.1% | 10,800.0 |

## By side

| Side | Trades | Net | Mean | Share of profit | Winners | Median hold (min) |
|:--|--:|--:|--:|--:|--:|--:|
| long | 282 | 1,213,323.09 | 4,302.56 | 100.0% | 29.1% | 10,800.0 |

## Settings

coroner 0.1.0. Seed 0, 2,000 permutation draws, 10,000 bootstrap paths, best-n 10, risk-free rate 0% a year. The same file and settings give the same report.
