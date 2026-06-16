#!/usr/bin/env python3
"""
clone_voice_spcs.py - Orchestrate voice cloning on Snowflake GPU via SPCS.

Single-command orchestrator that handles the full lifecycle:
  1. Ensure GPU compute pool exists and is active
  2. Ensure image repository + Docker image are available (with digest-based freshness check)
  3. Create/update network rule with required egress domains
  4. Create/update external access integration
  5. Upload voice sample + recording script to stage
  6. Run EXECUTE JOB SERVICE with external access + GPU
  7. Stream container logs with live progress
  8. Download generated audio locally
  9. Suspend compute pool to save credits

Usage:
    python <SKILL_DIR>/scripts/clone_voice_spcs.py \
        --voice-sample /path/to/my_voice.wav \
        --script /path/to/RECORDING_SCRIPT.md \
        --output-dir /local/output/dir \
        --connection <snowflake_connection_name>

    python <SKILL_DIR>/scripts/clone_voice_spcs.py \
        --check --connection <snowflake_connection_name>
"""

import argparse
import hashlib
import json
import os
import pathlib
import platform
import sys
import tempfile
import time
import subprocess
import shutil

DEFAULT_POOL_NAME = "DEMO_GPU_SE_POOL"
INSTANCE_FAMILY = "GPU_NV_S"
DEFAULT_REPO_NAME = "VOICE_CLONE_REPO"
IMAGE_NAME = "voice-cloner"
IMAGE_TAG = "latest"
DEFAULT_STAGE_NAME = "VOICE_CLONE_STAGE"
DEFAULT_JOB_NAME = "VOICE_CLONE_JOB"
DEFAULT_NETWORK_RULE_NAME = "VOICE_CLONE_EGRESS_RULE"
DEFAULT_ACCESS_INTEGRATION_NAME = "VOICE_CLONE_ACCESS_INTEGRATION"

DIGEST_FILE = ".image_digest"
CRANE_FAIL_EXIT_CODE = 42
CRANE_STATUS_FILE = ".crane_status.json"
MODEL_STAGE_PREFIX = "model"
MODEL_READY_SENTINEL = ".model_ready"

GITLAB_IMAGE = "registry.snow.gitlab-dedicated.com/snowflakecorp/se/sales-engineering/se-cortex-code-skills/demo-recording/voice-cloner"
GITLAB_TAG = "latest"

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


def log(msg: str):
    ts = time.strftime("%H:%M:%S", time.localtime())
    print(f"[{ts}] {msg}", flush=True)


def _digest_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "spcs", DIGEST_FILE)


def _compute_build_context_hash(spcs_dir: str) -> str:
    h = hashlib.sha256()
    for fname in sorted(os.listdir(spcs_dir)):
        fpath = os.path.join(spcs_dir, fname)
        if os.path.isfile(fpath) and not fname.startswith("."):
            h.update(fname.encode())
            with open(fpath, "rb") as f:
                h.update(f.read())
    return h.hexdigest()[:16]


