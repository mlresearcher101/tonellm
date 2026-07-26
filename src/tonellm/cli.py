"""Typer CLI: ask for a tone, get a .pdpreset on disk."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

from .service import run_from_descriptor, run_tone

app = typer.Typer(help="Generate Polychrome DSP presets for any artist/song via LLM.")


def _print_summary(result) -> None:
    d = result.descriptor
    typer.echo(f"\nWrote preset: {result.preset_path}")
    typer.echo(f"Wrote sidecar: {result.sidecar_path}")
    typer.echo(f"\nChannel: {d.amp_channel.value}  |  Cab: {d.cab_archetype.value}")
    typer.echo(
        f"Gain={d.gain_amount:.2f}  Bass={d.bass:.2f}  Mid={d.mid:.2f}  "
        f"Treble={d.treble:.2f}  Presence={d.presence:.2f}  Master={d.master:.2f}"
    )
    typer.echo(f"\nConfidence: {d.confidence:.2f}")
    if d.confidence < 0.6:
        typer.secho(
            "Low confidence - audition critically and adjust by ear.",
            fg=typer.colors.YELLOW,
        )
    typer.echo(f"\nProduction notes:\n{d.production_notes}")
    if d.daw_recommendations:
        typer.echo(f"\nDAW recommendations:\n{d.daw_recommendations}")


@app.command()
def tone(
    query: str = typer.Argument(..., help="e.g. 'Phil Collen Run Riot rhythm'"),
    out: Path = typer.Option(..., "-out", "-o", help="Where to write the .pdpreset"),
    guitar: Optional[str] = typer.Option(None, "-guitar", "-g", help="e.g. rg3550, strandberg-boden"),
    tuning: Optional[str] = typer.Option("E", "-tuning", "-t", help="e.g. E, DropD, DropC"),
    model: Optional[str] = typer.Option(None, "-model", "-m", help="Override OLLAMA_MODEL"),
    ref: Optional[Path] = typer.Option(
        None, "-ref", "-r",
        help="Optional reference MP3/WAV/FLAC. If provided, measured audio features are fed to the LLM as grounding.",
    ),
    section: Optional[str] = typer.Option(
        None, "-section", "-s",
        help="Optional time range of -ref to analyze, e.g. '1:30-2:10' or '90-130'. Use this on full mixes to isolate the solo.",
    ),
):
    """Generate a Polychrome preset for a target tone.

    Pass `-ref some.mp3` to additionally ground the LLM in measured audio
    features (spectral centroid, flatness, band balance, crest factor). Omit
    it for the original text-only workflow. Use `-section start-end` to
    target just the relevant region (e.g. the solo) of a longer recording.
    """
    if ref is not None:
        where = f" [{section}]" if section else ""
        typer.echo(f"Analyzing reference audio: {ref}{where}")

    typer.echo(f"Asking model for: {query}")
    try:
        result = run_tone(
            query=query,
            out=out,
            guitar=guitar,
            tuning=tuning or "E",
            model=model,
            ref=ref,
            section=section,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if result.audio_summary:
        typer.echo(result.audio_summary)
    _print_summary(result)


@app.command()
def from_descriptor(
    descriptor_file: Path = typer.Argument(..., help="Path to a .tone.json file"),
    out: Path = typer.Option(..., "-out", "-o"),
):
    """Skip the LLM: translate an existing .tone.json into a .pdpreset.

    Useful for re-translating after you've hand-edited a descriptor, or for
    porting a tone to a different plugin once more translators exist.
    """
    result = run_from_descriptor(descriptor_file, out)
    _print_summary(result)


@app.command()
def ui(
    port: int = typer.Option(8501, "-port", "-p", help="Local port for the web UI"),
):
    """Launch the local web UI in your browser."""
    import os

    # Streamlit executes ui.py as a script; ensure src/ is on PYTHONPATH.
    src_dir = Path(__file__).resolve().parents[1]
    ui_path = Path(__file__).with_name("ui.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(src_dir), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(ui_path),
        "--server.port",
        str(port),
        "--server.headless",
        "true",
    ]
    typer.echo(f"Starting UI at http://localhost:{port}")
    raise typer.Exit(subprocess.call(cmd, env=env))


if __name__ == "__main__":
    app()
