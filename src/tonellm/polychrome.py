"""Translate a ToneDescriptor into a Polychrome DSP .pdpreset XML file.

Pure and deterministic. Loads templates/base.pdpreset, overrides only the
attributes implied by the descriptor, writes the result. Anything not
mentioned in the descriptor is inherited from the base template, which
keeps us forward-compatible with future Polychrome versions.

Plugin-specific mappings (cab slots, delay subdivisions, reverb models) are
loaded from a private config file outside the repository.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from importlib.resources import files
from pathlib import Path

from .descriptor import (
    AmpChannel,
    BoostPedal,
    CabArchetype,
    DelayRole,
    ReverbType,
    ToneDescriptor,
)
from .private_assets import resolve_private_path

DEFAULT_MAPPINGS_PATH = Path.home() / ".config" / "tonellm" / "mappings.json"


# Per-channel knob attribute prefixes in the XML.
# acoustic=AC, clean=CA, edge=CB, gain=GA
CHANNEL_PREFIX: dict[AmpChannel, str] = {
    AmpChannel.acoustic: "AC",
    AmpChannel.clean: "CA",
    AmpChannel.edge: "CB",
    AmpChannel.gain: "GA",
}


def _load_mappings() -> dict:
    """Load cab/amp/delay/reverb mappings from a private config file.

    Resolution order:
    1. TONELLM_MAPPINGS env var (path)
    2. ~/.config/tonellm/mappings.json

    The public repo intentionally does not ship these mappings, since the
    best-guess slot numbers are hard-won tone knowledge.
    """
    mappings_path = resolve_private_path(
        env_var="TONELLM_MAPPINGS",
        default=DEFAULT_MAPPINGS_PATH,
        label="mappings",
    )
    return json.loads(mappings_path.read_text(encoding="utf-8"))


# Load private mappings once at module import time. The translator is
# deterministic; reloading on every call is unnecessary overhead.
_MAPPINGS = _load_mappings()

CAB_SLOT_MAP: dict[CabArchetype, int] = {
    CabArchetype[name]: value for name, value in _MAPPINGS["cab_slot_map"].items()
}

AMP_CHANNEL_INDEX: dict[AmpChannel, int] = {
    AmpChannel[name]: value for name, value in _MAPPINGS["amp_channel_index"].items()
}


def _f(v: float) -> str:
    """Polychrome stores floats as raw decimals - match that style."""
    return f"{v:.10f}"


def _delay_time_for_role(role: DelayRole) -> float:
    return _MAPPINGS["delay_time_for_role"][role.value]


def _reverb_model_for_type(rt: ReverbType) -> int:
    return _MAPPINGS["reverb_model_for_type"][rt.value]


def _apply_boost(root: ET.Element, d: ToneDescriptor) -> None:
    if d.boost_pedal == BoostPedal.off:
        root.set("HPressPower", "0")
        return
    root.set("HPressPower", "1")
    root.set("HPressBoost", _f(d.boost_drive))
    root.set("HPressLevel", _f(d.boost_level))
    root.set("HPressCompress", _f(0.5))
    # Boost pedal flavor influences warmth/tight/bright character.
    warmth = {
        BoostPedal.screamer: 0.45,
        BoostPedal.klon: 0.55,
        BoostPedal.rat: 0.7,
        BoostPedal.off: 0.5,
    }[d.boost_pedal]
    root.set("HPressWarmth", _f(warmth))
    root.set("HPressTight", "1" if d.boost_tight else "0")
    root.set("HPressBright", "1" if d.boost_bright else "0")


def _apply_amp(root: ET.Element, d: ToneDescriptor) -> None:
    root.set("AmpSel", str(AMP_CHANNEL_INDEX[d.amp_channel]))
    root.set("CurrentAmpPage", str(AMP_CHANNEL_INDEX[d.amp_channel]))
    p = CHANNEL_PREFIX[d.amp_channel]
    root.set(f"{p}Gain", _f(d.gain_amount))
    root.set(f"{p}Bass", _f(d.bass))
    root.set(f"{p}Treble", _f(d.treble))
    root.set(f"{p}Master", _f(d.master))
    # Edge channel uses CBBoost (toggle) instead of mid; others have Mid+Presence.
    if d.amp_channel == AmpChannel.edge:
        root.set("CBBoost", "1" if d.gain_amount > 0.6 else "0")
    else:
        root.set(f"{p}Mid", _f(d.mid))
        root.set(f"{p}Presence", _f(d.presence))


def _apply_cab(root: ET.Element, d: ToneDescriptor) -> None:
    slot = CAB_SLOT_MAP[d.cab_archetype]
    # Set slot for the active channel; leave the others alone.
    if d.amp_channel == AmpChannel.gain:
        root.set("GainSpk", str(slot))
    elif d.amp_channel == AmpChannel.edge:
        root.set("EdgeSpk", str(slot))
    elif d.amp_channel == AmpChannel.clean:
        root.set("CleanSpk", str(slot))
    root.set("SpkLowCut", _f(d.cab_low_cut))
    root.set("SpkHiCut", _f(d.cab_hi_cut))
    root.set("SpkAir", _f(d.cab_air))
    root.set("SpkResonance", _f(d.cab_resonance))
    root.set("SpeakersPower", "1")


def _apply_time_fx(root: ET.Element, d: ToneDescriptor) -> None:
    if d.delay_role == DelayRole.off or d.delay_mix < 0.01:
        root.set("DelPower", "0")
    else:
        root.set("DelPower", "1")
        root.set("DelSync", "1")
        root.set("DelTime", _f(_delay_time_for_role(d.delay_role)))
        root.set("DelFeedback", _f(d.delay_feedback))
        root.set("DelMix", _f(d.delay_mix))

    if d.reverb_type == ReverbType.off or d.reverb_mix < 0.01:
        root.set("RevPower", "0")
    else:
        root.set("RevPower", "1")
        root.set("RevModel", str(_reverb_model_for_type(d.reverb_type)))
        root.set("RevTime", _f(d.reverb_decay))
        root.set("RevMix", _f(d.reverb_mix))
        # Sensible defaults that prevent low-end wash and over-bright tails.
        root.set("RevLowCut", _f(0.85))
        root.set("RevHiCut", _f(0.7))
        root.set("RevPreDelay", _f(0.3))


def _apply_modulation_and_dynamics(root: ET.Element, d: ToneDescriptor) -> None:
    if d.chorus_amount > 0.01:
        root.set("ChorusPower", "1")
        root.set("ChorusAmount", _f(d.chorus_amount))
    else:
        root.set("ChorusPower", "0")

    if d.compression_amount > 0.01:
        root.set("CompPower", "1")
        root.set("CompAmount", _f(d.compression_amount))
    else:
        root.set("CompPower", "0")


def _disable_unused_pedals(root: ET.Element) -> None:
    """Force unused saturation/effect pedals off so we never get phantom stacking."""
    for power_attr in ("ShrPower", "RiffPower", "VibPower", "AttPower", "SynthOctPower"):
        root.set(power_attr, "0")


def _load_template() -> ET.ElementTree:
    tpl_path = files("tonellm.templates").joinpath("base.pdpreset")
    with tpl_path.open("rb") as f:
        return ET.parse(f)


def descriptor_to_preset(d: ToneDescriptor, preset_name: str) -> ET.ElementTree:
    """Apply a descriptor to the base template; return an ElementTree ready to write."""
    tree = _load_template()
    root = tree.getroot()
    root.set("presetName", preset_name)

    root.set("GlobalInput", _f(0.5))
    root.set("GlobalOutput", _f(0.5))
    root.set("Gate", _f(d.gate_threshold))
    root.set("Widener", "1" if d.widener_on else "0")

    _apply_amp(root, d)
    _apply_cab(root, d)
    _apply_boost(root, d)
    _apply_time_fx(root, d)
    _apply_modulation_and_dynamics(root, d)
    _disable_unused_pedals(root)

    return tree


def write_preset(d: ToneDescriptor, out_path: Path, preset_name: str | None = None) -> Path:
    """Translate descriptor and write a .pdpreset file. Returns the path written."""
    out_path = Path(out_path).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    name = preset_name or out_path.stem
    tree = descriptor_to_preset(d, name)
    tree.write(out_path, encoding="UTF-8", xml_declaration=True)
    return out_path
