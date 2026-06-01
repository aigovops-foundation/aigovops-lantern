# AIGovOps Lantern™

> **Beacon signs. Lantern reads.**

**AIGovOps Lantern™** is the human-carried companion to
[**AIGovOps Beacon™**](https://github.com/bobrapp/aigovops-beacon) within
the [**Umbrella-GovOps**](https://github.com/bobrapp/umbrella-govops)
framework maintained by the [AIGovOps Foundation](https://aigovops.org).

Where **Beacon** is the always-on policy-as-code runtime — signing,
attesting, and emitting machine-verifiable artifacts — **Lantern** is
the carried light. It reads those artifacts and illuminates conformance
for the people doing the work: engineers reviewing a PR, compliance
leads scoping a control, auditors tracing an evidence bundle, and
regulators reading a crosswalk.

**Status:** v0.1.0-alpha · CLI shipped · 43 tests · ruff/mypy strict clean

---

## Install

```bash
pip install aigovops-lantern   # once published; for now:
pip install git+https://github.com/bobrapp/aigovops-lantern.git
```

Requires Python 3.11+.

## Three commands

### 1. `lantern read`

Render a Beacon-signed evidence bundle (NDJSON, JSONL, or JSON array) as
text, Markdown, or JSON — optionally through a role lens.

```bash
lantern read ./evidence-bundle.ndjson
lantern read -f markdown -r auditor ./evidence-bundle.ndjson
lantern read -f json ./evidence-bundle.ndjson | jq '.event_types'
```

Output (Markdown excerpt):

```markdown
# Bundle: `evidence-bundle.ndjson`

_AIGovOps Lantern — Beacon signs. Lantern reads._

> **Auditor view.** Focus on the chain of custody: who produced each
> receipt, when, in which environment, and whether the receipt carries
> a signature.

- **Receipts:** 46
- **Signed:** 46 of 46
- **Distinct event types:** 7
- **Distinct evidence types:** 41
```

### 2. `lantern diff`

Compare two bundles. The narrative is targeted to a role: engineers see
pipeline-integrity callouts; compliance sees UCID mapping prompts;
auditors get chain-of-custody flags; regulators see framework-citation
deltas.

```bash
lantern diff ./before.ndjson ./after.ndjson
lantern diff -r engineer ./before.ndjson ./after.ndjson
lantern diff -f markdown -r compliance ./before.ndjson ./after.ndjson \
  >> $GITHUB_STEP_SUMMARY
```

### 3. `lantern explain`

Resolve a Unified Control Identifier (UCID) against the
[Umbrella-GovOps UCID Registry](https://github.com/bobrapp/umbrella-govops/blob/main/UCID-REGISTRY.md)
and render its framework citations.

```bash
lantern explain UCID-DATA-BIAS-001
lantern explain --registry ../umbrella-govops/crosswalks/unified-control-id.yaml \
  UCID-OVERSIGHT-001
```

Output:

```
# UCID-DATA-BIAS-001 — Dataset bias examination

Status: provisional

NIST AI RMF: MEASURE-2.11, MAP-2.3, MANAGE-2.3
EU AI Act: Articles 10(2)(f), 10(3) · Annex IV 2(d), 2(g)
ISO/IEC 42001: A.7.4
Implementing controls: DG-002
```

Without `--registry`, Lantern falls back to a small embedded snapshot
used for offline demos. **The registry source of truth lives in
umbrella-govops** — Lantern never mutates it.

## Why Lantern

Beacon answers the machine question: *"Is this artifact signed,
attested, and conformant?"*

Lantern answers the human question: *"Can I, the person who has to act
on this, understand what it means, what changed, and what I need to do?"*

The Foundation's premise is **humans are worthy** — the carried light,
not just the spotlight. Lantern is the reader, translator, and dignity
layer on top of the policy-as-code substrate.

## Design principles

- **Read-only by construction.** Lantern never produces signed
  artifacts. If a user needs a signature, they go to Beacon.
- **Local-first.** Works against local files with no network.
- **No telemetry.** Lantern is a tool people carry — surveillance is
  inconsistent with the dignity premise.
- **Small dependency footprint.** Three runtime deps (typer, rich,
  pyyaml). Auditors and regulators must be able to install Lantern
  without an enterprise approval chain.

## Relationship to Beacon

| Concern | Beacon | Lantern |
|---|---|---|
| Audience | Machines, pipelines, signers | Humans, reviewers, auditors |
| Primary verb | **Sign** / attest / emit | **Read** / interpret / translate |
| Failure mode | Refuses to sign | Refuses to confuse |
| Runtime | Always-on infrastructure | Person-carried, on-demand |
| Output | Cryptographic artifacts | Human narratives + diffs |
| Cadence | Per commit / per release | Per review / per question |

Lantern consumes Beacon output. It never re-signs, and it does not
verify cryptographic signatures — it reports their *presence*. For
verified chain-of-custody, run `beacon verify` first.

## Roadmap

- **v0.1 (now)** — CLI: `read`, `diff`, `explain`. Three output formats.
  Four role lenses. UCID lookup against local or embedded registry.
- **v0.2** — Web view (`lantern serve`). Per-receipt drill-in. Richer
  diff narratives.
- **v0.3** — GitHub Action wrapping the CLI to post bundle diffs as PR
  comments.
- **v1.0** — Stable role taxonomy. i18n. Reference renderers for at
  least one major regulator template (e.g., EU AI Act Annex IV form).

## Development

```bash
git clone https://github.com/bobrapp/aigovops-lantern
cd aigovops-lantern
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

ruff check src tests
mypy src
pytest --cov=aigovops_lantern
```

All commits must be DCO-signed (`git commit -s`).

## Contributing

Contributions are welcome under the same governance that covers the
broader Umbrella-GovOps framework. Please read:

- [Umbrella-GovOps GOVERNANCE.md](https://github.com/bobrapp/umbrella-govops/blob/main/GOVERNANCE.md)
- [Umbrella-GovOps TRADEMARK.md](https://github.com/bobrapp/umbrella-govops/blob/main/TRADEMARK.md)
- [UCID Registry](https://github.com/bobrapp/umbrella-govops/blob/main/UCID-REGISTRY.md)

## License

Apache License 2.0 — see [LICENSE](./LICENSE).

## Trademark

**AIGovOps Lantern™** is an unregistered trademark of the **AIGovOps
Foundation**, a U.S. 501(c)(3) nonprofit. The mark must always appear in
its compound `AIGovOps Lantern` form in product branding, package names,
and domain names. Bare "Lantern" is not a Foundation mark.

See the full [Trademark Policy](https://github.com/bobrapp/umbrella-govops/blob/main/TRADEMARK.md).

---

*Maintained by the AIGovOps Foundation · trademark@aigovopsfoundation.org*
