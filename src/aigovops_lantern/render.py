"""Human-facing rendering for receipts, bundles, diffs, and UCIDs.

Three render targets are supported:

  - ``text`` — Rich-styled terminal output (default)
  - ``markdown`` — plain Markdown suitable for PR comments and email
  - ``json`` — machine-readable, for downstream tooling

Lantern follows a "dignity premise": every output explains what it
shows and what action (if any) the reader should consider. We do not
emit raw artifact dumps without context.
"""

from __future__ import annotations

import json
from typing import Literal

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .bundle import Bundle, GateDecision, Receipt
from .ucid import Ucid

RenderFormat = Literal["text", "markdown", "json"]

Role = Literal["engineer", "compliance", "auditor", "regulator"]

_ROLE_TONES: dict[Role, str] = {
    "engineer": (
        "Engineer view — focus on the integrity of the pipeline that produced this bundle."
    ),
    "compliance": (
        "Compliance view — focus on which controls are covered, which gaps remain, and the "
        "evidence-to-control mapping."
    ),
    "auditor": (
        "Auditor view — focus on the chain of custody: who produced each receipt, when, "
        "in which environment, and whether the receipt carries a signature."
    ),
    "regulator": (
        "Regulator view — focus on framework citations (NIST AI RMF, EU AI Act, ISO 42001) "
        "and which obligations the bundle claims to satisfy."
    ),
}


# ──────────────────────────────────────────────────────────────────────
# Gate decisions, policy controls, Beacon bundle facts
# ──────────────────────────────────────────────────────────────────────

_DECISION_RANK = {"allow": 0, "hold": 1, "deny": 2}
_TIER_RANK = {f"C{i}": i for i in range(5)}
_CHANGE_FIELDS = (
    "tier",
    "decision",
    "approver_role",
    "reason",
    "result",
    "tier_target",
    "status",
)


def _policy_controls(bundle: Bundle) -> list[Receipt]:
    return [
        r
        for r in bundle.receipts
        if r.event_type == "policy.control" and "decision" in r.attributes
    ]


def _gate_dict(g: GateDecision) -> dict[str, object]:
    return {
        "receipt_id": g.receipt_id,
        "gate": g.gate,
        "result": g.result,
        "tier_target": g.tier_target,
        "reasons": list(g.reasons),
    }


def _beacon_dict(bundle: Bundle) -> dict[str, object] | None:
    b = bundle.beacon
    if b is None:
        return None
    return {
        "beacon_version": b.beacon_version,
        "generated_at_utc": b.generated_at_utc,
        "signing_algorithm": b.signing_algorithm,
        "public_key_fingerprints": list(b.public_key_fingerprints),
        "manifest_sha256_ok": b.manifest_sha256_ok,
        "receipt_files": list(b.receipt_files),
        "gate_decision_rows": b.gate_decision_rows,
        "problems": b.problems,
    }


def _md_cell(v: object) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ")


def _beacon_markdown(bundle: Bundle) -> list[str]:
    b = bundle.beacon
    if b is None:
        return []
    sha = {True: "matches", False: "**MISMATCH**", None: "absent"}[b.manifest_sha256_ok]
    lines = [
        "## Beacon audit bundle",
        "",
        f"- **Beacon version:** {b.beacon_version or 'unknown'}",
        f"- **Generated:** {b.generated_at_utc or 'unknown'}",
        f"- **Signing:** {b.signing_algorithm or 'unknown'} · keys "
        + (", ".join(f"`{k}`" for k in b.public_key_fingerprints) or "none listed"),
        f"- **manifest.sha256:** {sha}",
        "- **Receipt files:** " + ", ".join(f"`{f}`" for f in b.receipt_files),
        f"- **gate_decisions.json rows:** {b.gate_decision_rows}",
    ]
    for problem in b.problems:
        lines.append(f"- ⚠️ {problem}")
    lines.append("")
    return lines


