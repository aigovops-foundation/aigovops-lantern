## AIGovOps Lantern v0.1.0-alpha — first cut of the CLI

Lantern is the **human-readable companion** to [AIGovOps Beacon](https://github.com/bobrapp/aigovops-beacon). Beacon signs evidence bundles; Lantern reads them.

This first alpha ships the CLI scaffold so engineers, compliance, auditors, and regulators can all open a Beacon bundle and get the same facts in the language they care about.

### What's in the box

Three commands:

- `lantern read BUNDLE` — render a Beacon NDJSON/JSONL evidence bundle as a human summary
- `lantern diff OLD NEW` — compare two bundles with a role-targeted narrative of what changed
- `lantern explain UCID` — look up a Unified Control ID against the umbrella-govops registry

Four role lenses (`--role`):

- `engineer` — gate.failed callouts, unsigned receipts, CI signal
- `compliance` — UCID-mapping reminders, control coverage
- `auditor` — evidence completeness, signature presence, chain-of-custody hints
- `regulator` — plain-language framework crosswalk

Three output formats (`--format`):

- `text` — Rich panel for terminals
- `markdown` — drop straight into a PR comment
- `json` — machine readable for downstream tooling

### Quality

- 43 tests passing, 89% coverage
- `ruff` clean, `mypy --strict` clean
- CI matrix on Python 3.11 and 3.12 (Node 24 runtime)
- Apache-2.0, DCO sign-off enforced
- Fixtures use **real Beacon sample receipts** (`scoring/sample_receipts.ndjson`) so the renderer stays faithful to the on-the-wire OVERT 1.0 envelope

### Install

```bash
pip install git+https://github.com/bobrapp/aigovops-lantern.git@v0.1.0-alpha
lantern --version
```

### What this is not (yet)

- No web viewer — that's v0.2
- No GitHub Action wrapper — that's v0.3
- No i18n — that's v1.0
- No cryptographic verification — that's Beacon's job; Lantern reports signature **presence** only

### Trademark

AIGovOps Lantern™ is a common-law trademark of the AIGovOps Foundation. The bare word "Lantern" is **not** a Foundation mark; always use the compound form. See [TRADEMARK.md](https://github.com/bobrapp/umbrella-govops/blob/main/TRADEMARK.md) in umbrella-govops.

### Thanks

Built alongside [aigovops-beacon](https://github.com/bobrapp/aigovops-beacon) and [umbrella-govops](https://github.com/bobrapp/umbrella-govops). Issues and PRs welcome.
