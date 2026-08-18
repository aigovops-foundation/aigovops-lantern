# Data model

Lantern is a thin client over two upstream data models. It does not invent
its own — that is by design, so the same artifacts travel from Beacon
(producer) through Lantern (reader) without translation losses.

## 1. Beacon evidence bundle

A **bundle** is a sequence of receipts in one of three on-disk forms:

| Extension | Format | When to use |
|---|---|---|
| `.ndjson` | One JSON object per line | The canonical wire form. Append-only friendly. |
| `.jsonl` | Alias for `.ndjson` | Same shape; tooling parity. |
| `.json` | A JSON array of receipts | Convenient for hand-editing tiny bundles in fixtures. |

A **receipt** is a JSON object that conforms to the upstream [OVERT 1.0 receipt schema](https://github.com/aigovops-foundation/aigovops-beacon/blob/main/docs/blueprint/artifacts/receipt.schema.json).
See [actions.md](actions.md) for the required-field list and the
`event_type` vocabulary.

### Lantern's view of a receipt

In Lantern's Python API, a receipt is a `Receipt` dataclass with one
property: `raw: dict`. Lantern intentionally does **not** unpack every
field into typed attributes — receipts evolve faster than dataclasses,
and Lantern's job is to render whatever Beacon emits, not to gatekeep.

### Lantern's view of a bundle

```python
from aigovops_lantern.bundle import load

bundle = load("path/to/bundle.ndjson")
len(bundle)                  # receipt count
bundle.event_types           # dict[str, int]
bundle.evidence_type_counts  # dict[str, int]
bundle.signed_count          # int
bundle.id_set                # frozenset[str]
```

## 2. Unified Control ID (UCID) registry

A UCID is a stable identifier for a control concept (e.g. dataset-bias
examination, human oversight). UCIDs live in
[umbrella-govops/crosswalks/unified-control-id.yaml](https://github.com/aigovops-foundation/umbrella-govops/blob/main/crosswalks/unified-control-id.yaml).

### Schema

```yaml
ucids:
  - id: UCID-DATA-BIAS-001
    title: Dataset bias examination
    status: provisional       # provisional | stable | deprecated
    implementing_controls:
      - DG-002
    nist_ai_rmf:
      - MEASURE-2.11
      - MAP-2.3
    iso_42001:
      - A.7.4
    eu_ai_act_articles:
      - 10(2)(f)
      - 10(3)
    eu_ai_act_annex_iv:
      - 2(d)
      - 2(g)
```

### Lantern's view

```python
from aigovops_lantern.ucid import load_registry, lookup

registry = load_registry("path/to/unified-control-id.yaml")
u = lookup("UCID-DATA-BIAS-001", registry)
u.id, u.title, u.status, u.nist_ai_rmf
```

If `--registry` is omitted, Lantern falls back to an embedded subset
(`EMBEDDED_FALLBACK`) so basic explain queries work offline. Production
deployments should always pass the upstream registry path to stay current.

## 3. Output schemas (the public contract)

Every `--format json` shape Lantern emits has a published JSON Schema
under `/schemas`:

| Command | Schema file | Top-level shape |
|---|---|---|
| `lantern read` | [`schemas/lantern-read.schema.json`](https://github.com/aigovops-foundation/aigovops-lantern/blob/main/schemas/lantern-read.schema.json) | `{source, receipt_count, receipt_ids, event_types, evidence_types, signed_count}` |
| `lantern diff` | [`schemas/lantern-diff.schema.json`](https://github.com/aigovops-foundation/aigovops-lantern/blob/main/schemas/lantern-diff.schema.json) | `{old, new, added_ids, removed_ids, kept_count, event_deltas}` |
| `lantern explain` | [`schemas/lantern-explain.schema.json`](https://github.com/aigovops-foundation/aigovops-lantern/blob/main/schemas/lantern-explain.schema.json) | `{id, title, status, implementing_controls, nist_ai_rmf, …}` |

A schema-conformance test (`tests/test_schemas.py`) runs in CI to keep
the schemas honest — if a renderer's output drifts from its schema, CI
fails before the change merges.

## 4. The boundary Lantern enforces

Lantern is a **read** boundary, not a verify boundary. It will tell you a
bundle carries a signature envelope, but it will never tell you the
signature is valid. For verified chain-of-custody, run `beacon verify`
first and pass the verified bundle to Lantern.
