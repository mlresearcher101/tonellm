"""ToneDescriptor: high-level tonal intent emitted by the LLM.

The LLM never writes plugin XML directly. It produces this object,
and a deterministic translator maps it to .pdpreset attributes.
This isolates LLM weirdness from plugin correctness.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AmpChannel(str, Enum):
    acoustic = "acoustic"
    clean = "clean"
    edge = "edge"
    gain = "gain"


class Role(str, Enum):
    rhythm = "rhythm"
    lead = "lead"
    clean = "clean"
    arpeggio = "arpeggio"


class CabArchetype(str, Enum):
    # Mapped to Polychrome internal cab slots in polychrome.py CAB_SLOT_MAP.
    # User will audition slots and refine the mapping over time.
    v30_4x12 = "v30_4x12"
    greenback_4x12 = "greenback_4x12"
    g12_65_4x12 = "g12_65_4x12"
    g12h_4x12 = "g12h_4x12"
    fender_2x12 = "fender_2x12"
    tweed_1x12 = "tweed_1x12"


class BoostPedal(str, Enum):
    off = "off"
    screamer = "screamer"   # TS-style mid-hump, tightens lows
    klon = "klon"           # transparent boost
    rat = "rat"             # darker, fuzzier


class DelayRole(str, Enum):
    off = "off"
    slap = "slap"               # short, ~80-150ms, single repeat
    quarter = "quarter"
    dotted_eighth = "dotted_eighth"  # The Edge / modern lead
    ambient = "ambient"         # long, washy


class ReverbType(str, Enum):
    off = "off"
    plate = "plate"
    room = "room"
    hall = "hall"
    space = "space"             # ambient/shimmer


class ToneDescriptor(BaseModel):
    """Structured tonal intent. Every numeric value is normalized 0.0-1.0."""

    artist: str
    song: str
    era: str = Field(description="e.g. '1987 Hysteria', '1995 grunge', '2015 djent'")
    role: Role

    amp_channel: AmpChannel
    gain_amount: float = Field(ge=0.0, le=1.0)
    bass: float = Field(ge=0.0, le=1.0)
    mid: float = Field(ge=0.0, le=1.0)
    treble: float = Field(ge=0.0, le=1.0)
    presence: float = Field(ge=0.0, le=1.0)
    master: float = Field(ge=0.0, le=1.0)

    cab_archetype: CabArchetype
    cab_low_cut: float = Field(ge=0.0, le=1.0, description="Higher = tighter low end")
    cab_hi_cut: float = Field(ge=0.0, le=1.0, description="Higher = darker top end")
    cab_air: float = Field(ge=0.0, le=1.0)
    cab_resonance: float = Field(ge=0.0, le=1.0)

    boost_pedal: BoostPedal = BoostPedal.off
    boost_drive: float = Field(0.0, ge=0.0, le=1.0)
    boost_tone: float = Field(0.5, ge=0.0, le=1.0)
    boost_level: float = Field(0.5, ge=0.0, le=1.0)
    boost_tight: bool = False
    boost_bright: bool = False

    compression_amount: float = Field(0.0, ge=0.0, le=1.0)
    chorus_amount: float = Field(0.0, ge=0.0, le=1.0, description="0 = off")

    delay_role: DelayRole = DelayRole.off
    delay_feedback: float = Field(0.2, ge=0.0, le=1.0)
    delay_mix: float = Field(0.0, ge=0.0, le=1.0)

    reverb_type: ReverbType = ReverbType.off
    reverb_decay: float = Field(0.4, ge=0.0, le=1.0)
    reverb_mix: float = Field(0.0, ge=0.0, le=1.0)

    gate_threshold: float = Field(0.55, ge=0.0, le=1.0)
    widener_on: bool = Field(
        False,
        description="Default False: real DAW double-tracking sounds better than fake stereo",
    )

    confidence: float = Field(
        ge=0.0, le=1.0, description="LLM's self-rated confidence in this match"
    )
    production_notes: str = Field(
        description="Plain-English explanation: why these settings, what to do in the DAW"
    )
    daw_recommendations: Optional[str] = Field(
        default=None,
        description="Optional DAW-side moves: doubling, bus comp, post EQ, plate send",
    )
