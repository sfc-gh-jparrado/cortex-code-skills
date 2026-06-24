#!/usr/bin/env python3
"""
classify_template.py -- Onboarding helper for the generic branded-slides skill.

Turns a customer's UNtokenized Google Slides template into (a) a structured
analysis the agent uses to classify each text box, and (b) a template-config.json
catalog plus the token-injection requests that tokenize a copy of the template.

Two onboarding tiers are supported, both driven by this script:

  Tier 1 (default, zero manual steps): uses only what the Google Workspace MCP
    exposes -- read_presentation, which returns each slide's objectId plus the
    text strings in every box. Tokens are injected with replaceAllText (matching
    the box's existing text), scoped per slide. No shape objectIds are needed.
    Limitation: no programmatic font-fit / bullets (those require shape IDs).

  Tier 2 (optional, one paste): the customer runs scripts/extract_catalog.gs in
    the Apps Script editor on their template and pastes back the JSON. That adds
    a shape_catalog (shape IDs, default font sizes, char limits) which unlocks
    programmatic font-fit, bullets, and autofit repair.

Modes:

  analyze       -- parse a read_presentation dump into a per-slide / per-box
                   analysis (text, order, heuristic role guess) for the agent.

  build-config  -- take the agent's APPROVED mapping and emit:
                     { "config": <template-config.json>,
                       "inject_requests": [ replaceAllText ... ] }
                   build-config works for both tiers: if the mapping carries a
                   shape_catalog (Tier 2), it is merged into the config.

Usage:
  python classify_template.py --mode analyze \
    --presentation /tmp/read_presentation.json --output /tmp/analysis.json

  python classify_template.py --mode build-config \
    --mapping /tmp/approved_mapping.json --output /tmp/onboard.json

read_presentation dump schema (from the MCP tool):
  {"id": "...", "title": "...",
   "slides": [{"slideId": "g...", "texts": ["...", "..."],
               "images": [...], "tables": [...]}, ...]}

approved mapping schema (produced by the agent after the approval gate):
  {
    "template_name": "Acme Deck",
    "source_template_id": "<client original, untouched>",
    "master_template_id": "<the tokenized copy decks are built from>",
    "slides": [
      {"type": "COVER", "slide_id": "g..._2", "fixed": false,
       "tokens": [
         {"key": "COVER-TITLE",    "match_text": "Presentation title"},
         {"key": "COVER-SUBTITLE", "match_text": "Subtitle goes here"}
       ]},
      {"type": "THANKS", "slide_id": "g..._9", "fixed": true, "tokens": []}
    ],
    "autofill_fields": {"AGENDA": ["ITEM1", "ITEM2", "ITEM3"]},
    "toolbox_slide_ids": [],
    "shape_catalog": {            // OPTIONAL (Tier 2)
      "single_token_shapes": {"COVER-TITLE": {"shape_id": "g..._3",
                                              "default_pt": 44, "max_chars": 30}},
      "multi_token_shapes":  {},
      "bullet_shapes":       {"1COL-BODY": "g..._38"}
    }
  }
"""

import argparse
import json
import sys
from pathlib import Path


# -- Mode: analyze ------------------------------------------------------------

def _guess_role(idx: int, text: str, total: int) -> str:
    """Cheap heuristic role hint. The agent makes the final decision; this is
    only a starting suggestion based on order and length."""
    n = len(text)
    if idx == 0 and n <= 60:
        return "title?"
    if idx == 1 and n <= 80:
        return "subtitle?"
    if n <= 4:
        return "number/stat?"
    if n <= 25:
        return "heading?"
    return "body?"


def analyze(presentation: dict) -> dict:
    """Structure a read_presentation dump for the agent's classification step."""
    slides_out = []
    for s_idx, slide in enumerate(presentation.get("slides", [])):
        texts = [t for t in slide.get("texts", []) if t and t.strip()]
        boxes = []
        # Detect duplicate strings on the same slide -- replaceAllText cannot
        # disambiguate identical text within one slide, so flag for the agent.
        seen: dict[str, int] = {}
        for t in texts:
            seen[t] = seen.get(t, 0) + 1
        for b_idx, t in enumerate(texts):
            boxes.append({
                "order": b_idx,
                "text": t,
                "char_len": len(t),
                "role_guess": _guess_role(b_idx, t, len(texts)),
                "duplicate_on_slide": seen[t] > 1,
            })
        slides_out.append({
            "slide_index": s_idx,
            "slide_id": slide.get("slideId") or slide.get("slide_id"),
            "num_text_boxes": len(boxes),
            "num_images": len(slide.get("images", [])),
            "num_tables": len(slide.get("tables", [])),
            "boxes": boxes,
        })

    warnings = []
    for s in slides_out:
        dups = [b["text"] for b in s["boxes"] if b["duplicate_on_slide"]]
        if dups:
            warnings.append(
                f"Slide {s['slide_index']} (id {s['slide_id']}): duplicate text "
                f"{sorted(set(dups))} -- Tier 1 replaceAllText cannot target these "
                f"separately. Rename one box in the template, or use Tier 2."
            )
        if s["num_text_boxes"] == 0 and s["num_images"] == 0:
            warnings.append(
                f"Slide {s['slide_index']} (id {s['slide_id']}): no text boxes "
                f"detected -- likely a fixed/visual slide (treat as fixed)."
            )

    return {
        "presentation_id": presentation.get("id"),
        "title": presentation.get("title"),
        "slide_count": len(slides_out),
        "slides": slides_out,
        "warnings": warnings,
        "next_step": (
            "Agent: propose a per-slide mapping (type + token per box) and show it "
            "to the user for approval, then call --mode build-config."
        ),
    }