def _gates_markdown(bundle: Bundle, role: Role | None) -> list[str]:
    gates = bundle.gate_decisions
    if not gates:
        return []
    passed = sum(1 for g in gates if g.passed)
    lines = [
        "## Gate decisions",
        "",
        f"{passed} of {len(gates)} gate decision(s) passed.",
        "",
        "| Receipt | Gate | Tier target | Result | Reasons |",
        "|---|---|---|---|---|",
    ]
    for g in gates:
        reasons = "; ".join(g.reasons) if g.reasons else "—"
        lines.append(
            f"| `{g.receipt_id}` | {_md_cell(g.gate)} | {g.tier_target or '—'} "
            f"| **{_md_cell(g.result)}** | {_md_cell(reasons)} |"
        )
    if role == "auditor":
        lines.append("")
        lines.append(
            "> Each decision is only as good as its receipt's signature. Lantern reports "
            "presence, not validity — run `beacon-verify` on the bundle."
        )
    lines.append("")
    return lines


def _controls_markdown(bundle: Bundle) -> list[str]:
    controls = _policy_controls(bundle)
    if not controls:
        return []
    lines = [
        "## Policy controls",
        "",
        "| Action | Tier | Decision | Approver / reason |",
        "|---|---|---|---|",
    ]
    for r in controls:
        a = r.attributes
        who = a.get("approver_role") or a.get("reason") or "—"
        lines.append(
            f"| `{_md_cell(a.get('action', r.subject or '?'))}` | {a.get('tier', '—')} "
            f"| **{a.get('decision')}** | {_md_cell(who)} |"
        )
    lines.append("")
    return lines


def _change_key(r: Receipt) -> str | None:
    g = r.gate_decision
    if g is not None:
        return f"gate://{g.gate}/{g.inventory_id or '-'}"
    return r.subject


def _weakened(field_name: str, old: object, new: object) -> bool:
    if field_name == "decision":
        return _DECISION_RANK.get(str(new), 9) < _DECISION_RANK.get(str(old), -1)
    if field_name == "tier":
        return _TIER_RANK.get(str(new), 9) < _TIER_RANK.get(str(old), -1)
    return False


def compute_changes(old: Bundle, new: Bundle) -> list[dict[str, object]]:
    """Field-level changes between receipts that describe the same thing.

    Receipts are paired by ``subject`` (policy controls, checks) or, for gate
    decisions, by gate + inventory item, comparing the latest decision in
    each bundle. ``weakened`` marks a lower decision (deny > hold > allow) or
    a lower tier — the Knight Capital case: a policy change is itself a
    governed event.
    """
    def latest(b: Bundle) -> dict[str, Receipt]:
        out: dict[str, Receipt] = {}
        for r in sorted(b.receipts, key=lambda x: x.ts_utc):
            k = _change_key(r)
            if k is not None:
                out[k] = r
        return out

    old_by, new_by = latest(old), latest(new)
    changes: list[dict[str, object]] = []
    for key in sorted(set(old_by) & set(new_by)):
        o, n = old_by[key], new_by[key]
        if o.id == n.id:
            continue
        oa = dict(o.attributes)
        na = dict(n.attributes)
        og, ng = o.gate_decision, n.gate_decision
        if og is not None and ng is not None:
            oa["result"], na["result"] = og.result, ng.result
        for f in _CHANGE_FIELDS:
            if oa.get(f) != na.get(f):
                changes.append(
                    {
                        "subject": key,
                        "field": f,
                        "old": None if oa.get(f) is None else str(oa.get(f)),
                        "new": None if na.get(f) is None else str(na.get(f)),
                        "weakened": _weakened(f, oa.get(f), na.get(f)),
                    }
                )
    return changes


# ──────────────────────────────────────────────────────────────────────
# `lantern read`
# ──────────────────────────────────────────────────────────────────────


