# Security and data handling

Start with the offline synthetic example. Keep real datasets outside Git. Output contains aggregate metrics and validation errors, not row identifiers or raw upstream responses.

Webhook mode explicitly sends identifiers to an operator-selected endpoint. HTTPS and redirect rejection do not establish endpoint trust. Keep credentials in the environment. Requests time out after 15 seconds; responses are capped at 64 KiB. CSV input is held in local memory: do not expose this CLI as a public upload service.

Tests and scans do not certify absence of vulnerabilities. Report concerns privately through GitHub security advisories when available. Never post credentials or customer data in public issues.
