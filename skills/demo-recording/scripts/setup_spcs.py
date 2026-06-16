#!/usr/bin/env python3
"""
setup_spcs.py - One-time setup to deploy voice cloning to a Snowflake account.

Two main assets are deployed:
  1. Docker image (code + dependencies, ~8GB) — copied from GitLab via crane
  2. Model weights (~2.5GB) — downloaded from HuggingFace, uploaded to Snowflake stage

Splitting the image from the model weights solves the SSO token expiry problem:
no single upload exceeds ~2GB, so SSO tokens don't expire mid-push.

Flow:
  1. Download crane (single Go binary) if not already present
  2. Create image repo + copy image from GitLab -> Snowflake
  3. Create stage + download model weights + PUT to stage
  4. Create network rule, access integration, compute pool

Usage:
    python <SKILL_DIR>/scripts/setup_spcs.py --connection <snowflake_connection_name>
    python <SKILL_DIR>/scripts/setup_spcs.py --check --connection <snowflake_connection_name>
"""

import argparse
import glob
import os
import pathlib
import platform
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
import tarfile
import shutil

GITLAB_IMAGE = "registry.snow.gitlab-dedicated.com/snowflakecorp/se/sales-engineering/se-cortex-code-skills/demo-recording/voice-cloner"
GITLAB_TAG = "latest"

MODEL_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
MODEL_STAGE_PREFIX = "model"
MODEL_READY_SENTINEL = ".model_ready"

DEFAULT_REPO_NAME = "VOICE_CLONE_REPO"
IMAGE_NAME = "voice-cloner"
IMAGE_TAG = "latest"
CRANE_FAIL_EXIT_CODE = 42
CRANE_STATUS_FILE = ".crane_status.json"
DEFAULT_STAGE_NAME = "VOICE_CLONE_STAGE"
DEFAULT_POOL_NAME = "DEMO_GPU_SE_POOL"
INSTANCE_FAMILY = "GPU_NV_S"
DEFAULT_NETWORK_RULE_NAME = "VOICE_CLONE_EGRESS_RULE"
DEFAULT_ACCESS_INTEGRATION_NAME = "VOICE_CLONE_ACCESS_INTEGRATION"

EGRESS_DOMAINS = [
    "pypi.org",
    "files.pythonhosted.org",
    "huggingface.co",
    "hub.huggingface.co",
    "cdn-lfs.huggingface.co",
    "cdn-lfs-us-1.huggingface.co",
    "cdn-lfs.hf.co",
    "cdn-lfs-us-1.hf.co",
    "cdn-lfs-eu-1.hf.co",
    "transfer.xethub.hf.co",
    "cas-server.xethub.hf.co",
    "cas-bridge.xethub.hf.co",
]

CRANE_VERSION = "0.20.3"
CRANE_URLS = {
    ("Windows", "AMD64"): f"https://github.com/google/go-containerregistry/releases/download/v{CRANE_VERSION}/go-containerregistry_Windows_x86_64.tar.gz",
    ("Darwin", "x86_64"): f"https://github.com/google/go-containerregistry/releases/download/v{CRANE_VERSION}/go-containerregistry_Darwin_x86_64.tar.gz",
    ("Darwin", "arm64"): f"https://github.com/google/go-containerregistry/releases/download/v{CRANE_VERSION}/go-containerregistry_Darwin_arm64.tar.gz",
    ("Linux", "x86_64"): f"https://github.com/google/go-containerregistry/releases/download/v{CRANE_VERSION}/go-containerregistry_Linux_x86_64.tar.gz",
}


def log(msg: str):
    ts = time.strftime("%H:%M:%S", time.localtime())
    print(f"[{ts}] {msg}", flush=True)


def get_connection(connection_name: str):
    resolved = os.getenv("SNOWFLAKE_CONNECTION_NAME") or connection_name
    try:
        import snowflake.connector
        return snowflake.connector.connect(connection_name=resolved)
    except Exception as oauth_err:
        log(f"Python connector auth failed: {oauth_err}")
        log("Falling back to snow CLI session token...")
        return _get_connection_via_snow_cli(resolved)


