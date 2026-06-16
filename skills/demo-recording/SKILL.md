---
name: demo-recording
description: "Generate demo recording assets: talk track, timed recording script, and AI voice-over audio. Use when: user wants to create a demo video, screen recording, narration, talk track, or click track for an existing Streamlit app or dashboard. Triggers: demo recording, talk track, recording script, narration, screen recording, click track, voice-over, demo video."
---

# Demo Recording

Generate a polished talk track, timed recording script, and human-sounding AI-narrated audio file for an existing Streamlit (or other) demo app.

## Prerequisites

- An existing, deployed demo app (Streamlit in Snowflake, local Streamlit, or any web app)
- Access to the app's source code (to read pages, queries, and chart details)
- Python 3.11+ with `edge-tts` available (script installs via uv)
- **For voice cloning (optional):** Snowflake SPCS GPU access. No Docker required — `setup_spcs.py` handles image + model weight deployment.


**Load** `references/voice-setup.md` for platform notes, voice engine selection, and available voices.

## Workflow

### Step 1: Understand the App & Gather Context

**Goal:** Map every page, tab, chart, KPI, and interactive element — AND incorporate all prior context.

**Actions:**

1. **Gather context from the user.** Review the full conversation history for:
   - **Meeting notes** — names, titles, org, pain points, priorities
   - **Prospect/customer context** — who they're presenting to, their organization, strategic goals
   - **Prior instructions** — tone, emphasis areas, sections to skip, specific talking points

   Present a summary:
   ```
   Context I'm incorporating:
   - Meeting with: [Name] at [Org]
   - Audience: [Roles]
   - Key priorities: [List]
   - Tone: [consultative/technical/executive]
   ```

   **⚠️ STOP — use `ask_user_question` pop-up:**

   > *"Before I start writing the talk track, would you like to add more context? The more I know, the more personalized the recording."*

   Options:
   - **This is enough** — "I'll use what's already in our conversation to personalize the talk track."
   - **Add meeting notes** — "Paste meeting notes, call summaries, or transcript highlights. I'll extract names, pain points, and priorities."
   - **Add customer/prospect info** — "Share details about who you're presenting to: their org, role, strategic goals, what they care about."
   - **Point me to a resource** — "Give me a URL, doc, or file path with additional context (e.g., account plan, prior deck, Gong summary)."

   If user selects anything other than "This is enough", collect the additional context, update the summary above, and ask again (they may want to add multiple sources). Loop until they confirm.

2. **MANDATORY — Ask** user for ALL of the following via `ask_user_question`. Do NOT skip or assume any of these, even if you think you can infer them from context. Each must be explicitly confirmed by the user:
   - App location (Snowflake stage path, local directory, or URL)
   - **Target audience** — Who is the demo for? (e.g., "CMO and VP of Quality at Bayshore Health", "technical data engineers", "executive leadership team"). Never assume the audience.
   - **Desired runtime** — How long should the recording be? (default suggestion: 5 minutes, but always ask)
   - **Tone** — What tone should the narration use? Present these options explicitly: consultative, technical, executive. Never default without asking.

   **⚠️ Do NOT proceed to Step 1.3 until all four items above are answered by the user.** If the user provides partial answers, ask follow-up questions for the missing items.

3. **Read** every app page file to catalog pages, KPIs, charts, interactive elements.

