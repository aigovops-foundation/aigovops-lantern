"""Tests for the UCID registry loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from aigovops_lantern.ucid import (
    EMBEDDED_FALLBACK,
    UcidError,
    load_registry,
    lookup,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_embedded_fallback_has_known_ucids() -> None:
    assert "UCID-DATA-BIAS-001" in EMBEDDED_FALLBACK
    assert "UCID-OVERSIGHT-001" in EMBEDDED_FALLBACK


def test_load_registry_from_yaml() -> None:
    reg = load_registry(FIXTURES / "ucid_registry.yaml")
    assert "UCID-DATA-BIAS-001" in reg
    u = reg["UCID-DATA-BIAS-001"]
    assert u.title == "Dataset bias examination"
    assert "MEASURE-2.11" in u.nist_ai_rmf
    assert "10(2)(f)" in u.eu_ai_act_articles
    assert "2(d)" in u.eu_ai_act_annex_iv
    assert "A.7.4" in u.iso_42001
    assert "DG-002" in u.implementing_controls


def test_load_registry_missing_path() -> None:
    with pytest.raises(UcidError, match="not found"):
        load_registry("/nonexistent/registry.yaml")


def test_load_registry_wrong_shape(tmp_path: Path) -> None:
    p = tmp_path / "wrong.yaml"
    p.write_text("just_a_string\n")
    with pytest.raises(UcidError, match="not a UCID registry"):
        load_registry(p)


def test_lookup_unknown_raises() -> None:
    with pytest.raises(UcidError, match="unknown UCID"):
        lookup("UCID-NOPE-999")


def test_lookup_uses_embedded_when_no_registry() -> None:
    u = lookup("UCID-DATA-BIAS-001")
    assert u.id == "UCID-DATA-BIAS-001"


def test_lookup_with_explicit_registry() -> None:
    reg = load_registry(FIXTURES / "ucid_registry.yaml")
    u = lookup("UCID-OVERSIGHT-001", registry=reg)
    assert "GOVERN-3.2" in u.nist_ai_rmf
