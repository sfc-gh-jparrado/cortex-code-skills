# Demo Recording — Monitoring & Troubleshooting


## Monitoring Long-Running Processes (Timer Accuracy)

When monitoring long-running processes (crane copy, SPCS job execution, etc.), the agent MUST track elapsed time using **actual clock timestamps**, NOT by counting polling iterations.

**The problem:** `bash_output` with `wait=true` returns immediately when there is no new output (it does NOT block for the full timeout). If you count each poll as N minutes of elapsed time, your estimates will be wildly inflated.

**Correct approach:**
1. Record the start time using `Get-Date -Format "HH:mm:ss"` (Windows) or `date +%H:%M:%S` (macOS/Linux) when the process begins.
2. Use `Start-Sleep -Seconds N` (Windows) or `sleep N` (macOS/Linux) between checks to create real wall-clock delays.
3. Get the current time with `Get-Date` / `date` on each check and compute elapsed = current - start.
4. **Never** estimate elapsed time by multiplying poll count × timeout — this is always wrong.

**Example monitoring pattern (PowerShell):**
```powershell
Start-Sleep -Seconds 120; Get-Process crane -ErrorAction SilentlyContinue | Select-Object Id, CPU, WorkingSet64; Get-Date -Format "HH:mm:ss"
```

**Reference timing benchmarks** (observed on GPU_NV_S / A10G, April 2026):
| Phase | Duration |
|-------|----------|
| Compute pool startup (from SUSPENDED) | ~90 seconds |
| Whisper transcription (30s voice sample) | ~1.5 seconds |
| Model load (with flash-attn) | ~36 seconds |
| Audio generation (6 segments, ~66s audio) | ~140 seconds |
| Total job time (end-to-end) | ~200 seconds (3.3 min) |
| Crane copy (image, mostly cached) | 2-5 minutes |
| Crane copy (image, first time, ~8GB) | 10-20 minutes |
| Docker build (with flash-attn compilation) | 15-30 minutes |

## SPCS Job Log Retrieval

**CRITICAL:** SPCS cleans up job containers within seconds of `EXECUTE JOB SERVICE` completing. Logs become unavailable almost immediately.

**When the orchestrator handles it:** `clone_voice_spcs.py` grabs final logs automatically in `_wait_for_job_with_logs()` the moment it detects DONE/FAILED status. No action needed.

**When submitting jobs via manual SQL:** You MUST grab logs immediately. Use this pattern:

```sql
-- Poll for completion
SELECT SYSTEM$GET_SERVICE_STATUS('DB.SCHEMA.VOICE_CLONE_JOB');

-- THE MOMENT status shows DONE or FAILED, immediately run:
SELECT SYSTEM$GET_SERVICE_LOGS('DB.SCHEMA.VOICE_CLONE_JOB', '0', 'cloner', 500);
```

**Do NOT wait even 30 seconds after job completion to grab logs.** If you see "Unable to get container status for instance id: 0. Available instances: " — the container was already cleaned up and logs are gone.

## Troubleshooting

**edge-tts fails to install:**
- Ensure Python 3.11+ and try: `pip install edge-tts`

**Numbers in talk track don't match app:**
- This should be caught by Step 3b (Validate Live Data) which runs automatically before every audio generation
- If it slipped through, re-run the exact SQL from the app source code with current date filters
- Pay special attention to relative time filters (DATEADD, CURRENT_TIMESTAMP, CURRENT_DATE) — these drift daily

**Audio sounds too fast/slow:**
- Use `--rate` flag: `-15%` for slower, `+10%` for faster

**Audio sounds robotic despite neural voice:**
- Switch to Multilingual variant (e.g., `AndrewNeural` → `AndrewMultilingualNeural`)
- Check narration text for unnatural phrasing — contractions and varied sentence length help

**Voice cloning: no CUDA GPU available locally:**
- Use Snowflake SPCS GPU: `clone_voice_spcs.py` (no local GPU needed)
- Run `setup_spcs.py` first for one-time setup

**Voice cloning: cloned voice sounds distorted:**
- Provide a cleaner, longer voice sample (30 seconds ideal)
- The container auto-transcribes using Whisper for prosody cloning. To override, pass `--ref-text "<transcript>"` manually
- Ensure quiet room, no background noise
- Try WAV format at 44.1kHz or higher

**SPCS: "No GPU instance families available":**
- SPCS GPU is only available in some AWS regions
- Check: `SELECT CURRENT_REGION()`
- Contact your Snowflake account team

**SPCS: "CREATE COMPUTE POOL" permission denied:**
- Requires `CREATE COMPUTE POOL` privilege
- Ask ACCOUNTADMIN: `GRANT CREATE COMPUTE POOL ON ACCOUNT TO ROLE <your_role>`

**SPCS: Docker push fails / SSO token expired:**
- This is no longer an issue with the v2.0 architecture
- The Docker image (~8GB) has no layer >2GB, so SSO tokens don't expire during push
- Model weights are uploaded separately to a Snowflake stage as individual files
- If push still fails, run `snow spcs image-registry login --connection <CONN>` then retry

**SPCS: "Object already exists" when submitting job:**
- The orchestrator now auto-drops existing jobs before submission
- If manual cleanup needed: `DROP SERVICE IF EXISTS <db>.<schema>.VOICE_CLONE_JOB`

**SPCS: "Insufficient privileges" errors:**
- The orchestrator tries ACCOUNTADMIN, then SYSADMIN, then current role
- For pool creation: `GRANT CREATE COMPUTE POOL ON ACCOUNT TO ROLE <role>`
- For network rules: `GRANT CREATE NETWORK RULE ON SCHEMA <db>.<schema> TO ROLE <role>`
- For integrations: `GRANT CREATE INTEGRATION ON ACCOUNT TO ROLE <role>`

**setup_spcs.py: SYSTEM$GET_LOGIN_TOKEN fails:**
- This function only works inside SPCS containers, not from local machines
- setup_spcs.py now uses `snow spcs image-registry login` for authentication instead

**SPCS: Model download hangs:**
- If model weights are NOT on the stage, ensure the network rule includes XET CDN domains
- Run `setup_spcs.py` to upload model weights to stage (recommended — avoids all egress issues)
- Check staging status: `python setup_spcs.py --check --connection <CONN>`

**SPCS: Job fails or times out:**
- Check logs: `SELECT SYSTEM$GET_SERVICE_LOGS('<job_name>', '0', 'cloner', 500)`
- **CRITICAL: Grab logs IMMEDIATELY after job completion.** SPCS cleans up job containers within seconds of EXECUTE JOB SERVICE finishing. If you wait even 30 seconds, `SYSTEM$GET_SERVICE_LOGS` may return empty ("Unable to get container status for instance id: 0. Available instances: "). The orchestrator grabs final logs automatically, but if submitting jobs via manual SQL, you MUST poll `SYSTEM$GET_SERVICE_STATUS` and call `SYSTEM$GET_SERVICE_LOGS` the moment status changes to DONE or FAILED.
- Common causes: model weights not on stage (run `setup_spcs.py`), OOM (use 0.6B model)

**setup_spcs.py: crane download fails:**
- Download manually from https://github.com/google/go-containerregistry/releases
- Place the `crane` binary in `<SKILL_DIR>/.bin/`

**Microphone recording: permission denied (macOS):**
- System Settings → Privacy & Security → Microphone → allow your terminal app

**Microphone recording: no audio device found:**
- Windows: Settings → Sound → Input
- macOS: System Settings → Sound → Input
