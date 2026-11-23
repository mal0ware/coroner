# Sources, formulas and differences

Coroner replicates no single paper. It uses three published definitions and a few conventions of its own. This file gives each formula as implemented, where it was read, and where the implementation departs from the source.

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

The stationary-bootstrap algorithm is therefore from a companion paper, not from the JASA article the README cites. Everything else is from the source named.

## Formulas

### Per-trade t-statistic (`checks.trade_stats`)

With net results x_1 ... x_n: mean m = sum(x) / n, s^2 = sum((x - m)^2) / (n - 1), t = m / s x sqrt(n). This is the one-sample t-statistic against a mean of zero. No source was consulted; it is the textbook definition. No p-value is reported, because the trades of a strategy are rarely independent or identically distributed and a p-value would claim more than the number supports.

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
7. Discrete steps against a continuous formula. A resampled path moves in jumps and overshoots a barrier when it crosses; Brownian motion does not. In `results/barrier_check.md` Gaussian steps with sd 0.5 against barriers of 15 and 10 gave 0.5265 against the closed form's 0.5215 (z = +1.42), and steps of half that size gave 0.5219 (z = +0.09). The report prints the closed form as a reference and labels it as having no horizon.

## Claims and what was found

| Claim | Result |
|:--|:--|
| The simulator gives a/(a+b) for a fair +-1 walk | 0.4001 against 0.4000, 20,000 paths, z = +0.03 |
| The simulator matches the gambler's ruin formula for a biased walk | 0.8771 against 0.8815 (z = -1.90) and 0.1123 against 0.1185 (z = -2.71) |
| The simulator approaches the Brownian closed form as steps shrink | +0.0050 at sd 0.5, +0.0003 at sd 0.25 |
| A permutation test on uninformative labels returns p near 0.5 | mean p within 0.06 of 0.5 over 300 data sets, in the tests |
| The report tells the two samples apart | yes, by the leave-out and time-of-day checks; not by the t-statistic or the barrier odds (README, Limits) |

The z of -2.71 was followed up. Each biased walk was rerun once at 200,000 paths with seeds 1, 2 and 3:

| Walk | Exact | Seed 1 | Seed 2 | Seed 3 |
|:--|--:|--:|--:|--:|
| p = 0.55 | 0.8815 | 0.8811 (z -0.55) | 0.8814 (z -0.09) | 0.8818 (z +0.39) |
| p = 0.45 | 0.1185 | 0.1173 (z -1.66) | 0.1179 (z -0.87) | 0.1180 (z -0.70) |

The two walks are mirror images run through the same code, and the p = 0.55 runs straddle the exact value. I take the p = 0.45 row as chance. The four p = 0.45 results are all on the low side, which chance does about one time in eight, so a small bias is not excluded. These follow-up runs were typed at a prompt and are not part of `reproduce`.

## Variants tried

- Sample generator: one design, one seed (1989), run once. The parameters (400 trades, total 20,000, per-trade sd 250, ten large trades carrying 99%, sixty trades in the opening half hour with a 3-minute median hold) were fixed before the first run and not changed after seeing the reports.
- Verdict thresholds (half the profit for the concentration sentence, p below 0.01, cost share of one half, |t| of 2) and the short-hold thresholds were set before the first run and not changed.
- Barrier defaults (plus and minus 10% of capital, horizon equal to the trade count, 10,000 paths, mean block 10) were set before the first run and not changed.
- One change was made after seeing output: a six-trade test log annualised to an absurd return, so the annual return and Martin ratio are now left undefined for logs under 30 days. This does not affect the samples.
- The barrier follow-up above: six extra simulations.
