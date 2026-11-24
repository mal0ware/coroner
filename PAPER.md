# Sources, formulas and differences

Coroner replicates no single paper. It uses three published definitions, a few conventions of its own, and Ken French's public return data for the example logs. This file gives each formula as implemented, where it was read, and where the implementation departs from the source.

## What was read and what was not

| Source | Read? |
|:--|:--|
| Peter G. Martin, "Ulcer Index: An Alternative Approach to the Measurement of Investment Risk and Risk-Adjusted Performance", http://www.tangotools.com/ui/ui.htm | Yes. Martin's own page. It has no equation numbers; the sections are named below. |
| Peter G. Martin and Byron McCann, The Investor's Guide to Fidelity Funds: Winning Strategies for Mutual Fund Investors, John Wiley & Sons, 1989 | No. Cited on Martin's page as the origin of the index. |
| Politis and Romano, "The Stationary Bootstrap", JASA 89(428), 1994, 1303-1313 | No. Paywalled, and the Purdue technical-report copy returned 404. |
| Politis and Romano, "Limit theorems for weakly dependent Hilbert space valued random variables with application to the stationary bootstrap", Statistica Sinica 4, 1994, 461-476, https://www3.stat.sinica.edu.tw/statistica/oldpdf/A4n25.pdf | Yes, Section 3.1, pages 467-468. A scanned PDF read from page images. It states the same resampling algorithm by the same authors in the same year. |
| Karl Sigman, "Notes on Brownian Motion", Columbia University, http://www.columbia.edu/~ks20/FE-Notes/4700-07-Notes-BM.pdf | Yes, Sections 1.4 and 1.8. |
| Karl Sigman, "Gambler's Ruin Problem", Columbia University, http://www.columbia.edu/~ks20/stochastic-I/stochastic-I-GRP.pdf | Yes, Sections 1.1 and 1.3. |
| Wikipedia, "Ulcer index" | Yes, as a secondary check on Martin's page only. |
| Kenneth R. French, Data Library, "Fama/French 3 Factors [Daily]" and "10 Industry Portfolios [Daily]", https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html | The data files and the notes at the top of each. Used as data, not as a source of method. |

The stationary-bootstrap algorithm is therefore from a companion paper, not from the JASA article the README cites. Everything else is from the source named.

## Formulas

### Per-trade t-statistic (`checks.trade_stats`)

With net results x_1 ... x_n: mean m = sum(x) / n, s^2 = sum((x - m)^2) / (n - 1), t = m / s x sqrt(n). This is the one-sample t-statistic against a mean of zero. No source was consulted; it is the textbook definition. No p-value is reported, because the trades of a strategy are rarely independent or identically distributed and a p-value would claim more than the number supports.

### Clustered t-statistic (`checks.clustered_t`)

Trades are grouped into clusters by exit day or exit month. With residuals e_i = x_i - m, S_g the sum of e_i over cluster g and G clusters, Var(m) = G / (G - 1) x sum_g S_g^2 / n^2 and t = m / sqrt(Var(m)). This is the usual cluster-robust (sandwich) variance of a sample mean with the G / (G - 1) small-sample factor. No specific source was consulted. With one trade per cluster it reduces to the plain t-statistic, which a test checks. It allows any correlation inside a cluster and none across clusters.

### Concentration nulls (`checks.concentration_null`)

The statistics are the leave-out share of the best k trades and the trades-to-zero count. Each is recomputed on D logs of the same length n drawn under a null:

- Normal: x*_i i.i.d. N(m, s^2), with m and s the log's mean and n - 1 standard deviation.
- Reflected: x*_i = m + e_i (x_J - m), with J uniform on the trades and e_i = +1 or -1 with equal probability. This keeps the mean, the spread and the tail weight of the trades and makes the distribution symmetric about the mean.