def _get_connection_via_snow_cli(connection_name: str):
    snow_cmd = shutil.which("snow") or shutil.which("snow.exe")
    if not snow_cmd:
        log("ERROR: Both Python connector OAuth and snow CLI unavailable.")
        log("  Install snow CLI: pip install snowflake-cli")
        sys.exit(1)
    try:
        result = subprocess.run(
            [snow_cmd, "connection", "test", "--connection", connection_name],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            log(f"snow CLI connection test failed: {result.stderr.strip()[:200]}")
            sys.exit(1)
    except Exception as e:
        log(f"snow CLI connection test error: {e}")
        sys.exit(1)
    import snowflake.connector
    conn = snowflake.connector.connect(connection_name=connection_name)
    return conn


def _ensure_role(conn) -> str:
    for role in ["ACCOUNTADMIN", "SYSADMIN"]:
        try:
            conn.cursor().execute(f"USE ROLE {role}")
            log(f"Using role: {role}")
            return role
        except Exception:
            pass
    try:
        rows = conn.cursor().execute("SELECT CURRENT_ROLE()").fetchall()
        role = rows[0][0] if rows else "UNKNOWN"
        log(f"Using current role: {role}")
        return role
    except Exception:
        return "UNKNOWN"


def sql(conn, query: str, fetch: bool = True):
    cur = conn.cursor()
    try:
        cur.execute(query)
        if fetch:
            return cur.fetchall()
        return []
    finally:
        cur.close()


def _to_file_uri(path: str) -> str:
    return pathlib.PurePosixPath(pathlib.Path(path).resolve()).as_posix()


# ---------------------------------------------------------------------------
# Crane helpers
# ---------------------------------------------------------------------------

def get_crane_path() -> str:
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bin_dir = os.path.join(skill_dir, ".bin")
    ext = ".exe" if platform.system() == "Windows" else ""
    return os.path.join(bin_dir, f"crane{ext}")


def ensure_crane() -> str:
    crane_path = get_crane_path()
    if os.path.isfile(crane_path):
        log(f"crane found: {crane_path}")
        return crane_path
    if shutil.which("crane"):
        log("crane found on PATH")
        return "crane"

    system = platform.system()
    machine = platform.machine()
    url = CRANE_URLS.get((system, machine))
    if not url:
        log(f"ERROR: No crane binary for {system}/{machine}")
        sys.exit(1)

    bin_dir = os.path.dirname(crane_path)
    os.makedirs(bin_dir, exist_ok=True)
    archive_path = os.path.join(bin_dir, "crane_archive.tar.gz")
    log(f"Downloading crane v{CRANE_VERSION} for {system}/{machine}...")
    urllib.request.urlretrieve(url, archive_path)

    log("Extracting crane...")
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            if "crane" in member.name.lower():
                member.name = os.path.basename(crane_path)
                tar.extract(member, bin_dir, filter="data")
                break
    os.remove(archive_path)
    if system != "Windows":
        os.chmod(crane_path, os.stat(crane_path).st_mode | stat.S_IEXEC)
    if not os.path.isfile(crane_path):
        log("ERROR: crane extraction failed")
        sys.exit(1)
    log(f"crane installed: {crane_path}")
    return crane_path


def get_snowflake_registry_url(conn) -> str:
    rows = sql(conn, "SELECT CURRENT_ACCOUNT_NAME()")
    account = rows[0][0].lower()
    rows2 = sql(conn, "SELECT CURRENT_ORGANIZATION_NAME()")
    org = rows2[0][0].lower()
    return f"{org}-{account}.registry.snowflakecomputing.com".replace("_", "-")


GITLAB_REGISTRY = "registry.snow.gitlab-dedicated.com"


def _create_isolated_config() -> str:
    import json
    config_dir = tempfile.mkdtemp(prefix="crane_cfg_")
    with open(os.path.join(config_dir, "config.json"), "w") as f:
        json.dump({"auths": {}}, f)
    return config_dir


def _snow_registry_login(config_dir: str, connection_name: str) -> bool:
    snow_cmd = shutil.which("snow") or shutil.which("snow.exe")
    if not snow_cmd:
        log("  ERROR: `snow` CLI not found. Install: pip install snowflake-cli")
        return False
    env = os.environ.copy()
    env["DOCKER_CONFIG"] = config_dir
    try:
        result = subprocess.run(
            [snow_cmd, "spcs", "image-registry", "login",
             "--connection", connection_name],
            capture_output=True, text=True, env=env, timeout=120,
        )
        if result.returncode == 0:
            return True
        log(f"  snow registry login failed: {result.stderr.strip()[:200]}")
    except subprocess.TimeoutExpired:
        log("  snow registry login timed out (120s)")
    except Exception as e:
        log(f"  snow registry login error: {e}")
    return False


def _verify_sf_auth(crane_path: str, config_dir: str, sf_registry: str) -> bool:
    env = os.environ.copy()
    env["DOCKER_CONFIG"] = config_dir
    try:
        result = subprocess.run(
            [crane_path, "catalog", sf_registry],
            capture_output=True, text=True, env=env, timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


GITLAB_AUTH_FAIL_EXIT_CODE = 43
GITLAB_AUTH_STATUS_FILE = ".gitlab_auth_status.json"


def _ensure_gitlab_auth(crane_path: str, config_dir: str, gitlab_token: str = None) -> bool:
    env = os.environ.copy()
    env["DOCKER_CONFIG"] = config_dir
    try:
        probe = subprocess.run(
            [crane_path, "manifest", f"{GITLAB_IMAGE}:{GITLAB_TAG}"],
            capture_output=True, text=True, env=env, timeout=30,
        )
        if probe.returncode == 0:
            return True
    except Exception:
        pass

    token = gitlab_token or os.environ.get("GITLAB_TOKEN")
    if token:
        log("  Authenticating to GitLab registry with provided token...")
        try:
            result = subprocess.run(
                [crane_path, "auth", "login", GITLAB_REGISTRY,
                 "-u", "token", "--password-stdin"],
                input=token, capture_output=True, text=True, env=env, timeout=30,
            )
            if result.returncode == 0:
                return True
            log(f"  Token auth failed: {result.stderr.strip()[:200]}")
        except Exception as e:
            log(f"  Token auth error: {e}")

    log("  GitLab registry auth required. Trying interactive login...")
    try:
        result = subprocess.run(
            [crane_path, "auth", "login", GITLAB_REGISTRY],
            env=env, timeout=120,
        )
        if result.returncode == 0:
            return True
    except Exception as e:
        log(f"  GitLab interactive auth error: {e}")

    import json as _json
    status = {
        "event": "gitlab_auth_failed",
        "registry": GITLAB_REGISTRY,
        "image": f"{GITLAB_IMAGE}:{GITLAB_TAG}",
    }
    status_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), GITLAB_AUTH_STATUS_FILE)
    with open(status_path, "w") as f:
        _json.dump(status, f, indent=2)
    log(f"  GitLab auth status written to {GITLAB_AUTH_STATUS_FILE}")
    log("  Exiting for agent to prompt user for GitLab token.")
    sys.exit(GITLAB_AUTH_FAIL_EXIT_CODE)


