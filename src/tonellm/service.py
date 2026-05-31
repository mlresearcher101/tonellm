"""Shared tone-generation orchestration for CLI and UI."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .descriptor import ToneDescriptor
from .llm import generate_descriptor
from .polychrome import write_preset


@dataclass
class ToneResult:
    descriptor: ToneDescriptor
    preset_path: Path
    sidecar_path: Path
    audio_summary: Optional[str] = None


def write_sidecar(descriptor: ToneDescriptor, preset_path: Path) -> Path:
    """Save the descriptor as JSON next to the preset for audit/re-translation."""
    sidecar = preset_path.with_suffix(".tone.json")
    sidecar.write_text(descriptor.model_dump_json(indent=2), encoding="utf-8")
    return sidecar


def run_tone(
    query: str,
    out: Path,
    guitar: Optional[str] = None,
    tuning: str = "E",
    model: Optional[str] = None,
    ref: Optional[Path] = None,
    section: Optional[str] = None,
) -> ToneResult:
    """Generate a preset: optional audio grounding -> LLM -> .pdpreset + sidecar."""
    if section is not None and ref is None:
        raise ValueError("-section requires a reference audio file")

    audio_summary: Optional[str] = None
    if ref is not None:
        from .audio import extract_features, parse_section, summarize_for_llm

        sec = parse_section(section) if section else None
        where = f"section {section}" if section else None
        audio_summary = summarize_for_llm(
            extract_features(ref, section=sec), section_label=where
        )

    descriptor = generate_descriptor(
        query=query,
        guitar=guitar,
        tuning=tuning,
        model=model,
        audio_summary=audio_summary,
    )
    preset_path = write_preset(descriptor, out)
    sidecar_path = write_sidecar(descriptor, preset_path)
    return ToneResult(descriptor, preset_path, sidecar_path, audio_summary)


def run_from_descriptor(descriptor_file: Path, out: Path) -> ToneResult:
    """Skip the LLM: translate an existing .tone.json into a .pdpreset."""
    data = json.loads(descriptor_file.read_text(encoding="utf-8"))
    descriptor = ToneDescriptor.model_validate(data)
    preset_path = write_preset(descriptor, out)
    sidecar_path = write_sidecar(descriptor, preset_path)
    return ToneResult(descriptor, preset_path, sidecar_path)
