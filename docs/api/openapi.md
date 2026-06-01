# OpenAPI 3.1 — AIGovOps Lantern Web View (DRAFT v0.2)

The v0.2 web view is a planned read-only HTTP surface that wraps the same library functions exposed by the CLI. The spec is shipped as a **draft** alongside v0.1 so downstream tooling (Beacon, dashboards, the planned GitHub Action) can begin generating clients against a stable contract.

> **Status: DRAFT.** No server implementation exists in v0.1. Endpoints, request bodies, and response envelopes may change before v0.2.0 is tagged.

## View the spec

The raw spec lives at [`docs/api/openapi.yaml`](https://github.com/bobrapp/aigovops-lantern/blob/main/docs/api/openapi.yaml) in the repository.

Render it locally with any OpenAPI viewer, e.g.:

```bash
npx @redocly/cli preview-docs docs/api/openapi.yaml
# or
docker run -p 8080:8080 -e SPEC_URL=/spec/openapi.yaml \
  -v "$PWD/docs/api:/usr/share/nginx/html/spec" redocly/redoc
```

## Endpoints (summary)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/v1/healthz` | Liveness probe |
| `GET` | `/v1/version` | Build + UCID-registry version |
| `POST` | `/v1/render/read` | Render a receipt bundle for a role lens |
| `POST` | `/v1/render/diff` | Diff two bundles |
| `GET` | `/v1/explain/{ucid}` | Crosswalk a UCID to NIST / ISO / EU AI Act |

## Response schemas

All success responses match the JSON Schemas published at [`/schemas`](https://github.com/bobrapp/aigovops-lantern/tree/main/schemas):

- [`lantern-read.schema.json`](https://github.com/bobrapp/aigovops-lantern/blob/main/schemas/lantern-read.schema.json)
- [`lantern-diff.schema.json`](https://github.com/bobrapp/aigovops-lantern/blob/main/schemas/lantern-diff.schema.json)
- [`lantern-explain.schema.json`](https://github.com/bobrapp/aigovops-lantern/blob/main/schemas/lantern-explain.schema.json)

These are the same shapes returned by the v0.1 CLI when `--format json` is selected, which means a client written against the schemas works against both surfaces.

## Related

- [Data model](data-model.md)
- [Flows](flows.md)
- [Actions / event types](actions.md)
- Tracking issue: [aigovops-lantern#2](https://github.com/bobrapp/aigovops-lantern/issues/2)
