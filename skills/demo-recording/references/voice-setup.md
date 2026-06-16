# Demo Recording — Voice Setup & Selection

## Platform Notes (Mac & Windows)

All scripts are cross-platform. Follow these conventions:

- **Python invocation:** Use `python` on Windows, `python3` on macOS/Linux. The skill agent should detect the platform and use the correct one.
- **Path separators:** All scripts accept both `/` and `\`. Use forward slashes for portability.
- **ffmpeg:** Install via `winget install ffmpeg` (Windows) or `brew install ffmpeg` (macOS). Optional — only needed for WAV→MP3 conversion.
- **Microphone recording:** `sounddevice` and `soundfile` are base dependencies and installed automatically. On macOS, the first recording may trigger a system permission dialog — instruct the user to allow microphone access.
- **uv vs pip:** If `uv run --project` fails, fall back to running scripts directly with `python`/`python3` and ensure `edge-tts` is installed via `pip install edge-tts`.
- **Connection env var:** Always set `SNOWFLAKE_CONNECTION_NAME` inline when launching scripts, using the **same connection as the active Snowwork session** (check `<account_info>` in the system prompt for the current account — do NOT use a different connection even if one was mentioned in conversation history). On Windows (PowerShell): `$env:SNOWFLAKE_CONNECTION_NAME="<CONNECTION_NAME>"; python ...`. On macOS/Linux: `SNOWFLAKE_CONNECTION_NAME=<CONNECTION_NAME> python3 ...`. If the active session uses the default connection, omit the env var entirely or set it to `default`.
- **Background mode for long-running commands:** Use `run_in_background=true` for long-running commands like crane copy, SPCS job orchestration, etc. Use `Start-Sleep` between `bash_output` checks. **Exception: mic recording should run as a foreground process** (NOT background) — the Bash tool shows a spinning indicator while the script runs, and the script prints "RECORDING NOW" the instant it starts. This avoids the delay between chat messages and actual recording start.

## Voice Engine: Why edge-tts

The goal is the **most human-like voice possible** without paid API keys.

| Engine | Quality | Cost | Notes |
|--------|---------|------|-------|
| **edge-tts** (Microsoft Neural) | Best free option — neural, expressive, natural pauses | Free, no API key | Uses Microsoft Edge's cloud TTS. Multilingual variants sound even better. |
| gTTS (Google) | Decent but flat, robotic on long text | Free, no API key | Breaks on long input. No voice selection. Sounds like Google Translate. |
| pyttsx3 | Robotic, system-dependent | Free, offline | Uses OS voices (SAPI5/espeak). Not suitable for client-facing demos. |
| Azure Speech SDK (DragonHD) | Studio-quality, emotional, best in class | Paid (500k chars/mo free) | Requires Azure subscription + API key. Use if user has Azure access. |

**Always use edge-tts** unless the user explicitly provides an Azure Speech API key.

## Voice Selection Guide

**CRITICAL: Always run `generate_audio.py --list-voices` first** to get the latest available voices.

### Recommended voices (ranked by naturalness)

**Tier 1 — Multilingual Neural (most human-like):**

| Voice | Gender | Style |
|-------|--------|-------|
| `en-US-AndrewMultilingualNeural` | Male | Warm, natural conversational — top pick |
| `en-US-BrianMultilingualNeural` | Male | Polished, professional narrator |
| `en-US-AvaMultilingualNeural` | Female | Expressive, warm — top female pick |
| `en-US-EmmaMultilingualNeural` | Female | Clear, confident |

**Tier 2 — Standard Neural (very good):**

| Voice | Gender | Style |
|-------|--------|-------|
| `en-US-AndrewNeural` | Male | Warm, conversational |
| `en-US-GuyNeural` | Male | Clear, professional |
| `en-US-BrianNeural` | Male | Polished, balanced |
| `en-US-AriaNeural` | Female | Warm, expressive |
| `en-US-JennyNeural` | Female | Friendly, professional |

**Default recommendation:** `en-US-AndrewMultilingualNeural` (male) or `en-US-AvaMultilingualNeural` (female).

### If Azure Speech SDK is available (DragonHD voices)

- `en-US-Andrew:DragonHDLatestNeural` — conversational HD male
- `en-US-Ava:DragonHDLatestNeural` — conversational HD female

