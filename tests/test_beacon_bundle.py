"""Lantern reads a Beacon audit bundle directory and Beacon gate-decision receipts.

``tests/fixtures/beacon_bundle`` was produced by Beacon's own code, not
hand-written: three receipts (one invocation, two ``gate_decision`` receipts
shaped exactly as ``server/src/services/policies.js`` writes them — decision
under ``attributes``, no ``prompt_hash``) signed with
``beacons/_common.sign_receipt``, assembled with ``src/beacon_scan.build_bundle``,
plus a ``gate_decisions.json`` with the rows ``export.js`` writes. It passes
``verify_bundle.py`` (Beacon's auditor verifier). The verifier, VERIFY.md,
policies/ and checklists/ were left out of the fixture; Lantern does not read
them. ``gate_decision_receipt.json`` is the FAIL decision on its own.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aigovops_lantern.bundle import BundleError, is_beacon_bundle_dir, load
from aigovops_lantern.cli import app
from aigovops_lantern.render import compute_changes, render_bundle, render_diff

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent / "fixtures"
BEACON = FIXTURES / "beacon_bundle"
ONE_GATE = FIXTURES / "gate_decision_receipt.json"

runner = CliRunner()


def test_beacon_bundle_dir_detected_and_loaded() -> None:
    assert is_beacon_bundle_dir(BEACON)
    b = load(BEACON)
    assert len(b) == 3
    assert b.signed_count == 3
    assert b.event_types == {"invocation": 1, "gate_decision": 2}
    assert b.beacon is not None
    assert b.beacon.manifest_sha256_ok is True
    assert b.beacon.gate_decision_rows == 2
    assert b.beacon.problems == []
    assert b.beacon.signing_algorithm == "Ed25519"


def test_gate_decisions_extracted() -> None:
    gates = load(BEACON).gate_decisions
    assert [g.result for g in gates] == ["FAIL", "PASS"]
    fail = gates[0]
    assert fail.gate == "production-readiness"
    assert fail.tier_target == "T2"
    assert fail.reasons[0].startswith("nist-ai-rmf: 61%")
    assert not fail.passed and gates[1].passed


def test_real_gate_receipt_without_prompt_hash_is_accepted() -> None:
    raw = json.loads(ONE_GATE.read_text())
    assert "prompt_hash" not in raw  # what Beacon actually writes for a gate decision
    b = load(ONE_GATE)
    assert len(b) == 1
    assert b.gate_decisions[0].result == "FAIL"


def test_read_markdown_renders_gate_table_and_bundle_facts() -> None:
    out = render_bundle(load(BEACON), fmt="markdown", role="compliance")
    assert "## Beacon audit bundle" in out
    assert "**manifest.sha256:** matches" in out
    assert "## Gate decisions" in out
    assert "1 of 2 gate decision(s) passed." in out
    assert "| **FAIL** |" in out


def test_read_text_renders_gate_table() -> None:
    out = render_bundle(load(BEACON), fmt="text", role="auditor")
    assert "Gate decisions" in out
    assert "production-readiness" in out


def test_read_json_has_gate_decisions_and_beacon_block() -> None:
    data = json.loads(render_bundle(load(BEACON), fmt="json"))
    assert len(data["gate_decisions"]) == 2
    assert data["beacon_bundle"]["manifest_sha256_ok"] is True


def test_cli_read_directory() -> None:
    r = runner.invoke(app, ["read", "-f", "markdown", "-r", "compliance", str(BEACON)])
    assert r.exit_code == 0, r.output
    assert "Gate decisions" in r.output


def test_tampered_manifest_is_reported_not_hidden(tmp_path: Path) -> None:
    b = tmp_path / "bundle"
    shutil.copytree(BEACON, b)
    m = b / "manifest.json"
    m.write_text(m.read_text().replace('"beacon-scan"', '"someone-else"'))
    loaded = load(b)
    assert loaded.beacon is not None
    assert loaded.beacon.manifest_sha256_ok is False
    out = render_bundle(loaded, fmt="markdown")
    assert "**MISMATCH**" in out
    assert "manifest.sha256 does not match manifest.json" in out


def test_dropped_receipt_and_dangling_gate_row_are_reported(tmp_path: Path) -> None:
    b = tmp_path / "bundle"
    shutil.copytree(BEACON, b)
    f = next((b / "receipts").glob("*.ndjson"))
    lines = f.read_text().splitlines()
    f.write_text("\n".join(lines[:2]) + "\n")  # drop the PASS gate receipt
    problems = load(b).beacon.problems  # type: ignore[union-attr]
    assert any("manifest declares 3" in p for p in problems)
    assert any("not in the bundle" in p for p in problems)


def test_bundle_dir_without_receipts_is_an_error(tmp_path: Path) -> None:
    b = tmp_path / "bundle"
    b.mkdir()
    (b / "manifest.json").write_text("{}")
    (b / "receipts").mkdir()
    with pytest.raises(BundleError, match="no receipts"):
        load(b)


def test_umbrella_out_dir_picks_receipts_ndjson(tmp_path: Path) -> None:
    """`umbrella-conformance bundle --out ./out` leaves manifest.json and
    bundle.intoto.json beside receipts.ndjson; Lantern must pick the receipts."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "manifest.json").write_text("{}")
    (out / "bundle.intoto.json").write_text("{}")
    shutil.copy(FIXTURES / "bundle_new.ndjson", out / "receipts.ndjson")
    assert load(out).source.name == "receipts.ndjson"