def copy_image(crane_path: str, source: str, dest: str, sf_registry: str, connection_name: str, max_retries: int = 3, resume_attempt: int = 1, gitlab_token: str = None):
    log(f"Source: {source}")
    log(f"Dest:   {dest}")
    log(f"Copying image (up to {max_retries} attempts, resumable — skips already-pushed layers)...")

    config_dir = _create_isolated_config()
    try:
        log("  Authenticating to Snowflake registry via `snow spcs image-registry login`...")
        if not _snow_registry_login(config_dir, connection_name):
            log("  ERROR: Snowflake registry login failed.")
            log("  Run manually: snow spcs image-registry login --connection " + connection_name)
            sys.exit(1)

        if not _verify_sf_auth(crane_path, config_dir, sf_registry):
            log("  WARNING: Auth verification probe failed — proceeding anyway (probe may lack permissions)")

        log("  Snowflake auth OK.")

        if not _ensure_gitlab_auth(crane_path, config_dir, gitlab_token=gitlab_token):
            log("  ERROR: Cannot authenticate to GitLab registry.")
            log("  Run: crane auth login registry.snow.gitlab-dedicated.com")
            sys.exit(1)
        log("  GitLab auth OK.")

        for attempt in range(resume_attempt, max_retries + 1):
            log(f"  Attempt {attempt}/{max_retries}: starting copy with serialized uploads (-j 1)...")

            if attempt > resume_attempt or resume_attempt > 1:
                log("  Re-authenticating to Snowflake (fresh token)...")
                if not _snow_registry_login(config_dir, connection_name):
                    log("  WARNING: Re-auth failed, trying copy with existing credentials...")

            env = os.environ.copy()
            env["DOCKER_CONFIG"] = config_dir

            start_time = time.time()
            result = subprocess.run(
                [crane_path, "copy", "-j", "1", source, dest],
                capture_output=True, text=True, env=env,
            )
            elapsed = time.time() - start_time

            if result.returncode == 0:
                log(f"  Image copied successfully in {elapsed:.0f}s!")
                return

            stderr = result.stderr.strip()
            log(f"  Attempt {attempt} failed after {elapsed:.0f}s:")
            log(f"    {stderr[:300]}")

            if attempt < max_retries:
                import json as _json
                has_docker = bool(shutil.which("docker"))
                status = {
                    "event": "crane_attempt_failed",
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "elapsed_seconds": int(elapsed),
                    "error": stderr[:500],
                    "docker_available": has_docker,
                    "dest": dest,
                }
                status_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CRANE_STATUS_FILE)
                with open(status_path, "w") as f:
                    _json.dump(status, f, indent=2)
                log(f"  Crane status written to {CRANE_STATUS_FILE}")
                log("  Exiting for agent to prompt user (retry / Docker fallback / quit).")
                sys.exit(CRANE_FAIL_EXIT_CODE)
    finally:
        try:
            shutil.rmtree(config_dir, ignore_errors=True)
        except Exception:
            pass

    log(f"ERROR: crane copy failed after {max_retries} attempts")
    log("  You can retry this script, or try: python setup_spcs.py --docker --connection <conn>")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def ensure_image_repo(conn, database: str, schema: str, repo_name: str) -> str:
    fqn = f"{database}.{schema}.{repo_name}"
    sql(conn, f"CREATE IMAGE REPOSITORY IF NOT EXISTS {fqn}", fetch=False)
    rows = sql(conn, f"SHOW IMAGE REPOSITORIES LIKE '{repo_name}' IN SCHEMA {database}.{schema}")
    if rows:
        return rows[0][4]
    raise RuntimeError(f"Failed to find image repository {fqn}")


