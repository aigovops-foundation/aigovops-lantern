"""End-to-end tests for the Lantern CLI."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aigovops_lantern import __version__
from aigovops_lantern.cli import app

FIXTURES = Path(__file__).parent / "fixtures"
runner = CliRunner()


def test_version() -> None:
    r = runner.invoke(app, ["--version"])
    assert r.exit_code == 0
    assert __version__ in r.stdout


def test_help_lists_three_commands() -> None:
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    assert "read" in r.stdout
    assert "diff" in r.stdout
    assert "explain" in r.stdout


def test_read_json_command() -> None:
    r = runner.invoke(app, ["read", "-f", "json", str(FIXTURES / "bundle_old.ndjson")])
    assert r.exit_code == 0, r.stdout
    data = json.loads(r.stdout)
    assert data["receipt_count"] == 8


def test_read_markdown_with_role() -> None:
    r = runner.invoke(
        app,
        [
            "read",
            "-f",
            "markdown",
            "-r",
            "auditor",
            str(FIXTURES / "bundle_signed.ndjson"),
        ],
    )
    assert r.exit_code == 0
    assert "Auditor view" in r.stdout


def test_read_missing_file_exits_2(tmp_path: Path) -> None:
    r = runner.invoke(app, ["read", str(tmp_path / "nope.ndjson")])
    assert r.exit_code != 0


def test_diff_json() -> None:
    r = runner.invoke(
        app,
        [
            "diff",
            "-f",
            "json",
            str(FIXTURES / "bundle_old.ndjson"),
            str(FIXTURES / "bundle_new.ndjson"),
        ],
    )
    assert r.exit_code == 0
    data = json.loads(r.stdout)
    assert len(data["added_ids"]) == 4


def test_explain_known_ucid_json() -> None:
    r = runner.invoke(app, ["explain", "-f", "json", "UCID-DATA-BIAS-001"])
    assert r.exit_code == 0
    data = json.loads(r.stdout)
    assert data["id"] == "UCID-DATA-BIAS-001"


def test_explain_unknown_ucid_exits_2() -> None:
    r = runner.invoke(app, ["explain", "UCID-NOPE-999"])
    assert r.exit_code == 2


def test_explain_with_local_registry() -> None:
    r = runner.invoke(
        app,
        [
            "explain",
            "-f",
            "json",
            "--registry",
            str(FIXTURES / "ucid_registry.yaml"),
            "UCID-OVERSIGHT-001",
        ],
    )
    assert r.exit_code == 0
    data = json.loads(r.stdout)
    assert "GOVERN-3.2" in data["nist_ai_rmf"]