def render_bundle(bundle: Bundle, fmt: RenderFormat, role: Role | None = None) -> str:
    """Render a bundle in the requested format."""
    if fmt == "json":
        return _bundle_to_json(bundle)
    if fmt == "markdown":
        return _bundle_to_markdown(bundle, role=role)
    return _bundle_to_text(bundle, role=role)


def _bundle_to_json(bundle: Bundle) -> str:
    payload: dict[str, object] = {
        "source": str(bundle.source),
        "receipt_count": len(bundle),
        "signed_count": bundle.signed_count,
        "event_types": bundle.event_types,
        "evidence_types": bundle.evidence_type_counts,
        "receipt_ids": sorted(bundle.id_set),
        "gate_decisions": [_gate_dict(g) for g in bundle.gate_decisions],
    }
    beacon = _beacon_dict(bundle)
    if beacon is not None:
        payload["beacon_bundle"] = beacon
    return json.dumps(payload, indent=2, sort_keys=True)


def _bundle_to_markdown(bundle: Bundle, role: Role | None) -> str:
    lines: list[str] = []
    lines.append(f"# Bundle: `{bundle.source.name}`")
    lines.append("")
    lines.append("_AIGovOps Lantern — Beacon signs. Lantern reads._")
    lines.append("")
    if role:
        lines.append(f"> **{role.title()} view.** {_ROLE_TONES[role]}")
        lines.append("")
    lines.append(f"- **Receipts:** {len(bundle)}")
    lines.append(f"- **Signed:** {bundle.signed_count} of {len(bundle)}")
    lines.append(f"- **Distinct event types:** {len(bundle.event_types)}")
    lines.append(f"- **Distinct evidence types:** {len(bundle.evidence_type_counts)}")
    lines.append("")
    lines.append("## Event types")
    lines.append("")
    lines.append("| Event | Count |")
    lines.append("|---|---:|")
    for ev, count in sorted(bundle.event_types.items(), key=lambda kv: -kv[1]):
        lines.append(f"| `{ev}` | {count} |")
    if bundle.evidence_type_counts:
        lines.append("")
        lines.append("## Evidence types")
        lines.append("")
        lines.append("| Type | Count |")
        lines.append("|---|---:|")
        for et, count in sorted(bundle.evidence_type_counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"| `{et}` | {count} |")
    lines.append("")
    lines.extend(_beacon_markdown(bundle))
    lines.extend(_gates_markdown(bundle, role))
    lines.extend(_controls_markdown(bundle))
    if bundle.signed_count == 0:
        lines.append("")
        lines.append("> ⚠️ **No receipts in this bundle carry a signature envelope.**")
        lines.append(
            "> Lantern reads but does not verify signatures. Run `beacon verify` "
            "to confirm cryptographic integrity before relying on this bundle."
        )
    lines.append("")
    return "\n".join(lines)


def _bundle_to_text(bundle: Bundle, role: Role | None) -> str:
    console = Console(record=True, force_terminal=True, width=100)

    header = f"[bold]Bundle:[/bold] {bundle.source.name}"
    subtitle = "Beacon signs. Lantern reads."
    console.print(Panel(f"{header}\n[dim]{subtitle}[/dim]", border_style="cyan"))

    if role:
        console.print(f"[yellow]{role.title()} view —[/yellow] {_ROLE_TONES[role]}")
        console.print()

    summary = Table(show_header=False, box=None, padding=(0, 1))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Receipts", str(len(bundle)))
    summary.add_row("Signed", f"{bundle.signed_count} of {len(bundle)}")
    summary.add_row("Distinct event types", str(len(bundle.event_types)))
    summary.add_row("Distinct evidence types", str(len(bundle.evidence_type_counts)))
    console.print(summary)
    console.print()

    if bundle.event_types:
        ev_table = Table(title="Event types", show_header=True, header_style="bold cyan")
        ev_table.add_column("Event")
        ev_table.add_column("Count", justify="right")
        for ev, count in sorted(bundle.event_types.items(), key=lambda kv: -kv[1]):
            ev_table.add_row(ev, str(count))
        console.print(ev_table)
        console.print()

    if bundle.evidence_type_counts:
        et_table = Table(title="Evidence types", show_header=True, header_style="bold cyan")
        et_table.add_column("Type")
        et_table.add_column("Count", justify="right")
        for et, count in sorted(bundle.evidence_type_counts.items(), key=lambda kv: -kv[1]):
            et_table.add_row(et, str(count))
        console.print(et_table)
        console.print()

    _text_sections(console, bundle)

    if bundle.signed_count == 0:
        console.print(
            "[yellow]⚠ No receipts in this bundle carry a signature envelope.[/yellow]"
        )
        console.print(
            "[dim]Lantern reads but does not verify signatures. "
            "Run `beacon verify` for cryptographic assurance.[/dim]"
        )

    return console.export_text()