def check_image_exists(conn, database: str, schema: str, repo_name: str) -> str | None:
    try:
        rows = sql(conn, "SHOW IMAGE REPOSITORIES IN ACCOUNT")
        for row in rows:
            r_name = row[1]
            r_url = row[4]
            r_db = row[2]
            r_schema = row[3]
            try:
                fqn = f"{r_db}.{r_schema}.{r_name}"
                img_rows = sql(conn, f"SHOW IMAGES IN IMAGE REPOSITORY {fqn}")
                for img_row in img_rows:
                    if IMAGE_NAME in str(img_row):
                        found = f"{r_url}/{IMAGE_NAME}:{IMAGE_TAG}"
                        if r_db.upper() != database.upper() or r_schema.upper() != schema.upper():
                            log(f"  (found in {r_db}.{r_schema}, not {database}.{schema})")
                        return found
            except Exception:
                pass
    except Exception:
        pass
    try:
        fqn = f"{database}.{schema}.{repo_name}"
        rows = sql(conn, f"SHOW IMAGE REPOSITORIES LIKE '{repo_name}' IN SCHEMA {database}.{schema}")
        if not rows:
            return None
        repo_url = rows[0][4]
        images = sql(conn, f"SELECT SYSTEM$REGISTRY_LIST_IMAGES('/{database}/{schema}/{repo_name}')")
        if images and IMAGE_NAME in str(images[0][0]):
            return f"{repo_url}/{IMAGE_NAME}:{IMAGE_TAG}"
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Model weight staging
# ---------------------------------------------------------------------------

