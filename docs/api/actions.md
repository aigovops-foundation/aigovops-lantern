# Actions reference

The vocabulary of `event_type` values Lantern recognizes when rendering Beacon
bundles. These values come from the Beacon receipt schema
([receipt.schema.json](https://github.com/bobrapp/aigovops-beacon/blob/main/docs/blueprint/artifacts/receipt.schema.json));
Lantern's job is to interpret them in human terms for each role.

| event_type | What it means | Engineer view | Compliance view | Auditor view | Regulator view |
|---|---|---|---|---|---|
| `gate.evaluated` | A policy gate ran; produced a decision. | Confirms the gate executed in the pipeline. | Coverage signal — gate participated in this decision. | Chain-of-custody anchor. | Demonstrates due-diligence runtime check. |
| `gate.failed` | A policy gate denied or errored. | **Likely cause of a CI red — investigate.** | Control fired — escalate if production. | Records why the system refused. | Demonstrates enforcement, not just monitoring. |
| `bundle.signed` | The bundle was cryptographically signed. | Bundle is ready to publish/ship. | Tamper-evidence is established. | **Required for admissibility — confirm signature presence.** | Evidence integrity claim. |
| `bundle.anchored` | The bundle was anchored to a transparency log (e.g. Sigstore). | Public-log entry exists. | Third-party witness of timestamp. | Independent timestamp source. | External anchoring strengthens non-repudiation. |
| `admission.allowed` | An admission webhook permitted the request. | Workload was admitted. | Records a permit decision. | Authorization event in the trail. | Demonstrates control point exists and was exercised. |
| `admission.denied` | An admission webhook blocked the request. | Workload was blocked — debug the policy. | **Control denial — record reason.** | Records refusal in the trail. | Enforcement action evidence. |
| `inference.observed` | An inference call was logged for downstream review. | Observability hook fired. | Coverage of the monitored surface. | Activity record. | Transparency / explainability evidence. |
| `policy.updated` | A policy bundle was reloaded or changed. | Configuration drift event. | **Change-management trigger.** | Material change to controls. | Demonstrates managed change. |

## Required fields on every receipt

Lantern's loader rejects (with `BundleError`) any receipt missing these
fields. They are the minimum needed to make a receipt human-meaningful:

- `id` — stable, unique within the bundle
- `ts_utc` — ISO 8601 in UTC
- `user` — the actor (human or service) that triggered the event
- `vendor` — model provider (openai / anthropic / google / …)
- `model` — specific model identifier
- `version` — semver or build tag of the workload
- `prompt_hash` — `sha256:…` digest of the input
- `result_hash` — `sha256:…` digest of the output
- `event_type` — one of the values above
- `environment` — `prod` / `staging` / `dev` / …

## Optional fields Lantern looks for

| Field | What Lantern does with it |
|---|---|
| `signature` | Increments `signed_count`; surfaces to auditor role. |
| `evidence_type` | Counted into `evidence_types` summary. |
| `ucid` | If present, cross-references against the registry for explain-mode hints. |
| `pr_url`, `commit_sha` | Linked in markdown output when rendering for engineers. |
| `framework_citations` | Surfaced verbatim to regulator role. |

## Adding a new event_type

Lantern is **tolerant** of unknown event types — it counts them under
`event_types` and renders them with a neutral tone, so Beacon can add new
event types without breaking Lantern. To get a custom render lens for a new
event type, add a case to `_diff_narrative` in `src/aigovops_lantern/render.py`
and a row to the table above.
