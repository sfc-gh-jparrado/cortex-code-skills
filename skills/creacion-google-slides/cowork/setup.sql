-- ============================================================================
-- setup.sql -- Deploy the creacion-google-slides backend to Snowflake CoWork.
--
-- Creates: database/schema, CONFIG table, network rule, External Access
-- Integration, Google service-account SECRET, the BUILD_DECK procedure, and a
-- Snowflake-managed MCP server exposing BUILD_DECK as a tool for CoWork agents.
--
-- PREREQUISITES (see DEPLOY.md):
--   1. A Google Cloud project with the Google Slides API and Google Drive API enabled.
--   2. A Google service account + JSON key.
--   3. Your tokenized MASTER template shared with the service account's email
--      (Editor). Decks are created as copies of that master.
--   4. ACCOUNTADMIN (or a role with CREATE INTEGRATION / CREATE SECRET / CREATE
--      MCP SERVER) to run this script.
--
-- The BUILD_DECK procedure body below mirrors cowork/build_deck_proc.py
-- (source of truth). Keep them in sync if you change one.
-- ============================================================================

-- Edit these to taste -------------------------------------------------------
SET deploy_role  = 'OPENFLOW_ADMIN';     -- role that owns/runs the objects
SET deploy_wh    = 'BANCO_WH';           -- warehouse for the procedure
-- ---------------------------------------------------------------------------

CREATE DATABASE IF NOT EXISTS BRANDED_SLIDES;
CREATE SCHEMA   IF NOT EXISTS BRANDED_SLIDES.CONFIG;
CREATE SCHEMA   IF NOT EXISTS BRANDED_SLIDES.APP;

-- Catalog table: one row per onboarded template (CoCo uploads template-config.json here).
CREATE TABLE IF NOT EXISTS BRANDED_SLIDES.CONFIG.TEMPLATE_CONFIG (
    TEMPLATE_NAME STRING,
    CONFIG_JSON   STRING,
    UPDATED_AT    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Network egress allowlist for the Google APIs the procedure calls.
CREATE OR REPLACE NETWORK RULE BRANDED_SLIDES.APP.GOOGLE_APIS_RULE
    MODE = EGRESS
    TYPE = HOST_PORT
    VALUE_LIST = (
        'oauth2.googleapis.com',
        'slides.googleapis.com',
        'www.googleapis.com'
    );

-- Service-account key, stored as a generic-string secret.
-- Replace the value with the FULL contents of your service-account JSON key.
CREATE OR REPLACE SECRET BRANDED_SLIDES.APP.GOOGLE_SA
    TYPE = GENERIC_STRING
    SECRET_STRING = '{
  "type": "service_account",
  "project_id": "REPLACE_ME",
  "private_key": "-----BEGIN PRIVATE KEY-----\nREPLACE_ME\n-----END PRIVATE KEY-----\n",
  "client_email": "REPLACE_ME@REPLACE_ME.iam.gserviceaccount.com"
}';

CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION GOOGLE_SLIDES_EAI
    ALLOWED_NETWORK_RULES = (BRANDED_SLIDES.APP.GOOGLE_APIS_RULE)
    ALLOWED_AUTHENTICATION_SECRETS = (BRANDED_SLIDES.APP.GOOGLE_SA)
    ENABLED = TRUE;

-- ---------------------------------------------------------------------------
-- BUILD_DECK procedure (mirror of cowork/build_deck_proc.py)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE BRANDED_SLIDES.APP.BUILD_DECK(
    CONTENT_SPEC VARIANT,
    CONFIG_TABLE STRING DEFAULT 'BRANDED_SLIDES.CONFIG.TEMPLATE_CONFIG'
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python', 'requests', 'cryptography')
HANDLER = 'build_deck'
EXTERNAL_ACCESS_INTEGRATIONS = (GOOGLE_SLIDES_EAI)
SECRETS = ('google_sa' = BRANDED_SLIDES.APP.GOOGLE_SA)
AS
$$
import json, math, time, base64
import requests

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_COPY_URL = "https://www.googleapis.com/drive/v3/files/{file_id}/copy"
SLIDES_GET_URL = "https://slides.googleapis.com/v1/presentations/{pid}"
SLIDES_BATCH_URL = "https://slides.googleapis.com/v1/presentations/{pid}:batchUpdate"
SCOPES = "https://www.googleapis.com/auth/presentations https://www.googleapis.com/auth/drive"
BULLET_PRESETS = {"unordered": "BULLET_DISC_CIRCLE_SQUARE", "ordered": "NUMBERED_DIGIT_ALPHA_ROMAN"}

def _mint_access_token(sa):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claim = {"iss": sa["client_email"], "scope": SCOPES, "aud": GOOGLE_TOKEN_URL,
             "iat": now, "exp": now + 3600}
    def b64(b): return base64.urlsafe_b64encode(b).rstrip(b"=")
    signing_input = b64(json.dumps(header).encode()) + b"." + b64(json.dumps(claim).encode())
    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    sig = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    assertion = signing_input + b"." + b64(sig)
    r = requests.post(GOOGLE_TOKEN_URL, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion.decode()}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]

