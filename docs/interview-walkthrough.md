# Five minute evaluation walkthrough

Author: Cody Lalanne. Built with AI coding assistance; explain the implementation and its limits rather than claiming unaided authorship.

## Run and explain

From a fresh checkout, run `python3 verify_demo.py` with Python 3.10 or newer. No dependencies, credentials or external service are required. The runner executes the tests and verifies the actual CLI report.

At threshold 0.5, the 20 synthetic rows produce 8 true positives, 8 true negatives, 2 false positives and 2 false negatives. Precision and recall are each 80 percent. Coverage is 100 percent. These values describe deliberately constructed examples, not a real fraud model.

A false negative is a fraud-labeled row below the threshold. A false positive is a legitimate-labeled row above it. Choosing a threshold is a business tradeoff; the sweep is exploratory and does not replace evaluation on held-out data.

## Demonstrate missing and invalid data

Copy examples/synthetic.csv to a temporary directory, outside the repository. Blank one risk_score and rerun the CLI: coverage drops and metrics describe only the scored rows. Change a score to nan and rerun: validation rejects the input with exit code 2. The automated tests also cover these conditions.

## What this proves

CSV validation, deterministic metrics, missing-data accounting, CLI behavior and bounded optional HTTP handling. Show test_eval.py and the score validation function when asked how correctness is checked.

## What it does not prove

This is not a trained model, an LLM judge or a production screening service. Labels and dataset representativeness are not verified. The optional webhook tests use mocks; no production scoring integration or real-world accuracy is asserted. Keep client data out of this public repository.

## Explain the separate n8n harness

The private qualify_leads workflow checks an LLM scoring response contract and prefilter behavior. This public Python repository computes classifier metrics. They serve different purposes and should not be presented as the same harness.
