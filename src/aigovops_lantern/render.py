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

from .bundle import Bundle, Receipt
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
    payload = {
        "source": str(bundle.source),
        "receipt_count": len(bundle),
        "signed_count": bundle.signed_count,
        "event_types": bundle.event_types,
        "evidence_types": bundle.evidence_type_counts,
        "receipt_ids": sorted(bundle.id_set),
    }
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

    if bundle.signed_count == 0:
        console.print(
            "[yellow]⚠ No receipts in this bundle carry a signature envelope.[/yellow]"
        )
        console.print(
            "[dim]Lantern reads but does not verify signatures. "
            "Run `beacon verify` for cryptographic assurance.[/dim]"
        )

    return console.export_text()


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

    if fmt == "json":
        return json.dumps(
            {
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