def _read_saved_digest() -> dict:
    path = _digest_path()
    if os.path.isfile(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_digest(registry_digest: str, build_hash: str):
    path = _digest_path()
    with open(path, "w") as f:
        json.dump({"registry_digest": registry_digest, "build_hash": build_hash, "pushed_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, f)


def get_connection(connection_name: str):
    resolved = os.getenv("SNOWFLAKE_CONNECTION_NAME") or connection_name
    os.environ["SNOWFLAKE_DEFAULT_CONNECTION_NAME"] = resolved
    try:
        import snowflake.connector
        conn = snowflake.connector.connect(connection_name=resolved)
        return conn
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
    result = subprocess.run(
        [snow_cmd, "sql", "-q", "SELECT CURRENT_ACCOUNT()", "--connection", connection_name, "-o", "output_format=json"],
        capture_output=True, text=True, timeout=30,
    )
    conn = snowflake.connector.connect(connection_name=connection_name)
    return conn


def _ensure_role(conn) -> str:
    try:
        rows = sql(conn, "SELECT CURRENT_ROLE()")
        current_role = rows[0][0] if rows else None
    except Exception:
        current_role = None

    try:
        conn.cursor().execute("USE ROLE ACCOUNTADMIN")
        log("Using role: ACCOUNTADMIN")
        return "ACCOUNTADMIN"
    except Exception:
        pass

    try:
        conn.cursor().execute("USE ROLE SYSADMIN")
        log("Using role: SYSADMIN")
        return "SYSADMIN"
    except Exception:
        pass

    if current_role:
        log(f"Using current role: {current_role}")
        log("  NOTE: Some operations may fail if this role lacks CREATE COMPUTE POOL, CREATE INTEGRATION privileges.")
        log("  Ask your admin: GRANT CREATE COMPUTE POOL ON ACCOUNT TO ROLE <your_role>;")
        return current_role

    log("WARNING: Could not determine current role.")
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


def ensure_database_schema(conn, database: str, schema: str):
    try:
        sql(conn, f"CREATE DATABASE IF NOT EXISTS {database}", fetch=False)
    except Exception:
        pass
    try:
        sql(conn, f"CREATE SCHEMA IF NOT EXISTS {database}.{schema}", fetch=False)
    except Exception:
        pass
    try:
        sql(conn, f"USE DATABASE {database}", fetch=False)
        sql(conn, f"USE SCHEMA {schema}", fetch=False)
    except Exception as e:
        log(f"WARNING: Could not USE {database}.{schema}: {e}")


def ensure_compute_pool(conn, pool_name: str) -> str:
    log("Checking GPU compute pools...")
    rows = sql(conn, "SHOW COMPUTE POOLS")

    if pool_name:
        for row in rows:
            if row[0] == pool_name:
                state = row[1]
                ifam = row[4]
                if state == "SUSPENDED":
                    try:
                        log(f"Resuming specified pool: {pool_name} ({ifam})")
                        sql(conn, f"ALTER COMPUTE POOL {pool_name} RESUME", fetch=False)
                        _wait_for_pool(conn, pool_name)
                    except Exception as e:
                        if "OPERATE" in str(e) or "Insufficient privileges" in str(e).lower():
                            log(f"  Note: Cannot manually resume {pool_name} (no OPERATE privilege).")
                            log(f"  Pool has AUTO_RESUME — job submission will wake it automatically.")
                        else:
                            raise
                elif state in ("IDLE", "ACTIVE"):
                    log(f"Using specified pool: {pool_name} (state: {state})")
                else:
                    log(f"Pool {pool_name} in state {state}, waiting...")
                    _wait_for_pool(conn, pool_name)
                return pool_name

    gpu_pools = []
    for row in rows:
        pname = row[0]
        instance_family = row[4]
        state = row[1]
        if instance_family.startswith("GPU") and not pname.startswith("SYSTEM_"):
            gpu_pools.append((pname, state, instance_family))

    for pname, state, ifam in gpu_pools:
        if state == "SUSPENDED":
            try:
                log(f"Resuming existing GPU pool: {pname} ({ifam})")
                sql(conn, f"ALTER COMPUTE POOL {pname} RESUME", fetch=False)
                _wait_for_pool(conn, pname)
            except Exception as e:
                if "OPERATE" in str(e) or "Insufficient privileges" in str(e).lower():
                    log(f"  Note: Cannot manually resume {pname} (no OPERATE privilege).")
                    log(f"  Pool has AUTO_RESUME — job submission will wake it automatically.")
                else:
                    raise
        elif state in ("IDLE", "ACTIVE"):
            log(f"Using GPU pool: {pname} (state: {state})")
        else:
            log(f"GPU pool {pname} in state {state}, waiting...")
            _wait_for_pool(conn, pname)
        return pname

    log(f"No GPU pool found. Creating: {pool_name or DEFAULT_POOL_NAME} ({INSTANCE_FAMILY})")
    try:
        sql(conn, f"""
            CREATE COMPUTE POOL IF NOT EXISTS {pool_name}
            MIN_NODES = 1 MAX_NODES = 1
            INSTANCE_FAMILY = {INSTANCE_FAMILY}
            AUTO_RESUME = TRUE
            AUTO_SUSPEND_SECS = 300
        """, fetch=False)
    except Exception as e:
        err = str(e)
        if "Insufficient privileges" in err or "access control" in err.lower():
            log(f"ERROR: Cannot create compute pool — insufficient privileges.")
            log(f"  Ask your admin to run:")
            log(f"    GRANT CREATE COMPUTE POOL ON ACCOUNT TO ROLE <your_role>;")
            log(f"  Or create a pool manually:")
            log(f"    CREATE COMPUTE POOL {pool_name} MIN_NODES=1 MAX_NODES=1 INSTANCE_FAMILY={INSTANCE_FAMILY};")
            sys.exit(1)
        raise
    _wait_for_pool(conn, pool_name)
    return pool_name


def _wait_for_pool(conn, pool_name: str, timeout: int = 600):
    log(f"Waiting for {pool_name} to become active (up to {timeout//60} min)...")
    start = time.time()
    while time.time() - start < timeout:
        rows = sql(conn, f"DESCRIBE COMPUTE POOL {pool_name}")
        if rows:
            state = rows[0][1]
            elapsed = int(time.time() - start)
            if state in ("ACTIVE", "IDLE"):
                log(f"  Pool {pool_name} is {state} ({elapsed}s)")
                return
            elif state == "SUSPENDED":
                sql(conn, f"ALTER COMPUTE POOL {pool_name} RESUME", fetch=False)
            else:
                if elapsed % 30 == 0:
                    log(f"  Pool state: {state} ({elapsed}s elapsed)")
        time.sleep(10)
    log(f"WARNING: Pool did not become active within {timeout}s. Proceeding anyway...")


def ensure_image_repo(conn, database: str, schema: str, repo_name: str, role: str = None) -> str:
    fqn = f"{database}.{schema}.{repo_name}"
    sql(conn, f"CREATE IMAGE REPOSITORY IF NOT EXISTS {fqn}", fetch=False)
    if role:
        try:
            sql(conn, f"GRANT READ ON IMAGE REPOSITORY {fqn} TO ROLE {role}", fetch=False)
            log(f"  Granted READ on {repo_name} to {role} (discoverable from any schema)")
        except Exception:
            pass
    rows = sql(conn, f"SHOW IMAGE REPOSITORIES LIKE '{repo_name}' IN SCHEMA {database}.{schema}")
    if rows:
        repo_url = rows[0][4]
        log(f"Image repository: {repo_url}")
        return repo_url
    raise RuntimeError(f"Failed to find image repository {fqn}")


def check_image_exists(conn, database: str, schema: str, repo_name: str) -> str | None:
    try:
        fqn = f"{database}.{schema}.{repo_name}"
        rows = sql(conn, f"SHOW IMAGE REPOSITORIES LIKE '{repo_name}' IN SCHEMA {database}.{schema}")
        if not rows:
            return None
        repo_url = rows[0][4]
        rows = sql(conn, f"SHOW IMAGES IN IMAGE REPOSITORY {fqn}")
        for row in rows:
            if IMAGE_NAME in str(row):
                return f"{repo_url}/{IMAGE_NAME}:{IMAGE_TAG}"
    except Exception:
        pass
    return None


def check_image_freshness(spcs_dir: str) -> dict:
    current_hash = _compute_build_context_hash(spcs_dir)
    saved = _read_saved_digest()
    saved_hash = saved.get("build_hash", "")
    pushed_at = saved.get("pushed_at", "unknown")

    result = {
        "current_hash": current_hash,
        "saved_hash": saved_hash,
        "pushed_at": pushed_at,
        "is_stale": current_hash != saved_hash,
        "has_digest": bool(saved_hash),
    }
    return result


def _re_auth_docker_registry(repo_url: str) -> bool:
    registry_host = repo_url.split("/")[0]
    log(f"Re-authenticating Docker to {registry_host}...")

    snow_cmd = shutil.which("snow") or shutil.which("snow.exe")
    if snow_cmd:
        try:
            result = subprocess.run(
                [snow_cmd, "spcs", "image-registry", "login"],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                log("  Docker re-authenticated via `snow spcs image-registry login`")
                return True
            log(f"  snow login failed: {result.stderr.strip()}")
        except Exception as e:
            log(f"  snow login error: {e}")

    log("  ERROR: Could not re-authenticate Docker to Snowflake registry.")
    log("  Run manually: snow spcs image-registry login --connection <your_connection>")
    log("  Then re-run this script with --skip-build if push succeeded.")
    return False


def _get_crane_path() -> str:
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bin_dir = os.path.join(skill_dir, ".bin")
    ext = ".exe" if platform.system() == "Windows" else ""
    return os.path.join(bin_dir, f"crane{ext}")


def _find_crane() -> str | None:
    crane_path = _get_crane_path()
    if os.path.isfile(crane_path):
        return crane_path
    if shutil.which("crane"):
        return "crane"
    return None


def _get_snowflake_registry_url(conn) -> str:
    rows = sql(conn, "SELECT CURRENT_ACCOUNT_NAME()")
    account = rows[0][0].lower()
    rows2 = sql(conn, "SELECT CURRENT_ORGANIZATION_NAME()")
    org = rows2[0][0].lower()
    return f"{org}-{account}.registry.snowflakecomputing.com".replace("_", "-")


GITLAB_REGISTRY = "registry.snow.gitlab-dedicated.com"


def _create_isolated_config() -> str:
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

    status = {
        "event": "gitlab_auth_failed",
        "registry": GITLAB_REGISTRY,
        "image": f"{GITLAB_IMAGE}:{GITLAB_TAG}",
    }
    status_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), GITLAB_AUTH_STATUS_FILE)
    with open(status_path, "w") as f:
        json.dump(status, f, indent=2)
    log(f"  GitLab auth status written to {GITLAB_AUTH_STATUS_FILE}")
    log("  Exiting for agent to prompt user for GitLab token.")
    sys.exit(GITLAB_AUTH_FAIL_EXIT_CODE)


def _read_crane_status() -> dict | None:
    status_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CRANE_STATUS_FILE)
    if os.path.isfile(status_path):
        try:
            with open(status_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _clear_crane_status():
    status_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CRANE_STATUS_FILE)
    try:
        os.remove(status_path)
    except OSError:
        pass


def _crane_copy_image(conn, repo_url: str, connection_name: str, max_retries: int = 3, resume_attempt: int = 1, gitlab_token: str = None) -> str | None:
    crane_path = _find_crane()
    if not crane_path:
        log("  crane not found — skipping crane copy")
        return None

    source = f"{GITLAB_IMAGE}:{GITLAB_TAG}"
    dest = f"{repo_url}/{IMAGE_NAME}:{IMAGE_TAG}"
    sf_registry = repo_url.split("/")[0]

    log(f"Copying image via crane (no Docker required)...")
    log(f"  Source: {source}")
    log(f"  Dest:   {dest}")
    log(f"  Retries: up to {max_retries} attempts (resumable — skips already-pushed layers)")

    config_dir = _create_isolated_config()
    try:
        log("  Authenticating to Snowflake registry via `snow spcs image-registry login`...")
        if not _snow_registry_login(config_dir, connection_name):
            log("  ERROR: Snowflake registry login failed.")
            log("  Run manually: snow spcs image-registry login --connection " + connection_name)
            return None

        if not _verify_sf_auth(crane_path, config_dir, sf_registry):
            log("  WARNING: Auth verification probe failed — proceeding anyway (probe may lack permissions)")

        log("  Snowflake auth OK.")

        if not _ensure_gitlab_auth(crane_path, config_dir, gitlab_token=gitlab_token):
            log("  ERROR: Cannot authenticate to GitLab registry.")
            log("  Run: crane auth login registry.snow.gitlab-dedicated.com")
            return None
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
                log(f"  Image copied successfully via crane in {elapsed:.0f}s!")
                build_hash = _compute_build_context_hash(
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "spcs")
                )
                _save_digest("crane-copied", build_hash)
                return dest

            stderr = result.stderr.strip()
            log(f"  Attempt {attempt} failed after {elapsed:.0f}s:")
            log(f"    {stderr[:300]}")

            if attempt < max_retries:
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
                    json.dump(status, f, indent=2)
                log(f"  Crane status written to {CRANE_STATUS_FILE}")
                log("  Exiting for agent to prompt user (retry / Docker fallback / quit).")
                sys.exit(CRANE_FAIL_EXIT_CODE)
    finally:
        try:
            shutil.rmtree(config_dir, ignore_errors=True)
        except Exception:
            pass

    log(f"  crane copy failed after {max_retries} attempts")
    return None


