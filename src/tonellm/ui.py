"""Local Streamlit UI for Tone LLM."""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from tonellm.service import ToneResult, run_from_descriptor, run_tone

DEFAULT_PRESET_DIR = Path(
    "/Users/Shared/PolyChrome DSP/Presets/McRocklin Suite/User"
)


def _format_summary(result: ToneResult) -> str:
    d = result.descriptor
    lines = [
        f"**Preset:** `{result.preset_path}`",
        f"**Sidecar:** `{result.sidecar_path}`",
        "",
        f"**Channel:** {d.amp_channel.value}  |  **Cab:** {d.cab_archetype.value}",
        (
            f"Gain={d.gain_amount:.2f}  Bass={d.bass:.2f}  Mid={d.mid:.2f}  "
            f"Treble={d.treble:.2f}  Presence={d.presence:.2f}  Master={d.master:.2f}"
        ),
        "",
        f"**Confidence:** {d.confidence:.2f}",
        "",
        "**Production notes**",
        d.production_notes,
    ]
    if d.daw_recommendations:
        lines.extend(["", "**DAW recommendations**", d.daw_recommendations])
    return "\n\n".join(lines)


def main() -> None:
    st.set_page_config(page_title="Tone LLM", page_icon="🎸", layout="centered")
    st.title("Tone LLM")
    st.caption("Generate McRocklin Polychrome DSP presets from a tone description.")

    tab_tone, tab_retranslate = st.tabs(["Generate tone", "Re-translate sidecar"])

    with tab_tone:
        query = st.text_input(
            "Tone request",
            placeholder="Alex Skolnick Testament Lies lead",
            help="Artist, song, part, and style — same as the CLI query argument.",
        )
        col_g, col_t = st.columns(2)
        with col_g:
            guitar = st.text_input("Guitar (optional)", value="rg3550")
        with col_t:
            tuning = st.text_input("Tuning", value="E")

        ref_file = st.file_uploader(
            "Reference audio (optional)",
            type=["mp3", "wav", "flac", "m4a", "ogg"],
            help="Drop an MP3/WAV to ground the LLM in measured audio features.",
        )
        section = st.text_input(
            "Section (optional)",
            placeholder="3:22-3:55",
            help="Time range within the reference file. Requires reference audio.",
        )

        col_name, col_dir = st.columns(2)
        with col_name:
            preset_name = st.text_input("Preset filename", value="MyTone.pdpreset")
        with col_dir:
            out_dir = st.text_input("Output folder", value=str(DEFAULT_PRESET_DIR))

        model = st.text_input(
            "Model override (optional)",
            placeholder="Leave blank to use OLLAMA_MODEL from .env",
        )

        if st.button("Generate preset", type="primary", disabled=not query.strip()):
            out_path = Path(out_dir).expanduser() / preset_name
            out_path.parent.mkdir(parents=True, exist_ok=True)

            ref_path: Path | None = None
            temp_ref: tempfile.NamedTemporaryFile | None = None
            if ref_file is not None:
                suffix = Path(ref_file.name).suffix or ".mp3"
                temp_ref = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                temp_ref.write(ref_file.getvalue())
                temp_ref.close()
                ref_path = Path(temp_ref.name)

            try:
                with st.spinner("Generating preset..."):
                    if ref_path and section.strip():
                        st.info(f"Analyzing `{ref_file.name}` section {section.strip()}")
                    elif ref_path:
                        st.info(f"Analyzing `{ref_file.name}`")

                    result = run_tone(
                        query=query.strip(),
                        out=out_path,
                        guitar=guitar.strip() or None,
                        tuning=tuning.strip() or "E",
                        model=model.strip() or None,
                        ref=ref_path,
                        section=section.strip() or None,
                    )

                if result.audio_summary:
                    with st.expander("Audio features sent to LLM"):
                        st.text(result.audio_summary)

                st.success("Preset written.")
                st.markdown(_format_summary(result))

                preset_bytes = result.preset_path.read_bytes()
                sidecar_bytes = result.sidecar_path.read_bytes()
                dl1, dl2 = st.columns(2)
                with dl1:
                    st.download_button(
                        "Download .pdpreset",
                        preset_bytes,
                        file_name=result.preset_path.name,
                    )
                with dl2:
                    st.download_button(
                        "Download .tone.json",
                        sidecar_bytes,
                        file_name=result.sidecar_path.name,
                    )
            except Exception as exc:
                st.error(str(exc))
            finally:
                if temp_ref is not None:
                    Path(temp_ref.name).unlink(missing_ok=True)

    with tab_retranslate:
        st.caption("Edit a `.tone.json` sidecar, then re-translate without calling the LLM.")
        sidecar_upload = st.file_uploader(
            "Sidecar (.tone.json)",
            type=["json"],
            key="sidecar_upload",
        )
        rt_name = st.text_input("Output preset filename", value="Retranslated.pdpreset", key="rt_name")
        rt_dir = st.text_input("Output folder", value=str(DEFAULT_PRESET_DIR), key="rt_dir")

        if st.button("Re-translate", disabled=sidecar_upload is None):
            rt_out = Path(rt_dir).expanduser() / rt_name
            rt_out.parent.mkdir(parents=True, exist_ok=True)
            temp_json = tempfile.NamedTemporaryFile(delete=False, suffix=".tone.json")
            temp_json.write(sidecar_upload.getvalue())
            temp_json.close()
            try:
                with st.spinner("Translating..."):
                    result = run_from_descriptor(Path(temp_json.name), rt_out)
                st.success("Preset written.")
                st.markdown(_format_summary(result))
            except Exception as exc:
                st.error(str(exc))
            finally:
                Path(temp_json.name).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
