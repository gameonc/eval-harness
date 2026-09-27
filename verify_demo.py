#!/usr/bin/env python3
"""Reproduce the offline portfolio evidence; never enables network scoring."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

def main():
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=ROOT, check=True)
    result = subprocess.run([sys.executable, str(ROOT/'eval_harness.py'), str(ROOT/'examples/synthetic.csv'), '--json', '--sweep'], cwd=ROOT, check=True, capture_output=True, text=True)
    report = json.loads(result.stdout)
    expected = {'input_rows':20, 'total':20, 'tp':8, 'fp':2, 'tn':8, 'fn':2, 'coverage':100.0, 'mode':'precomputed'}
    for key, value in expected.items():
        if report.get(key) != value:
            raise SystemExit(f'Unexpected {key}: {report.get(key)!r}; expected {value!r}')
    if len(report['threshold_sweep']) != 19:
        raise SystemExit('Threshold sweep incomplete')
    print(json.dumps(report, indent=2, allow_nan=False))
    print('PASS: offline synthetic demonstration. This is not production model accuracy.')

if __name__ == '__main__':
    main()
