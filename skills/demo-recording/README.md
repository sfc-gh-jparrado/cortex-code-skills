# Demo Recording Skill

Generate polished demo recording assets — talk tracks, timed recording scripts, and AI voice-over audio — for any Streamlit (or web) demo app. Optionally clone your own voice using Snowflake SPCS GPU so the narration sounds like you, not a generic AI.

## Why This Exists

You built a killer demo for a prospect. Now you need a recording to leave behind — something they can rewatch, share with their team, and use to champion Snowflake internally. This skill turns your app into a narrated demo video asset in under 30 minutes, with your voice (or a high-quality AI voice) delivering a talk track personalized to the prospect.

## What It Does

| Step | What Happens | Output |
|------|--------------|--------|
| 1. **Analyze** | Reads every page, chart, KPI, and interactive element from your app's source code. Runs SQL to get live numbers. Incorporates meeting notes, prospect context, and pain points. | Page-by-page outline |
| 2. **Write** | Generates a conversational, timed talk track with action cues (`ACTION: click tab`), screen descriptions (`ON SCREEN:`), and real data woven in. Validates all numbers against live queries before finalizing. | `RECORDING_SCRIPT.md` |
| 3. **Voice** | Two paths — pick one or generate both for A/B comparison: | |
| | **a) Microsoft Neural Voice** — Free, no GPU, immediate. 12+ voice options ranked by naturalness. | `demo_narration_<voice>.mp3` |
| | **b) Your Own Voice** — Record a 30-second mic sample, clone it on Snowflake SPCS GPU (Qwen3-TTS + flash-attn on A10G). | `demo_narration_cloned.mp3` |
| 4. **Iterate** | Change voice, adjust speed, edit script, re-validate data, regenerate. The agent handles the loop. | Updated files |

## Quick Start

The skill activates automatically in Cortex Code. Just say:

- *"Create a demo recording for my Streamlit app"*
- *"Generate a talk track for this dashboard"*
- *"I need a narrated screen recording script"*
- *"Clone my voice for the demo narration"*

The agent walks you through each step with confirmation prompts — no manual CLI commands needed.

## Voice Cloning Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         YOUR MACHINE                            │
│                                                                 │
│  1. Record mic sample (30s WAV)                                 │
│  2. Local Whisper validation (catches bad recordings early)     │
│  3. clone_voice_spcs.py orchestrates everything:                │
│     - Resumes/creates compute pool                              │
│     - Uploads sample + script to stage                          │
│     - Submits EXECUTE JOB SERVICE                               │
│     - Streams container logs in real-time                       │
│     - Downloads result MP3                                      │
│     - Suspends pool to save credits                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SNOWFLAKE SPCS (A10G GPU)                    │
│                                                                 │
│  Container: voice-cloner (~8GB image, no model weights inside)  │
│  Stage mount: @VOICE_CLONE_STAGE/model/ (Qwen3-TTS ~2.5GB)     │
│                                                                 │
│  Pipeline:                                                      │
│    Whisper transcribe voice sample                              │
│      → Qwen3-TTS + flash-attn generate per-segment audio       │
│        → Silence trim + concatenate with natural pauses         │
│          → Upload final MP3 to stage                            │
└─────────────────────────────────────────────────────────────────┘
```

**No Docker Desktop required.** Image transfer uses [crane](https://github.com/google/go-containerregistry) — a single Go binary that copies OCI images between registries. Auto-downloaded on first run (~15MB).

## Image Delivery

```
GitLab Container Registry ──crane copy──► Snowflake Image Registry
        (~8GB, code + deps only)              (no model weights)

HuggingFace ──download──► Local ──PUT──► @VOICE_CLONE_STAGE/model/
     (Qwen3-TTS ~2.5GB)                      (mounted at runtime)
```

Model weights are kept on a Snowflake stage — not baked into the image. This avoids an 18GB image with layers that exceed SSO token lifetimes during push.

## Scripts

| Script | Purpose | When It Runs |
|--------|---------|--------------|
| `scripts/setup_spcs.py` | One-time setup: crane download, image copy to Snowflake, model weight upload, compute pool + network rule creation | First use per account |
| `scripts/clone_voice_spcs.py` | Full SPCS orchestrator: pool management, job submission, log streaming, download, pool suspension | Every voice clone run |
| `scripts/clone_voice.py` | Mic recording with countdown timer + local GPU voice cloning (Qwen3-TTS, Coqui XTTS, OpenVoice, Chatterbox) | Recording voice samples; local GPU cloning |
| `scripts/generate_audio.py` | edge-tts narration: recording script → MP3 using Microsoft Neural voices | AI voice generation |
| `scripts/spcs/job_clone_voice.py` | Container entrypoint: Whisper → Qwen3-TTS + flash-attn → cloned audio with per-segment progress | Runs inside SPCS |
| `scripts/spcs/Dockerfile` | Multi-stage build: compiles flash-attn in devel image, bundles Whisper + Qwen3-TTS in runtime (~8GB) | Image build |

## One-Time Setup

Run once per Snowflake account:

```bash
# PowerShell
$env:SNOWFLAKE_CONNECTION_NAME="<CONN>"; python scripts/setup_spcs.py --connection <CONN>

