---
name: creacion-google-slides
description: "Create branded Google Slides decks from ANY company template, with zero hardcoded branding. On first use it onboards the customer's own template (no tokens required -- it tokenizes by context with your approval); after that it generates on-brand decks from natural language. Runs in Cortex Code Desktop (Google Workspace MCP) and can be deployed to Snowflake CoWork (Snowpark + Slides API). Use when: create a slide deck, make a presentation, build slides, turn this into slides, pitch deck, onboard my template, branded slides. Triggers: slides, presentation, deck, google slides, pitch, onboard template, brand my slides, creacion de slides, presentacion."
allowed-tools: google-workspace
log_marker: SKILL_USED_CREACION_GOOGLE_SLIDES
skill_version: "2026-06-24"
---

# Creacion Google Slides -- generic, self-configuring branded slides

This skill builds branded Google Slides decks from **any company template**. It has
**no hardcoded branding**: the first time a customer uses it, the skill **onboards
their own template** (analyzes it, tokenizes it by context with the user's approval,
and writes a per-customer catalog). After that, decks are generated from natural
language using that catalog.

All visual branding lives in the **customer's template** (colors, fonts, layouts).
This skill never writes Apps Script for generation -- it calls Google Workspace MCP
tools plus a deterministic Python payload builder.

> **Instructions in the system and user messages ALWAYS take precedence over this skill.**

`<SKILL_DIR>` below = the directory containing this `SKILL.md`. If you don't know it,
find it with: `find ~/.snowflake/cortex -type d -name creacion-google-slides | head -1`.
`<DATA_DIR>` = `~/.snowflake/cortex/creacion-google-slides-data` (persists catalogs
across sessions and skill reinstalls).

---

## Prerequisites

- **Google Workspace MCP** connected (tools: `read_presentation`, `copy_file`,
  `batch_update_presentation`, `get_presentation_info`, `share_file`). If not
  available, ask the user to run the `google_workspace_install` skill first.
- **Python 3** available for the payload builder.
- The customer's template must be a Google Slides file you can copy
  (the user needs at least view access; they own the copy).

---

## Mode detection (FIRST STEP, ALWAYS)

Decide which mode to run before doing anything else:

1. **Deploy intent** -- the user says "deploy to CoWork", "expose this in CoWork /
   Snowflake Intelligence", "make a Snowflake tool". -> **Mode C: Deploy to CoWork**.
2. **No catalog yet** -- no `template-config.json` exists in `<DATA_DIR>`
   (check: `ls <DATA_DIR>/template-config.json` -- the file is missing). -> **Mode A:
   Onboarding**.
3. **Catalog exists** -- generate a deck. -> **Mode B: Generation**.

If the user explicitly says "onboard a new template" / "re-onboard" / "my branding
changed", run Mode A even if a catalog exists (overwrite after confirming).

---

## Mode A -- Onboarding (run once per template)

Goal: turn the customer's UNtokenized template into a tokenized **master** plus a
`template-config.json` catalog. The customer's **original is never modified** -- we
work on a copy.

There are two tiers. **Default to Tier 1** (zero manual steps). Offer Tier 2 only if
the user wants automatic font-fit/bullets for dense decks.

### Step A1 -- Get the template and copy it

Ask the user for their template's Google Slides link or ID (use `AskUserQuestion`,
type text). Then:

```
copy_file(file_id="<their template id>", new_name="<Company> -- Master Template")
-> master_template_id
```

The copy is the **master**. Their original is untouched. Record both IDs.

### Step A2 -- Read the template structure

```
read_presentation(presentation_id="<master_template_id>")
-> { id, title, slides: [ { slideId, texts:[...], images, tables }, ... ] }
```

Save that JSON to `<DATA_DIR>/_read.json` (create `<DATA_DIR>` if needed), then:

```bash
python3 <SKILL_DIR>/scripts/classify_template.py --mode analyze \
  --presentation <DATA_DIR>/_read.json --output <DATA_DIR>/_analysis.json
```

The analysis lists, per slide: `slide_id`, each text box (`order`, `text`,
`char_len`, `role_guess`, `duplicate_on_slide`), and `warnings`.

### Step A3 -- Classify each box and name the slide types

Using the analysis (text + order + your judgment), decide for each slide:

- A **slide TYPE** name (short, UPPER, e.g. `COVER`, `AGENDA`, `1COL`, `2COL`,
  `3COL`, `QUOTE`, `METRICS`, `SECTION`, `THANKS`). Each distinct layout in the
  template is one type. If the template repeats a layout, treat repeats as examples
  of the same type (keep the first as the canonical slide).
