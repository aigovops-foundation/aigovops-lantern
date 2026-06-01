# AIGovOps Lantern™

The human-carried companion to [AIGovOps Beacon](https://github.com/bobrapp/aigovops-beacon).
**Beacon signs. Lantern reads.**

Lantern turns Beacon evidence bundles — machine-signed NDJSON
streams of policy receipts — into language each role actually wants to see.
Same source of truth, four different lenses.

## Quick start

```bash
pip install git+https://github.com/bobrapp/aigovops-lantern.git@v0.1.0-alpha
lantern --version
lantern read bundle.ndjson -f markdown -r auditor
```

## Three commands

- **`lantern read`** — render a Beacon NDJSON bundle as a human summary
- **`lantern diff`** — compare two bundles with a role-targeted narrative
- **`lantern explain`** — resolve a Unified Control ID against the umbrella-govops registry

See the [CLI reference](cli.md) for every flag and example.

## Four role lenses

| Role | Focus |
|---|---|
| `engineer` | Pipeline integrity, gate failures, CI signal |
| `compliance` | Control coverage, UCID mapping, framework crosswalks |
| `auditor` | Chain of custody, signature presence, evidence completeness |
| `regulator` | Framework citations (NIST AI RMF, EU AI Act, ISO 42001) |

## Three output formats

- `text` — Rich panel for terminals (default)
- `markdown` — drop into a PR comment or email
- `json` — machine-readable, conforms to a [published schema](api/data-model.md#3-output-schemas-the-public-contract)

## Design principles

1. **Beacon is the boundary.** Lantern reads what Beacon signs; it never claims to verify.
2. **Role is a first-class input.** Same bundle, four narratives.
3. **Schemas are the contract.** Every JSON output validates against a published schema.
4. **Friendly failure.** Bad input never crashes — it raises a `BundleError` with an actionable message.

## Where to go next

- [CLI reference](cli.md) — every command and flag
- [API · Data model](api/data-model.md) — what a bundle looks like, what a UCID looks like
- [API · Actions](api/actions.md) — the `event_type` vocabulary
- [API · Flows](api/flows.md) — sequence diagrams for every journey
- [API · OpenAPI](api/openapi.md) — the planned v0.2 web view contract
- [Python API](python/bundle.md) — for tool authors embedding the renderer
- [Roadmap](roadmap.md) — what's coming in v0.2, v0.3, v1.0