def _text_sections(console: Console, bundle: Bundle) -> None:
    b = bundle.beacon
    if b is not None:
        sha = {True: "matches", False: "[red]MISMATCH[/red]", None: "absent"}[
            b.manifest_sha256_ok
        ]
        console.print(
            f"[bold]Beacon audit bundle[/bold] v{b.beacon_version or '?'} · "
            f"{b.signing_algorithm or '?'} · keys {', '.join(b.public_key_fingerprints) or '-'} · "
            f"manifest.sha256 {sha} · gate_decisions.json rows {b.gate_decision_rows}"
        )
        for problem in b.problems:
            console.print(f"[yellow]⚠ {problem}[/yellow]")
        console.print()
    gates = bundle.gate_decisions
    if gates:
        t = Table(title="Gate decisions", show_header=True, header_style="bold cyan")
        for col in ("Receipt", "Gate", "Tier target", "Result", "Reasons"):
            t.add_column(col)
        for g in gates:
            style = "green" if g.passed else "red"
            t.add_row(
                g.receipt_id,
                g.gate,
                g.tier_target or "-",
                f"[{style}]{g.result}[/{style}]",
                "; ".join(g.reasons) or "-",
            )
        console.print(t)
        console.print()
    controls = _policy_controls(bundle)
    if controls:
        t = Table(title="Policy controls", show_header=True, header_style="bold cyan")
        for col in ("Action", "Tier", "Decision", "Approver / reason"):
            t.add_column(col)
        for r in controls:
            a = r.attributes
            t.add_row(
                str(a.get("action", r.subject or "?")),
                str(a.get("tier", "-")),
                str(a.get("decision")),
                str(a.get("approver_role") or a.get("reason") or "-"),
            )
        console.print(t)
        console.print()


# ──────────────────────────────────────────────────────────────────────
# `lantern diff`
# ──────────────────────────────────────────────────────────────────────


def render_diff(
    old: Bundle, new: Bundle, fmt: RenderFormat, role: Role | None = None
) -> str:
    """Compare two bundles and render a role-targeted narrative."""
    added_ids = sorted(new.id_set - old.id_set)
    removed_ids = sorted(old.id_set - new.id_set)
    kept_count = len(new.id_set & old.id_set)

    old_events = old.event_types
    new_events = new.event_types
    event_keys = sorted(set(old_events) | set(new_events))
    event_deltas = [
        (ev, old_events.get(ev, 0), new_events.get(ev, 0))
        for ev in event_keys
        if old_events.get(ev, 0) != new_events.get(ev, 0)
    ]

    changes = compute_changes(old, new)

    if fmt == "json":
        return json.dumps(
            {
                "changes": changes,
                "old": str(old.source),
                "new": str(new.source),
                "added_ids": added_ids,
                "removed_ids": removed_ids,
                "kept_count": kept_count,
                "event_deltas": [
                    {"event": ev, "old": o, "new": n} for ev, o, n in event_deltas
                ],
            },
            indent=2,
            sort_keys=True,
        )

    narrative = _diff_narrative(
        old=old,
        new=new,
        added_ids=added_ids,
        removed_ids=removed_ids,
        kept_count=kept_count,
        event_deltas=event_deltas,
        role=role,
        changes=changes,
    )

    if fmt == "markdown":
        return narrative
    # text uses Rich for color
    console = Console(record=True, force_terminal=True, width=100)
    console.print(narrative)
    return console.export_text()