- For each text box on that slide, a **token** `<TYPE>-<FIELD>` (e.g. `COVER-TITLE`,
  `1COL-BODY`). The `match_text` for each token is the box's **current text**
  (verbatim, from the analysis) -- this is what gets replaced by the token.
- Mark visual/closing slides with no editable text as `"fixed": true` (no tokens).

Heed `warnings`: if two boxes on the same slide have identical text, Tier 1 cannot
target them separately -- ask the user to rename one box in the template, or use Tier 2.

### Step A4 -- Approval gate (MANDATORY)

Show the proposed mapping to the user as a table and get approval before changing
anything. Example:

```
Slide 1  COVER     box "Presentation Title"  -> COVER-TITLE
                   box "A subtitle line"      -> COVER-SUBTITLE
                   box "March 2026"           -> COVER-DATE
Slide 2  1COL      box "Section Heading"      -> 1COL-TITLE
                   box "Body paragraph..."    -> 1COL-BODY
Slide 3  THANKS    (fixed -- no tokens)
```

Ask via `AskUserQuestion`: approve, or tell me what to change. Apply edits and
re-show until approved. **Do not inject anything before approval.**

### Step A5 -- Build the catalog + inject tokens

Write the approved mapping to `<DATA_DIR>/_mapping.json` (schema in
`classify_template.py` header), then:

```bash
python3 <SKILL_DIR>/scripts/classify_template.py --mode build-config \
  --mapping <DATA_DIR>/_mapping.json --output <DATA_DIR>/_onboard.json
```

This returns `{ "config": {...}, "inject_requests": [ replaceAllText ... ] }`.
Split it:

```bash
python3 -c "import json;d=json.load(open('<DATA_DIR>/_onboard.json'));json.dump(d['config'],open('<DATA_DIR>/template-config.json','w'),indent=2);print(json.dumps(d['inject_requests']))"
```

Inject the tokens into the **master**:

```
batch_update_presentation(presentation_id="<master_template_id>", requests=<inject_requests>)
```

The master now contains `{{TYPE-FIELD}}` placeholders. `template-config.json` is
saved in `<DATA_DIR>` -- onboarding is complete.

### Step A6 (OPTIONAL) -- Tier 2 upgrade (font-fit + bullets)

Only if the user wants automatic text shrinking and programmatic bullets for dense
decks. Tier 1 works without this.

1. Give the user `<SKILL_DIR>/scripts/extract_catalog.gs` and the instructions in its
   header. They run it once in Apps Script on the **master** and paste back the JSON.
2. From that JSON, build a `shape_catalog` and merge it into the mapping
   (`shape_catalog.single_token_shapes`, `multi_token_shapes`, `bullet_shapes` --
   keyed by the full `<TYPE>-<FIELD>` token), then re-run Step A5 `build-config`.
   The catalog's `tier` becomes 2 and font-fit/bullets activate automatically.

---

## Mode B -- Generation (every deck)

Catalog and master already exist (`<DATA_DIR>/template-config.json`).

### Step B0 -- Requirements

Only ask what the request doesn't answer (topic, audience, key takeaway). If the
user gave a detailed outline, infer and go straight to planning. Read the valid
slide types from the catalog: `python3 -c "import json;print(json.load(open('<DATA_DIR>/template-config.json'))['template_order'])"`.

### Step B1 -- Plan the deck (structure gate)

