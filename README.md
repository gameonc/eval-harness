# Risk-score evaluation harness

A dependency-free Python CLI by **Cady Lalanne** for checking binary classifiers. Reports confusion matrices, coverage, precision, recall, and error rates. Invalid labels and non-finite/out-of-range scores fail validation instead of silently distorting results.

## Try it in one minute

Python 3.10+; no account, API key, installation, or network needed:

```sh
python3 eval_harness.py examples/synthetic.csv --json
python3 eval_harness.py examples/synthetic.csv --sweep
python3 -m unittest discover -s tests -v
```

The 20 included rows are **synthetic**, with intentionally imperfect predictions. They exercise the software; they do not establish real-world fraud detection accuracy.

## Your dataset

Required CSV columns: `actual_outcome` (`fraud` or `legit`) and `risk_score` (finite 0–1). A blank score is unscorable and reduces coverage. Invalid labels/scores, duplicate headers, missing columns, and malformed rows stop the run. Extra named columns are allowed. Keep customer data outside this repository.

```sh
python3 eval_harness.py /path/to/private.csv --threshold 0.6 --json
```

Undefined metrics are JSON `null`. Exit codes: `0` at least one scored row, `1` none scored, `2` invalid input/configuration. `--precomputed` remains an explicit alias for default offline mode.

## Optional webhook

Only `--webhook https://your-owned-scorer.example/score` enables network scoring. It sends `dot_number`, `mc_number`, and `carrier_name`; notes are excluded. Use a trusted endpoint and data you are authorized to send. HTTPS is required and redirects are rejected. The optional `WEBHOOK_TOKEN` environment variable supplies bearer authentication; never put credentials in source or URLs.

Responses must be JSON objects with `risk_score` in [0, 1]. Timeouts, oversized responses, malformed JSON/scores, and HTTP failures become unscorable rows. One attempt per row; no automatic retries. Integration tests use mocks, not a production scorer.

## Interpretation and limits

Metrics describe the scored subset: always show coverage. Small/single-class samples get warnings, not statistical guarantees. No fixed sample count establishes representativeness. Threshold sweeps explore the same data: choose business costs explicitly and validate on a separate held-out set. The CLI does not verify labels or provenance or generate marketing claims.

A local evaluation utility, not a trained model or production screening service. Read [SECURITY.md](SECURITY.md). MIT licensed.
