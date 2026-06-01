"""Tests for the bundle loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aigovops_lantern.bundle import BundleError, Receipt, load

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_ndjson_returns_expected_count() -> None:
    bundle = load(FIXTURES / "bundle_old.ndjson")
    assert len(bundle) == 8


def test_load_directory_picks_single_file(tmp_path: Path) -> None:
    src = (FIXTURES / "bundle_old.ndjson").read_text()
    (tmp_path / "only.ndjson").write_text(src)
    bundle = load(tmp_path)
    assert len(bundle) == 8


def test_load_directory_rejects_multiple_files(tmp_path: Path) -> None:
    src = (FIXTURES / "bundle_old.ndjson").read_text()
    (tmp_path / "a.ndjson").write_text(src)
    (tmp_path / "b.ndjson").write_text(src)
    with pytest.raises(BundleError, match="multiple bundle candidates"):
        load(tmp_path)


def test_load_missing_path_raises() -> None:
    with pytest.raises(BundleError, match="no such path"):
        load("/nonexistent/path/to/bundle.ndjson")


def test_load_invalid_json_line(tmp_path: Path) -> None:
    p = tmp_path / "bad.ndjson"
    p.write_text("not json\n")
    with pytest.raises(BundleError, match="invalid JSON"):
        load(p)


def test_load_missing_required_field(tmp_path: Path) -> None:
    p = tmp_path / "missing.ndjson"
    # Drop "event_type" — a required field per Beacon receipt schema.
    record = {
        "id": "01HXSZ" + "0" * 20,
        "ts_utc": "2026-05-13T14:00:00.000Z",
        "user": {"sub": "x", "oidc_issuer": "local"},
        "vendor": "in-house",
        "model": "n/a",
        "version": "n/a",
        "prompt_hash": "sha256:" + "0" * 64,
        "result_hash": "sha256:" + "0" * 64,
        # "event_type": missing
        "environment": "on_prem",
    }
    p.write_text(json.dumps(record) + "\n")
    with pytest.raises(BundleError, match="missing required fields"):
        load(p)


def test_load_json_array(tmp_path: Path) -> None:
    src_lines = (FIXTURES / "bundle_old.ndjson").read_text().splitlines()
    records = [json.loads(line) for line in src_lines if line.strip()]
    p = tmp_path / "as_array.json"
    p.write_text(json.dumps(records))
    bundle = load(p)
    assert len(bundle) == len(records)


def test_load_unknown_extension(tmp_path: Path) -> None:
    p = tmp_path / "bundle.txt"
    p.write_text("anything")
    with pytest.raises(BundleError, match="unrecognized extension"):
        load(p)


def test_event_type_counts() -> None:
    bundle = load(FIXTURES / "bundle_old.ndjson")
    counts = bundle.event_types
    # All 8 receipts in the fixture are gate.evaluated events.
    assert counts.get("gate.evaluated") == 8


def test_evidence_type_counts() -> None:
    bundle = load(FIXTURES / "bundle_old.ndjson")
    et = bundle.evidence_type_counts
    # Each receipt declares exactly one evidence type, so total == receipt count.
    assert sum(et.values()) == 8


def test_signed_count_unsigned_fixture() -> None:
    bundle = load(FIXTURES / "bundle_old.ndjson")
    assert bundle.signed_count == 0


def test_signed_count_signed_fixture() -> None:
    bundle = load(FIXTURES / "bundle_signed.ndjson")
    assert bundle.signed_count == 2


def test_receipt_properties() -> None:
    bundle = load(FIXTURES / "bundle_signed.ndjson")
    r = bundle.receipts[0]
    assert isinstance(r, Receipt)
    assert r.event_type == "bundle.signed"
    assert r.is_signed is True
    assert r.environment == "ci"
    assert r.user_sub == "ci@aigovopsfoundation.org"
