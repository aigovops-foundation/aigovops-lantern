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

> **Status:** v0.0 — namespace reserved · scoping in progress. First
> stable cut targeted for Q3 2026.

---

## Why Lantern

Beacon answers the machine question: *"Is this artifact signed, attested,
and conformant?"*

Lantern answers the human question: *"Can I, the person who has to act on
this, understand what it means, what changed, and what I need to do?"*

The Foundation's premise is **humans are worthy** — the carried light, not
just the spotlight. Lantern is the reader, translator, and dignity layer
on top of the policy-as-code substrate.

## Scope (v0.1 — draft)

- **Conformance reader** — render an Umbrella-GovOps evidence bundle
  (signed by Beacon) into human-readable form: control-by-control diff,
  attestation chain, UCID crosswalk view.
- **Plain-language explainers** — every UCID, control, and policy gets a
  short human gloss derived from the registry, not boilerplate.
- **Diff & narrative mode** — explain what changed between two evidence
  bundles in the language of the affected role (engineer, compliance,
  legal, regulator).
- **Portable** — runnable as CLI, GitHub Action, and small web view.
  Carried, not deployed.

## Relationship to Beacon

| Concern | Beacon | Lantern |
|---|---|---|
| Audience | Machines, pipelines, signers | Humans, reviewers, auditors |
| Primary verb | **Sign** / attest / emit | **Read** / interpret / translate |
| Failure mode | Refuses to sign | Refuses to confuse |
| Runtime | Always-on infrastructure | Person-carried, on-demand |
| Output | Cryptographic artifacts | Human narratives + diffs |
| Cadence | Per commit / per release | Per review / per question |

Lantern consumes Beacon output. It never re-signs and never asserts
attestation on its own — that is Beacon's role, and only Beacon's.

## Status & roadmap

This repository currently serves as the **namespace reservation and
public scoping ground** for the project. Concrete milestones:

- **v0.0 (now)** — README, scope, license, governance pointers
- **v0.1** — CLI skeleton; read & render a single signed evidence bundle
- **v0.2** — Diff-mode between two bundles; UCID glossary lookups
- **v0.3** — GitHub Action wrapping CLI for PR comment rendering
- **v1.0** — Stable web view + role-specific narrative templates

## Contributing

Contributions are welcome under the same governance that covers the
broader Umbrella-GovOps framework. Please read:

- [Umbrella-GovOps GOVERNANCE.md](https://github.com/bobrapp/umbrella-govops/blob/main/GOVERNANCE.md)
- [Umbrella-GovOps TRADEMARK.md](https://github.com/bobrapp/umbrella-govops/blob/main/TRADEMARK.md)
- [UCID Registry](https://github.com/bobrapp/umbrella-govops/blob/main/UCID-REGISTRY.md)

All commits must be signed off (DCO) per the Foundation contributing
policy.

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