def _docker_build_and_push(repo_url: str, spcs_dir: str) -> str:
    full_image = f"{repo_url}/{IMAGE_NAME}:{IMAGE_TAG}"
    log(f"Building Docker image: {full_image}")
    log("  (This includes model weight download — may take 5-10 min on first build)")

    build_start = time.time()
    subprocess.run(["docker", "build", "-t", full_image, spcs_dir], check=True)
    build_elapsed = time.time() - build_start
    log(f"  Build completed in {build_elapsed:.0f}s")

    if build_elapsed > 300:
        log("  Build took >5 min — re-authenticating Docker before push (SSO tokens may expire)...")
        _re_auth_docker_registry(repo_url)

    log("Pushing image to Snowflake registry...")
    try:
        subprocess.run(["docker", "push", full_image], check=True)
    except subprocess.CalledProcessError:
        log("  Push failed — attempting Docker re-authentication...")
        if _re_auth_docker_registry(repo_url):
            subprocess.run(["docker", "push", full_image], check=True)
        else:
            log("FATAL: Docker push failed after re-auth. See instructions above.")
            sys.exit(1)

    build_hash = _compute_build_context_hash(spcs_dir)
    _save_digest("pushed", build_hash)
    log("Image pushed successfully.")
    return full_image


def ensure_image(conn, repo_url: str, spcs_dir: str, connection_name: str,
                  force_docker: bool = False, resume_attempt: int = 1,
                  gitlab_token: str = None) -> str:
    if not force_docker:
        image_fqn = _crane_copy_image(conn, repo_url, connection_name,
                                       resume_attempt=resume_attempt,
                                       gitlab_token=gitlab_token)
        if image_fqn:
            _clear_crane_status()
            return image_fqn

    log("Falling back to Docker build + push...")
    if not shutil.which("docker"):
        log("ERROR: Docker is not installed either.")
        log("")
        log("To get the image into your Snowflake account, pick one:")
        log("  Option A: Run setup_spcs.py first (downloads crane automatically):")
        log("    python setup_spcs.py --connection <conn>")
        log("  Option B: Install Docker Desktop:")
        log("    https://www.docker.com/products/docker-desktop/")
        log("    Then re-run this script.")
        sys.exit(1)

    log("Docker detected — building and pushing image...")
    log("  NOTE: Large layers may cause SSO token expiry. If push fails,")
    log("  run setup_spcs.py instead (uses crane, no SSO issues).")
    return _docker_build_and_push(repo_url, spcs_dir)