def _calc_font(content, max_chars, default_pt, min_pt=8):
    n = len(content)
    if n <= max_chars or max_chars <= 0:
        return default_pt
    return max(math.floor(default_pt * (max_chars / n)), min_pt)

def _compute_structure(cfg, slides):
    order, ids = cfg["template_order"], cfg["slide_ids"]
    counts = {}
    for s in slides:
        counts[s["type"]] = counts.get(s["type"], 0) + 1
    unknown = set(counts) - set(order)
    if unknown:
        raise ValueError("Unknown slide types: %s" % sorted(unknown))
    reqs = [{"deleteObject": {"objectId": ids[t]}} for t in order if t not in counts]
    seen = set()
    for s in slides:
        t = s["type"]
        if t in seen:
            reqs.append({"duplicateObject": {"objectId": ids[t]}})
        else:
            seen.add(t)
    return reqs

def _compute_tokens(cfg, slides):
    autofill = cfg.get("autofill_fields", {})
    for s in slides:
        fields = s.setdefault("fields", {})
        for f in autofill.get(s["type"], []):
            fields.setdefault(f, " ")
    usage = {}
    for s in slides:
        for field, value in s.get("fields", {}).items():
            usage.setdefault(s["type"] + "-" + field, []).append((s["slide_id"], value))
    reqs, fits = [], []
    single = cfg.get("single_token_shapes", {})
    for key, inst in usage.items():
        token = "{{" + key + "}}"
        scope = len(inst) > 1
        for sid, val in inst:
            rat = {"containsText": {"text": token, "matchCase": True}, "replaceText": val}
            if scope:
                rat["pageObjectIds"] = [sid]
            reqs.append({"replaceAllText": rat})
        if key in single:
            spec = single[key]
            orig = next((v for sid, v in inst if not sid.startswith("SLIDES_API")), None)
            if orig is not None:
                pt = _calc_font(orig, spec["max_chars"], spec["default_pt"])
                if pt != spec["default_pt"]:
                    fits.append({"updateTextStyle": {"objectId": spec["shape_id"],
                                 "textRange": {"type": "ALL"},
                                 "style": {"fontSize": {"magnitude": pt, "unit": "PT"}},
                                 "fields": "fontSize"}})
    multi = cfg.get("multi_token_shapes", {})
    lookup = {tk: sid for sid, sp in multi.items() for tk in sp.get("tokens", {})}
    done = set()
    for key in usage:
        sid = lookup.get(key)
        if not sid or sid in done:
            continue
        done.add(sid)
        spec = multi[sid]
        smallest = spec["default_pt"]
        for tk, mc in spec.get("tokens", {}).items():
            orig = next((v for s2, v in usage.get(tk, []) if not s2.startswith("SLIDES_API")), None)
            if orig is None:
                continue
            smallest = min(smallest, _calc_font(orig, mc, spec["default_pt"]))
        if smallest != spec["default_pt"]:
            fits.append({"updateTextStyle": {"objectId": sid, "textRange": {"type": "ALL"},
                         "style": {"fontSize": {"magnitude": smallest, "unit": "PT"}},
                         "fields": "fontSize"}})
    bullets, seen_sid = [], set()
    bshapes = cfg.get("bullet_shapes", {})
    for s in slides:
        if s["slide_id"].startswith("SLIDES_API"):
            continue
        for field, btype in s.get("list_type", {}).items():
            preset = BULLET_PRESETS.get(btype)
            sid = bshapes.get(s["type"] + "-" + field)
            if not preset or not sid or sid in seen_sid:
                continue
            seen_sid.add(sid)
            bullets.append({"createParagraphBullets": {"objectId": sid,
                            "textRange": {"type": "ALL"}, "bulletPreset": preset}})
    return reqs + fits + bullets

def _compute_reorder(current, desired):
    cur = list(current); reqs = []
    for pos, sid in enumerate(desired):
        i = cur.index(sid)
        if i != pos:
            reqs.append({"updateSlidesPosition": {"slideObjectIds": [sid], "insertionIndex": pos}})
            cur.pop(i); cur.insert(pos, sid)
    return reqs

def _assign_fill(cfg, current_ids, slides):
    toolbox = set(cfg.get("toolbox_slide_ids", []))
    active = [s for s in current_ids if s not in toolbox]
    order = cfg["template_order"]
    used = list(dict.fromkeys(s["type"] for s in slides))
    kept = sorted(used, key=order.index)
    oi, ctype, t2ids = 0, None, {}
    for sid in active:
        if not sid.startswith("SLIDES_API"):
            ctype = kept[oi]; oi += 1
        t2ids.setdefault(ctype, []).append(sid)
    usage = {}
    for s in slides:
        t = s["type"]; idx = usage.get(t, 0)
        s["slide_id"] = t2ids[t][idx]; usage[t] = idx + 1
    return active, [s["slide_id"] for s in slides]

