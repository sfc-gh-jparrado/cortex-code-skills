---
name: kaniko-spcs
description: "Build Docker container images inside SPCS using Kaniko and push to the SPCS image registry. Use when: building Docker images in SPCS, pushing images to SPCS registry, setting up Kaniko on a new account, SPCS image build, avoiding VPN for large image pushes. Triggers: kaniko, spcs build, docker build spcs, build image in spcs, image build spcs, kaniko spcs, push image spcs, build container spcs."
---

# Build Docker Images in SPCS with Kaniko

Build and push Docker container images entirely within Snowflake's network using Google's [Kaniko](https://github.com/GoogleContainerTools/kaniko) — a daemonless, userspace image builder. This eliminates the need to push multi-GB images over VPN/home WiFi.

## When to Use

- Building a Docker image and pushing it to the SPCS image registry
- Large images (ML/CUDA) that are impractical to push over VPN
- Setting up Kaniko build infrastructure on a new Snowflake account
- Rebuilding an image that was perfected locally, from spec, in SPCS

## Prerequisites Discovery

Before anything, determine the active connection's account details. Run:

```bash
cortex connections list
```

From the active connection, derive:

| Value | How to get it |
|-------|---------------|
| `REGISTRY_HOST` | `<orgname>-<acctname>.registry.snowflakecomputing.com` (lowercase, hyphens) |
| `IMAGE_REPO_PATH` | `<db>/<schema>/<repo_name>` (e.g., `gehc_imaging/dicom/images_repo`) |
| `ACCOUNT_LOCATOR` | From connection config or `SELECT CURRENT_ACCOUNT()` |

Then check what infrastructure already exists:

```sql
SHOW COMPUTE POOLS;
SHOW IMAGE REPOSITORIES IN SCHEMA <db>.<schema>;
SHOW SECRETS IN SCHEMA <db>.<schema>;
SHOW EXTERNAL ACCESS INTEGRATIONS;
SHOW NETWORK RULES IN SCHEMA <db>.<schema>;
```

Look for:
- A CPU compute pool (`CPU_X64_M` or larger — XS will OOM on large builds)
- An image repository containing `kaniko-executor:v1.23.2-debug`
- A secret of TYPE=PASSWORD for registry PAT credentials
- Network rules for egress (`0.0.0.0`) and the registry host
- An external access integration referencing those network rules
- A stage named `BUILD_CONTEXT` (or similar) with `kaniko_entrypoint.sh` uploaded

**If all exist → use Mode 1 (Build an Image).**
**If missing → use Mode 2 (Setup Kaniko Infrastructure).**

---

## Mode 1: Build an Image

Use this when Kaniko infrastructure already exists on the account. This is the typical workflow.

### Step 1: Prepare Build Context

Identify the Dockerfile and any source files needed for the build. The user may specify a Dockerfile path or you can look for `Dockerfile.*` in the project.

Clean and upload files to the build context stage:

```sql
REMOVE @<db>.<schema>.BUILD_CONTEXT;
```

Then upload via Snow CLI:

```bash
snow stage copy <local_file> @<db>.<schema>.BUILD_CONTEXT -c <connection>
```

Upload all files the Dockerfile references (source .py files, requirements.txt, model weights, etc.) plus `kaniko_entrypoint.sh`. If `kaniko_entrypoint.sh` doesn't exist locally, recreate it from the reference doc at `references/kaniko-entrypoint.sh.md`.

### Step 2: Execute the Build Job

Generate and run the EXECUTE JOB SERVICE SQL. All placeholders must be replaced with actual values from the account:

```sql
EXECUTE JOB SERVICE
  IN COMPUTE POOL <COMPUTE_POOL>
  NAME = <db>.<schema>.KANIKO_BUILD_JOB
  EXTERNAL_ACCESS_INTEGRATIONS = (<EAI_NAME>)
  FROM SPECIFICATION $$
  spec:
    containers:
    - name: kaniko
      image: /<image_repo_path>/kaniko-executor:v1.23.2-debug
      env:
        REGISTRY_HOST: "<REGISTRY_HOST>"
      command:
      - /busybox/sh
      - /workspace/kaniko_entrypoint.sh
      - "--dockerfile=/workspace/<dockerfile_name>"
      - "--context=/workspace"
      - "--destination=<REGISTRY_HOST>/<image_repo_path>/<image_name>:<tag>"
      - "--cache=false"
      - "--verbosity=info"
      - "--snapshot-mode=redo"
      secrets:
      - snowflakeSecret: <db>.<schema>.<PAT_SECRET_NAME>
        secretKeyRef: username
        envVarName: REGISTRY_USERNAME
      - snowflakeSecret: <db>.<schema>.<PAT_SECRET_NAME>
        secretKeyRef: password
        envVarName: REGISTRY_PASSWORD
      volumeMounts:
      - name: build-context
        mountPath: /workspace
    volumes:
    - name: build-context
      source: "@<db>.<schema>.BUILD_CONTEXT"
  $$;
```

**Critical formatting rules:**
- `command` and `args` cannot both be lists — combine everything into the `command` list
- `env` block must come BEFORE `command` in the YAML
- Secrets use **flat syntax**: `snowflakeSecret: DB.SCHEMA.SECRET_NAME` (NOT nested `objectReference` — that syntax is rejected)
- Each `secretKeyRef` must be a separate list entry under `secrets` (not grouped)
- Secret name must be fully qualified (`DB.SCHEMA.SECRET_NAME`)
- The `image` path uses forward slashes with the repo path (no registry host prefix)
- Quote string args that contain `=` signs (e.g., `"--dockerfile=/workspace/Dockerfile.training"`)

### Step 3: Monitor the Build

Poll job status:

```sql
SELECT SYSTEM$GET_SERVICE_STATUS('<db>.<schema>.KANIKO_BUILD_JOB');
```

Wait for status `DONE` or `FAILED`. Once complete, get logs:

```sql
SELECT SYSTEM$GET_SERVICE_LOGS('<db>.<schema>.KANIKO_BUILD_JOB', 0, 'kaniko', 1000);
```

Look for `Kaniko exit code: 0` and the build timing in the output.

### Step 4: Verify

Confirm the image was pushed:

```sql
SHOW IMAGES IN IMAGE REPOSITORY <db>.<schema>.<repo_name>;
```

The new image name and tag should appear in the results.

**Cleanup:** Drop the job service before re-running with the same name:

```sql
DROP SERVICE IF EXISTS <db>.<schema>.KANIKO_BUILD_JOB;
```

---

## Mode 2: Setup Kaniko Infrastructure

Use this when setting up Kaniko on a new Snowflake account for the first time.

### Step 1: Create Role and Service User

```sql
-- Dedicated role for build operations
CREATE ROLE IF NOT EXISTS KANIKO_BUILD_ROLE;
GRANT ROLE KANIKO_BUILD_ROLE TO ROLE ACCOUNTADMIN;

-- Service user (no password login, PAT-only)
CREATE USER IF NOT EXISTS KANIKO_BUILD_SVC
  TYPE = SERVICE
  DEFAULT_ROLE = KANIKO_BUILD_ROLE;
GRANT ROLE KANIKO_BUILD_ROLE TO USER KANIKO_BUILD_SVC;
```

### Step 2: Create Compute Pool

```sql
CREATE COMPUTE POOL IF NOT EXISTS KANIKO_BUILD_POOL
  MIN_NODES = 1
  MAX_NODES = 1
  INSTANCE_FAMILY = CPU_X64_M
  AUTO_RESUME = TRUE
  AUTO_SUSPEND_SECS = 300;

GRANT USAGE ON COMPUTE POOL KANIKO_BUILD_POOL TO ROLE KANIKO_BUILD_ROLE;
GRANT MONITOR ON COMPUTE POOL KANIKO_BUILD_POOL TO ROLE KANIKO_BUILD_ROLE;
```

**CPU_X64_M is the minimum.** CPU_X64_XS (~6GB RAM) will OOM (exit 137) on large builds like CUDA + PyTorch images (~5-6GB).

### Step 3: Create Image Repository and Stage

```sql
CREATE IMAGE REPOSITORY IF NOT EXISTS <db>.<schema>.IMAGES_REPO;
CREATE STAGE IF NOT EXISTS <db>.<schema>.BUILD_CONTEXT
  ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');

GRANT READ, WRITE ON IMAGE REPOSITORY <db>.<schema>.IMAGES_REPO TO ROLE KANIKO_BUILD_ROLE;
GRANT READ, WRITE ON STAGE <db>.<schema>.BUILD_CONTEXT TO ROLE KANIKO_BUILD_ROLE;
```

### Step 4: Create Network Rules and External Access Integration

```sql
-- Egress to Docker Hub, NVIDIA NGC, etc. (Docker builds contact dynamic CDN hosts)
CREATE OR REPLACE NETWORK RULE <db>.<schema>.KANIKO_BUILD_RULE
  MODE = EGRESS
  TYPE = HOST_PORT
  VALUE_LIST = ('0.0.0.0:80', '0.0.0.0:443');

-- Egress to SPCS image registry for pushing built images
CREATE OR REPLACE NETWORK RULE <db>.<schema>.SPCS_REGISTRY_RULE
  MODE = EGRESS
  TYPE = HOST_PORT
  VALUE_LIST = ('<REGISTRY_HOST>:443');

CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION KANIKO_BUILD_EAI
  ALLOWED_NETWORK_RULES = (
    <db>.<schema>.KANIKO_BUILD_RULE,
    <db>.<schema>.SPCS_REGISTRY_RULE
  )
  ENABLED = TRUE;

GRANT USAGE ON INTEGRATION KANIKO_BUILD_EAI TO ROLE KANIKO_BUILD_ROLE;
```

### Step 5: Create Authentication Policy and PAT Secret

The SPCS auto-injected OAuth token (`/snowflake/session/token`) does NOT work for registry auth. A Programmatic Access Token (PAT) is required.

```sql
-- Auth policy that bypasses network policy for PAT auth
-- (SPCS container IPs are dynamic and not in any network policy allowlist)
CREATE OR REPLACE AUTHENTICATION POLICY <db>.<schema>.KANIKO_PAT_POLICY
  AUTHENTICATION_METHODS = (PASSWORD, PROGRAMMATIC_ACCESS_TOKEN)
  PAT_POLICY = (NETWORK_POLICY_EVALUATION = NOT_ENFORCED);

ALTER USER KANIKO_BUILD_SVC SET AUTHENTICATION POLICY <db>.<schema>.KANIKO_PAT_POLICY;
```

**Manual step — PAT creation must be done in Snowsight:**

1. Log in to Snowsight as ACCOUNTADMIN
2. Navigate to Admin → Users → KANIKO_BUILD_SVC → Programmatic Access Tokens
3. Create a new PAT with:
   - Name: `KANIKO_REGISTRY_PAT`
   - Role Restriction: `KANIKO_BUILD_ROLE` (**required for TYPE=SERVICE users**)
   - Days to Expiry: 365
4. **Copy the PAT value immediately** — it cannot be retrieved later

Then create the secret:

```sql
CREATE OR REPLACE SECRET <db>.<schema>.KANIKO_REGISTRY_PAT
  TYPE = PASSWORD
  USERNAME = 'KANIKO_BUILD_SVC'
  PASSWORD = '<paste PAT value here>';

GRANT READ ON SECRET <db>.<schema>.KANIKO_REGISTRY_PAT TO ROLE KANIKO_BUILD_ROLE;
```

### Step 6: Push the Kaniko Executor Image

This is a one-time step. Pull the Kaniko image from Google's registry and push it to the SPCS registry:

```bash
docker pull gcr.io/kaniko-project/executor:v1.23.2-debug
docker tag gcr.io/kaniko-project/executor:v1.23.2-debug <REGISTRY_HOST>/<image_repo_path>/kaniko-executor:v1.23.2-debug
snow spcs image-registry login -c <connection>
docker push <REGISTRY_HOST>/<image_repo_path>/kaniko-executor:v1.23.2-debug
```

### Step 7: Upload Entrypoint Script

Create `kaniko_entrypoint.sh` from the reference doc (`references/kaniko-entrypoint.sh.md`) and upload:

```bash
snow stage copy kaniko_entrypoint.sh @<db>.<schema>.BUILD_CONTEXT -c <connection>
```

### Step 8: Smoke Test

Run a minimal Alpine build to verify everything works:

Create `Dockerfile.kaniko-test`:
```dockerfile
FROM alpine:latest
RUN echo "Kaniko SPCS build test"
CMD ["echo", "success"]
```

Upload it, then run Mode 1 with `--dockerfile=/workspace/Dockerfile.kaniko-test` and `--destination=<REGISTRY_HOST>/<image_repo_path>/kaniko-test:v1`. This should complete in under 30 seconds.

---

## Critical Gotchas

| Issue | Detail |
|-------|--------|
| **PAT required for registry auth** | The SPCS OAuth token at `/snowflake/session/token` returns 401 for registry operations. Only PAT-based basic auth works. |
| **Auth policy PAT bypass is essential** | SPCS container IPs are dynamic. Without `NETWORK_POLICY_EVALUATION = NOT_ENFORCED`, the PAT gets blocked by network policy. |
| **CPU_X64_M minimum** | XS instances (~6GB RAM) OOM on large builds (exit 137). M instances (~28GB) handle 5-6GB images in ~6.5 min. |
| **`command` + `args` conflict** | SPCS rejects specs where both `command` (multi-item list) and `args` are set. Combine everything into a single `command` list. |
| **Secret format** | Each `secretKeyRef` (username, password) must be a separate list entry under `secrets`, not grouped. |
| **1000-line log limit** | SPCS only exposes 1000 lines via `SYSTEM$GET_SERVICE_LOGS`. The entrypoint captures output to `/kaniko/build.log` and tails 200 lines. |
| **TYPE=SERVICE PAT requires ROLE_RESTRICTION** | For `TYPE=SERVICE` users, Snowflake requires `ROLE_RESTRICTION` when creating a PAT. This must be done via Snowsight UI. |
| **Cannot delete individual images** | SPCS does not support dropping individual images from a repository. Only `DROP IMAGE REPOSITORY` (removes all) is available. |
| **`REGISTRY_HOST` env var** | The entrypoint reads `REGISTRY_HOST` from the environment, making the same script portable across accounts. Always set it in the job spec `env` block. |

## Quick Reference: Placeholder Map

When generating SQL, replace these placeholders with values from the active connection:

| Placeholder | Example Value | Source |
|-------------|---------------|--------|
| `<db>.<schema>` | `GEHC_IMAGING.DICOM` | Connection config or `SELECT CURRENT_DATABASE(), CURRENT_SCHEMA()` |
| `<REGISTRY_HOST>` | `kwlfcbn-djc73015.registry.snowflakecomputing.com` | `SHOW IMAGE REPOSITORIES` → `repository_url` column |
| `<image_repo_path>` | `gehc_imaging/dicom/images_repo` | `SHOW IMAGE REPOSITORIES` → `repository_url` (path portion) |
| `<repo_name>` | `IMAGES_REPO` | `SHOW IMAGE REPOSITORIES` → `name` |
| `<COMPUTE_POOL>` | `KANIKO_BUILD_POOL` | `SHOW COMPUTE POOLS` |
| `<EAI_NAME>` | `KANIKO_BUILD_EAI` | `SHOW EXTERNAL ACCESS INTEGRATIONS` |
| `<PAT_SECRET_NAME>` | `KANIKO_REGISTRY_PAT` | `SHOW SECRETS` |
| `<connection>` | `gehc` | Active cortex connection name |

## Stopping Points

- ⚠️ Before executing any SPCS job commands: confirm the mode (build image vs setup infrastructure) and the placeholder values with the user.
- ⚠️ Before pushing an image to the registry: confirm the target image name and tag.