def _policy_receipt(action: str, tier: str, decision: str, **extra: str) -> dict[str, object]:
    attrs: dict[str, object] = {"policy": "my-agent-v1", "action": action,
                                "tier": tier, "decision": decision, **extra}
    return {
        "id": f"{action}-{tier}-{decision}",
        "ts_utc": "2026-10-29T00:00:00Z",
        "user": {"sub": "umbrella-conformance"},
        "vendor": "in-house", "model": "n/a", "version": "0.1.0",
        "prompt_hash": "x", "result_hash": "y",
        "event_type": "policy.control", "environment": "local",
        "subject": f"policy://my-agent-v1/{action}",
        "attributes": attrs,
    }


def _write(p: Path, rows: list[dict[str, object]]) -> Path:
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def test_diff_names_the_weakened_rule(tmp_path: Path) -> None:
    """Level-200 step 5: C3 hold -> C1 allow must show up as a weakened rule."""
    deny = _policy_receipt("payment.*", "C4", "deny", reason="no")
    before = _write(tmp_path / "before.ndjson",
                    [_policy_receipt("commitment.make", "C3", "hold", approver_role="owner"), deny])
    after = _write(tmp_path / "after.ndjson",
                   [_policy_receipt("commitment.make", "C1", "allow"), deny])
    changes = compute_changes(load(before), load(after))
    by_field = {c["field"]: c for c in changes}
    assert by_field["decision"]["old"] == "hold" and by_field["decision"]["new"] == "allow"
    assert by_field["decision"]["weakened"] is True
    assert by_field["tier"]["weakened"] is True
    out = render_diff(load(before), load(after), fmt="markdown", role="engineer")
    assert "## What changed" in out
    assert "`policy://my-agent-v1/commitment.make` was **weakened**" in out
    r = runner.invoke(app, ["diff", "-f", "json", str(before), str(after)])
    assert r.exit_code == 0
    assert any(c["weakened"] for c in json.loads(r.output)["changes"])


def test_diff_policy_controls_render_in_read(tmp_path: Path) -> None:
    p = _write(tmp_path / "r.ndjson",
               [_policy_receipt("commitment.make", "C3", "hold", approver_role="owner")])
    out = render_bundle(load(p), fmt="markdown", role="compliance")
    assert "## Policy controls" in out
    assert "| `commitment.make` | C3 | **hold** | owner |" in out


def test_diff_gate_decision_flip(tmp_path: Path) -> None:
    """Old bundle ends on PASS; new bundle adds a FAIL decision for the same gate."""
    rows = [json.loads(x) for x in next((BEACON / "receipts").glob("*.ndjson")).read_text().splitlines()]
    invocation, fail, passed = rows
    old = _write(tmp_path / "old.ndjson", [invocation, passed])
    newer_fail = dict(fail, id="01NEWER", ts_utc="2099-01-01T00:00:00.000Z")
    new = _write(tmp_path / "new.ndjson", [invocation, passed, newer_fail])
    changes = compute_changes(load(old), load(new))
    assert {"field": "result", "old": "PASS", "new": "FAIL"}.items() <= changes[0].items()
    out = render_diff(load(old), load(new), fmt="markdown", role="engineer")
    assert "now **fails** its gate" in out


