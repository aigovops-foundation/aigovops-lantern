"""Tests for the renderers and diff narrative."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aigovops_lantern.bundle import load
from aigovops_lantern.render import (
    receipt_oneliner,
    render_bundle,
    render_diff,
    render_ucid,
)
from aigovops_lantern.ucid import lookup

FIXTURES = Path(__file__).parent / "fixtures"


def test_render_bundle_json_is_valid_json() -> None:
    bundle = load(FIXTURES / "bundle_old.ndjson")
    out = render_bundle(bundle, fmt="json")
    data = json.loads(out)
    assert data["receipt_count"] == 8
    assert data["signed_count"] == 0
    assert "gate.evaluated" in data["event_types"]


def test_render_bundle_markdown_contains_summary() -> None:
    bundle = load(FIXTURES / "bundle_old.ndjson")
    out = render_bundle(bundle, fmt="markdown")
    assert "Bundle:" in out
    assert "Receipts:" in out
    assert "## Event types" in out
    # 0 signed receipts → warning should appear
    assert "No receipts in this bundle carry a signature envelope" in out


def test_render_bundle_markdown_with_role() -> None:
    bundle = load(FIXTURES / "bundle_signed.ndjson")
    out = render_bundle(bundle, fmt="markdown", role="auditor")
    assert "Auditor view" in out
    # signed bundle should NOT trigger the unsigned warning
    assert "No receipts in this bundle carry a signature envelope" not in out


def test_render_bundle_text_runs() -> None:
    bundle = load(FIXTURES / "bundle_old.ndjson")
    out = render_bundle(bundle, fmt="text")
    assert "Bundle" in out
    assert "Beacon signs. Lantern reads." in out


def test_render_diff_json() -> None:
    old = load(FIXTURES / "bundle_old.ndjson")
    new = load(FIXTURES / "bundle_new.ndjson")
    out = render_diff(old, new, fmt="json")
    data = json.loads(out)
    assert len(data["added_ids"]) == 4  # 12 new - 8 old shared = 4 added
    assert data["removed_ids"] == []
    assert data["kept_count"] == 8


def test_render_diff_markdown_no_change() -> None:
    bundle = load(FIXTURES / "bundle_old.ndjson")
    out = render_diff(bundle, bundle, fmt="markdown")
    assert "Added: **0**" in out
    assert "Removed: **0**" in out


def test_render_diff_role_compliance_mentions_ucid_mapping() -> None:
    old = load(FIXTURES / "bundle_old.ndjson")
    new = load(FIXTURES / "bundle_new.ndjson")
    out = render_diff(old, new, fmt="markdown", role="compliance")
    assert "Compliance view" in out
    assert "UCID" in out


def test_render_ucid_markdown() -> None:
    u = lookup("UCID-DATA-BIAS-001")
    out = render_ucid(u, fmt="markdown")
    assert "UCID-DATA-BIAS-001" in out
    assert "Dataset bias examination" in out
    assert "NIST AI RMF" in out
    assert "EU AI Act" in out
    assert "ISO/IEC 42001" in out


def test_render_ucid_json() -> None:
    u = lookup("UCID-DATA-BIAS-001")
    out = render_ucid(u, fmt="json")
    data = json.loads(out)
    assert data["id"] == "UCID-DATA-BIAS-001"
    assert data["status"] == "provisional"
    assert "MEASURE-2.11" in data["nist_ai_rmf"]


def test_receipt_oneliner_format() -> None:
    bundle = load(FIXTURES / "bundle_signed.ndjson")
    line = receipt_oneliner(bundle.receipts[0])
    assert "[✓]" in line  # signed mark
    assert "bundle.signed" in line


@pytest.mark.parametrize("role", ["engineer", "compliance", "auditor", "regulator"])
def test_all_roles_render_without_error(role: str) -> None:
    bundle = load(FIXTURES / "bundle_signed.ndjson")
    out = render_bundle(bundle, fmt="markdown", role=role)  # type: ignore[arg-type]
    assert role.title() in out
