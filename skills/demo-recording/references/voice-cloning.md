# Demo Recording — Voice Cloning Setup


#### One-Time Setup (per Snowflake account)

If this is the first time using voice cloning on this account, run setup:

```bash
SNOWFLAKE_CONNECTION_NAME=<CONNECTION_NAME> python <SKILL_DIR>/scripts/setup_spcs.py --connection <CONNECTION_NAME>
```

This will:
- Download `crane` (single binary, no Docker needed)
- Copy the pre-built voice-cloner image (~8GB) from GitLab to Snowflake
- Download Qwen3-TTS model weights (~2.5GB) and upload to `@VOICE_CLONE_STAGE/model/`
- Create the network rule, external access integration, and compute pool

To check if setup is already complete:
```bash
SNOWFLAKE_CONNECTION_NAME=<CONNECTION_NAME> python <SKILL_DIR>/scripts/setup_spcs.py --check --connection <CONNECTION_NAME>
```

#### Actions

1. **Get a voice sample** — Before recording, check if `voice_sample.wav` already exists in the output directory (`<APP_DIR>/demo_recording/`).

   **Regardless of whether a sample is found or not**, always present all three options via `ask_user_question`. The user may have a voice sample from a previous project in a different directory — never assume they don't.

   **If a voice sample already exists in the output directory**, ask via `ask_user_question`:

   > *"I found an existing voice sample at `<path>` (<size> KB). How would you like to proceed?"*
   > - **Use it** — "Use the existing voice sample for cloning."
   > - **Use a different sample** — "I have an existing voice sample in another location. I'll provide the file path."
   > - **Record a new one** — "I'll record a fresh 30-second voice sample using your mic."
   > - **Play it first** — "Let me listen to the found sample before deciding."

   If "Play it first", open the file, then ask again with **Use it** / **Use a different sample** / **Record a new one**.

   **If no voice sample exists in the output directory**, ask via `ask_user_question`:

   > *"No voice sample found in the current project. How would you like to proceed?"*
   > - **I have one** — "I have an existing voice sample (e.g., from another project). I'll provide the file path."
   > - **Record a new one** — "I'll record a fresh 30-second voice sample using your mic."

   If the user picks "I have one", ask for the file path via a text input `ask_user_question`, verify the file exists, copy it to the output directory, and proceed to Whisper validation. If the file doesn't exist, inform the user and ask again.

   If recording a new one, proceed with the recording flow below.

   **Recording execution** — **always record automatically, never ask the user to run the command themselves.**

   ```bash
   python <SKILL_DIR>/scripts/clone_voice.py \
     --record 30 --output-dir <APP_DIR>/demo_recording --no-confirm
   ```
   **IMPORTANT — Recording UX for the agent:**
   - **NEVER ask the user to run the recording command manually.** The agent MUST execute it directly via the Bash tool. This is a core UX requirement — the skill handles everything end-to-end.
   - Always use `--no-confirm` so the script records and exits without waiting for terminal input.
   - Default recording duration is **30 seconds** (significant quality improvement over 10s — more phoneme coverage, better prosody cloning). Diminishing returns beyond 30s.
   - **No need to ask for a transcript** — the container auto-transcribes the voice sample using Whisper and uses the transcript for prosody cloning automatically. However, you MUST validate locally with Whisper first (Step 4, Action 4) to catch silent/corrupt recordings before uploading to SPCS.
   - The script writes status to `.recording_status` JSON file in the output dir. After the script finishes, check this file to confirm recording completed.

   **Recording flow (foreground with spinning indicator):**

   1. **Generate a reading passage:** Before recording, the agent MUST generate a ~30-second reading passage for the user to read aloud. This is CRITICAL to avoid "transcript bleed" — Whisper auto-transcribes the voice sample and the transcript's words can leak into the cloned output if they overlap with the narration script.
      - The passage MUST NOT contain any words or phrases from the recording script / talk track. Specifically, avoid: app-specific terms (product names, KPI names, feature names), domain jargon from the narration, and any distinctive phrases from the script.
      - The passage SHOULD be engaging and conversational — something pleasant to read aloud with natural expression (not dry or robotic). Good topics: travel stories, cooking descriptions, nature observations, sports commentary, movie reviews.
      - The passage SHOULD be ~150-200 words (fills ~30 seconds when read at a natural pace).
      - The passage SHOULD include varied sentence lengths, questions, and emotional range to capture the speaker's full vocal range.
      - Present the passage in chat with a brief instruction: "Read this aloud when recording starts. Be expressive — read it like you're telling a friend, not reading a textbook."

   2. **Prepare:** Share brief recording tips (2-3 sentences, casual):
      - "Find a quiet spot — close the door, no fans or AC running."
      - "Hold your mic about 6 inches from your mouth. Be expressive — vary your pitch and energy."
   3. **Record (background + sleep spinner pattern):**
      - **FIRST:** Output a bold, visible message in chat BEFORE launching the command. This is the user's primary signal — they may not be watching the terminal panel. Example:
        > **Get ready to read — recording starts in 3 seconds!**
      - **THEN:** Follow this exact 3-step pattern:

      **Step 1 — Launch recording in background:**
      ```bash
      python <SKILL_DIR>/scripts/clone_voice.py \
        --record 30 --output-dir <APP_DIR>/demo_recording --no-confirm
      # run_in_background=true  (save the shell ID)
      ```

      **Step 2 — Keep the spinner active with a sleep:**
      Immediately after launching, output a message like **"Recording now... (30 seconds)"** in chat, then run a sleep command:
      ```bash
      Start-Sleep -Seconds 36
      ```
      This keeps the agent's "working" spinner visible for the full recording duration. Without this, the background launch returns instantly with a checkmark, which makes it look like the recording finished in a split second — very confusing for the user. The 36-second sleep covers the 3s countdown + 30s recording + 3s overhead.

      **Step 3 — Collect result:**
      After the sleep, call `bash_output` with `wait=true` and `timeout_ms=10000` using the shell ID from Step 1 to get the recording output.

      The script prints a 3-2-1 countdown with a system bell (`\a`) on each tick, then `RECORDING NOW — START READING!` when recording begins.

   4. **Validate voice sample with local Whisper (MANDATORY):** Before presenting the sample to the user, run a local Whisper transcription to verify the audio contains recognizable speech. This catches silent/corrupt recordings and mic issues before wasting GPU time on SPCS.

      **Prerequisites:** `openai-whisper` must be installed (`pip install openai-whisper`). `ffmpeg` must be on PATH. If ffmpeg isn't found by Whisper, load the audio via `soundfile` + `scipy.signal.resample` to 16kHz float32 and pass the numpy array directly to `model.transcribe()`.

      ```python
      import numpy as np, soundfile as sf, whisper
      audio, sr = sf.read("<voice_sample_path>")
      if audio.ndim > 1: audio = audio.mean(axis=1)
      if sr != 16000:
          import scipy.signal
          audio = scipy.signal.resample(audio, int(len(audio) * 16000 / sr))
      audio = audio.astype(np.float32)
      model = whisper.load_model("base")
      result = model.transcribe(audio)
      print("LANGUAGE:", result.get("language"))
      print("TRANSCRIPT:", result["text"][:500])
      ```

      **Validation checks:**
      - **Language must be `en`** (or the expected language). If Whisper detects a wrong language (e.g., `nn`, `zh`), it's hallucinating — the audio is likely silent or corrupt.
      - **Transcript must be non-empty and coherent.** If empty, or if it's repetitive garbage (e.g., `1.5% 1.5% 1.5%`), the recording failed.
      - **Audio RMS must be > 0.01.** Also check: `rms = np.sqrt(np.mean(audio**2))`. If RMS < 0.01, the mic captured silence.

      **If validation fails**, inform the user clearly:
      > "Your voice sample appears to be silent or unrecognizable — Whisper couldn't transcribe it (detected language: `<lang>`, transcript: `<snippet>`). This usually means the mic was muted or the wrong input device was selected. Let's re-record."

      Then loop back to the recording step. Do NOT proceed to voice cloning with a bad sample — the container will fall back to x-vector mode which produces poor quality clones.

      **If validation passes**, proceed to step 5.

      **⚠️ This validation is MANDATORY for ALL voice samples** — newly recorded, re-recorded, or user-provided existing files. Never skip it.

   5. **Let the user listen and confirm:** After Whisper validation passes, tell the user where the file was saved and its size (e.g., "Voice sample saved: `<path>` (2584 KB, 30 seconds). Whisper transcription verified OK.").
      - Use `ask_user_question` with these options:
        - **Play it** — "Open the audio file so I can listen before deciding."
        - **Keep it** — "Sounds good, proceed to voice cloning."
        - **Re-record** — "Let me try another take."
      - If user picks "Play it", open the file (Windows: `Start-Process "<path>"`, macOS: `open "<path>"`), then ask again with just **Keep it** / **Re-record**.
      - If re-recording, use the same casual approach: "Okay, let's try again — start speaking immediately." Then repeat from the recording step (including Whisper validation again).

   **Why this works:** The background launch suppresses the "polling for output" notice entirely. The sleep command keeps the spinner active so the user sees the agent is "working" throughout the recording — no misleading instant checkmark. The chat message alerts the user before the terminal even starts. The system bell on each countdown tick provides an audible cue.

   On macOS, remind user to allow microphone access if prompted.

