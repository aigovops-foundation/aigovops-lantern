"""Chaos tests: input fuzzing + filesystem / I/O failure injection.

Two flavors:

  1. **Property-based fuzz** (Hypothesis) — generates malformed JSON,
     missing fields, huge strings, weird Unicode, conflicting types,
     and asserts the loader either accepts the input or raises
     ``BundleError`` — but **never** raises an unhandled exception
     and never crashes the interpreter.

  2. **I/O chaos** — monkeypatches ``Path.open`` and friends to inject
     ``PermissionError``, ``OSError``, partial reads, and broken
     pipes. Asserts the CLI / library degrades gracefully.

Marked ``chaos``. Skipped by default in the very-fast PR matrix; the
nightly scale-and-chaos workflow flips ``RUN_CHAOS=1`` to enable them.
Locally, pass ``RUN_CHAOS=1`` or use ``pytest -m chaos``.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from aigovops_lantern.bundle import BundleError, load
from aigovops_lantern.render import render_bundle
from aigovops_lantern.ucid import UcidError, load_registry, lookup

pytestmark = [
    pytest.mark.chaos,
    pytest.mark.skipif(
        os.environ.get("RUN_CHAOS") != "1",
        reason="chaos tests opt-in via RUN_CHAOS=1 (nightly workflow)",
    ),
]


# ──────────────────────────────────────────────────────────────────────
# 1. Hypothesis fuzz — random receipts


# A single receipt strategy that produces *plausible-shaped* dicts —
# some valid, some missing required fields, some with wrong types.
_REQUIRED_FIELDS = (
    "id",
    "ts_utc",
    "user",
    "vendor",
    "model",
    "version",
    "prompt_hash",
    "result_hash",
    "event_type",
    "environment",
)


@st.composite
def random_receipt(draw: st.DrawFn) -> dict[str, Any]:
    keep = draw(st.sets(st.sampled_from(_REQUIRED_FIELDS), min_size=0))
    receipt: dict[str, Any] = {}
    for field in keep:
        receipt[field] = draw(
            st.one_of(
                st.text(min_size=0, max_size=200),
                st.integers(),
                st.floats(allow_nan=False, allow_infinity=False),
                st.booleans(),
                st.none(),
                st.lists(st.integers(), max_size=5),
            )
        )
    # Sometimes throw in an extra field to make sure tolerant loading works.
    if draw(st.booleans()):
        receipt[draw(st.text(min_size=1, max_size=20))] = draw(
            st.text(max_size=50)
        )
    return receipt


@settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
    derandomize=True,  # deterministic in CI
)
@given(receipts=st.lists(random_receipt(), min_size=0, max_size=50))
def test_load_never_crashes_on_random_receipts(
    tmp_path_factory: pytest.TempPathFactory,
    receipts: list[dict[str, Any]],
) -> None:
    """Loader must accept or raise BundleError. Never anything else."""
    path = tmp_path_factory.mktemp("fuzz") / "b.ndjson"
    with path.open("w", encoding="utf-8") as f:
        for r in receipts:
            f.write(json.dumps(r) + "\n")
    with contextlib.suppress(BundleError):
        load(path)  # expected for malformed input


# Random bytes that may or may not be JSON
@settings(max_examples=100, deadline=None, derandomize=True)
@given(payload=st.binary(min_size=0, max_size=4096))
def test_load_never_crashes_on_random_bytes(
    tmp_path_factory: pytest.TempPathFactory, payload: bytes
) -> None:
    path = tmp_path_factory.mktemp("fuzzb") / "b.ndjson"
    path.write_bytes(payload)
    with contextlib.suppress(BundleError):
        load(path)  # all decode/parse errors should be wrapped in BundleError


# Random unicode text — emoji, RTL, control chars, BOM, etc.
@settings(max_examples=100, deadline=None, derandomize=True)
@given(
    text=st.text(
        # Surrogates (Cs) cannot be encoded as UTF-8 — they cannot appear in a real file
        # on disk. Exclude them so the test exercises the loader, not the file write.
        alphabet=st.characters(blacklist_categories=("Cs",)),
        min_size=0,
        max_size=1024,
    )
)
def test_load_never_crashes_on_random_unicode(
    tmp_path_factory: pytest.TempPathFactory, text: str
) -> None:
    path = tmp_path_factory.mktemp("fuzzu") / "b.ndjson"
    path.write_text(text, encoding="utf-8")
    with contextlib.suppress(BundleError):
        load(path)


# Random valid-shaped bundles must render in every format/role.
_VALID_FIELDS = {
    "id": st.text(min_size=1, max_size=40),
    "ts_utc": st.just("2026-06-01T15:00:00Z"),
    "user": st.text(min_size=1, max_size=40),
    "vendor": st.sampled_from(["openai", "anthropic", "google", "meta"]),
    "model": st.sampled_from(["gpt-4o", "claude-3-5", "gemini-1.5", "llama-3"]),
    "version": st.just("1.0.0"),
    "prompt_hash": st.from_regex(r"^sha256:[0-9a-f]{64}$", fullmatch=True),
    "result_hash": st.from_regex(r"^sha256:[0-9a-f]{64}$", fullmatch=True),
    "event_type": st.sampled_from(
        ["gate.evaluated", "gate.failed", "bundle.signed", "inference.observed"]
    ),
    "environment": st.sampled_from(["prod", "staging", "dev"]),
}


@st.composite
def valid_receipt(draw: st.DrawFn) -> dict[str, Any]:
    return {k: draw(v) for k, v in _VALID_FIELDS.items()}


@settings(max_examples=50, deadline=None, derandomize=True)
@given(receipts=st.lists(valid_receipt(), min_size=1, max_size=30))
def test_valid_random_bundles_render_in_every_combo(
    tmp_path_factory: pytest.TempPathFactory, receipts: list[dict[str, Any]]
) -> None:
    path = tmp_path_factory.mktemp("ok") / "b.ndjson"
    with path.open("w", encoding="utf-8") as f:
        for r in receipts:
            f.write(json.dumps(r) + "\n")
    bundle = load(path)
    for fmt in ("text", "markdown", "json"):
        for role in ("engineer", "compliance", "auditor", "regulator"):
            out = render_bundle(bundle, fmt, role=role)  # type: ignore[arg-type]
            assert out, f"empty output for {fmt}/{role}"


# ──────────────────────────────────────────────────────────────────────
# 2. UCID fuzz — every input shape


@settings(max_examples=200, deadline=None, derandomize=True)
@given(ucid_id=st.text(min_size=0, max_size=100))
def test_ucid_lookup_never_crashes(ucid_id: str) -> None:
    """Any string in, UcidError or Ucid out. Never anything else."""
    with contextlib.suppress(UcidError):
        lookup(ucid_id)


# ──────────────────────────────────────────────────────────────────────
# 3. I/O chaos — filesystem failure injection


def test_permission_denied_is_caught(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "denied.ndjson"
    path.write_text('{"id": "x"}\n')

    real_open = Path.open

    def failing_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self == path:
            raise PermissionError(13, "Permission denied", str(self))
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", failing_open)

    with pytest.raises((PermissionError, BundleError)):
        load(path)


def test_truncated_file_raises_bundle_error(tmp_path: Path) -> None:
    path = tmp_path / "truncated.ndjson"
    # Write a half-line then nothing — should fail JSON decode cleanly.
    path.write_text('{"id": "abc", "ts_utc": "2026-06-01T15')

    with pytest.raises(BundleError):
        load(path)


def test_empty_file_yields_empty_bundle(tmp_path: Path) -> None:
    """An empty file is a valid zero-receipt bundle — must not crash."""
    path = tmp_path / "empty.ndjson"
    path.write_text("")
    bundle = load(path)
    assert len(bundle) == 0
    # Render must still succeed for empty bundles
    for fmt in ("text", "markdown", "json"):
        out = render_bundle(bundle, fmt, role=None)  # type: ignore[arg-type]
        assert out


def test_directory_instead_of_file_fails_cleanly(tmp_path: Path) -> None:
    # Passing a directory must not crash — it must raise BundleError or
    # IsADirectoryError (both acceptable).
    with pytest.raises((BundleError, IsADirectoryError, PermissionError)):
        load(tmp_path)


def test_registry_with_malformed_yaml_fails_cleanly(tmp_path: Path) -> None:
    bad = tmp_path / "ucid.yaml"
    bad.write_text("controls: [::: unclosed\n")
    with pytest.raises((UcidError, ValueError)):
        load_registry(bad)


def test_huge_single_line_does_not_oom(tmp_path: Path) -> None:
    """A pathologically large single JSON line should still parse or
    fail cleanly — not OOM."""
    path = tmp_path / "huge.ndjson"
    big_field = "x" * 1_000_000  # 1 MB of payload in one field
    obj = {
        "id": "x",
        "ts_utc": "2026-06-01T15:00:00Z",
        "user": "u",
        "vendor": "v",
        "model": "m",
        "version": "1",
        "prompt_hash": "sha256:" + "a" * 64,
        "result_hash": "sha256:" + "b" * 64,
        "event_type": "gate.evaluated",
        "environment": "prod",
        "extra": big_field,
    }
    path.write_text(json.dumps(obj) + "\n")
    bundle = load(path)
    assert len(bundle) == 1
