"""The docs anchor guard (scripts/check_doc_anchors.py) must fail on a dead API anchor.

It is run the way CI runs it: as a subprocess, from the repo root's point of view, with a
RELATIVE site directory. That detail is the test. The first version of the guard only caught a
dead anchor on the same page; a link to a missing id on ANOTHER page passed whenever the site
path was relative, because the lookup compared absolute paths with relative ones.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_doc_anchors.py"
GOOD = "aigovops_lantern.bundle.Thing"
DEAD = "aigovops_lantern.bundle.DoesNotExist"


def _site(tmp_path: Path, *, cli_link: str, bundle_link: str = f"#{GOOD}") -> None:
    bundle = tmp_path / "site" / "python" / "bundle"
    cli = tmp_path / "site" / "python" / "cli"
    bundle.mkdir(parents=True)
    cli.mkdir(parents=True)
    (bundle / "index.html").write_text(f'<h2 id="{GOOD}">Thing</h2><a href="{bundle_link}">nav</a>')
    (cli / "index.html").write_text(f'<a href="{cli_link}">see bundle</a>')


def _run(tmp_path: Path, site_arg: str = "site") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), site_arg], cwd=tmp_path, capture_output=True, text=True, check=False
    )


def test_passes_when_every_anchor_resolves(tmp_path: Path) -> None:
    _site(tmp_path, cli_link=f"../bundle/#{GOOD}")
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    assert "checked 2 " in r.stdout  # both links were really checked, not skipped


def test_fails_on_a_dead_anchor_on_the_same_page(tmp_path: Path) -> None:
    _site(tmp_path, cli_link=f"../bundle/#{GOOD}", bundle_link=f"#{DEAD}")
    r = _run(tmp_path)
    assert r.returncode == 1
    assert DEAD in r.stderr


def test_fails_on_a_dead_anchor_on_another_page_with_a_relative_site(tmp_path: Path) -> None:
    _site(tmp_path, cli_link=f"../bundle/#{DEAD}")
    r = _run(tmp_path, "site")
    assert r.returncode == 1, "a cross-page dead anchor passed: the guard skipped it"
    assert "python/cli/index.html" in r.stderr and DEAD in r.stderr


def test_absolute_and_relative_site_agree(tmp_path: Path) -> None:
    _site(tmp_path, cli_link=f"../bundle/#{DEAD}")
    assert _run(tmp_path, "site").returncode == _run(tmp_path, str(tmp_path / "site")).returncode == 1


def test_a_missing_site_directory_is_a_failure(tmp_path: Path) -> None:
    assert _run(tmp_path).returncode == 1