2. **Choose a compute pool** — before running voice cloning, ask the user via `ask_user_question`:

   > *"For voice cloning I need a GPU compute pool. How would you like to proceed?"*
   > - **Find one for me** — I'll scan your account for existing GPU pools and recommend one.
   > - **I have one in mind** — Provide the pool name (must be a GPU pool — I'll verify).
   > - **Create a new one** — I'll create `DEMO_GPU_SE_POOL` (A10G GPU, auto-suspend 5 min).

   **If "Find one for me":**
   - Run `SHOW COMPUTE POOLS` and filter for GPU instance families.
   - If GPU pools exist, present them with state/size and ask the user to pick one.
   - If no GPU pools exist, inform the user and recommend creating a new one.

   **If "I have one in mind":**
   - User provides pool name via text input.
   - Run `DESCRIBE COMPUTE POOL <name>` and verify `instance_family` starts with `GPU_`.
   - If not a GPU pool, inform the user and ask again.

   **If "Create a new one":**
   - Proceed with default pool name `DEMO_GPU_SE_POOL`.

   Pass the chosen pool name via `--pool-name <POOL_NAME>` to the orchestrator.

3. **Run voice cloning:**
   ```bash
   SNOWFLAKE_CONNECTION_NAME=<CONNECTION_NAME> python <SKILL_DIR>/scripts/clone_voice_spcs.py \
     --voice-sample <APP_DIR>/demo_recording/voice_sample.wav \
     --script <APP_DIR>/demo_recording/RECORDING_SCRIPT.md \
     --output-dir <APP_DIR>/demo_recording \
     --connection <CONNECTION_NAME> \
     --pool-name <POOL_NAME>
   ```
   **IMPORTANT:** Always set `SNOWFLAKE_CONNECTION_NAME` env var inline to match the `--connection` value. This ensures the Python connector authenticates to the correct Snowflake account (matching Snowwork's active connection).
   **Note:** The container automatically transcribes the voice sample using Whisper and uses the transcript for prosody cloning. No `--ref-text` needed unless you want to override the auto-transcription.

   The orchestrator will:
   - Ensure compute pool is active (resume if suspended, or create if new)
   - Auto-detect model weights on stage (no egress needed if staged)
   - Upload voice sample and script to stage
   - Submit the job and stream container logs in real-time
   - Auto-transcribe the voice sample (Whisper) for prosody cloning
   - Show per-segment generation progress (e.g., `[3/12] Generating: "And here's where..." (245 chars)`)
   - Download the result and suspend the compute pool

   **Note:** The `--no-egress` flag is no longer needed when model weights are staged. The orchestrator auto-detects this.

   **⚠️ MANDATORY: Monitor container logs for x-vector fallback.** While streaming logs from the running job, watch for the message `x-vector only mode` or `Auto-transcription returned empty`. These indicate Whisper failed inside the container and the model fell back to x-vector-only cloning, which produces voice clones that do NOT sound like the user.

   **If x-vector fallback is detected in logs**, the agent MUST:
   1. Wait for the job to finish (don't cancel mid-generation — let it complete cleanly).
   2. **Warn the user immediately** that Whisper failed in the container and the clone will likely not sound like them.
   3. Use `ask_user_question` to present options:
      - **Re-record and retry** — "Record a fresh voice sample, validate with local Whisper, then re-run the cloning job."
      - **Retry with current sample** — "Re-run the job with the same sample (Whisper may succeed on retry if it was a transient issue)."
      - **Keep it anyway** — "Download and listen to the output despite the x-vector fallback."
   4. If user picks "Re-record and retry", loop back to the voice sample recording flow (Step 4b, Action 1). The new sample MUST pass local Whisper validation before re-submitting.
   5. If user picks "Retry with current sample", re-submit the job.
   6. If user picks "Keep it anyway", proceed to the download and review step.

   **Why both local and container validation?** Local Whisper (base model on CPU) and container Whisper (tiny model on GPU) can produce different results due to model size, audio preprocessing, and float precision. A sample that passes locally can still fail in the container (rare but possible). The local check catches ~95% of issues; the container check is the safety net.

4. **Report** generated file with size. **Do NOT auto-play the file.** Use `ask_user_question` to let the user decide:
   - **Play it** — "Open the audio file so I can listen and review."
   - **Sounds good** — "I'm happy with it, move on."
   - **Re-clone** — "Try again (re-record voice sample or adjust settings)."

   If user picks "Play it", open the file (Windows: `Start-Process "<path>"`, macOS: `open "<path>"`), then ask again with **Sounds good** / **Re-clone**.

**Voice sample tips to share with user (before recording):**
- **Quiet room** — close the door, turn off fans/AC, no background noise. The 0.6B model is sensitive to ambient sound.
- **Mic distance ~15cm (6 inches)** — too close causes plosives, too far picks up room echo.
- **Be expressive** — vary your pitch, energy, and pace. A monotone reading produces a monotone clone. Talk like you're presenting to a customer: engaged, confident, natural. Smile while speaking — it changes your tone.
- **Use complete sentences** — avoid short phrases like "Hello" or "Yes". Aim for at least 3 seconds of continuous speech between pauses.
- **Content DOES matter** — the agent generates a custom reading passage that avoids words from the narration script. This prevents "transcript bleed" where Whisper-transcribed words from the voice sample leak into the cloned output. NEVER let the user freestyle or talk about the app/demo — always provide the generated passage.
- **30 seconds is the sweet spot** — quality scales linearly from 3s to 15s, then plateaus. 30s gives extra phoneme coverage. Longer than 30s has diminishing returns and can cause generation instability.
- **Don't ramble or fill with filler words** — avoid excessive "um", "uh", throat clearing, or sighing. The model will replicate these.
- **WAV format at 44.1kHz mono** (the recording script handles this automatically).

**If SPCS fails:** Fall back to Step 4a (edge-tts neural voices).

**⚠️ STOP**: Let user listen to the cloned output.