4. **Execute** the key SQL queries so you have **exact current numbers available** (you won't necessarily narrate all of them — but you need them accurate for the ones you do use).

5. **Present** a page-by-page outline.

**⚠️ STOP**: Confirm outline and any pages to skip or emphasize.

### Step 2: Write the Talk Track

**Goal:** Create narration that sounds like a real person talking — not reading.

**Rules for human-like narration:**
- **Conversational contractions**: "it's", "you're", "we're", "that's", "don't"
- **Natural filler phrases**: "Now", "So", "And here's the thing", "What's cool is"
- **Vary sentence length**: Mix short punchy sentences with longer ones
- **Use dashes for pauses**: "This is the game-changer — Cortex reads patient comments in real time."
- **Ellipsis for trailing off**: "And the AI can generate specific staffing recommendations..."
- **Reference what's visible**: "See that red bar? That's Mountainside..." — describe visual patterns rather than reading every number
- **Rhetorical questions**: "What if your CMO could just ask a question at 8 PM on a Sunday?"
- **Weave in prospect context**: Reference the prospect by name, their org, their specific pain points.

**Data accuracy rules:**
- Always run the SQL queries from Step 1 so you have the exact numbers available — accuracy matters when you DO cite a number
- If you reference a specific number, use the exact value (e.g., "15.2%", not "about 15%")

**When to read numbers aloud vs. skip them:**
- **DO** cite a number when it tells a story, reveals a trend, creates contrast, or supports a key insight (e.g., "Readmissions dropped from 18% to 12% — that's the Cortex impact")
- **DO** cite a number when it's the punchline of a section or the thing you want the audience to remember
- **DO NOT** robotically read every KPI, chart label, or metric visible on screen — this sounds like a report, not a conversation
- **DO NOT** list numbers in sequence ("We see 272 events, 84 alerts, 68 falls, 15.1% readmission...") — pick the 1-2 that matter most and narrate around them
- **Instead of numbers**, describe what the audience should notice: "See that spike in October?", "The trend is clearly heading down", "This facility is the outlier"
- A good rule of thumb: if removing the number from the sentence makes it meaningless, keep it. If the sentence works without the number, drop it and describe the insight instead

**TTS anti-truncation rules (CRITICAL for voice cloning):**
Qwen3-TTS clips the final word of a segment when it ends on a hard consonant (plosive or stop). This is a known model behavior at segment boundaries. Follow these rules to prevent it:
- **Never end a quoted narration segment on a word with a hard ending consonant** — words ending in -ds, -ts, -ks, -ps, -ct, -nds, -mpt, -pt (e.g., "demands", "impacts", "expects", "results", "constraints") will be clipped.
- **Always end segments on soft landings** — words ending in open vowels, nasals, or continuants are safe: -ay, -ee, -ow, -tion, -ence, -ing, -ure, -ble, -ly, -ry (e.g., "deal", "story", "today", "picture", "visibility").
- **If a key sentence naturally ends on a hard consonant word, append a short trailing phrase** that acts as a buffer AND sounds conversational. Good trailing phrases: "That's a big deal.", "And that matters.", "Worth noting.", "That's the whole story.", "Pretty powerful.", "All in one place.", "Really important here."
- **Review every quoted line's final word before finalizing the script.** Scan for hard-consonant endings and add a trailing phrase where needed. This is non-negotiable — re-generating audio on SPCS GPU is expensive (10+ minutes per run).

**Timing rules:**
- Time each section to fit the requested total runtime
- For AI/ML features that take time to load, include filler narration
- Write quoted narration lines (`"..."`) — the audio generator extracts these
- Include `ACTION` cues for clicks, scrolls, tab switches
- Include `ON SCREEN` cues describing what's visible

**Structure each section as:**
```markdown

**Load** `references/talk-track-format.md` for the talk track section format template.

### Step 3b: Validate Live Data in Script (MANDATORY before every audio generation)

**Goal:** Ensure all numbers, KPIs, and metrics in the talk track match what the app currently shows. This step is MANDATORY before every audio generation — including re-generations — because relative time filters (e.g., `DATEADD('day', -7, ...)`) cause numbers to drift daily.

**Actions:**

1. **Scan the recording script** for any specific numbers, percentages, counts, or metrics that appear in quoted narration lines. Look for patterns like:
   - KPI values (e.g., "272 this week", "74.9 satisfaction", "15.1% readmission")
   - Counts (e.g., "200 denied claims", "84 high-risk")
   - Dollar amounts (e.g., "$1.5 million")
   - Percentages, averages, rates

2. **For each number found, trace it to the app source code** — find the SQL query that produces it. Read the corresponding app page file and identify the exact query.

3. **Execute those queries against the live database** using `snowflake_sql_execute`. Run them with the same filters the app uses (same date ranges, same WHERE clauses).

4. **Compare script values vs. live values.** For each mismatch:
   - Log the discrepancy: `Script says X, live data shows Y`
   - **Auto-fix the script** by replacing the stale number with the current value
   - Preserve the surrounding sentence structure — only change the number itself

5. **If any fixes were made**, show the user a summary:
   ```
   Updated stale numbers in RECORDING_SCRIPT.md:
   - Patient safety events: 272 → 160
   - High-risk alerts: 84 → 48
   - Fall events: 68 → 40
   ```

**Why this matters:** Any query with a relative time filter (`DATEADD`, `CURRENT_TIMESTAMP`, `CURRENT_DATE`, etc.) will produce different results on different days. Synthetic demo data is especially prone to this — rows age out of rolling windows. Even production data drifts. This step catches stale numbers before they get baked into audio that's expensive to regenerate.

**When to run this step:**
- Before EVERY audio generation (Step 4a or 4b)
- After any script edit (Step 5 / Script Edit Flow)
- When the user explicitly asks to regenerate audio
- Even if the script was "just written" — the queries may have run minutes ago and the agent should re-verify

**⚠️ Do NOT skip this step.** It takes <30 seconds and prevents costly re-recordings.

### Step 4: Generate Audio Narration

**Goal:** Generate the voice-over audio. **Prerequisite:** Step 3b (Validate Live Data) MUST have run and all numbers must be current.

1. **Present the voice choice:**

   **⚠️ MANDATORY — This question MUST always be asked via `ask_user_question`, even in continued/resumed sessions. Do NOT infer the answer from conversation history, prior context, or session summaries — the user may never have been presented with the voice cloning option. Never skip this step.**

   > *"How would you like to voice the narration?"*
   > - **Use your own voice** — Record a short mic sample, then clone your voice on Snowflake's GPU (via SPCS). No Docker or local GPU needed.
   > - **Use Microsoft Neural voice** — High-quality AI voice (Andrew, Ava, etc.). No GPU needed. Immediate.
   > - **Generate both** — Get an AI voice immediately AND clone your voice, so you can compare side by side and pick your favorite.

2. **Route based on choice:**
   - **Own voice** → Step 4b (voice cloning)
   - **MS Neural voice** → Step 4a
   - **Generate both** → Step 4a first (immediate), then Step 4b (voice cloning). Present both files at the end for the user to compare.

#### Step 4a: Generate with Microsoft Neural Voice (edge-tts)

1. **Discover latest voices:**
   ```bash
   python <SKILL_DIR>/scripts/generate_audio.py --list-voices
   ```

2. **Let the user choose a voice.** Present the top recommended voices via `ask_user_question` so the user can pick. Do NOT default to Andrew without asking. Example options:
   - **Andrew (Multilingual)** — "Warm, natural conversational male — top pick for naturalness."
   - **Brian (Multilingual)** — "Polished, professional male narrator."
   - **Ava (Multilingual)** — "Expressive, warm female — top female pick."
   - **Emma (Multilingual)** — "Clear, confident female."
   - **Guy** — "Clear, professional male."
   - **Jenny** — "Friendly, professional female."

   The user can also type a custom voice name via "Something else". Map labels to full voice IDs (e.g., "Andrew (Multilingual)" → `en-US-AndrewMultilingualNeural`).

3. **Generate:**
   ```bash
   python <SKILL_DIR>/scripts/generate_audio.py \
     --script <APP_DIR>/demo_recording/RECORDING_SCRIPT.md \
     --output-dir <APP_DIR>/demo_recording \
     --voices <CHOSEN_VOICE_ID>
   ```

4. **Report** generated file with size. **Do NOT auto-play the file.** Use `ask_user_question` to let the user decide:
   - **Play it** — "Open the audio file so I can listen and review."
   - **Sounds good** — "I'm happy with it, move on."
   - **Regenerate** — "Try again with a different voice or settings."

   If user picks "Play it", open the file (Windows: `Start-Process "<path>"`, macOS: `open "<path>"`), then ask again with **Sounds good** / **Regenerate**.

   **⚠️ This consent-before-play rule applies to EVERY audio generation — initial, re-generation after script edits, voice changes, or any other reason. NEVER auto-play or auto-open audio files. Always ask first via `ask_user_question`.**

**⚠️ STOP**: Let user listen and decide.

### Step 4b: Voice Cloning (Use Your Own Voice)

**Goal:** Clone the user's voice and generate narration that sounds like them.

**No Docker required.** The orchestrator (`clone_voice_spcs.py`) handles everything: compute pool, image registry, network rules, external access integration, job execution, log streaming, and local download.

**Load** `references/voice-cloning.md` for voice cloning setup and one-time SPCS configuration.

### Output Directory Convention

**All skill outputs go in a single subdirectory: `<APP_DIR>/demo_recording/`**

This includes:
- `RECORDING_SCRIPT.md` — the timed narration script
- `demo_narration_<voice>.mp3` — AI-generated voice (edge-tts)
- `demo_narration_cloned.mp3` — voice-cloned narration (SPCS)
- `voice_sample.wav` — recorded voice sample

Do NOT scatter outputs across the app root or multiple subdirectories.

### Step 5: Iterate (Optional)

- **Voice change** → Re-run Step 4 with different voice
- **Speed adjustment** → Re-run with `--rate` flag (e.g., `--rate "-10%"` for slower)
- **More human sound** → Try Multilingual variant, or generate 2-3 voices for A/B comparison
- **Voice cloning quality issues** → Provide a longer/cleaner voice sample, or fall back to edge-tts
- **Script edits** → See below.

#### Script Edit Flow (MANDATORY for any script change)

Whenever the user asks to update, edit, enhance, or revise the recording script — whether during initial creation or later iterations — you MUST follow this flow **every time**:

1. **Make the edits** to `RECORDING_SCRIPT.md`.
2. **Open the file** for the user to review (use the IDE's file open mechanism).
3. **Ask for approval** via `ask_user_question`:
   - **Looks good** — "Approve the changes and proceed."
   - **Needs more changes** — "I have additional feedback."
   - **Revert** — "Undo the changes and go back to the previous version."
4. **Do NOT proceed to audio generation** (Step 4) until the user explicitly approves the script.

If the user picks "Needs more changes", collect their feedback, apply edits, and repeat from step 2. Loop until approved.

**⚠️ This applies to ALL script modifications** — initial creation (Step 2), iteration (Step 5), and any ad-hoc edit requests mid-conversation. Never regenerate audio on an unapproved script. After approval, Step 3b (Validate Live Data) runs automatically before audio generation.

## Tools

### Script: generate_audio.py

Generates MP3 narration from a recording script using Microsoft Edge Neural TTS voices.

```bash
python <SKILL_DIR>/scripts/generate_audio.py --list-voices
python <SKILL_DIR>/scripts/generate_audio.py \
  --script <RECORDING_SCRIPT_PATH> \
  --output-dir <OUTPUT_DIRECTORY> \
  --voices en-US-AndrewMultilingualNeural
```

**Arguments:** `--list-voices`, `--locale`, `--script`, `--output-dir`, `--voices`, `--rate`, `--pitch`

### Script: clone_voice.py

Clones a user's voice from a short audio sample using open-source models. Handles mic recording with progress bar.

```bash
python <SKILL_DIR>/scripts/clone_voice.py --check-engines
python <SKILL_DIR>/scripts/clone_voice.py --record 30 --output-dir <DIR>
python <SKILL_DIR>/scripts/clone_voice.py \
  --voice-sample <PATH> --script <PATH> --output-dir <DIR> --engine auto
```

**Arguments:** `--check-engines`, `--record SECONDS`, `--voice-sample`, `--script`, `--text`, `--output-dir`, `--engine`, `--ref-text`

### Script: clone_voice_spcs.py

Full orchestrator for voice cloning on Snowflake SPCS GPU. Handles compute pool, image registry, network rules, external access integration, job execution with live log streaming, download, and cleanup.

```bash
SNOWFLAKE_CONNECTION_NAME=<CONN> python <SKILL_DIR>/scripts/clone_voice_spcs.py --check --connection <CONN>
SNOWFLAKE_CONNECTION_NAME=<CONN> python <SKILL_DIR>/scripts/clone_voice_spcs.py \
  --voice-sample <PATH> --script <PATH> --output-dir <DIR> --connection <CONN>
```

**Arguments:** `--check`, `--voice-sample`, `--script`, `--text`, `--output-dir`, `--connection`, `--database`, `--schema`, `--pool-name`, `--skip-build`, `--shared-image`, `--no-egress`, `--no-suspend`, `--retry-crane`, `--use-docker`, `--gitlab-token`, `--ref-text`

**Image reuse across schemas:** On every run, the script scans all image repositories in the account (`SHOW IMAGE REPOSITORIES IN ACCOUNT`) for an existing `voice-cloner` image. If found anywhere, it reuses it — no rebuild or repush needed, regardless of which database/schema the current session uses. On first build, `GRANT READ ON IMAGE REPOSITORY` is automatically issued to the current role so all future runs can discover it. To manually specify an image, pass `--shared-image <full_image_fqn>`.

**What it creates in Snowflake:**
- Compute pool: `DEMO_GPU_SE_POOL` (GPU_NV_S, auto-suspend 5 min) — or reuses an existing GPU pool chosen by the user
- Image repository: `VOICE_CLONE_REPO`
- Network rule: `VOICE_CLONE_EGRESS_RULE` (HuggingFace + XET CDN + PyPI)
- External access integration: `VOICE_CLONE_ACCESS_INTEGRATION`
- Stage: `VOICE_CLONE_STAGE`

**Image freshness detection:** The script tracks a build context hash in `spcs/.image_digest`. When Dockerfile or job_clone_voice.py changes, it auto-detects staleness and rebuilds. Use `--check` to see freshness status.

**Docker auth resilience:** If a Docker build takes >5 minutes (common on first build), the script automatically re-authenticates via `snow spcs image-registry login` before pushing. If push fails, it retries after re-auth.

**Crane failure handling (exit code 42):** When a crane copy attempt fails, both `clone_voice_spcs.py` and `setup_spcs.py` exit with code **42** and write a `.crane_status.json` file in the scripts directory. The agent MUST handle this:

1. Check if the process exited with code 42.
2. Read `.crane_status.json` from `<SKILL_DIR>/scripts/` to get failure details (`attempt`, `max_retries`, `error`, `docker_available`).
3. Present an `ask_user_question` pop-up with these options:
   - **Retry with crane** — "Resumes from where it left off. Already-uploaded layers are skipped automatically."
   - **Fall back to Docker** — If `docker_available` is true: "Requires Docker Desktop to be running." If false: "Docker is NOT installed on this machine — you'll need to install Docker Desktop first."
   - **Quit** — "Stop the image push. You can retry later."
4. Based on the user's choice:
   - **Retry**: Re-run the same command with `--retry-crane` added. This picks up from the next attempt.
   - **Docker**: For `clone_voice_spcs.py`, re-run with `--use-docker`. For `setup_spcs.py`, re-run with `--docker`.
   - **Quit**: Stop and inform the user they can retry later.

**GitLab auth handling (exit code 43):** When GitLab registry authentication fails, both scripts exit with code **43** and write `.gitlab_auth_status.json`. The agent MUST handle this:

1. Check if the process exited with code 43.
2. Present an `ask_user_question` pop-up explaining that GitLab registry access is needed to copy the pre-built voice-cloner image, and ask how to authenticate:
   - **I have a GitLab PAT** — "Paste your GitLab Personal Access Token (needs `read_registry` scope). It will be passed to the script and not stored."
   - **I have GITLAB_TOKEN set** — "The script will read it from your GITLAB_TOKEN environment variable."
   - **I need to generate one** — "Go to https://snow.gitlab-dedicated.com/-/user_settings/personal_access_tokens and create a token with `read_registry` scope. Then paste it here."
3. Based on the user's choice:
   - **Paste token**: User provides token via text input. Re-run with `--gitlab-token <token>` added to the command. Alternatively, set `GITLAB_TOKEN=<token>` inline in the environment when launching.
   - **Env var set**: Re-run the same command (script reads `GITLAB_TOKEN` automatically).
   - **Generate one**: After user generates and pastes, re-run with `--gitlab-token <token>`.

**IMPORTANT:** Never log or echo the GitLab token. Pass it via `--gitlab-token` flag or `GITLAB_TOKEN` env var only.

**Role handling:** Tries ACCOUNTADMIN first, falls back to SYSADMIN, then current role. Shows clear privilege grant instructions if operations fail.

### Script: setup_spcs.py

One-time setup to deploy the voice-cloner image to a Snowflake account. Uses `crane` (single binary) to copy the pre-built image from GitLab — **no Docker Desktop required**.

```bash
SNOWFLAKE_CONNECTION_NAME=<CONN> python <SKILL_DIR>/scripts/setup_spcs.py --check --connection <CONN>
SNOWFLAKE_CONNECTION_NAME=<CONN> python <SKILL_DIR>/scripts/setup_spcs.py --connection <CONN>
SNOWFLAKE_CONNECTION_NAME=<CONN> python <SKILL_DIR>/scripts/setup_spcs.py --connection <CONN> --docker
```

**Arguments:** `--check`, `--connection`, `--database`, `--schema`, `--skip-image`, `--skip-model`, `--docker`, `--retry-crane`, `--gitlab-token`

**What it does:**
1. Downloads `crane` (~15MB binary, cached in `.bin/`)
2. Copies voice-cloner image (~8GB, no model weights) from GitLab to Snowflake
3. Downloads Qwen3-TTS model weights (~2.5GB) and uploads individual files to `@VOICE_CLONE_STAGE/model/`
4. Creates network rule with all required egress domains
5. Creates external access integration
6. Creates GPU compute pool (if none exists)

**Architecture: Why image + stage?**
The Docker image contains only code and dependencies (~8GB). Model weights (~2.5GB) are hosted on a Snowflake stage and mounted into the container at runtime. This avoids a ~18GB image with a 2.9GB layer that causes SSO token expiry during push. Individual model files (max ~600MB) upload within SSO token lifetime.

## Stopping Points

- Step 1: Context summary + app outline confirmed
- Step 2: Talk track approved
- Step 4: Voice choice made
- Step 4a: Audio reviewed (edge-tts)
- Step 4b: Cloned voice reviewed

## Output

All outputs are placed in `<APP_DIR>/demo_recording/`:

| Artifact | Description |
|----------|-------------|
| `RECORDING_SCRIPT.md` | Timed script with narration, action cues, and setup instructions |
| `demo_narration_<voice>.mp3` | AI-generated voice-over using edge-tts |
| `demo_narration_cloned.mp3` | Voice-cloned narration via SPCS GPU |
| `voice_sample.wav` | Recorded voice sample (if `--record` was used) |

**Load** `references/troubleshooting.md` for monitoring long-running processes, SPCS job log retrieval, and troubleshooting.

