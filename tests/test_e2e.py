"""End-to-end CLI tests.

These tests shell out to the installed ``lantern`` console script and
exercise every subcommand, flag, and format combination as a real user
would. They are slower than the unit tests but they catch packaging,
entry-point, and argument-parsing regressions the unit tests miss.

Marked ``e2e``. Always run in CI; opt-in to skip locally with
``pytest -m "not e2e"``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
BUNDLE_OLD = FIXTURES / "bundle_old.ndjson"
BUNDLE_NEW = FIXTURES / "bundle_new.ndjson"
BUNDLE_SIGNED = FIXTURES / "bundle_signed.ndjson"
UCID_REGISTRY = FIXTURES / "ucid_registry.yaml"

pytestmark = pytest.mark.e2e


def _lantern() -> list[str]:
    """Return the command prefix for invoking the CLI.

    Prefer the installed `lantern` entry-point; fall back to
    `python -m aigovops_lantern.cli` so the suite works in editable-only
    environments.
    """
    exe = shutil.which("lantern")
    if exe:
        return [exe]
    return [sys.executable, "-m", "aigovops_lantern.cli"]


def _run(*args: str, expect_code: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [*_lantern(), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == expect_code, (
        f"exit {proc.returncode}; stderr={proc.stderr!r}; stdout={proc.stdout!r}"
    )
    return proc


# ──────────────────────────────────────────────────────────────────────
# version / help


def test_version_flag() -> None:
    out = _run("--version").stdout
    assert "aigovops-lantern" in out
    assert "0.1" in out


def test_help_lists_all_commands() -> None:
    out = _run("--help").stdout
    for command in ("read", "diff", "explain"):
        assert command in out


# ──────────────────────────────────────────────────────────────────────
# read


@pytest.mark.parametrize("fmt", ["text", "markdown", "json"])
@pytest.mark.parametrize("role", ["engineer", "compliance", "auditor", "regulator"])
def test_read_every_role_and_format(fmt: str, role: str) -> None:
    proc = _run("read", str(BUNDLE_NEW), "-f", fmt, "-r", role)
    assert proc.stdout.strip(), "expected non-empty output"


def test_read_json_is_valid_json() -> None:
    proc = _run("read", str(BUNDLE_NEW), "-f", "json")
    data = json.loads(proc.stdout)
    assert "receipt_ids" in data
    assert isinstance(data["receipt_ids"], list)
    assert len(data["receipt_ids"]) > 0
    assert "event_types" in data


def test_read_markdown_contains_receipt_count() -> None:
    proc = _run("read", str(BUNDLE_NEW), "-f", "markdown")
    assert "receipt" in proc.stdout.lower()


def test_read_signed_bundle_reports_signature_presence() -> None:
    proc = _run("read", str(BUNDLE_SIGNED), "-f", "json")
    data = json.loads(proc.stdout)
    assert data["signed_count"] >= 1


def test_read_missing_file_fails_cleanly(tmp_path: Path) -> None:
    proc = _run("read", str(tmp_path / "does-not-exist.ndjson"), expect_code=2)
    assert proc.stderr or proc.stdout, "expected an error message"


# ──────────────────────────────────────────────────────────────────────
# diff


@pytest.mark.parametrize("fmt", ["text", "markdown", "json"])
@pytest.mark.parametrize("role", ["engineer", "compliance", "auditor", "regulator"])
def test_diff_every_role_and_format(fmt: str, role: str) -> None:
    proc = _run("diff", str(BUNDLE_OLD), str(BUNDLE_NEW), "-f", fmt, "-r", role)
    assert proc.stdout.strip()


def test_diff_json_reports_added_count() -> None:
    proc = _run("diff", str(BUNDLE_OLD), str(BUNDLE_NEW), "-f", "json")
    data = json.loads(proc.stdout)
    assert "added_ids" in data
    assert len(data["added_ids"]) >= 1


def test_diff_identical_bundles_reports_no_changes() -> None:
    proc = _run("diff", str(BUNDLE_OLD), str(BUNDLE_OLD), "-f", "json")
    data = json.loads(proc.stdout)
    assert len(data["added_ids"]) == 0
    assert len(data["removed_ids"]) == 0


# ──────────────────────────────────────────────────────────────────────
# explain


@pytest.mark.parametrize("fmt", ["text", "markdown", "json"])
def test_explain_known_ucid(fmt: str) -> None:
    proc = _run(
        "explain",
        "UCID-DATA-BIAS-001",
        "--registry",
        str(UCID_REGISTRY),
        "-f",
        fmt,
    )
    assert "UCID-DATA-BIAS-001" in proc.stdout


def test_explain_unknown_ucid_fails_cleanly() -> None:
    proc = _run(
        "explain",
        "UCID-DOES-NOT-EXIST-999",
        "--registry",
        str(UCID_REGISTRY),
        expect_code=2,
    )
    assert proc.stderr or proc.stdout


def test_explain_json_has_required_fields() -> None:
    proc = _run(
        "explain",
        "UCID-DATA-BIAS-001",
        "--registry",
        str(UCID_REGISTRY),
        "-f",
        "json",
    )
    data = json.loads(proc.stdout)
    assert data["id"] == "UCID-DATA-BIAS-001"
    assert "title" in data


# ──────────────────────────────────────────────────────────────────────
# argument hygiene


def test_invalid_role_is_rejected() -> None:
    proc = _run(
        "read", str(BUNDLE_NEW), "-r", "executive", expect_code=2
    )
    assert proc.stderr or proc.stdout


def test_invalid_format_is_rejected() -> None:
    proc = _run("read", str(BUNDLE_NEW), "-f", "xml", expect_code=2)
    assert proc.stderr or proc.stdout