def _diff_narrative(
    *,
    old: Bundle,
    new: Bundle,
    added_ids: list[str],
    removed_ids: list[str],
    kept_count: int,
    event_deltas: list[tuple[str, int, int]],
    role: Role | None,
    changes: list[dict[str, object]] | None = None,
) -> str:
    lines: list[str] = []
    lines.append(f"# Diff: `{old.source.name}` → `{new.source.name}`")
    lines.append("")
    if role:
        lines.append(f"> **{role.title()} view.** {_ROLE_TONES[role]}")
        lines.append("")
    lines.append(f"- Added: **{len(added_ids)}**")
    lines.append(f"- Removed: **{len(removed_ids)}**")
    lines.append(f"- Carried over: **{kept_count}**")
    lines.append(f"- Old total: {len(old)} · New total: {len(new)}")
    lines.append("")

    if event_deltas:
        lines.append("## Event type changes")
        lines.append("")
        lines.append("| Event | Was | Now | Δ |")
        lines.append("|---|---:|---:|---:|")
        for ev, o, n in event_deltas:
            delta = n - o
            sign = "+" if delta > 0 else ""
            lines.append(f"| `{ev}` | {o} | {n} | {sign}{delta} |")
        lines.append("")
    else:
        lines.append("_No change in the distribution of event types._")
        lines.append("")

    lines.extend(_changes_markdown(changes or [], role))

    if role == "engineer" and event_deltas:
        lines.append("### What an engineer should check")
        lines.append("")
        new_fail = next(
            (n for ev, _o, n in event_deltas if ev == "gate.failed" and n > 0), 0
        )
        if new_fail:
            lines.append(
                f"- {new_fail} `gate.failed` receipt(s) appear in the new bundle. "
                "Look at the gate name and inspect the policy file before re-running."
            )
        new_signed = next(
            (n - o for ev, o, n in event_deltas if ev == "bundle.signed"), 0
        )
        if new_signed > 0:
            lines.append(
                f"- {new_signed} additional `bundle.signed` event(s) — pipeline produced new "
                "signed artifacts; confirm they correspond to expected releases."
            )

    if role == "compliance" and added_ids:
        lines.append("### What compliance should review")
        lines.append("")
        new_evidence_types = (
            set(new.evidence_type_counts) - set(old.evidence_type_counts)
        )
        if new_evidence_types:
            lines.append(
                "- New evidence types introduced: "
                + ", ".join(f"`{t}`" for t in sorted(new_evidence_types))
            )
        lines.append(
            f"- {len(added_ids)} new receipt(s) — confirm each maps to a UCID via the "
            "implementing-controls crosswalk."
        )

    if role == "auditor":
        unsigned_new = sum(1 for r in new.receipts if r.id in added_ids and not r.is_signed)
        if unsigned_new:
            lines.append("### What an auditor should flag")
            lines.append("")
            lines.append(
                f"- {unsigned_new} of the {len(added_ids)} newly-added receipt(s) "
                "have no signature envelope. Lantern does not verify signatures — "
                "run `beacon verify` to confirm chain of custody."
            )

    if added_ids:
        lines.append("")
        lines.append("## Added receipt IDs")
        lines.append("")
        for rid in added_ids[:20]:
            lines.append(f"- `{rid}`")
        if len(added_ids) > 20:
            lines.append(f"- … and {len(added_ids) - 20} more")
    if removed_ids:
        lines.append("")
        lines.append("## Removed receipt IDs")
        lines.append("")
        for rid in removed_ids[:20]:
            lines.append(f"- `{rid}`")
        if len(removed_ids) > 20:
            lines.append(f"- … and {len(removed_ids) - 20} more")

    return "\n".join(lines)