# ── Review hardening (PR #16) ─────────────────────────────────────────


def _gate_rows() -> list[dict[str, object]]:
    f = next((BEACON / "receipts").glob("*.ndjson"))
    return [json.loads(x) for x in f.read_text().splitlines()]


def test_gate_decisions_carry_inventory_id_from_gate_rows() -> None:
    gates = load(BEACON).gate_decisions
    assert {g.inventory_id for g in gates} == {"inv_01JBEACONFIXTURE0000000001"}


def test_gate_changes_do_not_cross_inventory_items(tmp_path: Path) -> None:
    """A new item's FAIL must not read as an existing item's regression."""
    invocation, fail, passed = _gate_rows()
    other_item_fail = dict(fail, id="01OTHER", ts_utc="2099-01-01T00:00:00.000Z",
                           model="claude-sonnet", version="2026-01-01")
    old = _write(tmp_path / "old.ndjson", [invocation, passed])
    new = _write(tmp_path / "new.ndjson", [invocation, passed, other_item_fail])
    assert [c for c in compute_changes(load(old), load(new)) if c["field"] == "result"] == []


def test_gate_reason_and_tier_changes_are_reported(tmp_path: Path) -> None:
    invocation, fail, _ = _gate_rows()
    attrs = dict(fail["attributes"], tier_target="T3", reasons=["a different reason"])  # type: ignore[arg-type]
    later = dict(fail, id="01LATER", ts_utc="2099-01-01T00:00:00.000Z", attributes=attrs)
    old = _write(tmp_path / "old.ndjson", [invocation, fail])
    new = _write(tmp_path / "new.ndjson", [invocation, fail, later])
    fields = {c["field"] for c in compute_changes(load(old), load(new))}
    assert {"tier_target", "reasons"} <= fields


def test_unlisted_receipt_file_is_reported(tmp_path: Path) -> None:
    b = tmp_path / "bundle"
    shutil.copytree(BEACON, b)
    src = next((b / "receipts").glob("*.ndjson"))
    shutil.copy(src, b / "receipts" / "2099-01-01.ndjson")
    problems = load(b).beacon.problems  # type: ignore[union-attr]
    assert any("2099-01-01.ndjson is not listed in the manifest" in p for p in problems)


def test_missing_receipt_files_map_is_reported(tmp_path: Path) -> None:
    b = tmp_path / "bundle"
    shutil.copytree(BEACON, b)
    m = json.loads((b / "manifest.json").read_text())
    del m["receipt_files"]
    (b / "manifest.json").write_text(json.dumps(m))
    problems = load(b).beacon.problems  # type: ignore[union-attr]
    assert any("no receipt_files map" in p for p in problems)


@pytest.mark.skipif(
    __import__("os").geteuid() == 0 if hasattr(__import__("os"), "geteuid") else True,
    reason="needs POSIX permissions and a non-root user",
)
def test_unreadable_manifest_is_a_bundle_error(tmp_path: Path) -> None:
    b = tmp_path / "bundle"
    shutil.copytree(BEACON, b)
    (b / "manifest.json").chmod(0o000)
    try:
        with pytest.raises(BundleError, match="cannot read"):
            load(b)
        r = runner.invoke(app, ["read", str(b)])
        assert r.exit_code == 2
    finally:
        (b / "manifest.json").chmod(0o644)


def test_receipt_text_is_not_rich_markup(tmp_path: Path) -> None:
    """A reason like `[link=…]PASS[/link]` must print literally, not as markup."""
    invocation, fail, _ = _gate_rows()
    evil = "[green]PASS[/green] [link=https://evil.example]details[/link]"
    attrs = dict(fail["attributes"], reasons=[evil])  # type: ignore[arg-type]
    p = _write(tmp_path / "evil.ndjson", [invocation, dict(fail, attributes=attrs)])
    out = render_bundle(load(p), fmt="text")
    # Table cells wrap, so look for the literal markup fragments, not the whole string.
    assert "[green]" in out and "[/green]" in out
    assert "[link=" in out
