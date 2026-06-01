"""UCID registry loader & lookup.

The Unified Control Identifier (UCID) registry is maintained at
https://github.com/bobrapp/umbrella-govops/blob/main/crosswalks/unified-control-id.yaml
under the Designated Expert review process described in
``UCID-REGISTRY.md`` of the same repository.

Lantern does **not** maintain its own copy of the registry. It either:

  - reads a local YAML file the user points it at (``--registry``), or
  - falls back to a minimal bundled snapshot used purely for tests and
    offline demos (see ``EMBEDDED_FALLBACK`` below).

Lantern is read-only with respect to the registry: it never mutates,
re-numbers, or "fixes" UCIDs. The Designated Expert process is the only
way to change a UCID's metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class UcidError(LookupError):
    """A UCID could not be resolved."""


@dataclass(frozen=True, slots=True)
class Ucid:
    """One UCID entry as Lantern surfaces it.

    Mirrors the fields most relevant for human-readable rendering.
    Unknown fields from the YAML are preserved in ``extras`` so that
    Lantern degrades gracefully when the upstream registry adds
    columns.
    """

    id: str
    title: str
    status: str
    nist_ai_rmf: tuple[str, ...] = ()
    eu_ai_act_articles: tuple[str, ...] = ()
    eu_ai_act_annex_iv: tuple[str, ...] = ()
    iso_42001: tuple[str, ...] = ()
    implementing_controls: tuple[str, ...] = ()
    extras: dict[str, Any] | None = None


# A tiny embedded snapshot — used only when no --registry path is
# supplied and the project does not ship its own. Keeps the offline
# demo and unit tests deterministic. NOT the source of truth.
EMBEDDED_FALLBACK: dict[str, Ucid] = {
    "UCID-DATA-BIAS-001": Ucid(
        id="UCID-DATA-BIAS-001",
        title="Dataset bias examination",
        status="provisional",
        nist_ai_rmf=("MEASURE-2.11", "MAP-2.3", "MANAGE-2.3"),
        eu_ai_act_articles=("10(2)(f)", "10(3)"),
        eu_ai_act_annex_iv=("2(d)", "2(g)"),
        iso_42001=("A.7.4",),
        implementing_controls=("DG-002",),
    ),
    "UCID-OVERSIGHT-001": Ucid(
        id="UCID-OVERSIGHT-001",
        title="Human oversight measures",
        status="provisional",
        nist_ai_rmf=("GOVERN-3.2", "MANAGE-4.1"),
        eu_ai_act_articles=("14(1)", "14(4)"),
        iso_42001=("A.6.2.2",),
        implementing_controls=("HO-001",),
    ),
}


def _normalize_list(v: Any) -> tuple[str, ...]:
    if v is None:
        return ()
    if isinstance(v, str):
        return (v,)
    if isinstance(v, list):
        return tuple(str(x) for x in v)
    return (str(v),)


def _parse_entry(entry: dict[str, Any]) -> Ucid:
    eu = entry.get("eu_ai_act") or {}
    if isinstance(eu, dict):
        articles = _normalize_list(eu.get("articles"))
        annex_iv = _normalize_list(eu.get("annex_iv"))
    else:
        articles = ()
        annex_iv = ()

    known = {
        "id",
        "title",
        "status",
        "created",
        "proposer",
        "nist_ai_rmf",
        "eu_ai_act",
        "iso_42001",
        "implementing_controls",
    }
    extras = {k: v for k, v in entry.items() if k not in known}

    return Ucid(
        id=str(entry["id"]),
        title=str(entry.get("title", "")),
        status=str(entry.get("status", "unknown")),
        nist_ai_rmf=_normalize_list(entry.get("nist_ai_rmf")),
        eu_ai_act_articles=articles,
        eu_ai_act_annex_iv=annex_iv,
        iso_42001=_normalize_list(entry.get("iso_42001")),
        implementing_controls=_normalize_list(entry.get("implementing_controls")),
        extras=extras or None,
    )


def load_registry(path: str | Path | None = None) -> dict[str, Ucid]:
    """Load a UCID registry from a YAML file, or return the embedded fallback.

    ``path`` should point at a ``unified-control-id.yaml``-shaped file
    (the canonical source lives in umbrella-govops/crosswalks/).
    """
    if path is None:
        return dict(EMBEDDED_FALLBACK)

    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise UcidError(f"registry not found: {p}")

    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise UcidError(f"{p}: malformed YAML — {exc}") from exc
    if not isinstance(raw, dict) or "ucids" not in raw:
        raise UcidError(f"{p}: not a UCID registry (no top-level 'ucids' key)")

    entries = raw["ucids"]
    if not isinstance(entries, list):
        raise UcidError(f"{p}: 'ucids' must be a list")

    out: dict[str, Ucid] = {}
    for entry in entries:
        if not isinstance(entry, dict) or "id" not in entry:
            continue
        u = _parse_entry(entry)
        out[u.id] = u
    return out


def lookup(ucid_id: str, registry: dict[str, Ucid] | None = None) -> Ucid:
    reg = registry if registry is not None else EMBEDDED_FALLBACK
    try:
        return reg[ucid_id]
    except KeyError as exc:
        raise UcidError(f"unknown UCID: {ucid_id!r}") from exc