def _changes_markdown(changes: list[dict[str, object]], role: Role | None) -> list[str]:
    if not changes:
        return []
    lines = [
        "## What changed",
        "",
        "| Subject | Field | Was | Now |",
        "|---|---|---|---|",
    ]
    for c in changes:
        flag = " ⚠️ weakened" if c["weakened"] else ""
        lines.append(
            f"| `{c['subject']}` | {c['field']} | {c['old'] or '—'} | **{c['new'] or '—'}**{flag} |"
        )
    lines.append("")
    weakened = sorted({str(c["subject"]) for c in changes if c["weakened"]})
    failing = sorted(
        {
            str(c["subject"])
            for c in changes
            if c["field"] == "result" and str(c["new"]).upper() == "FAIL"
        }
    )
    if role == "engineer" and (weakened or failing):
        lines.append("### What an engineer should check")
        lines.append("")
        for subj in weakened:
            lines.append(
                f"- `{subj}` was **weakened**. A policy change is itself a governed event: "
                "the policy gate should refuse the merge until a reviewer has seen this diff."
            )
        for subj in failing:
            lines.append(f"- `{subj}` now **fails** its gate. Read the reasons before re-running.")
        lines.append("")
    elif weakened:
        lines.append(
            f"> ⚠️ {len(weakened)} rule(s) weakened: "
            + ", ".join(f"`{x}`" for x in weakened)
        )
        lines.append("")
    return lines


# ──────────────────────────────────────────────────────────────────────
# `lantern explain`
# ──────────────────────────────────────────────────────────────────────


def render_ucid(u: Ucid, fmt: RenderFormat) -> str:
    if fmt == "json":
        return json.dumps(
            {
                "id": u.id,
                "title": u.title,
                "status": u.status,
                "nist_ai_rmf": list(u.nist_ai_rmf),
                "eu_ai_act_articles": list(u.eu_ai_act_articles),
                "eu_ai_act_annex_iv": list(u.eu_ai_act_annex_iv),
                "iso_42001": list(u.iso_42001),
                "implementing_controls": list(u.implementing_controls),
            },
            indent=2,
            sort_keys=True,
        )

    lines: list[str] = []
    lines.append(f"# {u.id} — {u.title}")
    lines.append("")
    lines.append(f"**Status:** `{u.status}`")
    lines.append("")
    if u.nist_ai_rmf:
        lines.append("**NIST AI RMF:** " + ", ".join(f"`{x}`" for x in u.nist_ai_rmf))
    if u.eu_ai_act_articles or u.eu_ai_act_annex_iv:
        bits: list[str] = []
        if u.eu_ai_act_articles:
            bits.append("Articles " + ", ".join(u.eu_ai_act_articles))
        if u.eu_ai_act_annex_iv:
            bits.append("Annex IV " + ", ".join(u.eu_ai_act_annex_iv))
        lines.append("**EU AI Act:** " + " · ".join(bits))
    if u.iso_42001:
        lines.append("**ISO/IEC 42001:** " + ", ".join(f"`{x}`" for x in u.iso_42001))
    if u.implementing_controls:
        lines.append(
            "**Implementing controls:** " + ", ".join(f"`{x}`" for x in u.implementing_controls)
        )
    lines.append("")
    lines.append("> Source of truth: ")
    lines.append(
        "> https://github.com/bobrapp/umbrella-govops/blob/main/UCID-REGISTRY.md"
    )

    md = "\n".join(lines)
    if fmt == "markdown":
        return md
    # text — print via Rich for nice styling
    console = Console(record=True, force_terminal=True, width=100)
    console.print(Panel(md, border_style="cyan", title=u.id))
    return console.export_text()


def receipt_oneliner(r: Receipt) -> str:
    """A single line summary for log-style output."""
    sig = "✓" if r.is_signed else " "
    return f"[{sig}] {r.ts_utc}  {r.event_type:<32} {r.subject or '-'}"
