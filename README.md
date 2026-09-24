# Eval harness

**A small script for turning "the system runs" into "the system is measured."**

If you have built a classifier that scores something — carriers, leads, tickets,
claims — you will eventually be asked how well it works. This produces the answer
in a form you can publish, and refuses to produce one when your labeled set is too
small to mean anything.

Written for carrier fraud screening in freight brokerage, but the scorer is a
single function you replace. Nothing else is domain-specific.

## What you need

A CSV of cases you have already seen, where you know how it turned out. 40–60 rows
is enough to be meaningful. Include both good and bad outcomes; aim for at least
8–10 known-bad ones or the recall number means nothing.

```csv
dot_number,mc_number,carrier_name,actual_outcome,notes
604653,,Example Trucking,legit,hauled 12 loads clean
,1234567,Sketchy Freight LLC,fraud,double-brokered a load in March
```

`actual_outcome` must be `legit` or `fraud`.

## Plugging in your scorer

Edit `score_carrier()`. Three options:

1. Call your webhook (default — set `WEBHOOK_URL`)
2. Import your scoring function directly
3. Precompute scores into a `risk_score` column and run `--precomputed`

Return a float from 0.0 to 1.0, or `None` if the case could not be scored at all.
Unscorable rows are excluded from the metrics and reported separately — a system
that cannot score 30% of its inputs has a coverage problem, and you want that
number in front of you rather than averaged away.

## Running it

```bash
python3 eval_harness.py labeled_carriers.csv
python3 eval_harness.py labeled_carriers.csv --threshold 0.6
python3 eval_harness.py labeled_carriers.csv --sweep
```

No dependencies beyond the standard library.

## What it tells you

A confusion matrix and five numbers: accuracy, recall, precision, false-negative
rate, false-positive rate.

**Recall** is the number that sells — of the bad ones, how many did it catch.
**False-negative rate** is the number that keeps you honest — the ones it waved
through.

`--sweep` walks every threshold and suggests an operating point, weighting recall
2:1 over precision, which is the right trade when a miss costs money and a false
alarm costs a phone call.

Two guardrails it will not let you skip:

- Fewer than 8 known-bad cases and it refuses to treat recall as trustworthy
- Low scoring coverage and it tells you the coverage percentage, because a buyer
  will ask

## Why

Most AI pilots die at the question "how do you know it works." This is the
cheapest possible answer to that question.

MIT licensed. Take it, use it, tell me what breaks.
