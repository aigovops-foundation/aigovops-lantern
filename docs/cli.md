# CLI reference

Every command, flag, and exit code Lantern's CLI exposes.

## Global options

```
lantern [OPTIONS] COMMAND [ARGS]...

  --version, -V         show version and exit
  --help                show help and exit
```

## `lantern read`

Render a Beacon evidence bundle as a human-readable summary.

```
lantern read BUNDLE [--format {text|markdown|json}] [--role ROLE]
```

| Flag | Default | What it does |
|---|---|---|
| `BUNDLE` | _required_ | Path to a `.ndjson`, `.jsonl`, or `.json` bundle file. |
| `-f`, `--format` | `text` | Output format. `text` uses a Rich panel; `markdown` is PR-comment ready; `json` conforms to [`lantern-read.schema.json`](api/data-model.md#3-output-schemas-the-public-contract). |
| `-r`, `--role` | _(none)_ | Reader lens — one of `engineer`, `compliance`, `auditor`, `regulator`. Adjusts tone and call-outs. |

### Examples

```bash
# Human-readable summary for a terminal
lantern read evidence/bundle.ndjson

# Auditor-flavored markdown for a PR comment
lantern read evidence/bundle.ndjson -f markdown -r auditor

# Machine-readable summary for a downstream script
lantern read evidence/bundle.ndjson -f json | jq '.event_types'
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `2` | Argument error (bad role/format, file missing, bundle malformed) |

## `lantern diff`

Compare two bundles and explain what changed.

```
lantern diff OLD NEW [--format {text|markdown|json}] [--role ROLE]
```

| Flag | Default | What it does |
|---|---|---|
| `OLD` | _required_ | Baseline bundle path. |
| `NEW` | _required_ | Candidate bundle path. |
| `-f`, `--format` | `text` | Output format. JSON conforms to [`lantern-diff.schema.json`](api/data-model.md#3-output-schemas-the-public-contract). |
| `-r`, `--role` | _(none)_ | Reader lens. Engineer sees gate.failed callouts; auditor sees unsigned-receipt warnings; compliance sees UCID-mapping reminders; regulator sees framework-citation drift. |

### Examples

```bash
# Engineer flavor in a terminal
lantern diff base.ndjson head.ndjson -r engineer

# Markdown diff suitable for a PR sticky comment
lantern diff base.ndjson head.ndjson -f markdown -r engineer

# JSON for a CI gate
lantern diff base.ndjson head.ndjson -f json | jq '.removed_ids | length == 0'
```

## `lantern explain`

Resolve a Unified Control ID against a registry.

```
lantern explain UCID [--registry PATH] [--format {text|markdown|json}]
```

| Flag | Default | What it does |
|---|---|---|
| `UCID` | _required_ | The control ID, e.g. `UCID-DATA-BIAS-001`. Must match `^UCID-[A-Z0-9-]+-[0-9]{3,6}$`. |
| `--registry` | _(embedded fallback)_ | Path to `unified-control-id.yaml`. Without this, Lantern uses a small embedded set; production use should always pass the upstream registry. |
| `-f`, `--format` | `text` | Output format. JSON conforms to [`lantern-explain.schema.json`](api/data-model.md#3-output-schemas-the-public-contract). |

### Examples

```bash
# Quick lookup using the embedded fallback
lantern explain UCID-DATA-BIAS-001

# Production: use the upstream registry
lantern explain UCID-OVERSIGHT-001 \
  --registry ./umbrella-govops/crosswalks/unified-control-id.yaml \
  -f markdown

# Machine-readable for a downstream policy linter
lantern explain UCID-DATA-BIAS-001 -f json | jq '.nist_ai_rmf'
```

### Errors

- `UcidError: unknown UCID: 'UCID-…'` → the ID doesn't exist in the registry; check spelling or pass `--registry`.
- `UcidError: registry not found: …` → bad `--registry` path.
- `UcidError: malformed YAML — …` → the registry file isn't valid YAML.

## Environment variables

| Variable | Effect |
|---|---|
| `RUN_SCALE=1` | Run `tests/test_scale.py` (otherwise skipped). Used by the nightly workflow. |
| `RUN_CHAOS=1` | Run `tests/test_chaos.py`. Used by the nightly workflow. |
| `NO_COLOR=1` | Disable Rich's ANSI colors in `text` output. Useful for piping. |
