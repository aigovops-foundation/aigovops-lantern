# Lantern flows

This document maps the end-to-end journeys Lantern participates in.
Each diagram is Mermaid; GitHub renders these inline.

## 1. Read a bundle (CLI today, web in v0.2)

```mermaid
sequenceDiagram
    autonumber
    actor User as Engineer / Compliance / Auditor / Regulator
    participant CLI as lantern CLI
    participant Loader as bundle.load
    participant Renderer as render.render_bundle
    participant Out as stdout

    User->>CLI: lantern read bundle.ndjson -f markdown -r auditor
    CLI->>Loader: load(path)
    Loader-->>CLI: Bundle (validated receipts)
    CLI->>Renderer: render_bundle(bundle, "markdown", "auditor")
    Renderer-->>CLI: rendered text
    CLI->>Out: write
    Out-->>User: human-readable summary
```

## 2. Compare two bundles

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as lantern CLI
    participant Loader as bundle.load
    participant Diff as render.render_diff
    participant Out as stdout

    User->>CLI: lantern diff old.ndjson new.ndjson -r engineer
    CLI->>Loader: load(old)
    Loader-->>CLI: Bundle A
    CLI->>Loader: load(new)
    Loader-->>CLI: Bundle B
    CLI->>Diff: render_diff(A, B, "text", "engineer")
    Note over Diff: id-set delta + event-count delta + role narrative
    Diff-->>CLI: rendered diff
    CLI->>Out: write
    Out-->>User: what changed (and what to do)
```

## 3. Explain a Unified Control ID

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as lantern CLI
    participant Reg as ucid.load_registry
    participant Lookup as ucid.lookup
    participant Out as stdout

    User->>CLI: lantern explain UCID-DATA-BIAS-001
    alt --registry passed
        CLI->>Reg: load_registry(path)
        Reg-->>CLI: dict[id → Ucid]
    else use embedded fallback
        CLI->>Reg: load_registry(None)
        Reg-->>CLI: EMBEDDED_FALLBACK
    end
    CLI->>Lookup: lookup("UCID-DATA-BIAS-001", registry)
    Lookup-->>CLI: Ucid (with framework citations)
    CLI->>Out: render_ucid(...)
    Out-->>User: control + citations
```

## 4. End-to-end with Beacon (the big picture)

```mermaid
sequenceDiagram
    autonumber
    participant Workload as AI Workload
    participant Beacon as Beacon (signer)
    participant Anchor as Anchor (Sigstore / SLSA)
    participant Bundle as Evidence Bundle (.ndjson)
    participant Lantern as Lantern (reader)
    participant Reader as Auditor / Compliance / Regulator

    Workload->>Beacon: emit receipt (event_type, prompt_hash, result_hash, …)
    Beacon->>Beacon: validate against OVERT 1.0 schema
    Beacon->>Anchor: keyless sign + attest
    Anchor-->>Beacon: signature envelope
    Beacon->>Bundle: append signed receipt
    Note over Bundle: Bundle is the boundary between<br/>"machines write" and "humans read"
    Bundle->>Lantern: load(bundle.ndjson)
    Lantern->>Lantern: render_bundle / render_diff / render_ucid
    Lantern-->>Reader: role-appropriate narrative
```

## 5. PR-comment workflow (planned v0.3 action)

```mermaid
sequenceDiagram
    autonumber
    actor Developer
    participant CI as GitHub Actions
    participant Beacon as Beacon CI step
    participant LanternAction as aigovops/lantern-action@v1
    participant PR as Pull Request

    Developer->>PR: push commits
    PR->>CI: trigger workflow
    CI->>Beacon: produce base + head bundles
    CI->>LanternAction: diff base vs head with role=engineer
    LanternAction->>LanternAction: pip install lantern + run `lantern diff -f markdown`
    LanternAction->>PR: upsert sticky PR comment with the rendered diff
    PR-->>Developer: comment notification
```
