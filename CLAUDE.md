# AIGovOps Lantern: notes for Claude

Lantern is the reader for Beacon's signed evidence: a Python CLI (`lantern read` and others) that
renders receipts and bundles for people. Python 3.11+. Public repo.

## Layout

- `src/aigovops_lantern/`: the package. `tests/`: unit, end-to-end, scale and chaos tests.
- `schemas/`: the schemas the reader checks against.
- `docs/` and `mkdocs.yml`: the documentation site, built by `.github/workflows/docs.yml` and
  published through GitHub Pages on a push to `main`.

## Checks to run before a pull request

```bash
ruff check src tests
mypy src
pytest -m "not scale and not chaos" --cov=aigovops_lantern --cov-report=term-missing --cov-fail-under=80
pytest -m scale -v
pytest -m chaos -v
python -m mkdocs build --strict
```

These are the commands CI runs. Coverage under 80% fails the build, and the docs build is strict:
a broken link or anchor fails it.

## Things that are easy to get wrong

- Lantern reads; it never signs. Do not add anything that writes or alters a receipt.
- When Lantern reports that a manifest hash or a receipt count does not match, that report is the
  feature. Never soften a mismatch into a warning to make a test pass.

## Rules for an agent

- Agents propose, humans approve. Open a pull request; do not merge it, and do not push to `main`.
- Never sign, approve or rule on anything in a human's name.
- Secrets live in 1Password. Never print, paste or commit a key, token or private key.
- A check that was not run is reported as not run. Do not write "passes" from memory.
- Read `CONTRIBUTING.md` where there is one. It wins over this file where they differ.
