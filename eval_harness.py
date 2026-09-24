#!/usr/bin/env python3
"""
LalanneShield evaluation harness.

Purpose: produce the accuracy numbers you can publish. Right now you have a
system that runs. This turns it into a system you can prove.

WHAT YOU NEED
  A CSV of carriers you have already seen, where you know how it turned out.
  40-60 rows is enough to be meaningful. Include both good and bad carriers;
  aim for at least 8-10 known-bad ones or the recall number means nothing.

  labeled_carriers.csv
    dot_number,mc_number,carrier_name,actual_outcome,notes
    604653,,Example Trucking,legit,hauled 12 loads clean
    ,1234567,Sketchy Freight LLC,fraud,double-brokered load in March

  actual_outcome must be one of: legit | fraud
  "fraud" = anything you would refuse today: double-brokering, identity
  theft, fake authority, chameleon carrier, insurance lapse you got burned on.

HOW TO PLUG IN YOUR SCORER
  Edit score_carrier() below. Three options, pick one:
    1. Call your n8n webhook (default, see USE_WEBHOOK)
    2. Import your scoring function directly
    3. Paste scores into a column and run in --precomputed mode

RUN
    python3 eval_harness.py labeled_carriers.csv
    python3 eval_harness.py labeled_carriers.csv --threshold 0.6
    python3 eval_harness.py labeled_carriers.csv --sweep

OUTPUT
    A confusion matrix, the four numbers that matter, and a block of text
    formatted for the website. The number that sells is RECALL — of the bad
    carriers, how many did it catch. The number that keeps you honest is the
    FALSE NEGATIVE RATE — the ones it waved through.
"""

import argparse
import csv
import json
import sys
import time
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# CONFIG - edit this block
# ---------------------------------------------------------------------------

USE_WEBHOOK = True
WEBHOOK_URL = "https://YOUR-N8N-HOST/webhook/lalanneshield-score"
WEBHOOK_TIMEOUT = 45          # seconds; FMCSA lookups are slow
WEBHOOK_AUTH_HEADER = None    # e.g. {"Authorization": "Bearer ..."} - keep out of git

# A carrier scoring at or above this is treated as "flag it".
DEFAULT_THRESHOLD = 0.5

# Seconds to wait between calls so you don't hammer FMCSA.
POLITE_DELAY = 1.0


