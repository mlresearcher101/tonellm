# Tone LLM (`tonellm`)

Generate **McRocklin Polychrome DSP** `.pdpreset` files from a text description — optionally grounded by a reference recording — using an LLM plus a deterministic translator.

--

## Setup

Uses [uv](https://docs.astral.sh/uv/) (Python 3.11+ per `pyproject.toml`). Install uv if needed: `curl -LsSf https://astral.sh/uv/install.sh | sh`

```bash
uv venv -python 3.11
source .venv/bin/activate
uv pip install -e ".[ui]"   
```

Create a `.env` file in the project root. I've used Ollama here but choose your poison accordingly.

```env
OLLAMA_API_KEY=your_key_here
OLLAMA_HOST=https://ollama.com
OLLAMA_MODEL=deepseek-v4-pro
```

--

## Usage

### Web UI (recommended)

```bash
tonellm ui
```

Opens **[http://localhost:8501](http://localhost:8501)**. Enter a tone request, optionally drop a reference MP3/WAV, set a section range for solo isolation, choose an output folder, and download the preset + sidecar.

Custom port:

```bash
tonellm ui -port 8502
```

### CLI — text only

```bash
tonellm tone "George Harrison All Things Must Pass rhythm" \
    -guitar rg3550 \
    -tuning E \
    -out "/Users/Shared/PolyChrome DSP/Presets/McRocklin Suite/User/George.pdpreset"
```

### CLI — with reference audio

Add `-ref` to ground the LLM in measured audio features. Omit it and the command behaves exactly as before.

```bash
tonellm tone "Alex Skolnick Testament So Many Lies lead" \
    -guitar rg3550 -tuning E \
    -ref ./lies.mp3 \
    -out "/Users/Shared/PolyChrome DSP/Presets/McRocklin Suite/User/Skolnick_Lies.pdpreset"
```

On a **full mix** (drums, bass, vocals), use `-section` to analyze only the guitar part. Accepts seconds (`90-130`) or `mm:ss` (`3:22-3:55`):

```bash
tonellm tone "Alex Skolnick Testament So Many Lies lead" \
    -guitar rg3550 -tuning E \
    -ref ./lies.mp3 -section 3:22-3:55 \
    -out "/Users/Shared/PolyChrome DSP/Presets/McRocklin Suite/User/Skolnick_Lies.pdpreset"
```

### CLI — re-translate a sidecar (skip the LLM)

Edit a `.tone.json` sidecar by hand, then rebuild the preset without another LLM call:

```bash
tonellm from-descriptor RunRiot.tone.json \
    -out "/Users/Shared/PolyChrome DSP/Presets/McRocklin Suite/User/RunRiot_v2.pdpreset"
```

### Load in Polychrome

1. Open Polychrome DSP.
2. Hit the preset arrow → find your preset in the User folder.
3. Load and audition.

Each run also writes a **sidecar** (`RunRiot.tone.json`) next to the preset. Use it to audit what the LLM decided, tweak values, and re-translate.

--

<p align="center">
  <a href="https://www.youtube.com/watch?v=oogeqoSQgUE">
    <img src="https://img.youtube.com/vi/oogeqoSQgUE/maxresdefault.jpg" alt="Tone LLM demo" width="500">
  </a>
  <br>
  <em>Watch the demo</em>
</p>