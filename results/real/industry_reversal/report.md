# Coroner report: industry_reversal.csv

## Verdict

5,267 trades made 439,576.14 net, a mean of 83.46 per trade with a t-statistic of 1.90, which is within two standard errors of zero. The best ten trades carry 46% of the profit, against a median of 24% for logs drawn from a Normal with the same mean and spread (p = 0.1869), and the best 28 would have to go before the total reached zero. The first half of the trades made 78,163.99 and the second half made 361,412.15. Costs took 55% of the gross profit.

## Input

File `industry_reversal.csv`: 5,267 trades, first entry 1926-07-08 16:00, last exit 2026-09-30 16:00.

Clock: timestamps without offset, used as written. Trades are ordered by exit time.

Starting capital 100,000.00 (set with `--capital`). Percentage drawdowns, the ulcer index and the Martin ratio depend on it.

## Per-trade result

The t-statistic is mean / standard deviation x sqrt(number of trades), with the n - 1 standard deviation. It treats trades as independent draws.

The clustered t-statistics use a cluster-robust standard error: trades that exit on the same day (or in the same month) may be correlated in any way, and the days (months) are taken as independent. With few clusters the clustered standard error is itself noisy.

|  | Trades | Total | Mean | Std dev | t-statistic |
|:--|--:|--:|--:|--:|--:|
| Net | 5,267 | 439,576.14 | 83.46 | 3,194.53 | 1.90 |
| Gross | 5,267 | 966,276.14 | 183.46 | 3,194.53 | 4.17 |

| Net, t-statistic | Clusters | t-statistic |
|:--|--:|--:|
| Trades independent | 5,267 | 1.90 |
| Clustered by exit day | 5,267 | 1.90 |
| Clustered by exit month | 1,203 | 1.90 |

![Cumulative net result with and without the best ten trades](figures/equity.png)

## Without the best trades

Trades are ranked by net result and the best are removed. Share of profit is the removed trades' total over the total of all trades.

Smallest number of best trades whose removal takes the total to zero or below: **28** of 5,267.

|  | Removed | Removed total | Share of profit | Remaining total | Remaining mean | Remaining t |
|:--|--:|--:|--:|--:|--:|--:|
| All trades | 0 | 0.00 | 0.0% | 439,576.14 | 83.46 | 1.90 |
| Without best 10 | 10 | 200,737.91 | 45.7% | 238,838.23 | 45.43 | 1.07 |
| Without best 5% | 264 | 2,021,385.68 | 459.8% | -1,581,809.54 | -316.17 | -8.51 |

## Is that more concentrated than chance?

Each row draws 2,000 logs of 5,267 trades under a null and computes the same two numbers. The Normal null keeps the mean and standard deviation and has thin tails and no skew. The reflected null resamples these trades and flips each one about the mean with a random sign, which keeps the tails and removes the skew. p is one-sided: the share of draws at least as concentrated as this log, counting the log itself.

A draw whose total is zero or below counts as fully concentrated. Normal, same mean and std dev: 55 such draws; Trades resampled and reflected about the mean: 60 such draws.

|  | Share in best 10 | 95th pct | p | Trades to zero | 5th pct | p |
|:--|--:|--:|--:|--:|--:|--:|
| This log | 45.7% |  |  | 28 |  |  |
| Normal, same mean and std dev | 24.0% | 170.1% | 0.1869 | 50 | 6 | 0.2299 |
| Trades resampled and reflected about the mean | 45.5% | 358.6% | 0.4988 | 29 | 3 | 0.4928 |

## First half against second half

Trades in exit-time order, split by count: the first n // 2 and the rest.

|  | Trades | Total | Mean | Std dev | t-statistic |
|:--|--:|--:|--:|--:|--:|
| First half | 2,633 | 78,163.99 | 29.69 | 3,135.96 | 0.49 |
| Second half | 2,634 | 361,412.15 | 137.21 | 3,251.72 | 2.17 |

## Time of day

Buckets of 60 minutes by entry time.

A bucket is flagged when its median hold is under 5 minutes and it has at least 20 trades. Results from trades held that briefly depend heavily on the fill and cost assumptions behind them.

Permutation test: not run, all trades fall in one time-of-day bucket.

| Entry time | Trades | Net | Mean | Share of profit | Winners | Median hold (min) | Flag |
|:--|--:|--:|--:|--:|--:|--:|--:|
| 16:00-17:00 | 5,267 | 439,576.14 | 83.46 | 100.0% | 52.0% | 10,080.0 |  |

![Net result by entry time of day](figures/time_of_day.png)

## Weekday

By weekday of entry.

Permutation test, weekday labels shuffled 2,000 times across 6 buckets: p = 0.2029. A small p means results differ across buckets more than chance would give.

