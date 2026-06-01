# AIGovOps Lantern — Scope v0.1

**Status:** v0.1 shipped (alpha).

> "Beacon signs. Lantern reads."

## Premise

Beacon emits machine-verifiable artifacts. Lantern turns those artifacts
into something a human can act on without losing fidelity.

This is the **dignity layer**: the assumption that humans are worthy of
clear explanation, not just compliance checkboxes.

## Non-goals (explicit)

Lantern is **not**:

- A signer or attester. That is Beacon's job, exclusively.
- A policy authoring tool. Policies live in Umbrella-GovOps.
- A registry of record. The UCID registry is the source of truth.
- A privacy / anonymization / circumvention tool. (Important: the bare
  trademark "Lantern" is held by Brave New Software in the
  privacy-tool space — AIGovOps Lantern must never position itself as
  a privacy-circumvention product.)
- A GRC platform. Lantern reads bundles; it does not replace enterprise
  GRC.

## Goals (v0.1 → v1.0)

1. **Read a Beacon-signed evidence bundle** and render it human-readable.
2. **Diff two bundles** and produce a role-targeted narrative
   (engineer / compliance / auditor / regulator).
3. **Resolve UCIDs to plain-language explanations** from the published
   registry.
4. **Run in three places**: CLI, GitHub Action (PR comment), small web
   view. No deployed service required to use it.

## Interfaces (v0.1 shipped)

```
lantern read    ./evidence-bundle.ndjson [-f text|markdown|json] [-r engineer|compliance|auditor|regulator]
lantern diff    ./old.ndjson ./new.ndjson [-f ...] [-r ...]
lantern explain UCID-DATA-BIAS-001 [--registry ./unified-control-id.yaml] [-f ...]
```

## Interfaces (deferred to v0.2+)

```
lantern serve --port 8080   # local web view
```

## Architecture principles

- **Read-only by construction.** Lantern never produces signed
  artifacts. If a user needs a signature, they go to Beacon.
- **Local-first.** Works against local files with no network.
- **No telemetry.** Lantern is a tool people carry — surveillance is
  inconsistent with the dignity premise.
- **Small dependency footprint.** Auditors and regulators must be able
  to install and run Lantern themselves without an enterprise approval
  chain.

## Open questions for v0.1

- Bundle schema: pin to Beacon's current emitted schema or define a
  Lantern-facing read schema?
- Role taxonomy: how many narrative "lenses" do we ship initially?
- Output formats: Markdown + ANSI + HTML — is JSON output also required
  for downstream tooling?
- i18n: the dignity premise implies non-English readers. Defer or design
  in from v0.1?

## Companion repo

Beacon: https://github.com/bobrapp/aigovops-beacon
Umbrella: https://github.com/bobrapp/umbrella-govops