def try_ensure_egress(conn, database: str, schema: str, rule_name: str, integration_name: str) -> bool:
    fqn = f"{database}.{schema}.{rule_name}"
    port_list = ", ".join(f"'{d}:443'" for d in EGRESS_DOMAINS)

    log("Creating egress rules for HuggingFace API access...")
    log(f"  Egress domains: {len(EGRESS_DOMAINS)} (HuggingFace + XET CDN + PyPI)")

    try:
        try:
            sql(conn, f"DROP NETWORK RULE IF EXISTS {fqn}", fetch=False)
        except Exception:
            pass

        sql(conn, f"""
            CREATE NETWORK RULE {fqn}
            MODE = EGRESS
            TYPE = HOST_PORT
            VALUE_LIST = ({port_list})
        """, fetch=False)
        log(f"  Network rule created: {fqn}")

        try:
            sql(conn, f"DROP INTEGRATION IF EXISTS {integration_name}", fetch=False)
        except Exception:
            pass

        sql(conn, f"""
            CREATE EXTERNAL ACCESS INTEGRATION {integration_name}
            ALLOWED_NETWORK_RULES = ({fqn})
            ENABLED = TRUE
        """, fetch=False)
        log(f"  Integration created: {integration_name}")
        return True
    except Exception as e:
        err = str(e)
        if "Insufficient privileges" in err or "access control" in err.lower():
            log(f"  WARNING: Insufficient privileges to create network rules/integrations.")
            log(f"  Ask your admin:")
            log(f"    GRANT CREATE NETWORK RULE ON SCHEMA {database}.{schema} TO ROLE <your_role>;")
            log(f"    GRANT CREATE INTEGRATION ON ACCOUNT TO ROLE <your_role>;")
        else:
            log(f"  WARNING: Could not create egress rules: {e}")
        log("  Falling back to offline mode (model weights must be baked into image)")
        return False


