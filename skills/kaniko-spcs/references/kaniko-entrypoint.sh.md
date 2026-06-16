# kaniko_entrypoint.sh

This is the entrypoint script that runs inside the Kaniko container in SPCS. Upload it to the `@BUILD_CONTEXT` stage before running a build.

```sh
#!/busybox/sh
# kaniko_entrypoint.sh - Authenticate to SPCS registry via PAT and run Kaniko
# This script runs inside the Kaniko container in SPCS.
# Registry credentials are injected via Snowflake SECRET (type=PASSWORD)
# as environment variables: REGISTRY_USERNAME and REGISTRY_PASSWORD
#
# Build output is captured to a log file to avoid filling the 1000-line
# SPCS log buffer with verbose apt-get/pip output.

set -e

REGISTRY_HOST="${REGISTRY_HOST:-SET_ME.registry.snowflakecomputing.com}"
LOG_FILE="/kaniko/build.log"

echo "[kaniko-entrypoint] Starting SPCS Kaniko build..."

# Validate that credentials were injected
if [ -z "$REGISTRY_USERNAME" ] || [ -z "$REGISTRY_PASSWORD" ]; then
    echo "[kaniko-entrypoint] ERROR: REGISTRY_USERNAME or REGISTRY_PASSWORD not set."
    echo "[kaniko-entrypoint] Ensure the job spec includes the secret with envVarName mappings."
    exit 1
fi

echo "[kaniko-entrypoint] Registry credentials found for user: ${REGISTRY_USERNAME}"

# Create docker config.json with basic auth for the SPCS registry
# Kaniko reads this from /kaniko/.docker/config.json
mkdir -p /kaniko/.docker

# Build the auth string: base64(username:password)
printf "%s:%s" "$REGISTRY_USERNAME" "$REGISTRY_PASSWORD" > /kaniko/auth_raw
AUTH=$(base64 /kaniko/auth_raw | tr -d '\n')

cat > /kaniko/.docker/config.json <<DOCKERCFG
{
  "auths": {
    "${REGISTRY_HOST}": {
      "auth": "${AUTH}"
    }
  }
}
DOCKERCFG

# Clean up temp files
rm -f /kaniko/auth_raw

echo "[kaniko-entrypoint] Docker config.json created for ${REGISTRY_HOST}"
echo "[kaniko-entrypoint] Build context contents:"
ls -la /workspace/

echo "[kaniko-entrypoint] Starting Kaniko executor..."
echo "[kaniko-entrypoint] Build started at: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "[kaniko-entrypoint] Build output captured to ${LOG_FILE} (last 200 lines shown on completion)"

# Run Kaniko executor, capturing all output to log file
# Use set +e to capture exit code without exiting
set +e
/kaniko/executor "$@" > "$LOG_FILE" 2>&1
KANIKO_EXIT=$?
set -e

echo "[kaniko-entrypoint] Build finished at: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "[kaniko-entrypoint] Kaniko exit code: ${KANIKO_EXIT}"
echo "[kaniko-entrypoint] Log file size: $(wc -c < "$LOG_FILE") bytes, $(wc -l < "$LOG_FILE") lines"
echo "--- LAST 200 LINES OF BUILD LOG ---"
tail -200 "$LOG_FILE"
echo "--- END BUILD LOG ---"

exit $KANIKO_EXIT
```

## Key Design Notes

- **`/busybox/sh`**: The Kaniko debug image only ships busybox — no bash, no coreutils.
- **`REGISTRY_HOST` env var**: Injected via the job spec `env` block. The default is a placeholder; each account must set its own.
- **Log capture**: SPCS only exposes 1000 lines via `SYSTEM$GET_SERVICE_LOGS`. Verbose Docker builds (apt-get, pip) easily exceed that. The script captures everything to `/kaniko/build.log` and tails the last 200 lines.
- **`"$@"` passthrough**: All Kaniko flags (`--dockerfile`, `--destination`, `--context`, `--cache`, etc.) are passed as args from the job spec `command` list.
- **Exit code preservation**: The script captures Kaniko's exit code and re-exits with it so SPCS correctly reports job success/failure.
