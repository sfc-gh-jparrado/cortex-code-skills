#!/usr/bin/env python3
"""
build_deck_proc.py -- Snowpark handler for generating branded decks in Snowflake CoWork.

This is the SOURCE OF TRUTH for the CoWork BUILD_DECK stored procedure. CoCo (Mode C
deploy) inlines this handler into the CREATE PROCEDURE statement in setup.sql at the
marker `-- <<INLINE build_deck_proc.py HERE>>`. Keeping it here (instead of duplicated
in setup.sql) avoids drift and lets it be linted locally.

Why a procedure (not the MCP): CoWork has no local Python and no Google Slides MCP, so
deck generation runs server-side. The procedure calls the Google Slides + Drive REST
APIs directly through an External Access Integration, authenticating with a Google
service account whose JSON key is stored in a Snowflake SECRET.

It mirrors the structure/fill logic of scripts/build_payload.py (Tier 2 font-fit and
bullets included when the catalog provides a shape map).

Packages (Snowflake Anaconda channel): snowflake-snowpark-python, requests, cryptography.
Secret: google_sa  (generic string = the full service-account JSON key).
Config: read from a table whose name is passed in (default BRANDED_SLIDES.CONFIG.TEMPLATE_CONFIG).

Input (content_spec, VARIANT):
  {
    "template_name": "Acme Deck",          # which catalog row to use
    "deck_title": "Q1 Results",            # optional
    "slides": [ {"type": "...", "fields": {...}, "list_type": {...}}, ... ]
  }
Returns (VARIANT): {"status": "...", "url": "...", "file_id": "...", "slides": N}
"""

import json
import math
import time
import base64

import requests

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_COPY_URL = "https://www.googleapis.com/drive/v3/files/{file_id}/copy"
SLIDES_GET_URL = "https://slides.googleapis.com/v1/presentations/{pid}"
SLIDES_BATCH_URL = "https://slides.googleapis.com/v1/presentations/{pid}:batchUpdate"
SCOPES = "https://www.googleapis.com/auth/presentations https://www.googleapis.com/auth/drive"

BULLET_PRESETS = {
    "unordered": "BULLET_DISC_CIRCLE_SQUARE",
    "ordered": "NUMBERED_DIGIT_ALPHA_ROMAN",
}


# -- Google auth (service account JWT -> access token; cryptography only) ------

def _mint_access_token(sa: dict) -> str:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claim = {
        "iss": sa["client_email"],
        "scope": SCOPES,
        "aud": GOOGLE_TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }

    def b64(obj_bytes: bytes) -> bytes:
        return base64.urlsafe_b64encode(obj_bytes).rstrip(b"=")

    signing_input = (
        b64(json.dumps(header).encode()) + b"." + b64(json.dumps(claim).encode())
    )
    private_key = serialization.load_pem_private_key(
        sa["private_key"].encode(), password=None
    )
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    assertion = signing_input + b"." + b64(signature)

    resp = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion.decode(),
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


# -- Catalog logic (mirrors scripts/build_payload.py) -------------------------

def _calc_font(content, max_chars, default_pt, min_pt=8):
    n = len(content)
    if n <= max_chars or max_chars <= 0:
        return default_pt
    return max(math.floor(default_pt * (max_chars / n)), min_pt)


def _compute_structure(cfg, slides):
    order = cfg["template_order"]
    ids = cfg["slide_ids"]
    counts = {}
    for s in slides:
        counts[s["type"]] = counts.get(s["type"], 0) + 1
    unknown = set(counts) - set(order)
    if unknown:
        raise ValueError(f"Unknown slide types: {sorted(unknown)}")
    reqs = []
    for t in order:
        if t not in counts:
            reqs.append({"deleteObject": {"objectId": ids[t]}})
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
            usage.setdefault(f'{s["type"]}-{field}', []).append((s["slide_id"], value))

    reqs, fits = [], []
    single = cfg.get("single_token_shapes", {})
    for key, instances in usage.items():
        token = "{{" + key + "}}"
        scope = len(instances) > 1
        for sid, val in instances:
            rat = {"containsText": {"text": token, "matchCase": True}, "replaceText": val}
            if scope:
                rat["pageObjectIds"] = [sid]
            reqs.append({"replaceAllText": rat})
        if key in single:
            spec = single[key]
            orig = next((v for sid, v in instances if not sid.startswith("SLIDES_API")), None)
            if orig is not None:
                pt = _calc_font(orig, spec["max_chars"], spec["default_pt"])
                if pt != spec["default_pt"]:
                    fits.append({"updateTextStyle": {"objectId": spec["shape_id"],
                                 "textRange": {"type": "ALL"},
                                 "style": {"fontSize": {"magnitude": pt, "unit": "PT"}},
                                 "fields": "fontSize"}})

    multi = cfg.get("multi_token_shapes", {})
    lookup = {tk: sid for sid, spec in multi.items() for tk in spec.get("tokens", {})}
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
            sid = bshapes.get(f'{s["type"]}-{field}')
            if not preset or not sid or sid in seen_sid:
                continue
            seen_sid.add(sid)
            bullets.append({"createParagraphBullets": {"objectId": sid,
                            "textRange": {"type": "ALL"}, "bulletPreset": preset}})
    return reqs + fits + bullets