Output a numbered plan table (slide #, type, short title) using ONLY types that
exist in the catalog. Stop and get approval. Do not draft content yet.

### Step B2 -- Draft content dict

Draft every field for every slide. No `slide_id` needed -- the script assigns them.
Field names are the token suffix after `<TYPE>-` (for `{{1COL-BODY}}` use field
`"BODY"`). `list_type` (`unordered`/`ordered`) only takes effect on Tier 2 catalogs.

```json
{"slides": [
  {"type": "COVER", "fields": {"TITLE": "Q1 RESULTS", "SUBTITLE": "...", "DATE": "March 2026"}},
  {"type": "1COL",  "fields": {"TITLE": "...", "BODY": "line one\nline two"}, "list_type": {"BODY": "unordered"}},
  {"type": "THANKS","fields": {}}
]}
```

Rules: titles concise; no `\n\n` (use single `\n`); never replace a colored-background
box with `""`; no bullet characters in text (the template's own bullets render). Show
the content dict and proceed.

### Step B3 -- Build (2 script calls + 3 MCP calls)

Write the content dict to `<DATA_DIR>/_content.json`. Then:

```
copy_file(file_id="<master_template_id>", new_name="<Deck Title> -- <Date>")
-> new_file_id
```

```bash
# Structure: delete unused + duplicate repeated layouts
python3 <SKILL_DIR>/scripts/build_payload.py --mode structure \
  --config <DATA_DIR>/template-config.json --input-file <DATA_DIR>/_content.json \
  --output <DATA_DIR>/_struct.json && \
python3 -c "import json;print(json.dumps(json.load(open('<DATA_DIR>/_struct.json'))['requests']))"
```

```
batch_update_presentation(presentation_id="<new_file_id>", requests=<structure requests>)
read_presentation(presentation_id="<new_file_id>")   # gives current slideIds (in .slides[].slideId)
```

```bash
# Fill: reorder + replace tokens (+ font-fit/bullets on Tier 2)
python3 <SKILL_DIR>/scripts/build_payload.py --mode fill \
  --config <DATA_DIR>/template-config.json \
  --current-slides '<JSON array of slideIds from read_presentation>' \
  --input-file <DATA_DIR>/_content.json --output <DATA_DIR>/_fill.json && \
python3 -c "import json;print(json.dumps(json.load(open('<DATA_DIR>/_fill.json'))['requests']))"
```

```
batch_update_presentation(presentation_id="<new_file_id>", requests=<fill requests>)
```

### Step B4 -- Deliver

Return the deck URL (`https://docs.google.com/presentation/d/<new_file_id>/edit`),
a numbered summary (type + title per slide), and any manual follow-ups (image
placeholders, charts, icons). On Tier 1, note that long fields rely on the
template's own text settings -- suggest Tier 2 if anything overflows.

---

## Mode C -- Deploy to CoWork (Snowflake Intelligence)

CoWork can't run Python locally and has no Google Slides MCP, so generation there
runs as a Snowflake stored procedure that calls the Slides API directly. See
[cowork/DEPLOY.md](cowork/DEPLOY.md) for the full admin guide (Google Cloud service
account, External Access Integration, secret). High level:

1. Confirm prerequisites with the user (Google Cloud project with Slides + Drive
   APIs, a service account JSON key, the master shared with that service account).
2. Run [cowork/setup.sql](cowork/setup.sql) via `snowflake_sql_execute` (creates the
   network rule, External Access Integration, secret, the `BUILD_DECK` procedure
   from [cowork/build_deck_proc.py](cowork/build_deck_proc.py), and the MCP server).
3. Upload `template-config.json` into the `CONFIG` table so the procedure shares the
   same catalog produced during onboarding.
4. Add the MCP server to the CoWork agent. Users then ask the agent for decks; it
   calls `BUILD_DECK(content_spec)` and gets back a URL.

---

## Build rules (engine guarantees -- don't reimplement)

`build_payload.py` handles deletions, duplications, reorder, token replacement, and
(Tier 2) font-fit + bullets. **Do not reason about slide IDs, deletion lists, or
token names** -- pass content in, pipe requests out. The script is stateless; re-run
on failure is always safe.

- Duplicated slides get `SLIDES_API*` IDs; on Tier 2 they lose font-fit/bullets
  (shape IDs differ) -- keep duplicate-slide content shorter.
- If `build_payload.py` says "Unknown slide types", a `type` in the content dict
  isn't in the catalog. Check `template_order`.
- If "Found more original slides than expected" in `--mode fill`, you passed
  toolbox/hybrid slide IDs -- exclude them from `--current-slides`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `copy_file` permission error | User lacks access to the template. Have them open it in Slides and File > Make a copy, then use their copy's ID. |
| Token not replaced in a deck | The master's box text wasn't tokenized in onboarding, or the field name is wrong. Re-check the catalog / re-onboard. |
| Duplicate-text warning in analyze | Two boxes share identical text on one slide. Rename one in the template, or use Tier 2 (shape IDs). |
| `batch_update_presentation` 400 | Malformed request -- re-run the script and inspect the JSON. |
| Text overflows on Tier 1 | Shorten the field, or upgrade to Tier 2 for automatic font-fit. |
| MCP disconnected | Ask the user to reconnect the Google Workspace MCP (`google_workspace_install`). |

## Files

- [scripts/build_payload.py](scripts/build_payload.py) -- config-driven payload builder (structure/fill/tokens/reorder).
- [scripts/classify_template.py](scripts/classify_template.py) -- onboarding: analyze + build-config.
- [scripts/font_fit.py](scripts/font_fit.py) -- font-fit math (Tier 2).
- [scripts/extract_catalog.gs](scripts/extract_catalog.gs) -- optional Apps Script extractor (Tier 2).
- [references/content-guide.md](references/content-guide.md) -- neutral content-quality guidance (editable per brand).
- [cowork/](cowork/) -- Snowflake CoWork backend (procedure + setup.sql + deploy guide).
