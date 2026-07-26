"""Ollama Cloud client. Sends a prompt to Deepseek-V4 (or any configured model)
with the ToneDescriptor JSON schema as a hard constraint, so the model
literally cannot return malformed JSON. I had mixed results with other models so your experience may vary.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from ollama import Client

from .descriptor import ToneDescriptor
from .private_assets import resolve_private_path

load_dotenv()


DEFAULT_SYSTEM_PROMPT_PATH = Path.home() / ".config" / "tonellm" / "prompts" / "tone_system.md"


def _extract_json(text: str) -> str:
    """Pull the first JSON object out of an LLM response.

    Hosted models often wrap JSON in ```json ... ``` fences or add prose,
    even when asked for structured output. This extractor handles all
    common cases so the validator never sees garbage.
    """
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


def _load_system_prompt() -> str:
    """Load the tone-engineering system prompt from a private source.

    Resolution order:
    1. TONELLM_SYSTEM_PROMPT env var (path or https URL)
    2. ~/.config/tonellm/prompts/tone_system.md

    Raises FileNotFoundError if none are available, since the public repo
    intentionally does not ship the prompt.
    """
    prompt_path = resolve_private_path(
        env_var="TONELLM_SYSTEM_PROMPT",
        default=DEFAULT_SYSTEM_PROMPT_PATH,
        label="system prompt",
    )
    return prompt_path.read_text(encoding="utf-8")


def _client() -> Client:
    host = os.getenv("OLLAMA_HOST", "https://ollama.com")
    api_key = os.getenv("OLLAMA_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    return Client(host=host, headers=headers)


def _build_user_prompt(
    query: str,
    guitar: str | None,
    tuning: str | None,
    audio_summary: str | None = None,
) -> str:
    parts = [f"Tone request: {query}"]
    if guitar:
        parts.append(f"Guitar: {guitar} (apply guitar-specific compensations)")
    if tuning:
        parts.append(f"Tuning: {tuning}")
    if audio_summary:
        # Audio-derived grounding: nudges the LLM toward what the recording actually sounds like.
        parts.append(audio_summary)
    parts.append(
        "Produce a ToneDescriptor JSON for McRocklin Polychrome DSP. "
        "Set widener_on=false unless explicitly needed. "
        "Disable boost/distortion pedals not required for this tone."
    )
    return "\n".join(parts)


def generate_descriptor(
    query: str,
    guitar: str | None = None,
    tuning: str | None = None,
    model: str | None = None,
    audio_summary: str | None = None,
) -> ToneDescriptor:
    """One LLM call -> validated ToneDescriptor.

    Schema-constrained output via Ollama's `format=` parameter means the
    model is forced to emit JSON conforming to ToneDescriptor's schema.
    Pydantic validates again as a safety net.
    """
    model = model or os.getenv("OLLAMA_MODEL", "kimi2.6")
    client = _client()

    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": _load_system_prompt()},
            {"role": "user", "content": _build_user_prompt(query, guitar, tuning, audio_summary)},
        ],
        format=ToneDescriptor.model_json_schema(),
        options={"temperature": 0.4},
    )

    raw = response["message"]["content"]
    extracted = _extract_json(raw)
    try:
        return ToneDescriptor.model_validate_json(extracted)
    except Exception as e:
        # Surface the raw model output so prompt iteration is debuggable.
        preview = extracted[:1000] + ("..." if len(extracted) > 1000 else "")
        raise RuntimeError(
            f"LLM response did not match ToneDescriptor schema.\n"
            f"-- raw JSON (first 1000 chars) --\n{preview}\n"
            f"-- pydantic error --\n{e}"
        ) from e