# -- Mode: build-config -------------------------------------------------------

def _field_from_token(token_key: str, slide_type: str) -> str:
    """field = token_key with the leading '<TYPE>-' stripped."""
    prefix = f"{slide_type}-"
    return token_key[len(prefix):] if token_key.startswith(prefix) else token_key


def build_config(mapping: dict) -> dict:
    """Produce the template-config.json catalog and token-injection requests."""
    slides = mapping["slides"]

    # template_order = unique types in first-seen order.
    template_order: list[str] = []
    slide_ids: dict[str, str] = {}
    for s in slides:
        t = s["type"]
        if t not in slide_ids:
            template_order.append(t)
            slide_ids[t] = s["slide_id"]

    fixed_slides = sorted({s["type"] for s in slides if s.get("fixed")})

    # Optional Tier 2 shape catalog.
    shape_catalog = mapping.get("shape_catalog", {}) or {}
    single_token_shapes = shape_catalog.get("single_token_shapes", {})
    multi_token_shapes = shape_catalog.get("multi_token_shapes", {})
    bullet_shapes = shape_catalog.get("bullet_shapes", {})

    config = {
        "template_name": mapping.get("template_name", "Untitled template"),
        "source_template_id": mapping.get("source_template_id"),
        "master_template_id": mapping.get("master_template_id"),
        "tier": 2 if shape_catalog else 1,
        "template_order": template_order,
        "slide_ids": slide_ids,
        "toolbox_slide_ids": mapping.get("toolbox_slide_ids", []),
        "single_token_shapes": single_token_shapes,
        "multi_token_shapes": multi_token_shapes,
        "bullet_shapes": bullet_shapes,
        "autofill_fields": mapping.get("autofill_fields", {}),
        "fixed_slides": fixed_slides,
    }

    # Token-injection requests: replace each box's existing text with its token,
    # scoped to the slide so identical strings on other slides are untouched.
    inject_requests: list[dict] = []
    issues: list[str] = []
    for s in slides:
        slide_id = s["slide_id"]
        slide_type = s["type"]
        for tok in s.get("tokens", []):
            key = tok["key"]
            match_text = tok.get("match_text")
            if not key.startswith(f"{slide_type}-"):
                issues.append(
                    f"Token '{key}' on slide {slide_id} does not start with "
                    f"'{slide_type}-'. Token keys MUST be '<TYPE>-<FIELD>'."
                )
            if not match_text:
                issues.append(
                    f"Token '{key}' has no match_text -- cannot inject via "
                    f"replaceAllText (Tier 1). Provide the box's current text."
                )
                continue
            inject_requests.append({
                "replaceAllText": {
                    "containsText": {"text": match_text, "matchCase": True},
                    "replaceText": f"{{{{{key}}}}}",
                    "pageObjectIds": [slide_id],
                }
            })

    if issues:
        raise ValueError("build-config rejected the mapping:\n  - " + "\n  - ".join(issues))

    return {"config": config, "inject_requests": inject_requests}


# -- CLI ----------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Onboarding helper: analyze a template and build its catalog.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--mode", choices=["analyze", "build-config"], required=True)
    parser.add_argument("--presentation", help="[analyze] Path to read_presentation JSON dump")
    parser.add_argument("--mapping", help="[build-config] Path to approved mapping JSON")
    parser.add_argument("--output", help="Write result JSON to this file instead of stdout")
    args = parser.parse_args()

    if args.mode == "analyze":
        if not args.presentation:
            parser.error("--presentation required for --mode analyze")
        result = analyze(json.loads(Path(args.presentation).read_text()))
    else:
        if not args.mapping:
            parser.error("--mapping required for --mode build-config")
        result = build_config(json.loads(Path(args.mapping).read_text()))

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2))
        print(f"Wrote result to {args.output}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
