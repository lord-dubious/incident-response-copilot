# Demo Guide

Run the app locally:

```bash
uv run incident-response-copilot
```

Open `http://127.0.0.1:8060` and walk through the credential stuffing, Kubernetes egress, and malware callback scenarios. Emphasize evidence, approval tasks, and playbook review boundaries.

## Try Local Triage

Use the dashboard triage panel or call the API directly:

```bash
curl -s http://127.0.0.1:8060/api/incidents/triage \
  -H 'content-type: application/json' \
  -d '{
    "title": "Suspicious production admin login spike",
    "signal_source": "siem.alert",
    "description": "Multiple failed admin logins followed by a successful production login from a new ASN",
    "metadata": {"environment": "production", "failed_logins": 37, "asset": "admin-portal"}
  }' | python -m json.tool
```

The expected output is a high-severity containment incident with evidence, timeline events, approval-gated tasks, and playbook steps.

## What To Point Out

- The app creates new incidents from local input, not just seeded fixtures.
- The severity logic is deterministic and documented.
- Containment remains behind human review.
- The project is intentionally local-first and does not touch production systems.