# macOS/Linux
SNOWFLAKE_CONNECTION_NAME=<CONN> python3 scripts/setup_spcs.py --connection <CONN>
```

This will:
1. Download `crane` (single binary, cached in `.bin/`)
2. Copy the pre-built voice-cloner image (~8GB) from GitLab to Snowflake
3. Download Qwen3-TTS model weights (~2.5GB) and upload to `@VOICE_CLONE_STAGE/model/`
4. Create the network rule, external access integration, and GPU compute pool

Check if setup is already done:
```bash
$env:SNOWFLAKE_CONNECTION_NAME="<CONN>"; python scripts/setup_spcs.py --check --connection <CONN>
```

## Snowflake Objects Created

| Object | Name | Purpose |
|--------|------|---------|
| Compute Pool | `DEMO_GPU_SE_POOL` (or user-chosen) | GPU_NV_S (A10G) instance, auto-suspend 5 min |
| Image Repository | `VOICE_CLONE_REPO` | Stores the voice-cloner Docker image |
| Stage | `VOICE_CLONE_STAGE` | Model weights + job I/O (voice samples, scripts, output) |
| Network Rule | `VOICE_CLONE_EGRESS_RULE` | Egress to HuggingFace, XET CDN, PyPI |
| External Access Integration | `VOICE_CLONE_ACCESS_INTEGRATION` | Grants network access to SPCS jobs |

## Voice Options

### Microsoft Neural (edge-tts) — Free, Immediate

| Voice | Gender | Style |
|-------|--------|-------|
| `en-US-AndrewMultilingualNeural` | Male | Warm, natural conversational — top pick |
| `en-US-BrianMultilingualNeural` | Male | Polished, professional narrator |
| `en-US-AvaMultilingualNeural` | Female | Expressive, warm — top female pick |
| `en-US-EmmaMultilingualNeural` | Female | Clear, confident |

12+ additional voices available. Run `python scripts/generate_audio.py --list-voices` to see all.

### Voice Cloning (SPCS GPU) — Sounds Like You

- **Model:** Qwen3-TTS 0.6B with flash-attn acceleration
- **Input:** 30-second voice sample (WAV, 44.1kHz mono)
- **Processing:** ~3-4 minutes end-to-end on A10G (including pool startup)
- **Quality:** Captures pitch, cadence, and speaking style. Best results from expressive, varied recordings in a quiet room.

## Smart Script Generation

The talk track isn't generic — it incorporates:

- **Prospect context** — Names, org, role, pain points from meeting notes and conversation history
- **Live data** — SQL queries run against the actual database; numbers in narration match what's on screen
- **Data validation** — Before every audio generation, all metrics are re-verified against live queries (catches drift from relative date filters)
- **TTS anti-truncation rules** — Scripts are written to avoid words that Qwen3-TTS clips at segment boundaries (hard consonant endings like -ds, -ts, -ks). Segments end on soft landings or include trailing buffer phrases.

## Error Handling

| Scenario | Exit Code | What Happens |
|----------|-----------|--------------|
| Crane copy fails | 42 | Agent offers: retry (resumable), fall back to Docker, or quit |
| GitLab auth fails | 43 | Agent prompts for GitLab PAT (paste, env var, or generate new) |
| Voice sample silent/corrupt | — | Local Whisper catches it before SPCS upload; agent prompts re-record |
| Whisper fails in container | — | Agent detects x-vector fallback in logs; prompts re-record or retry |
| SPCS permission denied | — | Agent shows exact GRANT statements needed for the current role |
| Numbers drift in script | — | Step 3b auto-validates and patches stale numbers before audio gen |

## Performance Benchmarks

Observed on GPU_NV_S (A10G), April 2026:

| Phase | Duration |
|-------|----------|
| Compute pool startup (from SUSPENDED) | ~90 seconds |
| Whisper transcription (30s sample) | ~1.5 seconds |
| Model load (with flash-attn) | ~36 seconds |
| Audio generation (17 segments, ~4 min audio) | ~140 seconds |
| **Total job time (end-to-end)** | **~4 minutes** |
| Crane copy (image, mostly cached) | 2-5 minutes |
| Crane copy (image, first time, ~8GB) | 10-20 minutes |

## Output Files

All outputs go in `<APP_DIR>/demo_recording/`:

| File | Description |
|------|-------------|
| `RECORDING_SCRIPT.md` | Timed narration script with action cues, setup instructions, and recording tips |
| `demo_narration_<voice>.mp3` | AI voice-over (edge-tts, Microsoft Neural) |
| `demo_narration_cloned.mp3` | Voice-cloned narration (your voice via SPCS GPU) |
| `voice_sample.wav` | Recorded voice sample used for cloning |

## GitLab Authentication

The pre-built image lives on GitLab's container registry. The skill handles auth automatically:

| Scenario | How It Works |
|----------|--------------|
| Already authenticated | Crane probes the registry — if creds exist, no action needed |
| `GITLAB_TOKEN` env var set | Script reads the token automatically |
| `--gitlab-token <PAT>` flag | Pass a Personal Access Token directly |
| None of the above | Script exits with code 43; the agent shows a pop-up asking for your token |

Generate a PAT at: https://snow.gitlab-dedicated.com/-/user_settings/personal_access_tokens (needs `read_registry` scope).

## Requirements

- Python 3.11+
- `edge-tts` (installed automatically via `pyproject.toml`)
- Snowflake account with SPCS GPU access (for voice cloning)
- No Docker Desktop required (crane handles image transfer)
- `ffmpeg` for WAV→MP3 conversion (optional: `winget install ffmpeg` / `brew install ffmpeg`)
