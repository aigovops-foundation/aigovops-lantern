"""Verify that Lantern's `--format json` outputs conform to the published schemas.

The schemas under ``schemas/`` are the public contract for downstream
tooling. These tests are the contract's enforcement: every JSON output
shape the CLI emits must validate against the corresponding schema, and
the schemas themselves must be valid JSON Schema 2020-12.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).parent.parent
SCHEMAS = REPO_ROOT / "schemas"
FIXTURES = Path(__file__).parent / "fixtures"

READ_SCHEMA = json.loads((SCHEMAS / "lantern-read.schema.json").read_text())
DIFF_SCHEMA = json.loads((SCHEMAS / "lantern-diff.schema.json").read_text())
EXPLAIN_SCHEMA = json.loads((SCHEMAS / "lantern-explain.schema.json").read_text())


def _lantern_json(*args: str) -> dict[str, object]:
    proc = subprocess.run(
        [sys.executable, "-m", "aigovops_lantern.cli", *args, "-f", "json"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(proc.stdout)


def test_read_schema_is_valid_jsonschema_2020_12() -> None:
    jsonschema.Draft202012Validator.check_schema(READ_SCHEMA)


def test_diff_schema_is_valid_jsonschema_2020_12() -> None:
    jsonschema.Draft202012Validator.check_schema(DIFF_SCHEMA)


def test_explain_schema_is_valid_jsonschema_2020_12() -> None:
    jsonschema.Draft202012Validator.check_schema(EXPLAIN_SCHEMA)


def test_read_output_conforms_to_schema() -> None:
    data = _lantern_json("read", str(FIXTURES / "bundle_new.ndjson"))
    jsonschema.validate(data, READ_SCHEMA)


def test_read_signed_output_conforms_to_schema() -> None:
    data = _lantern_json("read", str(FIXTURES / "bundle_signed.ndjson"))
    jsonschema.validate(data, READ_SCHEMA)


def test_diff_output_conforms_to_schema() -> None:
    data = _lantern_json(
        "diff",
        str(FIXTURES / "bundle_old.ndjson"),
        str(FIXTURES / "bundle_new.ndjson"),
    )
    jsonschema.validate(data, DIFF_SCHEMA)


def test_explain_output_conforms_to_schema() -> None:
    data = _lantern_json(
        "explain",
        "UCID-DATA-BIAS-001",
        "--registry",
        str(FIXTURES / "ucid_registry.yaml"),
    )
    jsonschema.validate(data, EXPLAIN_SCHEMA)
