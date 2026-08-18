# Roadmap

AIGovOps Lantern is the read-only **viewer** half of the AIGovOps Foundation toolchain. AIGovOps Beacon emits receipts; Lantern explains them.

## Shipped — v0.1.0-alpha

The [v0.1.0-alpha release](https://github.com/aigovops-foundation/aigovops-lantern/releases/tag/v0.1.0-alpha) ships:

- `lantern read` — render a receipt bundle for one of four role lenses (operator, auditor, exec, dev) in markdown, JSON, or table
- `lantern diff` — show the delta between two bundles
- `lantern explain` — crosswalk a UCID to NIST AI RMF, ISO 42001, and EU AI Act articles
- Stable JSON output schemas under [`/schemas`](https://github.com/aigovops-foundation/aigovops-lantern/tree/main/schemas)
- DRAFT OpenAPI 3.1 contract for the v0.2 web view under [`docs/api/`](api/openapi.md)
- E2E + scale + chaos test pyramid (see [Testing](https://github.com/aigovops-foundation/aigovops-lantern/blob/main/README.md#testing) in the README)

## In flight

| Milestone | Tracking issue | Status |
| --- | --- | --- |
| **v0.2** — read-only web viewer (FastAPI server matching the OpenAPI draft) | [#2](https://github.com/aigovops-foundation/aigovops-lantern/issues/2) | scoped, draft spec landed |
| **v0.3** — GitHub Action wrapper (`uses: aigovops-foundation/aigovops-lantern@v0.3`) for PR comments | [#3](https://github.com/aigovops-foundation/aigovops-lantern/issues/3) | scoped |

## Beyond v0.3

- HTML export for offline auditor packages
- Plug-in crosswalks (HIPAA, SOC 2, FedRAMP)
- Streaming ingestion for very large bundles (>1M receipts)

Latest issues and discussions: [github.com/aigovops-foundation/aigovops-lantern/issues](https://github.com/aigovops-foundation/aigovops-lantern/issues)
