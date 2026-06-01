"""Bundle loader.

A Lantern "bundle" is one of:

  1. A path to an NDJSON file of AIGovOps Beacon receipts (the
     ``aigovops-beacon.v1`` profile of the OVERT 1.0 receipt envelope).
  2. A path to a JSON file containing a list of such receipts.
  3. A directory containing either of the above files (auto-detected).

Lantern is read-only by construction. It validates structure for parsing
purposes only — it never re-signs and never asserts attestation.
Signature verification is Beacon's job; if a caller needs cryptographic
assurance, run ``beacon verify`` first and feed the verified output here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Minimum fields a record must have to be treated as a Beacon receipt.
# Mirrors the required[] list in
# https://github.com/bobrapp/aigovops-beacon/blob/main/docs/blueprint/artifacts/receipt.schema.json
_REQUIRED_FIELDS = frozenset(
    {
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
    }
)


class BundleError(ValueError):
    """A bundle could not be loaded or parsed."""


@dataclass(frozen=True, slots=True)
class Receipt:
    """A single Beacon receipt, as Lantern reads it.

    This is intentionally a thin wrapper around the parsed dict. Beacon
    owns the canonical schema; Lantern only requires enough structure to
    render a human-readable view.
    """

    raw: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.raw["id"])

    @property
    def ts_utc(self) -> str:
        return str(self.raw["ts_utc"])

    @property
    def event_type(self) -> str:
        return str(self.raw["event_type"])

    @property
    def subject(self) -> str | None:
        v = self.raw.get("subject")
        return str(v) if v is not None else None

    @property
    def vendor(self) -> str:
        return str(self.raw.get("vendor", "unknown"))

    @property
    def model(self) -> str:
        return str(self.raw.get("model", "n/a"))

    @property
    def environment(self) -> str:
        return str(self.raw.get("environment", "unknown"))

    @property
    def user_sub(self) -> str:
        u = self.raw.get("user") or {}
        return str(u.get("sub", "unknown"))

    @property
    def evidence_types(self) -> list[str]:
        meta = self.raw.get("evidence_meta") or {}
        types = meta.get("evidence_types") or []
        return [str(t) for t in types]

    @property
    def is_signed(self) -> bool:
        """Whether the receipt carries a signature envelope.

        Lantern reports the *presence* of a signature; it does not
        attempt to verify it. Use Beacon for cryptographic verification.
        """
        return "signature" in self.raw and bool(self.raw["signature"])


@dataclass(frozen=True, slots=True)
class Bundle:
    """A collection of Beacon receipts loaded from disk."""

    source: Path
    receipts: tuple[Receipt, ...] = field(default_factory=tuple)

    def __len__(self) -> int:
        return len(self.receipts)

    @property
    def event_types(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.receipts:
            counts[r.event_type] = counts.get(r.event_type, 0) + 1
        return counts

    @property
    def evidence_type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.receipts:
            for t in r.evidence_types:
                counts[t] = counts.get(t, 0) + 1
        return counts

    @property
    def signed_count(self) -> int:
        return sum(1 for r in self.receipts if r.is_signed)

    @property
    def id_set(self) -> frozenset[str]:
        return frozenset(r.id for r in self.receipts)


def _validate_receipt(obj: object, line_no: int | None = None) -> Receipt:
    """Ensure a parsed object is shaped like a Beacon receipt.

    Lantern is permissive: missing optional fields are fine, but the
    required envelope fields must be present so we know we are reading
    a real receipt rather than arbitrary JSON.
    """
    if not isinstance(obj, dict):
        where = f"line {line_no}" if line_no is not None else "input"
        raise BundleError(f"expected JSON object at {where}, got {type(obj).__name__}")
    missing = _REQUIRED_FIELDS - obj.keys()
    if missing:
        where = f"line {line_no}" if line_no is not None else "input"
        raise BundleError(
            f"receipt at {where} is missing required fields: {sorted(missing)!r}"
        )
    return Receipt(raw=obj)


def _load_ndjson(path: Path) -> tuple[Receipt, ...]:
    receipts: list[Receipt] = []
    try:
        fh = path.open("r", encoding="utf-8")
    except OSError as exc:
        raise BundleError(f"{path}: cannot open — {exc}") from exc
    with fh:
        try:
            lines = list(enumerate(fh, start=1))
        except UnicodeDecodeError as exc:
            raise BundleError(f"{path}: not valid UTF-8 — {exc}") from exc
        for line_no, raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BundleError(f"{path}: invalid JSON on line {line_no}: {exc}") from exc
            receipts.append(_validate_receipt(obj, line_no=line_no))
    return tuple(receipts)


def _load_json_array(path: Path) -> tuple[Receipt, ...]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise BundleError(f"{path}: not valid UTF-8 — {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BundleError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise BundleError(f"{path}: expected a JSON array of receipts, got {type(data).__name__}")
    return tuple(_validate_receipt(item) for item in data)


def load(source: str | Path) -> Bundle:
    """Load a bundle from a file or directory path.

    Recognized inputs:
      - ``*.ndjson`` / ``*.jsonl`` — newline-delimited Beacon receipts
      - ``*.json`` — single JSON array of Beacon receipts
      - a directory containing exactly one of the above
    """
    path = Path(source).expanduser().resolve()
    if not path.exists():
        raise BundleError(f"no such path: {path}")

    if path.is_dir():
        candidates = sorted(
            [
                *path.glob("*.ndjson"),
                *path.glob("*.jsonl"),
                *path.glob("*.json"),
            ]
        )
        if not candidates:
            raise BundleError(f"{path}: no .ndjson, .jsonl, or .json file found in directory")
        if len(candidates) > 1:
            raise BundleError(
                f"{path}: multiple bundle candidates found ({[c.name for c in candidates]!r}); "
                "pass the file directly"
            )
        path = candidates[0]

    if path.suffix in {".ndjson", ".jsonl"}:
        receipts = _load_ndjson(path)
    elif path.suffix == ".json":
        receipts = _load_json_array(path)
    else:
        raise BundleError(
            f"{path}: unrecognized extension {path.suffix!r}; expected .ndjson, .jsonl, or .json"
        )

    return Bundle(source=path, receipts=receipts)
