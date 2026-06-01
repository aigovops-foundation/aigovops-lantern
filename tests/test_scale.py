"""Scale / throughput tests.

These tests generate large synthetic bundles and assert the CLI stays
within reasonable wall-clock and memory budgets. They are skipped by
default to keep PR feedback fast; opt-in with ``RUN_SCALE=1``.

Budgets target a hosted GitHub Actions runner (2 vCPU, 7 GB RAM):

  - 10 000 receipts  · load + render JSON     · < 5 s,  < 256 MB
  - 50 000 receipts  · load + render markdown · < 20 s, < 512 MB
  - 100 000 receipts · diff against half      · < 30 s, < 768 MB
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import psutil
import pytest

from aigovops_lantern.bundle import load
from aigovops_lantern.render import render_bundle, render_diff

pytestmark = [
    pytest.mark.scale,
    pytest.mark.skipif(
        os.environ.get("RUN_SCALE") != "1",
        reason="scale tests opt-in via RUN_SCALE=1",
    ),
]


def _make_receipt(i: int) -> dict[str, object]:
    return {
        "id": f"r-{i:08d}",
        "ts_utc": "2026-06-01T15:00:00Z",
        "user": f"actor-{i % 17}",
        "vendor": "openai" if i % 3 else "anthropic",
        "model": "gpt-4o-mini" if i % 3 else "claude-3-5-sonnet",
        "version": "1.0.0",
        "prompt_hash": f"sha256:{i:064x}",
        "result_hash": f"sha256:{(i * 7) & ((1 << 256) - 1):064x}",
        "event_type": "gate.evaluated" if i % 5 else "gate.failed",
        "environment": "prod" if i % 2 else "staging",
    }


def _write_bundle(path: Path, n: int) -> Path:
    with path.open("w", encoding="utf-8") as f:
        for i in range(n):
            f.write(json.dumps(_make_receipt(i)) + "\n")
    return path


def _rss_mb() -> float:
    return psutil.Process().memory_info().rss / (1024 * 1024)


# ──────────────────────────────────────────────────────────────────────


def test_load_and_render_json_10k(tmp_path: Path) -> None:
    path = _write_bundle(tmp_path / "bundle_10k.ndjson", 10_000)
    rss_before = _rss_mb()

    t0 = time.perf_counter()
    bundle = load(path)
    out = render_bundle(bundle, "json", role=None)
    elapsed = time.perf_counter() - t0

    rss_after = _rss_mb()
    assert len(bundle) == 10_000
    assert out, "expected output"
    assert elapsed < 5.0, f"10k took {elapsed:.2f}s, budget 5s"
    assert rss_after - rss_before < 256, f"RSS delta {rss_after - rss_before:.1f}MB > 256MB"


def test_load_and_render_markdown_50k(tmp_path: Path) -> None:
    path = _write_bundle(tmp_path / "bundle_50k.ndjson", 50_000)
    rss_before = _rss_mb()

    t0 = time.perf_counter()
    bundle = load(path)
    out = render_bundle(bundle, "markdown", role="auditor")
    elapsed = time.perf_counter() - t0

    rss_after = _rss_mb()
    assert len(bundle) == 50_000
    assert out
    assert elapsed < 20.0, f"50k took {elapsed:.2f}s, budget 20s"
    assert rss_after - rss_before < 512, f"RSS delta {rss_after - rss_before:.1f}MB > 512MB"


def test_diff_100k_against_50k(tmp_path: Path) -> None:
    base = _write_bundle(tmp_path / "base.ndjson", 50_000)
    head = _write_bundle(tmp_path / "head.ndjson", 100_000)
    rss_before = _rss_mb()

    t0 = time.perf_counter()
    bundle_a = load(base)
    bundle_b = load(head)
    out = render_diff(bundle_a, bundle_b, "json", role="engineer")
    elapsed = time.perf_counter() - t0

    rss_after = _rss_mb()
    data = json.loads(out)
    assert len(data["added_ids"]) == 50_000
    assert elapsed < 30.0, f"diff took {elapsed:.2f}s, budget 30s"
    assert rss_after - rss_before < 768, f"RSS delta {rss_after - rss_before:.1f}MB > 768MB"