def _compute_reorder(current, desired):
    cur = list(current)
    reqs = []
    for pos, sid in enumerate(desired):
        i = cur.index(sid)
        if i != pos:
            reqs.append({"updateSlidesPosition": {"slideObjectIds": [sid], "insertionIndex": pos}})
            cur.pop(i)
            cur.insert(pos, sid)
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
            ctype = kept[oi]
            oi += 1
        t2ids.setdefault(ctype, []).append(sid)
    usage = {}
    for s in slides:
        t = s["type"]
        idx = usage.get(t, 0)
        s["slide_id"] = t2ids[t][idx]
        usage[t] = idx + 1
    return active, [s["slide_id"] for s in slides]


# -- REST helpers -------------------------------------------------------------

def _slides_batch(token, pid, requests_list):
    if not requests_list:
        return
    # Keep batches small to avoid timeouts.
    for i in range(0, len(requests_list), 18):
        chunk = requests_list[i:i + 18]
        r = requests.post(
            SLIDES_BATCH_URL.format(pid=pid),
            headers={"Authorization": f"Bearer {token}"},
            json={"requests": chunk},
            timeout=60,
        )
        r.raise_for_status()


def _slide_ids(token, pid):
    r = requests.get(
        SLIDES_GET_URL.format(pid=pid),
        headers={"Authorization": f"Bearer {token}"},
        params={"fields": "slides.objectId"},
        timeout=60,
    )
    r.raise_for_status()
    return [s["objectId"] for s in r.json().get("slides", [])]


# -- Procedure entry point ----------------------------------------------------

def build_deck(session, content_spec, config_table="BRANDED_SLIDES.CONFIG.TEMPLATE_CONFIG"):
    import _snowflake

    spec = content_spec if isinstance(content_spec, dict) else json.loads(content_spec)
    slides = spec["slides"]
    template_name = spec.get("template_name")
    deck_title = spec.get("deck_title", "Generated Deck")

    # Load catalog from the CONFIG table (one JSON per template_name).
    where = f"WHERE TEMPLATE_NAME = '{template_name}'" if template_name else ""
    rows = session.sql(
        f"SELECT CONFIG_JSON FROM {config_table} {where} "
        f"ORDER BY UPDATED_AT DESC LIMIT 1"
    ).collect()
    if not rows:
        return {"status": "error", "message": f"No catalog found for {template_name}"}
    cfg = json.loads(rows[0]["CONFIG_JSON"])
    master_id = cfg["master_template_id"]

    sa = json.loads(_snowflake.get_generic_secret_string("google_sa"))
    token = _mint_access_token(sa)

    # 1. Copy the master.
    cp = requests.post(
        DRIVE_COPY_URL.format(file_id=master_id),
        headers={"Authorization": f"Bearer {token}"},
        json={"name": f"{deck_title}"},
        timeout=60,
    )
    cp.raise_for_status()
    new_id = cp.json()["id"]

    # 2. Structure, then 3. discover IDs, then 4. fill.
    _slides_batch(token, new_id, _compute_structure(cfg, slides))
    current_ids = _slide_ids(token, new_id)
    active, desired = _assign_fill(cfg, current_ids, slides)
    fill_reqs = _compute_reorder(active, desired) + _compute_tokens(cfg, slides)
    _slides_batch(token, new_id, fill_reqs)

    return {
        "status": "ok",
        "file_id": new_id,
        "url": f"https://docs.google.com/presentation/d/{new_id}/edit",
        "slides": len(slides),
    }