def check_model_staged(conn, stage_fqn: str) -> bool:
    try:
        rows = sql(conn, f"LIST @{stage_fqn}/{MODEL_STAGE_PREFIX}/{MODEL_READY_SENTINEL}")
        return len(rows) > 0
    except Exception:
        return False


def download_model_weights(dest_dir: str):
    log(f"Downloading model weights: {MODEL_ID}")
    log("  This downloads ~2.5GB of model files from HuggingFace...")
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        log("  Installing huggingface_hub...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "huggingface_hub"])
        from huggingface_hub import snapshot_download

    model_dir = snapshot_download(
        MODEL_ID,
        local_dir=dest_dir,
        local_dir_use_symlinks=False,
    )
    log(f"  Downloaded to: {model_dir}")

    total_size = 0
    file_count = 0
    for root, _, files in os.walk(model_dir):
        for f in files:
            fp = os.path.join(root, f)
            if os.path.isfile(fp):
                total_size += os.path.getsize(fp)
                file_count += 1
    log(f"  {file_count} files, {total_size / (1024**3):.2f} GB total")
    return model_dir


def upload_model_to_stage(conn, stage_fqn: str, model_dir: str):
    log("Uploading model weights to Snowflake stage...")
    log(f"  Stage: @{stage_fqn}/{MODEL_STAGE_PREFIX}/")

    all_files = []
    for root, _, files in os.walk(model_dir):
        for f in files:
            fp = os.path.join(root, f)
            if os.path.isfile(fp) and not f.startswith("."):
                rel = os.path.relpath(fp, model_dir).replace("\\", "/")
                all_files.append((fp, rel))

    uploaded = 0
    for fp, rel in all_files:
        size_mb = os.path.getsize(fp) / (1024 * 1024)
        stage_path = f"@{stage_fqn}/{MODEL_STAGE_PREFIX}/{os.path.dirname(rel)}" if os.path.dirname(rel) else f"@{stage_fqn}/{MODEL_STAGE_PREFIX}"
        log(f"  [{uploaded+1}/{len(all_files)}] {rel} ({size_mb:.1f} MB)")
        sql(conn, f"PUT 'file://{_to_file_uri(fp)}' '{stage_path}/' AUTO_COMPRESS=FALSE OVERWRITE=TRUE", fetch=False)
        uploaded += 1

    sentinel_path = os.path.join(model_dir, MODEL_READY_SENTINEL)
    with open(sentinel_path, "w") as f:
        f.write(f"model={MODEL_ID}\nuploaded={time.strftime('%Y-%m-%dT%H:%M:%S')}\nfiles={uploaded}\n")
    sql(conn, f"PUT 'file://{_to_file_uri(sentinel_path)}' '@{stage_fqn}/{MODEL_STAGE_PREFIX}/' AUTO_COMPRESS=FALSE OVERWRITE=TRUE", fetch=False)

    log(f"  Uploaded {uploaded} files + sentinel to @{stage_fqn}/{MODEL_STAGE_PREFIX}/")


# ---------------------------------------------------------------------------
# Status check
# ---------------------------------------------------------------------------

def check_setup_status(conn, database: str, schema: str, repo_name: str,
                       stage_name: str, rule_name: str, integration_name: str):
    log("Checking setup status...")
    log("=" * 60)

    image_fqn = check_image_exists(conn, database, schema, repo_name)

    stage_fqn = f"{database}.{schema}.{stage_name}"
    model_staged = check_model_staged(conn, stage_fqn)

    pool_exists = False
    pool_state = None
    try:
        rows = sql(conn, "SHOW COMPUTE POOLS")
        for row in rows:
            if row[4].startswith("GPU") and not row[0].startswith("SYSTEM_"):
                pool_exists = True
                pool_state = row[1]
                break
    except Exception:
        pass

    rule_exists = False
    try:
        sql(conn, f"DESCRIBE NETWORK RULE {database}.{schema}.{rule_name}")
        rule_exists = True
    except Exception:
        pass

    integration_exists = False
    try:
        sql(conn, f"DESCRIBE INTEGRATION {integration_name}")
        integration_exists = True
    except Exception:
        pass

    ok = lambda v: "OK" if v else "MISSING"
    log(f"  Docker image     : {ok(image_fqn)} {('(' + image_fqn + ')') if image_fqn else ''}")
    log(f"  Model weights    : {ok(model_staged)} {'(staged at @' + stage_fqn + '/' + MODEL_STAGE_PREFIX + '/)' if model_staged else ''}")
    log(f"  GPU compute pool : {ok(pool_exists)} {('(state: ' + pool_state + ')') if pool_state else ''}")
    log(f"  Network rule     : {ok(rule_exists)}")
    log(f"  Access integration: {ok(integration_exists)}")
    log("")

    all_ok = all([image_fqn, model_staged, pool_exists, rule_exists, integration_exists])
    if all_ok:
        log("All components ready. You can run clone_voice_spcs.py.")
    else:
        log("Setup incomplete. Run setup_spcs.py without --check to complete.")
    return all_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Set up SPCS voice cloning (one-time)")
    parser.add_argument("--connection", default="default", help="Snowflake connection name")
    parser.add_argument("--database", default=None, help="Database (default: current)")
    parser.add_argument("--schema", default=None, help="Schema (default: current)")
    parser.add_argument("--check", action="store_true", help="Check setup status")
    parser.add_argument("--skip-image", action="store_true", help="Skip image copy")
    parser.add_argument("--skip-model", action="store_true", help="Skip model weight upload")
    parser.add_argument("--docker", action="store_true", help="Use local Docker build instead of crane")
    parser.add_argument("--retry-crane", action="store_true",
                        help="Resume a previously failed crane copy (picks up from last attempt)")
    parser.add_argument("--gitlab-token", default=None,
                        help="GitLab PAT for authenticating to the container registry (also reads GITLAB_TOKEN env var)")
    args = parser.parse_args()

    conn = get_connection(args.connection)
    role = _ensure_role(conn)

    db_row = sql(conn, "SELECT CURRENT_DATABASE()")
    schema_row = sql(conn, "SELECT CURRENT_SCHEMA()")
    database = args.database or (db_row[0][0] if db_row and db_row[0][0] else "VOICE_CLONE_DB")
    schema = args.schema or (schema_row[0][0] if schema_row and schema_row[0][0] else "PUBLIC")

    stage_name = DEFAULT_STAGE_NAME

    if args.check:
        ready = check_setup_status(conn, database, schema, DEFAULT_REPO_NAME,
                                   stage_name, DEFAULT_NETWORK_RULE_NAME,
                                   DEFAULT_ACCESS_INTEGRATION_NAME)
        sys.exit(0 if ready else 1)

    log("=" * 60)
    log("SPCS VOICE CLONING SETUP")
    log("=" * 60)
    log(f"Role: {role}")
    log(f"Database: {database}, Schema: {schema}")
    log("")

    try:
        sql(conn, f"CREATE DATABASE IF NOT EXISTS {database}", fetch=False)
    except Exception:
        pass
    try:
        sql(conn, f"CREATE SCHEMA IF NOT EXISTS {database}.{schema}", fetch=False)
    except Exception:
        pass

    # Step 1: Image repository + copy
    log("--- Step 1: Docker Image ---")
    repo_url = ensure_image_repo(conn, database, schema, DEFAULT_REPO_NAME)
    dest_image = f"{repo_url}/{IMAGE_NAME}:{IMAGE_TAG}"
    log(f"Repository: {repo_url}")

    if not args.skip_image:
        existing = check_image_exists(conn, database, schema, DEFAULT_REPO_NAME)
        if existing:
            log(f"Image already exists: {existing}")
        elif args.docker:
            spcs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spcs")
            from clone_voice_spcs import _docker_build_and_push
            _docker_build_and_push(repo_url, spcs_dir)
        else:
            crane_path = ensure_crane()
            sf_registry = get_snowflake_registry_url(conn)
            resume_attempt = 1
            if args.retry_crane:
                import json as _json
                status_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CRANE_STATUS_FILE)
                if os.path.isfile(status_path):
                    try:
                        with open(status_path, "r") as f:
                            prev = _json.load(f)
                        resume_attempt = prev.get("attempt", 0) + 1
                        log(f"Resuming crane copy from attempt {resume_attempt} (previous failed at attempt {prev.get('attempt')})")
                        os.remove(status_path)
                    except Exception:
                        pass
            copy_image(crane_path, f"{GITLAB_IMAGE}:{GITLAB_TAG}", dest_image, sf_registry, args.connection, resume_attempt=resume_attempt, gitlab_token=args.gitlab_token)

    try:
        sql(conn, f"GRANT READ ON IMAGE REPOSITORY {database}.{schema}.{DEFAULT_REPO_NAME} TO ROLE {role}", fetch=False)
    except Exception:
        pass
    log("")

    # Step 2: Stage + model weights
    log("--- Step 2: Model Weights ---")
    stage_fqn = f"{database}.{schema}.{stage_name}"
    sql(conn, f"CREATE STAGE IF NOT EXISTS {stage_fqn} ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')", fetch=False)
    log(f"Stage: @{stage_fqn}")

    if not args.skip_model:
        if check_model_staged(conn, stage_fqn):
            log(f"Model weights already staged at @{stage_fqn}/{MODEL_STAGE_PREFIX}/")
        else:
            with tempfile.TemporaryDirectory(prefix="qwen_tts_") as tmpdir:
                model_dir = download_model_weights(tmpdir)
                upload_model_to_stage(conn, stage_fqn, model_dir)
    log("")

    # Step 3: Network rule
    log("--- Step 3: Network Rule ---")
    rule_fqn = f"{database}.{schema}.{DEFAULT_NETWORK_RULE_NAME}"
    port_list = ", ".join(f"'{d}:443'" for d in EGRESS_DOMAINS)
    try:
        sql(conn, f"DROP NETWORK RULE IF EXISTS {rule_fqn}", fetch=False)
    except Exception:
        pass
    sql(conn, f"""
        CREATE NETWORK RULE {rule_fqn}
        MODE = EGRESS TYPE = HOST_PORT
        VALUE_LIST = ({port_list})
    """, fetch=False)
    log(f"Created: {rule_fqn}")
    log("")

    # Step 4: External access integration
    log("--- Step 4: External Access Integration ---")
    try:
        sql(conn, f"DROP INTEGRATION IF EXISTS {DEFAULT_ACCESS_INTEGRATION_NAME}", fetch=False)
    except Exception:
        pass
    sql(conn, f"""
        CREATE EXTERNAL ACCESS INTEGRATION {DEFAULT_ACCESS_INTEGRATION_NAME}
        ALLOWED_NETWORK_RULES = ({rule_fqn})
        ENABLED = TRUE
    """, fetch=False)
    log(f"Created: {DEFAULT_ACCESS_INTEGRATION_NAME}")
    log("")

    # Step 5: GPU compute pool
    log("--- Step 5: GPU Compute Pool ---")
    rows = sql(conn, "SHOW COMPUTE POOLS")
    has_gpu = any(r[4].startswith("GPU") and not r[0].startswith("SYSTEM_") for r in rows)
    if has_gpu:
        for r in rows:
            if r[4].startswith("GPU") and not r[0].startswith("SYSTEM_"):
                log(f"Existing GPU pool: {r[0]} (state: {r[1]})")
                break
    else:
        log(f"Creating GPU compute pool: {DEFAULT_POOL_NAME}")
        try:
            sql(conn, f"""
                CREATE COMPUTE POOL IF NOT EXISTS {DEFAULT_POOL_NAME}
                MIN_NODES = 1 MAX_NODES = 1
                INSTANCE_FAMILY = {INSTANCE_FAMILY}
                AUTO_RESUME = TRUE
                AUTO_SUSPEND_SECS = 300
            """, fetch=False)
            log(f"Created: {DEFAULT_POOL_NAME}")
        except Exception as e:
            log(f"WARNING: Could not create compute pool: {e}")
    log("")

    log("=" * 60)
    log("SETUP COMPLETE")
    log("=" * 60)
    log("")
    log("Run voice cloning with:")
    log("  python clone_voice_spcs.py \\")
    log("    --voice-sample <path/to/voice.wav> \\")
    log("    --script <path/to/RECORDING_SCRIPT.md> \\")
    log("    --output-dir <output/dir> \\")
    log(f"    --connection {args.connection}")
    log("")

    conn.close()


if __name__ == "__main__":
    main()