def ensure_stage(conn, database: str, schema: str, stage_name: str) -> str:
    fqn = f"{database}.{schema}.{stage_name}"
    sql(conn, f"CREATE STAGE IF NOT EXISTS {fqn} ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')", fetch=False)
    return fqn


def _to_file_uri(path: str) -> str:
    return pathlib.PurePosixPath(pathlib.Path(path).resolve()).as_posix()


def upload_files(conn, stage_fqn: str, voice_sample: str, script_path: str = None):
    log("Uploading voice sample to stage...")
    sql(conn, f"PUT 'file://{_to_file_uri(voice_sample)}' @{stage_fqn}/input/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE", fetch=False)

    if script_path:
        log("Uploading recording script to stage...")
        sql(conn, f"PUT 'file://{_to_file_uri(script_path)}' @{stage_fqn}/input/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE", fetch=False)


def check_model_staged(conn, stage_fqn: str) -> bool:
    try:
        rows = sql(conn, f"LIST @{stage_fqn}/{MODEL_STAGE_PREFIX}/{MODEL_READY_SENTINEL}")
        return len(rows) > 0
    except Exception:
        return False


def find_model_stage_in_account(conn, current_stage_fqn: str) -> str | None:
    if check_model_staged(conn, current_stage_fqn):
        return current_stage_fqn
    log("Scanning account for existing model weights on other stages...")
    try:
        rows = sql(conn, "SHOW STAGES IN ACCOUNT")
        for row in rows:
            stage_db = row[2]
            stage_schema = row[3]
            stage_name = row[1]
            fqn = f"{stage_db}.{stage_schema}.{stage_name}"
            if fqn == current_stage_fqn:
                continue
            if DEFAULT_STAGE_NAME.lower() not in stage_name.lower():
                continue
            if check_model_staged(conn, fqn):
                log(f"  Found model weights on: @{fqn}")
                return fqn
    except Exception as e:
        log(f"  WARNING: Could not scan stages in account: {e}")
    return None


def run_job(conn, pool_name: str, image_fqn: str, stage_fqn: str,
            database: str, schema: str, job_name: str, integration_name: str,
            has_script: bool, text: str = None, needs_egress: bool = True,
            model_on_stage: bool = False, connection_name: str = "default",
            ref_text: str = None):
    voice_env = "VOICE_SAMPLE_PATH: /stage/input/voice_sample.wav"
    if has_script:
        script_env = "SCRIPT_PATH: /stage/input/RECORDING_SCRIPT.md"
    else:
        script_env = f'TEXT: "{text}"' if text else 'TEXT: "Hello, this is a test of voice cloning on Snowflake."'

    if model_on_stage:
        hf_home_env = f"HF_HOME: /stage/{MODEL_STAGE_PREFIX}"
        offline_envs = "HF_HUB_OFFLINE: '1'"
        log("  Model weights loaded from stage (offline mode)")
    elif not needs_egress:
        hf_home_env = "HF_HOME: /root/.cache/huggingface"
        offline_envs = "HF_HUB_OFFLINE: '1'"
    else:
        hf_home_env = "HF_HOME: /root/.cache/huggingface"
        offline_envs = ""

    eai_clause = ""
    if needs_egress and not model_on_stage:
        eai_clause = f"EXTERNAL_ACCESS_INTEGRATIONS = ({integration_name})"

    env_lines = [
        voice_env,
        script_env,
        "OUTPUT_DIR: /stage/output",
        hf_home_env,
    ]
    if offline_envs:
        env_lines.append(offline_envs)
    if ref_text:
        ref_text_escaped = ref_text.replace('"', '\\"').replace("'", "''")
        env_lines.append(f'REF_TEXT: "{ref_text_escaped}"')

    env_block = "\n".join(f"      {line}" for line in env_lines)

    import yaml
    try:
        test_spec = f"""
spec:
  containers:
  - name: cloner
    image: {image_fqn}
    env:
{env_block}
"""
        parsed = yaml.safe_load(test_spec)
        if not parsed or "spec" not in parsed:
            raise ValueError("Parsed YAML has no 'spec' key")
        log("  YAML spec validated OK")
    except ImportError:
        log("  WARNING: PyYAML not installed, skipping YAML validation")
    except Exception as e:
        log(f"  ERROR: Generated YAML spec is invalid: {e}")
        log(f"  Env block:\n{env_block}")
        sys.exit(1)

    volume_mounts = """    volumeMounts:
    - name: stage-vol
      mountPath: /stage"""
    volumes = f"""  volumes:
  - name: stage-vol
    source: "@{stage_fqn}"
"""

    spec = f"""
spec:
  containers:
  - name: cloner
    image: {image_fqn}
    env:
{env_block}
    resources:
      requests:
        nvidia.com/gpu: 1
        memory: 16Gi
      limits:
        nvidia.com/gpu: 1
        memory: 24Gi
{volume_mounts}
{volumes}"""

    job_fqn = f"{database}.{schema}.{job_name}"
    log(f"Submitting voice cloning job to {pool_name}...")
    if needs_egress and not model_on_stage:
        log(f"  External access: {integration_name}")
    elif model_on_stage:
        log("  No external access needed (model weights on stage)")
    else:
        log("  No external access needed (offline mode)")

    try:
        sql(conn, f"DROP SERVICE IF EXISTS {job_fqn}", fetch=False)
    except Exception:
        pass

    time.sleep(2)

    import threading

    job_sql = f"""
        EXECUTE JOB SERVICE
        IN COMPUTE POOL {pool_name}
        NAME = {job_fqn}
        {eai_clause}
        FROM SPECIFICATION $${spec}$$
    """

    job_error = [None]
    current_role = sql(conn, 'SELECT CURRENT_ROLE()')[0][0]
    job_conn = conn
    try:
        job_conn.cursor().execute(f"USE ROLE {current_role}")
        job_conn.cursor().execute(f"USE DATABASE {database}")
        job_conn.cursor().execute(f"USE SCHEMA {schema}")
    except Exception:
        pass

    def _run_job():
        try:
            cur = job_conn.cursor()
            cur.execute(job_sql)
            cur.close()
        except Exception as e:
            job_error[0] = e

    job_thread = threading.Thread(target=_run_job, daemon=True)
    job_thread.start()
    log("Job submitted. Streaming logs...")
    _wait_for_job_with_logs(conn, job_fqn, job_thread=job_thread)

    if job_error[0]:
        log(f"ERROR: Job execution failed: {job_error[0]}")
        sys.exit(1)


