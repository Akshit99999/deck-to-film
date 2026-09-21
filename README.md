# deck-to-film

> Turn a PowerPoint deck + website repo into a polished ~8-minute narrated explainer video with 3D animated scenes, a **live demo** of the actual website running, and professional captions.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Node 20+](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org)

## What it produces

| File | Description |
|------|-------------|
| `out/video_captioned.mp4` | Final 1920×1080 30fps H.264/AAC video with burned-in captions |
| `out/video_clean.mp4` | Same video without captions (for re-captioning or localization) |
| `out/video_subtitled.mp4` | Same as captioned but with SRT embedded as a soft subtitle track |
| `out/captions_en.srt` / `.vtt` | English captions (one file per language configured) |
| `out/contact_sheet.jpg` | One frame per 30 seconds for quick review |
| `out/script.md` | Full narration script |
| `build/plan.json` | Editable scene plan — re-render without new LLM calls |
| `build/demo/` | Raw demo recordings + demo script JSON |

## Quick start

### Prerequisites

| Tool | Install |
|------|---------|
| Python 3.11+ | [python.org](https://python.org) |
| Node.js 20+ | [nodejs.org](https://nodejs.org) |
| ffmpeg | `brew install ffmpeg` / `apt install ffmpeg` |
| LibreOffice | `brew install libreoffice` / `apt install libreoffice` |
| poppler | `brew install poppler` / `apt install poppler-utils` |
| git | pre-installed on most systems |

### Install

```bash
git clone https://github.com/Akshit99999/deck-to-film
cd deck-to-film

# Python package
pip install -e ".[dev]"

# Playwright browser (for demo capture)
playwright install chromium --with-deps

# Remotion dependencies
cd remotion && npm install && cd ..
```

### Set API keys

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # Required
export ELEVENLABS_API_KEY=...              # Optional — falls back to Edge TTS (free)
```

### Configure

```bash
cp config.example.yaml videogen.yaml
# Edit videogen.yaml — set input.pptx and input.repo at minimum
```

### Run

```bash
# Full pipeline
videogen build

# Dry run (prints cost estimate, no API calls)
videogen build --dry-run

# Individual stages
videogen plan      # PPTX + repo → build/plan.json
videogen demo      # Capture live demo footage
videogen voice     # Generate narration audio
videogen captions  # Generate SRT/VTT captions
videogen render    # Render final video
videogen preview   # Quick low-res (1280×720) preview
```

---

## Configuration reference

See `config.example.yaml` for all options. Key fields:

```yaml
input:
  pptx: ./deck/my_product.pptx     # Required
  repo: https://github.com/you/app  # Required — URL or local path
  live_url: https://myapp.com       # Optional — skip local build
  brand_colors: ["#6366f1"]         # Optional — detected from deck/repo if omitted
  target_length_secs: 480           # Default: 8 minutes
  demo_credentials:                 # Optional — for login-protected demos
    username: demo@example.com
    password: demo1234

voice:
  provider: auto         # auto | elevenlabs | edge_tts
  voice_id: Rachel       # ElevenLabs: voice name; Edge TTS: see below

captions:
  languages: [en]        # Primary is burned in; others get SRT/VTT only
  word_highlight: true   # Highlight spoken word in accent color
```

### Edge TTS voice names

If ElevenLabs is unavailable, Edge TTS is used automatically. Available voices:

| Friendly name | Edge TTS voice |
|--------------|----------------|
| Rachel | en-US-AriaNeural |
| Josh | en-US-GuyNeural |
| Bella | en-US-JennyNeural |
| Adam | en-US-DavisNeural |

---

## Hand-editing the demo script

After running `videogen plan`, open `build/plan.json`. Find `demo_flows[*].steps`:

```json
{
  "action": "click",
  "target": "role=button[name='Sign in']",
  "value": null,
  "narration_cue": "Let's sign in to the dashboard.",
  "wait_after_ms": 800
}
```

**Action types:**

| Action | `target` | `value` |
|--------|----------|---------|
| `goto` | URL path `/dashboard` | — |
| `click` | `role=button[name='X']` or CSS `#id` | — |
| `type` | `role=textbox[name='Email']` | Text to type |
| `scroll` | `body` or any selector | Pixels e.g. `"300"` |
| `hover` | any selector | — |
| `wait` | any string (ignored) | Milliseconds e.g. `"1000"` |
| `press` | Key name e.g. `"Enter"` | — |

After editing, run `videogen demo` to re-record, then `videogen render`.

---

## Hand-editing captions

Edit `out/captions_en.srt` directly:

```srt
1
00:00:02,100 --> 00:00:05,800
Welcome to Launchpad —
the fastest way to ship.

2
00:00:05,900 --> 00:00:09,200
Today I'll show you how to go
from zero to deployed in minutes.
```

Then re-run `videogen render` — the renderer reads the SRT from `out/` directly.

To regenerate captions from scratch: `videogen captions`.

---

## Multi-language captions

Add languages to `config.yaml`:

```yaml
captions:
  languages: [en, hi, pa]
```

- Translation uses Claude (requires `ANTHROPIC_API_KEY`)
- Brand names and technical terms are preserved untranslated
- Fonts: Noto Sans Devanagari (Hindi), Noto Sans Gurmukhi (Punjabi) — included in the Docker image
- Voice-over stays in English unless you configure a translated voice

---

## Branding customization

1. **Colors** — set `input.brand_colors` in config. If not set, colors are inferred from the deck/site.
2. **Fonts** — set `render.font_heading` and `render.font_body` to any Google Fonts name.
3. **Logo** — set `input.logo` to a PNG path; it appears in the title and outro scenes.
4. **Captions style** — edit `/remotion/src/components/CaptionOverlay.tsx` for full control over font, size, position, and animation.

---

## Docker

```bash
# Build
docker build -t videogen:latest .

# Run full pipeline
docker run --rm \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e ELEVENLABS_API_KEY=$ELEVENLABS_API_KEY \
  -v $(pwd)/workspace:/workspace \
  videogen:latest build --config /workspace/videogen.yaml

# Or use docker compose
docker compose run --rm videogen build --config /workspace/videogen.yaml
```

---

## Troubleshooting

**`libreoffice: command not found`**
Install LibreOffice: `brew install libreoffice` (macOS) or `apt install libreoffice` (Ubuntu).

**`pdftoppm: command not found`**
Install poppler: `brew install poppler` or `apt install poppler-utils`.

**Site won't start locally**
Set `input.live_url` in config to use a running instance. Or provide `input.demo_credentials` if login is required.

**ElevenLabs quota exceeded**
The pipeline falls back to Edge TTS automatically. Set `voice.provider: edge_tts` explicitly to skip ElevenLabs entirely.

**Whisper is slow**
Change `captions.whisper_model: tiny` for ~4× speed at slightly lower accuracy. The force-alignment step corrects product name spellings regardless.

**`playwright install` fails**
Run `playwright install chromium --with-deps` to install system dependencies, or use the Docker image which has everything pre-installed.

**Plan looks wrong**
Edit `build/plan.json` directly and run `videogen render` — no API call needed. The critic pass can be re-run manually by deleting `build/plan_meta.json` and re-running `videogen plan`.

---

## Architecture

```
videogen/          Python orchestrator
├── ingest/        PPTX parse + repo clone/analyze
├── demo/          Site runner + Playwright capture
├── planner.py     Claude → scene plan + demo script
├── voice.py       ElevenLabs / Edge TTS
├── captions.py    Whisper + force-align → SRT/VTT
├── renderer.py    Remotion orchestration
├── qa.py          Duration + audio + caption QA
└── pipeline.py    Stage runner

remotion/          Remotion + Three.js video renderer
├── src/scenes/    TitleScene, BulletsScene, StatScene,
│                  SlideShowcaseScene, LiveDemoScene,
│                  ArchitectureScene, OutroScene
└── src/components/ CaptionOverlay, DeviceFrame
```

---

## Known limitations

1. **Remotion render requires a display** — in headless CI, set `DISPLAY=:0` or use `xvfb-run`. The Docker image handles this automatically.
2. **Mobile responsive demo** — the phone-frame scene is built but `has_responsive_mobile` must be true in the plan; currently the planner only sets it when it detects responsive CSS in the repo.
3. **Music ducking** — background music is mixed in but sidechained ducking during speech is approximate (−10 dB under voice). A proper sidechain compressor would improve this.
4. **Long repos** — repos with >80 relevant source files are truncated for the LLM context window. This is intentional; the planner reads enough to understand structure and flows.

---

## Top 3 next improvements

1. **True sidechain music ducking** using ffmpeg's `sidechaincompress` filter for broadcast-quality audio.
2. **Automatic mobile demo scene** — detect `@media` queries in CSS and automatically record a second pass at 390×844 with the phone-frame scene.
3. **Remotion Lambda rendering** for 10× faster cloud renders — Remotion has first-class AWS Lambda support that would cut render time from ~10 min to ~60s.
