"""Bundle loader.

A Lantern "bundle" is one of:

  1. A path to an NDJSON file of AIGovOps Beacon receipts (the
     ``aigovops-beacon.v1`` profile of the OVERT 1.0 receipt envelope).
  2. A path to a JSON file containing a list of such receipts, or a single
     receipt object (for example one gate-decision receipt).
  3. A **Beacon audit bundle directory** — what ``beacon export`` and
     ``beacon-scan`` write::

         manifest.json  manifest.sha256  receipts/YYYY-MM-DD.ndjson
         public_keys/<fpr>.pem  gate_decisions.json  ...

     Every ``receipts/*.ndjson`` is read. Lantern also reports, without
     raising, whether ``manifest.sha256`` still matches ``manifest.json``,
     whether the per-file receipt counts match the manifest, and whether
     every ``gate_decisions.json`` row points at a receipt in the bundle.
  4. Any other directory holding exactly one receipt file (for example an
     ``umbrella-conformance bundle --out`` directory, whose receipts live in
     ``receipts.ndjson``). Known non-receipt files — ``manifest.json``,
     ``bundle.intoto.json``, ``inventory.json``, ``attestations.json``,
     ``gate_decisions.json`` — are ignored when choosing.

Lantern is read-only by construction. It validates structure for parsing
purposes only — it never re-signs and never asserts attestation.
Signature verification is Beacon's job; if a caller needs cryptographic
assurance, run ``beacon-verify`` first and feed the verified output here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Minimum fields a record must have to be treated as a Beacon receipt.
# Beacon's receipt writer (server/src/services/receipts.js) only sets
# ``prompt_hash`` / ``result_hash`` when there is a prompt / result, so real
# gate-decision and attestation receipts omit them; they are optional here.
_REQUIRED_FIELDS = frozenset(
    {
        "id",
        "ts_utc",
        "user",
        "vendor",
        "model",
        "version",
        "event_type",
        "environment",
    }
)

# Event types that record a gate decision. ``gate_decision`` is what Beacon
# writes; ``gate.evaluated`` / ``gate.failed`` are the OVERT-style names.
GATE_EVENT_TYPES = frozenset({"gate_decision", "gate.evaluated", "gate.failed"})

# JSON files that sit beside receipts but are not receipts.
_NON_RECEIPT_FILES = frozenset(
    {
        "manifest.json",
        "bundle.intoto.json",
        "inventory.json",
        "attestations.json",
        "gate_decisions.json",
    }
)


class BundleError(ValueError):
    """A bundle could not be loaded or parsed."""


@dataclass(frozen=True, slots=True)
class GateDecision:
    """The decision a gate-decision receipt records."""

    receipt_id: str
    gate: str
    result: str
    tier_target: str | None
    reasons: tuple[str, ...]
    inventory_id: str | None = None

    @property
    def passed(self) -> bool:
        return self.result.upper() in {"PASS", "ALLOW", "ALLOWED", "APPROVED"}


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
        return str(u.get("sub", "unknown")) if isinstance(u, dict) else "unknown"

    @property
    def attributes(self) -> dict[str, Any]:
        a = self.raw.get("attributes")
        return a if isinstance(a, dict) else {}

    @property
    def evidence_types(self) -> list[str]:
        meta = self.raw.get("evidence_meta") or {}
        types = meta.get("evidence_types") or [] if isinstance(meta, dict) else []
        return [str(t) for t in types]

    @property
    def is_signed(self) -> bool:
        """Whether the receipt carries a signature envelope.

        Lantern reports the *presence* of a signature; it does not
        attempt to verify it. Use Beacon for cryptographic verification.
        """
        return "signature" in self.raw and bool(self.raw["signature"])

    @property
    def gate_decision(self) -> GateDecision | None:
        """The gate decision this receipt records, if it is a gate-decision receipt."""
        if self.event_type not in GATE_EVENT_TYPES:
            return None
        # Beacon's server writes the decision under `attributes`; receipts built
        # with beacons/_common.make_receipt carry it in `evidence_meta`.
        meta = self.raw.get("evidence_meta")
        a = self.attributes or (meta if isinstance(meta, dict) else {})
        result = a.get("result") or a.get("decision")
        if result is None:
            result = "FAIL" if self.event_type == "gate.failed" else "unknown"
        reasons = a.get("reasons") or []
        if not isinstance(reasons, list):
            reasons = [reasons]
        tier = a.get("tier_target") or a.get("tier")
        inv = a.get("inventory_id") or self.raw.get("inventory_id")
        return GateDecision(
            receipt_id=self.id,
            gate=str(a.get("gate") or self.subject or "unnamed"),
            result=str(result),
            tier_target=str(tier) if tier is not None else None,
            reasons=tuple(_reason_text(r) for r in reasons),
            inventory_id=str(inv) if inv is not None else None,
        )


def _reason_text(r: object) -> str:
    if isinstance(r, dict):
        for k in ("message", "reason", "text", "id"):
            if k in r:
                return str(r[k])
        return json.dumps(r, sort_keys=True)
    return str(r)


@dataclass(frozen=True, slots=True)
class BeaconBundleInfo:
    """What a Beacon audit bundle directory says about itself, and whether it holds up.

    These are integrity *observations*, not verification: Lantern never
    checks Ed25519 signatures.
    """

    beacon_version: str | None
    generated_at_utc: str | None
    public_key_fingerprints: tuple[str, ...]
    signing_algorithm: str | None
    manifest_sha256_ok: bool | None  # None = no manifest.sha256 present
    receipt_files: tuple[str, ...]
    count_mismatches: tuple[str, ...]
    gate_decision_rows: int
    dangling_gate_rows: tuple[str, ...]

    @property
    def problems(self) -> list[str]:
        out: list[str] = []
        if self.manifest_sha256_ok is False:
            out.append("manifest.sha256 does not match manifest.json")
        if self.manifest_sha256_ok is None:
            out.append("no manifest.sha256 in the bundle")
        out.extend(self.count_mismatches)
        for rid in self.dangling_gate_rows:
            out.append(f"gate_decisions.json row points at receipt {rid} not in the bundle")
        return out


@dataclass(frozen=True, slots=True)
class Bundle:
    """A collection of Beacon receipts loaded from disk."""

    source: Path
    receipts: tuple[Receipt, ...] = field(default_factory=tuple)
    beacon: BeaconBundleInfo | None = None

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

    @property
    def gate_decisions(self) -> list[GateDecision]:
        return [g for r in self.receipts if (g := r.gate_decision) is not None]


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
            except RecursionError as exc:
                raise BundleError(f"{path}: JSON nested too deeply on line {line_no}") from exc
            receipts.append(_validate_receipt(obj, line_no=line_no))
    return tuple(receipts)


def _load_json(path: Path) -> tuple[Receipt, ...]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise BundleError(f"{path}: not valid UTF-8 — {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BundleError(f"{path}: invalid JSON: {exc}") from exc
    if isinstance(data, dict):
        # A single receipt — e.g. one gate-decision receipt saved on its own.
        return (_validate_receipt(data),)
    if not isinstance(data, list):
        raise BundleError(
            f"{path}: expected a JSON array of receipts or one receipt object, "
            f"got {type(data).__name__}"
        )
    return tuple(_validate_receipt(item) for item in data)


def _load_file(path: Path) -> tuple[Receipt, ...]:
    if path.suffix in {".ndjson", ".jsonl"}:
        return _load_ndjson(path)
    if path.suffix == ".json":
        return _load_json(path)
    raise BundleError(
        f"{path}: unrecognized extension {path.suffix!r}; expected .ndjson, .jsonl, or .json"
    )


def is_beacon_bundle_dir(path: Path) -> bool:
    """True for a Beacon audit bundle directory (manifest.json + receipts/)."""
    return path.is_dir() and (path / "manifest.json").is_file() and (path / "receipts").is_dir()


def _load_beacon_bundle(path: Path) -> Bundle:
    manifest_path = path / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BundleError(f"{manifest_path}: invalid JSON — {exc}") from exc
    if not isinstance(manifest, dict):
        raise BundleError(f"{manifest_path}: expected a JSON object")

    sha_ok: bool | None = None
    sha_file = path / "manifest.sha256"
    if sha_file.is_file():
        parts = sha_file.read_text(encoding="utf-8", errors="replace").split()
        sha_ok = bool(parts) and parts[0].lower() == hashlib.sha256(manifest_bytes).hexdigest()

    files = sorted((path / "receipts").glob("*.ndjson"))
    if not files:
        raise BundleError(f"{path}: Beacon bundle has no receipts/*.ndjson")
    declared = manifest.get("receipt_files") or {}
    receipts: list[Receipt] = []
    mismatches: list[str] = []
    for f in files:
        rows = _load_ndjson(f)
        want = declared.get(f.name) if isinstance(declared, dict) else None
        if want is not None and want != len(rows):
            mismatches.append(
                f"receipts/{f.name} holds {len(rows)} receipt(s); manifest declares {want}"
            )
        receipts.extend(rows)
    if isinstance(declared, dict):
        for name in sorted(set(declared) - {f.name for f in files}):
            mismatches.append(f"manifest lists receipts/{name}, which is missing")

    ids = {r.id for r in receipts}
    gate_rows: list[Any] = []
    gd = path / "gate_decisions.json"
    if gd.is_file():
        try:
            loaded = json.loads(gd.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise BundleError(f"{gd}: invalid JSON — {exc}") from exc
        gate_rows = loaded if isinstance(loaded, list) else []
    dangling = tuple(
        str(row.get("receipt_id"))
        for row in gate_rows
        if isinstance(row, dict) and row.get("receipt_id") not in ids
    )

    keys = manifest.get("public_key_fingerprints") or []
    info = BeaconBundleInfo(
        beacon_version=_opt_str(manifest.get("beacon_version")),
        generated_at_utc=_opt_str(manifest.get("generated_at_utc")),
        public_key_fingerprints=tuple(str(k) for k in keys) if isinstance(keys, list) else (),
        signing_algorithm=_opt_str(manifest.get("signing_algorithm")),
        manifest_sha256_ok=sha_ok,
        receipt_files=tuple(f.name for f in files),
        count_mismatches=tuple(mismatches),
        gate_decision_rows=len(gate_rows),
        dangling_gate_rows=dangling,
    )
    return Bundle(source=path, receipts=tuple(receipts), beacon=info)


def _opt_str(v: object) -> str | None:
    return None if v is None else str(v)


def _pick_receipt_file(path: Path) -> Path:
    candidates = sorted(
        c
        for c in [*path.glob("*.ndjson"), *path.glob("*.jsonl"), *path.glob("*.json")]
        if c.name not in _NON_RECEIPT_FILES
    )
    if not candidates:
        raise BundleError(f"{path}: no .ndjson, .jsonl, or .json file found in directory")
    if len(candidates) > 1:
        raise BundleError(
            f"{path}: multiple bundle candidates found ({[c.name for c in candidates]!r}); "
            "pass the file directly"
        )
    return candidates[0]


def load(source: str | Path) -> Bundle:
    """Load a bundle from a file or directory path.

    Recognized inputs:
      - ``*.ndjson`` / ``*.jsonl`` — newline-delimited Beacon receipts
      - ``*.json`` — a JSON array of Beacon receipts, or one receipt object
      - a Beacon audit bundle directory (``manifest.json`` + ``receipts/``)
      - any other directory containing exactly one receipt file
    """
    path = Path(source).expanduser().resolve()
    if not path.exists():
        raise BundleError(f"no such path: {path}")

    if is_beacon_bundle_dir(path):
        return _load_beacon_bundle(path)
    if path.is_dir():
        path = _pick_receipt_file(path)

    return Bundle(source=path, receipts=_load_file(path))