def _wait_for_job_with_logs(conn, job_fqn: str, timeout: int = 900, job_thread=None):
    start = time.time()
    last_log_len = 0
    log_conn = conn

    while time.time() - start < timeout:
        if job_thread and not job_thread.is_alive():
            _print_final_logs(log_conn, job_fqn, last_log_len)
            log("Job thread finished.")
            return

        try:
            rows = sql(log_conn, f"SELECT SYSTEM$GET_SERVICE_STATUS('{job_fqn}')")
            if rows and rows[0][0]:
                statuses = json.loads(rows[0][0])
                for s in statuses:
                    status = s.get("status", "").upper()
                    if status == "DONE":
                        _print_final_logs(log_conn, job_fqn, last_log_len)
                        log("Job completed successfully!")
                        return
                    elif status == "FAILED":
                        _print_final_logs(log_conn, job_fqn, last_log_len)
                        log("Job FAILED! Check logs above for details.")
                        sys.exit(1)
        except Exception:
            pass

        try:
            logs = sql(log_conn, f"SELECT SYSTEM$GET_SERVICE_LOGS('{job_fqn}', '0', 'cloner', 500)")
            if logs and logs[0][0]:
                full_log = logs[0][0]
                if len(full_log) > last_log_len:
                    new_lines = full_log[last_log_len:].strip()
                    if new_lines:
                        for line in new_lines.split("\n"):
                            print(f"  | {line}", flush=True)
                    last_log_len = len(full_log)
        except Exception:
            pass

        time.sleep(10)

    log(f"WARNING: Job did not complete within {timeout}s.")
    log("Check logs manually: SELECT SYSTEM$GET_SERVICE_LOGS('" + job_fqn + "', '0', 'cloner', 500)")


def _print_final_logs(conn, job_fqn: str, last_log_len: int):
    try:
        logs = sql(conn, f"SELECT SYSTEM$GET_SERVICE_LOGS('{job_fqn}', '0', 'cloner', 500)")
        if logs and logs[0][0]:
            full_log = logs[0][0]
            if len(full_log) > last_log_len:
                new_lines = full_log[last_log_len:].strip()
                if new_lines:
                    for line in new_lines.split("\n"):
                        print(f"  | {line}", flush=True)
    except Exception:
        pass


