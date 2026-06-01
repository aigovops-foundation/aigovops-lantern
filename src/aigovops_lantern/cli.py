"""``lantern`` — command-line entry point.

Three top-level commands, each read-only:

  lantern read    BUNDLE              render a bundle for humans
  lantern diff    OLD NEW             compare two bundles
  lantern explain UCID                look up a UCID in the registry

Run ``lantern --help`` for the full surface.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from . import __version__
from .bundle import BundleError, load
from .render import RenderFormat, Role, render_bundle, render_diff, render_ucid
from .ucid import UcidError, load_registry, lookup

app = typer.Typer(
    name="lantern",
    help=(
        "AIGovOps Lantern™ — Beacon signs. Lantern reads.\n\n"
        "Read AIGovOps Beacon evidence bundles and render them for the humans who "
        "have to act on them. Local-first. No telemetry. Apache-2.0."
    ),
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)

_stderr = Console(stderr=True)


class FormatChoice(StrEnum):
    text = "text"
    markdown = "markdown"
    json = "json"


class RoleChoice(StrEnum):
    engineer = "engineer"
    compliance = "compliance"
    auditor = "auditor"
    regulator = "regulator"


def _version_callback(show: bool) -> None:
    if show:
        typer.echo(f"aigovops-lantern {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
) -> None:
    """Root callback exists to register --version."""


@app.command("read")
def cmd_read(
    bundle_path: Annotated[
        Path,
        typer.Argument(
            help="Path to a Beacon bundle (.ndjson, .jsonl, .json) or directory containing one.",
            exists=True,
            file_okay=True,
            dir_okay=True,
            readable=True,
        ),
    ],
    fmt: Annotated[
        FormatChoice,
        typer.Option("--format", "-f", help="Output format."),
    ] = FormatChoice.text,
    role: Annotated[
        RoleChoice | None,
        typer.Option("--role", "-r", help="Role lens for the rendered output."),
    ] = None,
) -> None:
    """Render a Beacon-signed evidence bundle for humans."""
    try:
        bundle = load(bundle_path)
    except BundleError as exc:
        _stderr.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    output = render_bundle(
        bundle,
        fmt=_as_format(fmt),
        role=_as_role(role),
    )
    typer.echo(output)


@app.command("diff")
def cmd_diff(
    old: Annotated[
        Path,
        typer.Argument(help="Older bundle.", exists=True, readable=True),
    ],
    new: Annotated[
        Path,
        typer.Argument(help="Newer bundle.", exists=True, readable=True),
    ],
    fmt: Annotated[
        FormatChoice,
        typer.Option("--format", "-f", help="Output format."),
    ] = FormatChoice.text,
    role: Annotated[
        RoleChoice | None,
        typer.Option("--role", "-r", help="Role lens for the rendered diff."),
    ] = None,
) -> None:
    """Compare two bundles and explain what changed."""
    try:
        bundle_old = load(old)
        bundle_new = load(new)
    except BundleError as exc:
        _stderr.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    output = render_diff(
        bundle_old,
        bundle_new,
        fmt=_as_format(fmt),
        role=_as_role(role),
    )
    typer.echo(output)


@app.command("explain")
def cmd_explain(
    ucid_id: Annotated[
        str,
        typer.Argument(help="A UCID identifier, e.g. UCID-DATA-BIAS-001."),
    ],
    registry: Annotated[
        Path | None,
        typer.Option(
            "--registry",
            help=(
                "Path to a local copy of unified-control-id.yaml. "
                "If omitted, uses Lantern's small embedded fallback."
            ),
            exists=True,
            readable=True,
        ),
    ] = None,
    fmt: Annotated[
        FormatChoice,
        typer.Option("--format", "-f", help="Output format."),
    ] = FormatChoice.text,
) -> None:
    """Look up a UCID and render its citations in plain language."""
    try:
        reg = load_registry(registry)
        u = lookup(ucid_id, registry=reg)
    except UcidError as exc:
        _stderr.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    typer.echo(render_ucid(u, fmt=_as_format(fmt)))


def _as_format(fmt: FormatChoice) -> RenderFormat:
    return fmt.value


def _as_role(role: RoleChoice | None) -> Role | None:
    return role.value if role else None


def main() -> None:  # pragma: no cover - thin entrypoint
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
