"""Audio analysis: turn a reference MP3/WAV/FLAC into a compact set of
audio-engineering features the LLM can reason about.

We do NOT try to classify the tone here. We measure interpretable features
(brightness, flatness, band balance, crest factor, tempo) and hand them to
the existing LLM step, which already speaks this language via tone_system.md.
That keeps one source of truth for tonal reasoning.
"""
from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import librosa
import numpy as np


class AudioFeatures(TypedDict):
    duration_s: float
    tempo_bpm: float
    rms_db: float                 # average loudness (lower = quieter recording)
    crest_db: float               # peak - RMS; low crest = compressed/distorted
    spectral_centroid_hz: float   # higher = brighter
    spectral_rolloff_hz: float    # frequency below which 85% of energy lives
    spectral_flatness: float      # 0 tonal -> 1 noise-like (distortion raises it)
    zero_crossing_rate: float     # rises with distortion / high-frequency content
    low_band_db: float            # 60-250 Hz   (chug / body)
    mid_band_db: float            # 250-2000 Hz (note definition / honk)
    high_band_db: float           # 2-8 kHz     (presence / pick attack)


def _band_db(stft_mag: np.ndarray, freqs: np.ndarray, lo: float, hi: float) -> float:
    """Average magnitude in a band, expressed in dB."""
    band = stft_mag[(freqs >= lo) & (freqs < hi), :].mean()
    return float(20 * np.log10(band + 1e-9))


def parse_section(spec: str) -> tuple[float, float]:
    """Parse a 'start-end' time range. Accepts seconds ('90-130') or mm:ss ('1:30-2:10').

    Returns (start_seconds, end_seconds). Raises ValueError on malformed input
    so the CLI can fail fast with a useful message instead of decoding garbage.
    """
    def to_seconds(token: str) -> float:
        token = token.strip()
        if ":" in token:
            parts = token.split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            raise ValueError(f"Bad timestamp: {token}")
        return float(token)

    if "-" not in spec:
        raise ValueError(f"Section must be 'start-end', got: {spec!r}")
    a, b = spec.split("-", 1)
    start, end = to_seconds(a), to_seconds(b)
    if end <= start:
        raise ValueError(f"Section end ({end}s) must be after start ({start}s)")
    return start, end


def extract_features(
    path: Path,
    section: tuple[float, float] | None = None,
    default_duration_s: float = 30.0,
) -> AudioFeatures:
    """Load mono audio and compute a small feature dict.

    If `section` is given, analyze that range; otherwise analyze the first
    ~30s. 30s is plenty to characterize a guitar tone and keeps the LLM
    prompt small. librosa picks soundfile / audioread automatically, so
    MP3/WAV/FLAC all work.
    """
    if section is not None:
        offset, end = section
        duration = end - offset
    else:
        offset, duration = 0.0, default_duration_s
    y, sr = librosa.load(str(path), sr=22050, mono=True, offset=offset, duration=duration)
    if y.size == 0:
        raise ValueError(f"Could not decode any audio from {path}")

    # Compute STFT once and reuse for band energies.
    stft_mag = np.abs(librosa.stft(y, n_fft=2048))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)

    rms = float(librosa.feature.rms(y=y).mean())
    peak = float(np.max(np.abs(y)))
    centroid = float(librosa.feature.spectral_centroid(y=y, sr=sr).mean())
    rolloff = float(librosa.feature.spectral_rolloff(y=y, sr=sr).mean())
    flatness = float(librosa.feature.spectral_flatness(y=y).mean())
    zcr = float(librosa.feature.zero_crossing_rate(y).mean())
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

    return AudioFeatures(
        duration_s=float(len(y) / sr),
        tempo_bpm=float(tempo),
        rms_db=float(20 * np.log10(rms + 1e-9)),
        crest_db=float(20 * np.log10((peak + 1e-9) / (rms + 1e-9))),
        spectral_centroid_hz=centroid,
        spectral_rolloff_hz=rolloff,
        spectral_flatness=flatness,
        zero_crossing_rate=zcr,
        low_band_db=_band_db(stft_mag, freqs, 60, 250),
        mid_band_db=_band_db(stft_mag, freqs, 250, 2000),
        high_band_db=_band_db(stft_mag, freqs, 2000, 8000),
    )


def _crest_label(crest_db: float) -> str:
    """Calibrated interpretation of crest factor for guitar/music signals."""
    if crest_db < 10:
        return "squashed / heavily limited"
    if crest_db < 15:
        return "moderately compressed"
    return "transients preserved"


def summarize_for_llm(f: AudioFeatures, section_label: str | None = None) -> str:
    """Human-readable feature summary to inject into the LLM user prompt."""
    where = section_label if section_label else f"first ~{f['duration_s']:.0f}s"
    return (
        f"Measured audio features ({where} of the reference):\n"
        f"- Tempo: {f['tempo_bpm']:.0f} BPM\n"
        f"- Loudness RMS: {f['rms_db']:.1f} dBFS, crest factor {f['crest_db']:.1f} dB "
        f"({_crest_label(f['crest_db'])})\n"
        f"- Spectral centroid: {f['spectral_centroid_hz']:.0f} Hz "
        "(higher = brighter top end)\n"
        f"- Spectral rolloff (85%): {f['spectral_rolloff_hz']:.0f} Hz\n"
        f"- Spectral flatness: {f['spectral_flatness']:.3f} "
        "(higher = more noise-like / more distortion)\n"
        f"- Band energy dB: low {f['low_band_db']:.1f}, "
        f"mid {f['mid_band_db']:.1f}, high {f['high_band_db']:.1f}\n"
        f"- Zero-crossing rate: {f['zero_crossing_rate']:.3f}\n"
        "Ground the descriptor in these measurements: match brightness, "
        "gain character, and band balance you see in the numbers. "
        "If the source is a full mix (drums/bass/vocals present), down-weight "
        "low-band energy and crest factor when inferring the guitar's character."
    )