def download_result(conn, stage_fqn: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    log(f"Downloading generated audio to {output_dir}...")

    sql(conn, f"GET @{stage_fqn}/output/ 'file://{_to_file_uri(output_dir)}/'", fetch=False)

    for f in os.listdir(output_dir):
        if f.startswith("demo_narration_cloned"):
            fpath = os.path.join(output_dir, f)
            size_mb = os.path.getsize(fpath) / (1024 * 1024)
            log(f"Downloaded: {fpath} ({size_mb:.2f} MB)")
            return fpath

    log("WARNING: No output audio found on stage. Check job logs.")
    return None


def suspend_pool(conn, pool_name: str):
    log(f"Suspending compute pool {pool_name} to save costs...")
    try:
        sql(conn, f"ALTER COMPUTE POOL {pool_name} SUSPEND", fetch=False)
        log("Pool suspended.")
    except Exception as e:
        log(f"Note: Could not suspend pool: {e}")


def cleanup_stage(conn, stage_fqn: str):
    try:
        sql(conn, f"REMOVE @{stage_fqn}/input/", fetch=False)
        sql(conn, f"REMOVE @{stage_fqn}/output/", fetch=False)
    except Exception:
        pass


def _find_existing_image(conn, shared_image_override: str = None) -> str | None:
    if shared_image_override:
        log(f"Using image override: {shared_image_override}")
        return shared_image_override

    log("Scanning account for existing voice-cloner image...")
    try:
        rows = sql(conn, "SHOW IMAGE REPOSITORIES IN ACCOUNT")
        for row in rows:
            repo_name = row[1]
            repo_url = row[4]
            repo_db = row[2]
            repo_schema = row[3]
            try:
                fqn = f"{repo_db}.{repo_schema}.{repo_name}"
                img_rows = sql(conn, f"SHOW IMAGES IN IMAGE REPOSITORY {fqn}")
                for img_row in img_rows:
                    if IMAGE_NAME in str(img_row):
                        image_fqn = f"{repo_url}/{IMAGE_NAME}:{IMAGE_TAG}"
                        log(f"  Found image in {fqn}")
                        return image_fqn
            except Exception:
                pass
    except Exception as e:
        log(f"  Could not scan image repos: {e}")

    return None


def check_spcs_readiness(conn, database: str, schema: str, repo_name: str):
    log("Checking SPCS GPU availability...")
    log("=" * 60)

    rows = sql(conn, "SHOW COMPUTE POOL INSTANCE FAMILIES")
    gpu_families = []
    for row in rows:
        name = row[0]
        if name.startswith("GPU"):
            gpu_families.append({"name": name, "gpu": row[5], "gpu_memory_gib": row[7]})

    if gpu_families:
        log(f"GPU instance families available: {len(gpu_families)}")
        for fam in gpu_families:
            log(f"  {fam['name']}: {fam['gpu']} ({fam['gpu_memory_gib']}GB VRAM)")
    else:
        log("NO GPU instance families available in this account/region.")
        log("Voice cloning via SPCS is not possible here.")
        log("Fallback: Use edge-tts neural voices (generate_audio.py)")
        return False

    rows = sql(conn, "SHOW COMPUTE POOLS")
    pool_found = False
    for row in rows:
        if row[4].startswith("GPU") and not row[0].startswith("SYSTEM_"):
            log(f"\nExisting GPU compute pool: {row[0]} (state: {row[1]})")
            pool_found = True
            break
    if not pool_found:
        log(f"\nNo GPU compute pool exists. Will create one on first use.")

    image_fqn = check_image_exists(conn, database, schema, repo_name)
    if image_fqn:
        log(f"\nDocker image: {image_fqn}")
        spcs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spcs")
        freshness = check_image_freshness(spcs_dir)
        if freshness["has_digest"]:
            if freshness["is_stale"]:
                log(f"  WARNING: Image may be STALE (local build context changed since last push at {freshness['pushed_at']})")
                log(f"  Run without --skip-build to rebuild and push.")
            else:
                log(f"  Image is UP TO DATE (pushed at {freshness['pushed_at']})")
        else:
            log("  No local digest found — freshness unknown. Run a build to establish baseline.")
    else:
        log("\nNo Docker image found in registry. Will build on first use.")

    log("\nSPCS voice cloning is available.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Clone a voice using Snowflake SPCS GPU compute")
    parser.add_argument("--check", action="store_true", help="Check SPCS GPU availability without running a job")
    parser.add_argument("--voice-sample", help="Path to local voice sample WAV/MP3 (3-30 seconds)")
    parser.add_argument("--script", help="Path to local RECORDING_SCRIPT.md")
    parser.add_argument("--text", help="Direct text to synthesize (alternative to --script)")
    parser.add_argument("--output-dir", help="Local directory to download result to")
    parser.add_argument("--connection", default="default", help="Snowflake connection name")
    parser.add_argument("--database", default=None, help="Database (default: current)")
    parser.add_argument("--schema", default=None, help="Schema (default: current)")
    parser.add_argument("--pool-name", default=None, help="Compute pool name (default: auto-detect or create)")
    parser.add_argument("--skip-build", action="store_true", help="Skip Docker build, assume image exists in registry")
    parser.add_argument("--shared-image", default=None,
                        help="Full image FQN to use (e.g. registry.snowflakecomputing.com/db/schema/repo/image:tag). Skips build/push.")
    parser.add_argument("--no-egress", action="store_true",
                        help="Skip network rule/integration setup (use when image has baked-in model weights)")
    parser.add_argument("--no-suspend", action="store_true", help="Keep compute pool running after job completes")
    parser.add_argument("--retry-crane", action="store_true",
                        help="Resume a previously failed crane copy (picks up from last attempt)")
    parser.add_argument("--use-docker", action="store_true",
                        help="Skip crane and use Docker build + push instead")
    parser.add_argument("--ref-text", default=None,
                        help="Transcript of what was said in the voice sample (improves prosody cloning)")
    parser.add_argument("--gitlab-token", default=None,
                        help="GitLab PAT for authenticating to the container registry (also reads GITLAB_TOKEN env var)")
    args = parser.parse_args()

    conn = get_connection(args.connection)
    role = _ensure_role(conn)

    db_row = sql(conn, "SELECT CURRENT_DATABASE()")
    schema_row = sql(conn, "SELECT CURRENT_SCHEMA()")
    database = args.database or (db_row[0][0] if db_row and db_row[0][0] else "VOICE_CLONE_DB")
    schema = args.schema or (schema_row[0][0] if schema_row and schema_row[0][0] else "PUBLIC")

    ensure_database_schema(conn, database, schema)

    if args.pool_name:
        pool_name = args.pool_name
    else:
        pool_name = DEFAULT_POOL_NAME
    repo_name = DEFAULT_REPO_NAME
    stage_name = DEFAULT_STAGE_NAME
    job_name = DEFAULT_JOB_NAME
    rule_name = DEFAULT_NETWORK_RULE_NAME
    integration_name = DEFAULT_ACCESS_INTEGRATION_NAME

    if args.check:
        available = check_spcs_readiness(conn, database, schema, repo_name)
        sys.exit(0 if available else 1)

    if not args.voice_sample:
        parser.error("--voice-sample is required")
    if not os.path.isfile(args.voice_sample):
        log(f"ERROR: Voice sample not found: {args.voice_sample}")
        sys.exit(1)
    if not args.output_dir:
        parser.error("--output-dir is required")

    log("=" * 60)
    log("VOICE CLONING ORCHESTRATOR")
    log("=" * 60)
    log(f"Role: {role}")
    log(f"Database: {database}, Schema: {schema}")
    log(f"Voice sample: {args.voice_sample}")
    log(f"Output dir: {args.output_dir}")
    log(f"Egress rules: {'skip' if args.no_egress else 'auto-detect'}")
    log("")

    log("--- Phase 1: Infrastructure ---")
    pool_name = ensure_compute_pool(conn, pool_name)
    log("")

    resume_attempt = 1
    if args.retry_crane:
        prev = _read_crane_status()
        if prev:
            resume_attempt = prev.get("attempt", 0) + 1
            log(f"Resuming crane copy from attempt {resume_attempt} (previous failed at attempt {prev.get('attempt')})")
            _clear_crane_status()

    spcs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spcs")
    image_fqn = _find_existing_image(conn, args.shared_image)
    if image_fqn:
        freshness = check_image_freshness(spcs_dir)
        if not args.skip_build and freshness["has_digest"] and freshness["is_stale"]:
            log(f"Image is stale (build context changed since {freshness['pushed_at']}). Rebuilding...")
            repo_url = ensure_image_repo(conn, database, schema, repo_name, role=role)
            image_fqn = ensure_image(conn, repo_url, spcs_dir, args.connection,
                                      force_docker=args.use_docker, resume_attempt=resume_attempt,
                                      gitlab_token=args.gitlab_token)
        else:
            log(f"Using existing image (skipping build/push): {image_fqn}")
    else:
        log("No existing image found. Pushing...")
        repo_url = ensure_image_repo(conn, database, schema, repo_name, role=role)
        image_fqn = ensure_image(conn, repo_url, spcs_dir, args.connection,
                                  force_docker=args.use_docker, resume_attempt=resume_attempt,
                                  gitlab_token=args.gitlab_token)
    log("")

    stage_fqn = ensure_stage(conn, database, schema, stage_name)

    if args.no_egress:
        needs_egress = False
        model_on_stage = False
        log("Egress rules skipped (--no-egress).")
    else:
        found_stage = find_model_stage_in_account(conn, stage_fqn)
        if found_stage:
            if found_stage != stage_fqn:
                log(f"Model weights found on @{found_stage} — switching to that stage.")
                stage_fqn = found_stage
            else:
                log("Model weights detected on stage — no egress needed.")
            model_on_stage = True
            needs_egress = False
        else:
            model_on_stage = False
            log("Model weights NOT on stage. Creating egress rules for HuggingFace download...")
            log("  TIP: Run setup_spcs.py to upload model weights to stage (faster, no egress needed)")
            needs_egress = try_ensure_egress(conn, database, schema, rule_name, integration_name)
    log("")

    log("--- Phase 2: Upload & Execute ---")
    try:
        log("Cleaning previous output from stage...")
        sql(conn, f"REMOVE @{stage_fqn}/output/", fetch=False)
    except Exception:
        pass
    upload_files(conn, stage_fqn, args.voice_sample, args.script)
    log("")

    has_script = bool(args.script)
    run_job(conn, pool_name, image_fqn, stage_fqn, database, schema,
            job_name, integration_name, has_script, args.text,
            needs_egress=needs_egress, model_on_stage=model_on_stage,
            connection_name=args.connection, ref_text=args.ref_text)
    log("")

    log("--- Phase 3: Download & Cleanup ---")
    result_path = download_result(conn, stage_fqn, args.output_dir)
    cleanup_stage(conn, stage_fqn)

    if not args.no_suspend:
        suspend_pool(conn, pool_name)

    log("")
    if result_path:
        log(f"Voice cloning complete! Audio saved to: {result_path}")
    else:
        log("Job completed but no audio file was downloaded. Check Snowflake logs.")

    log("=" * 60)
    conn.close()


if __name__ == "__main__":
    main()