def score_carrier(row):
    """
    Return a risk score between 0.0 (clearly fine) and 1.0 (clearly bad).

    Return None if the carrier could not be scored at all (lookup failed,
    no authority record found). Those rows are excluded from the metrics
    and reported separately - a system that can't score 30% of carriers
    has a coverage problem, and you want to know that.
    """
    if not USE_WEBHOOK:
        raise NotImplementedError(
            "Set USE_WEBHOOK = True and fill in WEBHOOK_URL, or import your "
            "scoring function here and return a float."
        )

    payload = {
        "dot_number": (row.get("dot_number") or "").strip(),
        "mc_number": (row.get("mc_number") or "").strip(),
        "carrier_name": (row.get("carrier_name") or "").strip(),
        "source": "eval_harness",
    }

    req = urllib.request.Request(
        WEBHOOK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(WEBHOOK_AUTH_HEADER or {})},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        print(f"    ! scoring failed for {payload['carrier_name'] or payload['dot_number']}: {exc}",
              file=sys.stderr)
        return None

    # Adjust these key names to match what your workflow actually returns.
    for key in ("risk_score", "score", "risk", "confidence"):
        if key in body and body[key] is not None:
            try:
                return float(body[key])
            except (TypeError, ValueError):
                pass

    # Fallback: a categorical verdict.
    verdict = str(body.get("verdict", "")).lower()
    mapping = {"high": 0.9, "flag": 0.9, "reject": 0.95,
               "medium": 0.6, "review": 0.6,
               "low": 0.1, "pass": 0.05, "clear": 0.05}
    if verdict in mapping:
        return mapping[verdict]

    print(f"    ! no recognisable score in response: {body}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def evaluate(scored, threshold):
    """scored = list of (label, score). Returns a metrics dict."""
    tp = fp = tn = fn = 0
    for label, score in scored:
        flagged = score >= threshold
        bad = label == "fraud"
        if flagged and bad:
            tp += 1
        elif flagged and not bad:
            fp += 1
        elif not flagged and bad:
            fn += 1
        else:
            tn += 1

    total = tp + fp + tn + fn
    n_bad = tp + fn
    n_good = tn + fp

    def pct(num, den):
        return (100.0 * num / den) if den else float("nan")

    return {
        "threshold": threshold,
        "total": total,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "accuracy": pct(tp + tn, total),
        "recall": pct(tp, n_bad),                 # of the bad ones, how many caught
        "precision": pct(tp, tp + fp),            # of the flags, how many were real
        "false_negative_rate": pct(fn, n_bad),    # the one that costs money
        "false_positive_rate": pct(fp, n_good),   # the one that annoys dispatch
        "n_bad": n_bad,
        "n_good": n_good,
    }


def print_report(m, unscorable, source_file):
    w = 62
    print()
    print("=" * w)
    print("  LALANNESHIELD - EVALUATION REPORT")
    print("=" * w)
    print(f"  source            {source_file}")
    print(f"  carriers scored   {m['total']}  ({m['n_bad']} known bad, {m['n_good']} known good)")
    if unscorable:
        print(f"  unscorable        {unscorable}  (excluded - see coverage note below)")
    print(f"  flag threshold    {m['threshold']:.2f}")
    print("-" * w)
    print("  CONFUSION MATRIX")
    print()
    print("                     predicted BAD   predicted OK")
    print(f"    actually BAD  {m['tp']:>12}   {m['fn']:>12}   <- misses cost money")
    print(f"    actually OK   {m['fp']:>12}   {m['tn']:>12}")
    print("-" * w)
    print("  HEADLINE NUMBERS")
    print()
    print(f"    Accuracy               {m['accuracy']:.1f}%")
    print(f"    Recall (caught)        {m['recall']:.1f}%   <- the number that sells")
    print(f"    Precision (of flags)   {m['precision']:.1f}%")
    print(f"    False negative rate    {m['false_negative_rate']:.1f}%   <- the number that keeps you honest")
    print(f"    False positive rate    {m['false_positive_rate']:.1f}%")
    print("=" * w)

    print()
    print("  ---- PASTE INTO THE WEBSITE ----")
    print()
    print(f"  Evaluated against {m['total']} historical carriers with known outcomes:")
    print(f"  {m['accuracy']:.0f}% accuracy, {m['false_negative_rate']:.0f}% false-negative rate.")
    print()
    if m["n_bad"] < 8:
        print("  ! WARNING: fewer than 8 known-bad carriers. Recall and false-negative")
        print("    rate are not yet trustworthy. Add more bad examples before publishing.")
    if unscorable:
        cov = 100.0 * m["total"] / (m["total"] + unscorable)
        print(f"  ! COVERAGE: only {cov:.0f}% of carriers could be scored at all.")
        print("    Publish this honestly or fix the lookup gap first. A buyer will ask.")
    print()


def sweep(scored):
    print()
    print("  THRESHOLD SWEEP - pick the operating point you actually want")
    print()
    print("   thresh   recall   precision   false-neg   false-pos")
    print("   " + "-" * 50)
    best = None
    for i in range(1, 20):
        t = i / 20.0
        m = evaluate(scored, t)
        print(f"    {t:.2f}    {m['recall']:6.1f}%   {m['precision']:7.1f}%   "
              f"{m['false_negative_rate']:8.1f}%   {m['false_positive_rate']:8.1f}%")
        # Favour catching fraud: weight recall 2x precision.
        if m["recall"] == m["recall"] and m["precision"] == m["precision"]:
            score = 2 * m["recall"] + m["precision"]
            if best is None or score > best[1]:
                best = (t, score)
    if best:
        print()
        print(f"   Suggested threshold: {best[0]:.2f}  (weights catching fraud 2:1 over")
        print("   avoiding false alarms - which is the right trade for a broker)")
    print()


def main():
    ap = argparse.ArgumentParser(description="Evaluate LalanneShield against known outcomes.")
    ap.add_argument("csv_file", help="labeled carriers CSV")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    ap.add_argument("--sweep", action="store_true", help="try every threshold")
    ap.add_argument("--precomputed", action="store_true",
                    help="read a 'risk_score' column instead of calling the scorer")
    ap.add_argument("--limit", type=int, default=0, help="only score the first N rows")
    args = ap.parse_args()

    with open(args.csv_file, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    if args.limit:
        rows = rows[:args.limit]

    valid_labels = {"legit", "fraud"}
    scored = []
    unscorable = 0

    print(f"\nScoring {len(rows)} carriers...")
    for i, row in enumerate(rows, 1):
        label = (row.get("actual_outcome") or "").strip().lower()
        if label not in valid_labels:
            print(f"  row {i}: skipping, actual_outcome must be legit|fraud (got '{label}')",
                  file=sys.stderr)
            continue

        if args.precomputed:
            raw = (row.get("risk_score") or "").strip()
            score = float(raw) if raw else None
        else:
            score = score_carrier(row)
            time.sleep(POLITE_DELAY)

        if score is None:
            unscorable += 1
            continue

        scored.append((label, score))
        name = (row.get("carrier_name") or row.get("dot_number") or "?")[:34]
        print(f"  [{i:>3}/{len(rows)}] {name:<34} {score:.2f}  ({label})")

    if not scored:
        print("\nNothing scored. Check the scorer config and your CSV.", file=sys.stderr)
        return 1

    if args.sweep:
        sweep(scored)

    print_report(evaluate(scored, args.threshold), unscorable, args.csv_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
