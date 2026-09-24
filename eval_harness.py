#!/usr/bin/env python3
"""Evaluate binary risk scores. Offline by default; standard library only."""
import argparse
import csv
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_THRESHOLD = 0.5
MAX_RESPONSE = 65536


def probability(value):
    if isinstance(value, bool):
        raise ValueError('Scores must be finite numbers from 0 to 1.')
    try:
        score = float(value)
    except (TypeError, ValueError):
        raise ValueError('Scores must be finite numbers from 0 to 1.') from None
    if not math.isfinite(score) or not 0 <= score <= 1:
        raise ValueError('Scores must be finite numbers from 0 to 1.')
    return score


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_webhook(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('Webhook must be an HTTPS URL without credentials, query, or fragment.')
    return url


def score_carrier(row, url):
    """Only explicitly selected webhook mode sends identifiers to an operator URL."""
    payload = {k: (row.get(k) or '').strip() for k in ('dot_number', 'mc_number', 'carrier_name')}
    headers = {'Content-Type': 'application/json'}
    token = os.environ.get('WEBHOOK_TOKEN', '')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request(validate_webhook(url), data=json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            return None
        body = json.loads(raw)
        return probability(body['risk_score']) if isinstance(body, dict) else None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
        # Never print response bodies, URLs, tokens, or carrier identifiers.
        return None


def evaluate(scored, threshold=DEFAULT_THRESHOLD):
    threshold = probability(threshold)
    tp = fp = tn = fn = 0
    for label, score in scored:
        if label not in ('fraud', 'legit'):
            raise ValueError('Labels must be fraud or legit.')
        flagged = probability(score) >= threshold
        if label == 'fraud':
            tp += int(flagged)
            fn += int(not flagged)
        else:
            fp += int(flagged)
            tn += int(not flagged)
    total, bad, good = tp + fp + tn + fn, tp + fn, tn + fp
    def pct(n, d):
        return 100.0 * n / d if d else None
    return dict(threshold=threshold, total=total, tp=tp, fp=fp, tn=tn, fn=fn,
                n_bad=bad, n_good=good, accuracy=pct(tp + tn, total), recall=pct(tp, bad),
                precision=pct(tp, tp + fp), false_negative_rate=pct(fn, bad),
                false_positive_rate=pct(fp, good))


def read_rows(path, limit=0, webhook=False):
    with open(path, newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        required = {'actual_outcome'} | (set() if webhook else {'risk_score'})
        if len(fields) != len(set(fields)) or not required.issubset(fields):
            raise ValueError('CSV needs unique headers including actual_outcome and, offline, risk_score.')
        rows = list(reader)
    if limit:
        rows = rows[:limit]
    for index, row in enumerate(rows, 2):
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f'CSV row {index} has the wrong number of columns.')
        row['actual_outcome'] = row['actual_outcome'].strip().lower()
        if row['actual_outcome'] not in ('fraud', 'legit'):
            raise ValueError(f'CSV row {index} has an invalid label.')
        if not webhook and row['risk_score'].strip():
            try:
                probability(row['risk_score'])
            except ValueError:
                raise ValueError(f'CSV row {index} has an invalid risk_score.') from None
    return rows


def run(rows, threshold, webhook=None, do_sweep=False):
    scored = []
    unscorable = 0
    for row in rows:
        raw = row.get('risk_score', '').strip()
        score = score_carrier(row, webhook) if webhook else (probability(raw) if raw else None)
        if score is None:
            unscorable += 1
        else:
            scored.append((row['actual_outcome'], score))
    report = evaluate(scored, threshold)
    report.update(input_rows=len(rows), unscorable=unscorable,
                  coverage=100 * len(scored) / len(rows) if rows else 0,
                  mode='webhook' if webhook else 'precomputed', warnings=[])
    if report['n_bad'] < 8 or report['n_good'] < 8:
        report['warnings'].append('Small or single-class sample: descriptive metrics only; not evidence of generalization.')
    if unscorable:
        report['warnings'].append('Metrics exclude unscorable rows. Report coverage alongside all metrics.')
    report['warnings'].append('Data provenance is not verified. Synthetic results are not production accuracy.')
    if do_sweep:
        report['threshold_sweep'] = [evaluate(scored, i / 20) for i in range(1, 20)]
        report['warnings'].append('Threshold exploration uses this same dataset. Validate choices on a separate held-out set.')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_file')
    parser.add_argument('--threshold', type=probability, default=DEFAULT_THRESHOLD)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--precomputed', action='store_true', help='offline mode (default)')
    modes.add_argument('--webhook', type=validate_webhook, help='explicitly send row identifiers to this HTTPS scorer')
    parser.add_argument('--sweep', action='store_true')
    parser.add_argument('--json', action='store_true', help='machine-readable report; undefined metrics are null')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args(argv)
    if args.limit < 0:
        parser.error('--limit must be nonnegative')
    try:
        rows = read_rows(args.csv_file, args.limit, bool(args.webhook))
        report = run(rows, args.threshold, args.webhook, args.sweep)
    except (ValueError, OSError, csv.Error, UnicodeError) as exc:
        print(f'Input error: {exc.__class__.__name__}. Check the file, headers, labels and finite scores in [0, 1].', file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, allow_nan=False))
    else:
        print('Risk-score evaluation — descriptive results')
        for key in ('input_rows', 'total', 'unscorable', 'coverage', 'tp', 'fp', 'tn', 'fn', 'accuracy', 'recall', 'precision', 'false_negative_rate', 'false_positive_rate'):
            print(f'{key}: {report[key] if report[key] is not None else "undefined"}')
        for warning in report['warnings']:
            print('Note: ' + warning)
        if args.sweep:
            for item in report['threshold_sweep']:
                print(f'Threshold {item["threshold"]:.2f}: recall={item["recall"]}, precision={item["precision"]}')
    return 0 if report['total'] else 1


if __name__ == '__main__':
    sys.exit(main())