A draw whose total is zero or below has no share to compute. It is given share +infinity and trades-to-zero 0, so it counts as fully concentrated. Percentiles are order statistics (numpy's `inverted_cdf`). The one-sided p-value is (1 + draws with share >= observed) / (1 + D), and for trades-to-zero (1 + draws with count <= observed) / (1 + D). Both nulls are this project's construction; no source was consulted.

### Permutation test (`checks.permutation_test`)

Statistic: the between-group sum of squares, sum over groups g of n_g (m_g - m)^2. Under a shuffle of the labels the total sum of squares is fixed, so this orders the shuffles the same way the one-way ANOVA F statistic does. p = (1 + number of shuffles with statistic >= observed) / (1 + draws). The +1 terms count the observed labelling as one of the arrangements, which keeps p above zero. This is the standard Monte Carlo permutation p-value; no specific source was consulted.

### Ulcer index (`checks.ulcer_index`)

Martin's page, section "How is Ulcer Index Calculated?", gives a loop:

```
SumSq = 0
MaxValue = 0
for T = 1 to NumOfPeriods do
  if Value[T] > MaxValue then MaxValue = Value[T]
  else SumSq = SumSq + sqr(100 * ((Value[T] / MaxValue) - 1))
UI = sqrt(SumSq / NumOfPeriods)
```

The running maximum is over all earlier periods, with no lookback window, and the divisor is the number of periods including those at new highs. The implementation is the same quantity in array form: UI = sqrt(mean((100 x (peak_t - value_t) / peak_t)^2)). A test runs Martin's loop on a random series and compares.

### Martin ratio (`checks.martin_ratio`)

Martin's page, section "Measuring Investment Performance": UPI = (Total return - Risk-free return) / UI. Also called the Martin ratio.

### Stationary bootstrap (`barrier.stationary_indices`)

Statistica Sinica 4, Section 3.1:

- Blocks B_{i,b} = {X_i, X_{i+1}, ..., X_{i+b-1}} (eq. 3.1, p. 467).
- Wrapping: for j > n, X_j is X_i with i = j mod n and X_0 = X_n (p. 467).
- Block lengths L_1, L_2, ... are i.i.d. geometric, P(L = m) = (1 - p)^(m-1) p for m = 1, 2, ... (p. 467).
- Block starts I_1, I_2, ... are i.i.d. uniform on {1, ..., n} (p. 468).
- Sequential form: X*_1 = X_{I_1}; given X*_i = X_J, X*_{i+1} is X_{J+1} with probability 1 - p and a uniform draw from the n observations with probability p (p. 468).

The code uses the sequential form. A geometric length with that mass function has mean 1/p, so `--block` sets p = 1 / block. The pages read do not state the mean in those words; it follows from the mass function.

### Target before loss limit, closed forms (`barrier.brownian_hit_probability`, `barrier.gamblers_ruin_probability`)

For X(t) = sigma B(t) + mu t started at 0, Sigman's Brownian-motion notes, Section 1.8, the display after Proposition 1.4, give the probability of reaching a before -b as

p_a = (1 - e^((2 mu / sigma^2) b)) / (e^(-(2 mu / sigma^2) a) - e^((2 mu / sigma^2) b)).

His upper barrier a is this project's target b, and his lower barrier b is this project's loss limit a. With c = 2 mu / sigma^2 and the relabelling, multiplying numerator and denominator by -e^(-c a) gives the form in the README:

P(reach +b before -a) = (1 - e^(-2 mu a / sigma^2)) / (1 - e^(-2 mu (a + b) / sigma^2)),

which tends to a / (a + b) as mu -> 0 (Sigman, Proposition 1.1 for the driftless case).

For a +-1 walk with up-probability p and q = 1 - p, Sigman's gambler's-ruin notes, Section 1.3, eq. (7), give the probability of reaching a before -b as (1 - (q/p)^b) / (1 - (q/p)^(a+b)), or b / (a + b) when p = 1/2. With the same relabelling: P(reach +b before -a) = (1 - (q/p)^a) / (1 - (q/p)^(a+b)).

The sigma symbols in the Brownian display did not survive text extraction from the PDF and were restored from context. The formula was then checked three ways in the tests: against its mu -> 0 limit, against the gambler's ruin formula at small drift, and by simulation.

### The public-data trade logs (`strategies.py`)

Daily returns r_t are read from the first table of each Ken French file and divided by 100. The market return is Mkt-RF + RF. The industry returns are the value-weighted ones.

- Moving-average rule: the level is L_t = prod_{u <= t} (1 + r_u). The signal at close t is L_t > (L_{t-199} + ... + L_t) / 200, and the position over day t + 1 is the signal at close t. A trade is a maximal run of days held long. It enters at the close before the run's first day and exits at the close of its last day. Gross = notional x (prod over the run of (1 + r) - 1).
- Reversal rule: at close t, the industry with the lowest return over days t - 4 .. t is bought and held over days t + 1 .. t + 5, and the next pick is made at close t + 5.
- Net = gross - 0.001 x notional. Notional is 100,000 for the market and reversal rules and 10,000 per industry for the industry rule. A position open on the last day is closed at that close.

### Conventions with no source

- Recovery factor = net profit / maximum drawdown, both in currency. A trading-platform convention.
- Maximum drawdown: the largest fall of equity from a running maximum.
- Longest time under water: the longest span from the last moment at a peak to the first later moment equity is back at or above it. A spell still open at the last trade is measured to that trade and marked not recovered.
- Cost share = sum(gross - net) / sum(gross), reported as not defined when sum(gross) <= 0.
- Leave-out share = sum of the removed trades / sum of all trades, not defined when the total is not positive. It can exceed 100% when the remaining trades lost money.
- Best 5% = ceil(0.05 n) trades.
- Short-hold flag: median hold below 5 minutes with at least 20 trades in the bucket. Both thresholds are options.

## Differences from the sources

1. Ulcer index input. Martin applies the index to a fund's price series. A trade log has no price, so the series is starting capital plus cumulative net result, and the index depends on the `--capital` setting.
2. Ulcer index sampling. The series is end-of-day equity on every calendar day from the first exit to the last, with days that have no closed trade carried forward. Martin's page works with periodic closes and does not treat weekends. A drawdown carried over a weekend therefore counts for three days.
3. Ulcer index first observation. The starting capital is prepended as one extra observation with zero drawdown, so the divisor is the number of days plus one. On the samples, which span about 364 days, this lowers the index by about 0.1%.
4. Martin ratio numerator. Martin's page says "Total return" and does not say annualised. Wikipedia's statement of the same ratio says the returns should be annualised. The code uses the compound annual return on 365.25 days a year, and the risk-free rate defaults to 0. For logs shorter than 30 days the annual return and the ratio are not computed.
5. Stationary bootstrap path length. The paper generates a pseudo-series of the same length n as the data. The code generates paths of `--horizon` trades, which defaults to n and can be set otherwise.
6. Stationary bootstrap block length. The paper leaves p to the user. The default mean block of 10 trades is this project's choice and is not derived from the paper or estimated from the data.
7. Discrete steps against a continuous formula. A resampled path moves in jumps and overshoots a barrier when it crosses; Brownian motion does not. In `results/barrier_check.md` Gaussian steps with sd 0.5 against barriers of 15 and 10 gave 0.52621 against the closed form's 0.52155 (z = +2.95, 100,000 paths), and steps of half that size gave 0.52329 (z = +1.10). The report prints the closed form as a reference and labels it as having no horizon.

## Claims and what was found

| Claim | Result |
|:--|:--|
| The simulator gives a/(a+b) for a fair +-1 walk | 0.40009 against 0.40000, 1,000,000 paths, z = +0.19 |
| The simulator matches the gambler's ruin formula for a biased walk | 0.88118 against 0.88150 (z = -1.00) and 0.11882 against 0.11850 (z = +0.98), 1,000,000 paths each |
| The simulator approaches the Brownian closed form as steps shrink | +0.0047 at sd 0.5 (z = +2.95), +0.0017 at sd 0.25 (z = +1.10), 100,000 paths each |
| A permutation test on uninformative labels returns p near 0.5 | mean p within 0.06 of 0.5 over 300 data sets, in the tests |
| The concentration null gives near-uniform p on data drawn from it | mean p between 0.4 and 0.6, and under 12% of p below 0.05, over 60 data sets, in the tests |
| The report tells the two synthetic samples apart | yes, by the leave-out t-statistic and the time-of-day test; not by the plain t-statistic, the barrier odds or the concentration null (README) |

An earlier version ran the barrier check at 20,000 paths, and the p = 0.45 walk came out 2.7 standard errors below the exact value. Four reruns at 200,000 paths were all low as well, and that write-up said a small bias was not excluded. `reproduce` now runs each walk at 1,000,000 paths. The p = 0.45 walk lands 0.98 standard errors above the exact value and the p = 0.55 walk 1.00 below, so there is no sign of a bias at this precision. The Gaussian row at sd 0.5 is 2.95 standard errors high. That is the overshoot of a discrete step (difference 7), and it shrinks when the step is halved.

## Variants tried

Git history shows what was committed, not when a choice was made relative to a run. What can be said:

- Sample generator: one design, one seed (1989). Its parameters (400 trades, total 20,000, per-trade sd 250, ten large trades carrying 99%, sixty trades in the opening half hour with a 3-minute median hold) were chosen to make the two cases differ.
- The three public-data rules, their sizes and the 10 basis point cost were chosen in the second revision, before Coroner was run on the logs. Each rule was run once. No other rule, window or cost was tried.
- The first version's concentration sentence fired when the best N carried at least half the profit. The second revision replaced that with p below 0.05 against the Normal null, chosen before the real logs were analysed. Post hoc: it does not flag the synthetic concentrated log (p = 0.12). It was kept, and the weakness is reported. A robust scale would flag that log, but switching to one after seeing this would be tuning to a fixture built to be flagged.
- The reflected null and the two clustering periods (exit day, exit month) were chosen with the Normal null, before the real logs were analysed.
- Post hoc: the null's percentiles use order statistics because numpy's default interpolation returned NaN between two infinite shares. The test of the null against a few huge winners first used 500 trades plus 5 winners of 200. The inflated standard deviation hid them (p = 0.096), so the test now uses 2,000 trades plus 5 winners of 60.
- Unchanged from the first version: p below 0.01 for the permutation sentence, the cost share of one half, |t| of 2, the short-hold thresholds, and the barrier defaults (plus and minus 10% of capital, horizon equal to the trade count, 10,000 paths, mean block 10).
- Changed in the first version after seeing output: a six-trade test log annualised to an absurd return, so the annual return and Martin ratio are left undefined for logs under 30 days.