| Weekday | Trades | Net | Mean | Share of profit | Winners | Median hold (min) | Flag |
|:--|--:|--:|--:|--:|--:|--:|--:|
| Monday | 926 | 170,618.56 | 184.25 | 38.8% | 50.5% | 10,080.0 |  |
| Tuesday | 1,004 | 270,177.75 | 269.10 | 61.5% | 55.6% | 10,080.0 |  |
| Wednesday | 1,069 | 14,993.05 | 14.03 | 3.4% | 51.6% | 10,080.0 |  |
| Thursday | 1,020 | -9,246.37 | -9.07 | -2.1% | 51.1% | 10,080.0 |  |
| Friday | 1,016 | 23,113.89 | 22.75 | 5.3% | 51.5% | 10,080.0 |  |
| Saturday | 232 | -30,080.74 | -129.66 | -6.8% | 51.3% | 8,640.0 |  |

![Net result by weekday of entry](figures/weekday.png)

## Costs

Cost is gross minus net, summed over all trades. Cost share is cost over gross.

|  | Amount |
|:--|--:|
| Gross result | 966,276.14 |
| Cost | 526,700.00 |
| Net result | 439,576.14 |
| Cost share of gross | 54.5% |

## Drawdown

The ulcer index and Martin ratio use end-of-day equity on every calendar day from the first exit to the last. Maximum drawdown, time under water and recovery factor use the trade-by-trade equity curve.

The annualised return is compound, on 365.25 days a year, and is not computed for logs shorter than 30 days.

Recovery factor is net profit over maximum drawdown. It is a trading-platform convention, not a statistic from the literature.

|  | Value |
|:--|--:|
| Ulcer index (%) | 20.816 |
| Annualised return (%) | 1.70 |
| Martin ratio | 0.08 |
| Maximum drawdown | 173,634.43 |
| Maximum drawdown (% of peak) | 100.54 |
| Longest time under water | 11,425 days 0 h |
| Recovery factor | 2.53 |

![Percentage drawdown of end-of-day equity](figures/drawdown.png)

## Positive periods

Net result by exit date. Only periods with at least one closed trade are counted.

|  | Positive | Total | Share |
|:--|--:|--:|--:|
| Days | 2,741 | 5,267 | 52.0% |
| Months | 661 | 1,203 | 54.9% |
| Quarters | 238 | 401 | 59.4% |

## Target before loss limit

Target +10,000.00, loss limit -10,000.00, horizon 5,267 trades. Trades are resampled into paths and each path's running total is followed until it reaches a barrier or the horizon ends.

The closed form uses the per-trade mean and standard deviation and has no horizon, so it gives no weight to paths that reach neither barrier.

Resampling assumes future trades look like these ones, including the best of them arriving as often as they did here.

|  | Target first | Loss limit first | Neither | Paths |
|:--|--:|--:|--:|--:|
| i.i.d. bootstrap | 56.0% | 44.0% | 0.0% | 10,000 |
| Stationary bootstrap, mean block 10 | 57.1% | 42.9% | 0.0% | 10,000 |
| i.i.d. bootstrap without best 10 | 54.0% | 46.0% | 0.0% | 10,000 |
| Brownian closed form, no horizon | 54.1% | 45.9% |  |  |

## By symbol

| Symbol | Trades | Net | Mean | Share of profit | Winners | Median hold (min) |
|:--|--:|--:|--:|--:|--:|--:|
| Telcm | 653 | 192,074.46 | 294.14 | 43.7% | 55.3% | 10,080.0 |
| Durbl | 856 | 133,913.77 | 156.44 | 30.5% | 52.5% | 10,080.0 |
| HiTec | 631 | 100,136.06 | 158.69 | 22.8% | 53.1% | 10,080.0 |
| Hlth | 609 | 61,671.01 | 101.27 | 14.0% | 50.7% | 10,080.0 |
| NoDur | 230 | 32,566.02 | 141.59 | 7.4% | 56.5% | 10,080.0 |
| Enrgy | 898 | 18,021.44 | 20.07 | 4.1% | 51.7% | 10,080.0 |
| Shops | 342 | 9,449.62 | 27.63 | 2.1% | 54.1% | 10,080.0 |
| Manuf | 154 | -19,119.18 | -124.15 | -4.3% | 45.5% | 10,080.0 |
| Utils | 622 | -42,122.69 | -67.72 | -9.6% | 50.0% | 10,080.0 |
| Other | 272 | -47,014.37 | -172.85 | -10.7% | 46.7% | 10,080.0 |

## By side

| Side | Trades | Net | Mean | Share of profit | Winners | Median hold (min) |
|:--|--:|--:|--:|--:|--:|--:|
| long | 5,267 | 439,576.14 | 83.46 | 100.0% | 52.0% | 10,080.0 |

## Settings

coroner 0.1.0. Seed 0, 2,000 permutation draws, 10,000 bootstrap paths, best-n 10, risk-free rate 0% a year. The same file and settings give the same report.
