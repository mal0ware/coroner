# Coroner

**Give it a list of trades. It tells you what the profit died of.**

> **Status: planned.** This repository holds the design. No results exist yet, and nothing below is a finding. Each box in the roadmap gets ticked when the code and its tests are in.

## The question

A backtest made money. Was that a broad small edge, or ten lucky trades and one hour of the day?

## What this will contain

- A command-line tool that reads a CSV of trades and writes an HTML and a markdown report
- Per-trade t-statistic, and a label-shuffle permutation test
- First half against second half
- Profit by time of day and by weekday, with a flag for windows where trades are held only minutes
- The result without the best N trades, and how many of the best trades must go before the total reaches zero
- Cost as a share of gross profit
- Ulcer index, recovery factor, and the share of days, months and quarters that ended positive
- The odds of reaching a profit target before a loss limit, by resampling the trades

## The result it is built to show

Two sample trade files with the same total profit. One is a broad small edge. In the other, ten trades are everything. The report tells them apart on the first page.

Whatever the answer turns out to be goes at the top of this file, with one chart, before any installation step.

## Sources

- Martin and McCann, The Investor's Guide to Fidelity Funds, Wiley, 1989 (the ulcer index)
- Politis and Romano, "The Stationary Bootstrap", Journal of the American Statistical Association 89, 1994
- The barrier simulator is checked against the closed form for Brownian motion with drift: P(hit +b before -a) = (1 - exp(-2*mu*a/sigma^2)) / (1 - exp(-2*mu*(a+b)/sigma^2))

Every number that differs from a source will be listed in `PAPER.md` with the likely reason.

## Data

Any trade log with entry time, exit time, gross and net result. Synthetic samples ship with the repo.

## How it is tested

The maths is tested before any result is trusted.

- Exact algebra on small hand-built trade files
- The barrier simulator against the closed form above, and against a/(a+b) for a fair walk
- A permutation test that returns p near 0.5 when the labels carry no information

## Layout

```
src/coroner/      the code
tests/             maths tests first
scripts/reproduce.py   one command rebuilds every figure and table
scripts/fetch_data.py  downloads public data into data/ (never committed)
results/           committed figures and small tables
PAPER.md           citations, claims tested, comparison with the sources
```

## Roadmap

- [ ] Project skeleton, CI, and the reproduce command
- [ ] A command-line tool that reads a CSV of trades and writes an HTML and a markdown report
- [ ] Per-trade t-statistic, and a label-shuffle permutation test
- [ ] First half against second half
- [ ] Profit by time of day and by weekday, with a flag for windows where trades are held only minutes
- [ ] The result without the best N trades, and how many of the best trades must go before the total reaches zero
- [ ] Cost as a share of gross profit
- [ ] Ulcer index, recovery factor, and the share of days, months and quarters that ended positive
- [ ] The odds of reaching a profit target before a loss limit, by resampling the trades
- [ ] `PAPER.md` comparison with the sources
- [ ] Results and limits written up at the top of this file

## Limits

- Resampling assumes the future looks like the sample. It often does not.
- It judges the trades you give it. It cannot see the versions you tried and threw away; Procrustes is the tool for that.
- The checks came out of a private project, where they showed that a strategy with 202 trades owed 99% of its gain to 10 of them.
- This is research code. It is not investment advice and it does not trade.

## The name

A coroner does not ask whether the patient looked healthy. A coroner finds the cause.

## Licence

MIT. See `LICENSE`.