def _slides_batch(token, pid, reqs):
    if not reqs:
        return
    for i in range(0, len(reqs), 18):
        r = requests.post(SLIDES_BATCH_URL.format(pid=pid),
                          headers={"Authorization": "Bearer " + token},
                          json={"requests": reqs[i:i + 18]}, timeout=60)
        r.raise_for_status()

def _slide_ids(token, pid):
    r = requests.get(SLIDES_GET_URL.format(pid=pid),
                     headers={"Authorization": "Bearer " + token},
                     params={"fields": "slides.objectId"}, timeout=60)
    r.raise_for_status()
    return [s["objectId"] for s in r.json().get("slides", [])]

def build_deck(session, content_spec, config_table="BRANDED_SLIDES.CONFIG.TEMPLATE_CONFIG"):
    import _snowflake
    spec = content_spec if isinstance(content_spec, dict) else json.loads(content_spec)
    slides = spec["slides"]
    template_name = spec.get("template_name")
    deck_title = spec.get("deck_title", "Generated Deck")
    where = ("WHERE TEMPLATE_NAME = '%s'" % template_name) if template_name else ""
    rows = session.sql("SELECT CONFIG_JSON FROM %s %s ORDER BY UPDATED_AT DESC LIMIT 1"
                       % (config_table, where)).collect()
    if not rows:
        return {"status": "error", "message": "No catalog for %s" % template_name}
    cfg = json.loads(rows[0]["CONFIG_JSON"])
    master_id = cfg["master_template_id"]
    sa = json.loads(_snowflake.get_generic_secret_string("google_sa"))
    token = _mint_access_token(sa)
    cp = requests.post(DRIVE_COPY_URL.format(file_id=master_id),
                       headers={"Authorization": "Bearer " + token},
                       json={"name": deck_title}, timeout=60)
    cp.raise_for_status()
    new_id = cp.json()["id"]
    _slides_batch(token, new_id, _compute_structure(cfg, slides))
    current_ids = _slide_ids(token, new_id)
    active, desired = _assign_fill(cfg, current_ids, slides)
    _slides_batch(token, new_id, _compute_reorder(active, desired) + _compute_tokens(cfg, slides))
    return {"status": "ok", "file_id": new_id,
            "url": "https://docs.google.com/presentation/d/" + new_id + "/edit",
            "slides": len(slides)}
$$;

-- ---------------------------------------------------------------------------
-- Expose BUILD_DECK as a tool on a Snowflake-managed MCP server for CoWork.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE MCP SERVER BRANDED_SLIDES.APP.SLIDES_MCP
  FROM SPECIFICATION $$
tools:
  - name: "build_deck"
    identifier: "BRANDED_SLIDES.APP.BUILD_DECK"
    type: "GENERIC"
    title: "Build branded slide deck"
    description: "Generate a branded Google Slides deck from a content spec. Input: a JSON object with template_name, optional deck_title, and a slides array of {type, fields, list_type}. Returns the deck URL."
    config:
      type: "procedure"
      query_timeout: 300
      input_schema:
        type: "object"
        properties:
          content_spec:
            type: "object"
            description: "Deck content: {template_name, deck_title, slides:[{type, fields, list_type}]}"
        required: ["content_spec"]
$$;

-- ---------------------------------------------------------------------------
-- Grants (adjust roles as needed).
-- ---------------------------------------------------------------------------
GRANT USAGE ON DATABASE BRANDED_SLIDES TO ROLE IDENTIFIER($deploy_role);
GRANT USAGE ON SCHEMA BRANDED_SLIDES.APP TO ROLE IDENTIFIER($deploy_role);
GRANT USAGE ON SCHEMA BRANDED_SLIDES.CONFIG TO ROLE IDENTIFIER($deploy_role);
GRANT SELECT, INSERT, UPDATE ON TABLE BRANDED_SLIDES.CONFIG.TEMPLATE_CONFIG TO ROLE IDENTIFIER($deploy_role);
GRANT USAGE ON PROCEDURE BRANDED_SLIDES.APP.BUILD_DECK(VARIANT, STRING) TO ROLE IDENTIFIER($deploy_role);
GRANT USAGE ON INTEGRATION GOOGLE_SLIDES_EAI TO ROLE IDENTIFIER($deploy_role);
GRANT USAGE ON MCP SERVER BRANDED_SLIDES.APP.SLIDES_MCP TO ROLE IDENTIFIER($deploy_role);

-- Smoke test (after uploading a catalog row and configuring the secret):
--   CALL BRANDED_SLIDES.APP.BUILD_DECK(
--     PARSE_JSON('{"template_name":"Acme Deck","deck_title":"Test",
--                  "slides":[{"type":"COVER","fields":{"TITLE":"HELLO"}},
--                            {"type":"THANKS","fields":{}}]}'));
