#!/usr/bin/env python3
"""
build_payload.py -- Generic branded-slides payload builder (config-driven)

Offloads ALL mechanical orchestration into deterministic Python so the LLM
only has to think about content.  It is fully template-agnostic: instead of any
hardcoded slide/shape IDs, it loads a per-customer catalog from a
template-config.json file produced once during onboarding (see
classify_template.py).

Four modes:

  reorder   -- compute updateSlidesPosition requests
  tokens    -- compute replaceAllText + updateTextStyle + createParagraphBullets
  structure -- compute deleteObject + duplicateObject from content dict + config
  fill      -- auto-assign slide IDs, then compute reorder + tokens in one shot

Usage:
  python build_payload.py --mode structure \
    --config /path/to/template-config.json \
    --input '{"slides":[{"type":"COVER","fields":{...}},...]}'

  python build_payload.py --mode fill \
    --config /path/to/template-config.json \
    --current-slides '["id0","id1",...]' \
    --input '{"slides":[{"type":"COVER","fields":{...}},...]}'

Output: JSON.  structure/fill print objects with metadata; reorder/tokens print
bare arrays ready for batch_update_presentation.  Use --output to write to a
file (recommended -- stdout can be large).

template-config.json schema (produced by classify_template.py):
{
  "template_name": "Acme Corp Deck",
  "source_template_id": "<client original, untouched>",
  "master_template_id": "<tokenized copy we build decks from>",
  "template_order":  ["COVER", "AGENDA", "1COL", "2COL-T", "THANKS"],
  "slide_ids":       {"COVER": "g..._2", "1COL": "g..._37", ...},
  "toolbox_slide_ids": ["g..._900", ...],
  "single_token_shapes": {
    "COVER-TITLE": {"shape_id": "g..._3", "default_pt": 44, "max_chars": 30}
  },
  "multi_token_shapes": {
    "g..._34": {"default_pt": 26, "tokens": {"CH-LABEL": 20, "CH-TITLE": 25}}
  },
  "bullet_shapes":   {"1COL-BODY": "g..._38"},
  "autofill_fields": {"AGENDA": ["ITEM1", "ITEM2", "ITEM3"]},
  "fixed_slides":    ["THANKS", "SAFE-HARBOR"]
}
"""

import argparse
import json
import math
import sys
from pathlib import Path

# Make font_fit importable regardless of CWD.
_script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_script_dir))

try:
    from font_fit import calculate_font_size, make_update_text_style_request
except ImportError:
    def calculate_font_size(content, max_chars, default_font_size, min_font_size=8):
        actual = len(content)
        if actual <= max_chars or max_chars <= 0:
            return default_font_size
        fitted = math.floor(default_font_size * (max_chars / actual))
        return max(fitted, min_font_size)

    def make_update_text_style_request(object_id, font_size_pt):
        return {
            "updateTextStyle": {
                "objectId": object_id,
                "textRange": {"type": "ALL"},
                "style": {"fontSize": {"magnitude": font_size_pt, "unit": "PT"}},
                "fields": "fontSize",
            }
        }


BULLET_PRESETS = {
    "unordered": "BULLET_DISC_CIRCLE_SQUARE",
    "ordered": "NUMBERED_DIGIT_ALPHA_ROMAN",
}


# -- Config loading -----------------------------------------------------------

class TemplateConfig:
    """Parsed view over a template-config.json catalog."""

    def __init__(self, data: dict):
        self.data = data
        self.template_order: list[str] = data["template_order"]
        self.slide_ids: dict[str, str] = data["slide_ids"]
        self.toolbox_slide_ids: list[str] = data.get("toolbox_slide_ids", [])
        self.toolbox_set: set[str] = set(self.toolbox_slide_ids)

        # single_token_shapes: "TOKEN-KEY" -> {shape_id, default_pt, max_chars}
        self.single_token_shapes: dict[str, dict] = data.get("single_token_shapes", {})

        # multi_token_shapes: shape_id -> {default_pt, tokens:{TOKEN-KEY:max_chars}}
        self.multi_token_shapes: dict[str, dict] = data.get("multi_token_shapes", {})

        # bullet_shapes: "TOKEN-KEY" -> shape_id
        self.bullet_shapes: dict[str, str] = data.get("bullet_shapes", {})

        # autofill_fields: "TYPE" -> [field, ...]
        self.autofill_fields: dict[str, list[str]] = data.get("autofill_fields", {})

        self.fixed_slides: list[str] = data.get("fixed_slides", [])

        # Reverse lookup: token_key -> multi-token shape_id
        self._multi_lookup: dict[str, str] = {}
        for shape_id, spec in self.multi_token_shapes.items():
            for token_key in spec.get("tokens", {}):
                self._multi_lookup[token_key] = shape_id

        self._validate()

    def _validate(self) -> None:
        missing = [t for t in self.template_order if t not in self.slide_ids]
        if missing:
            raise ValueError(
                f"Config invalid: template_order types missing from slide_ids: {missing}"
            )

    @classmethod
    def load(cls, path: str) -> "TemplateConfig":
        return cls(json.loads(Path(path).read_text()))


# -- Mode: reorder ------------------------------------------------------------

def compute_reorder(current_ids: list[str], desired_ids: list[str]) -> list[dict]:
    """Return updateSlidesPosition requests to go from current to desired order."""
    if sorted(current_ids) != sorted(desired_ids):
        missing = set(desired_ids) - set(current_ids)
        extra = set(current_ids) - set(desired_ids)
        raise ValueError(
            "current_ids and desired_ids must contain the same slide IDs.\n"
            f"  In desired but not current: {missing}\n"
            f"  In current but not desired: {extra}"
        )

    current = list(current_ids)
    requests = []
    for target_pos, slide_id in enumerate(desired_ids):
        current_pos = current.index(slide_id)
        if current_pos != target_pos:
            requests.append({
                "updateSlidesPosition": {
                    "slideObjectIds": [slide_id],
                    "insertionIndex": target_pos,
                }
            })
            current.pop(current_pos)
            current.insert(target_pos, slide_id)
    return requests


# -- Mode: tokens -------------------------------------------------------------

def compute_tokens(cfg: TemplateConfig, slides: list[dict]) -> list[dict]:
    """Return replaceAllText + updateTextStyle + createParagraphBullets requests."""
    # Phase 1: auto-fill unused optional slots (e.g. AGENDA items, SPEAKERS).
    for slide in slides:
        slide_type = slide["type"]
        fields = slide.setdefault("fields", {})
        for optional_field in cfg.autofill_fields.get(slide_type, []):
            if optional_field not in fields:
                fields[optional_field] = " "

    # Phase 2: collect (slide_id, value) per token_key.
    token_usage: dict[str, list[tuple[str, str]]] = {}
    for slide in slides:
        slide_id = slide["slide_id"]
        slide_type = slide["type"]
        for field, value in slide.get("fields", {}).items():
            token_key = f"{slide_type}-{field}"
            token_usage.setdefault(token_key, []).append((slide_id, value))

    requests: list[dict] = []
    font_fit_requests: list[dict] = []

    # Phase 3: replaceAllText (scope to slide when a token repeats across slides).
    for token_key, instances in token_usage.items():
        token_str = f"{{{{{token_key}}}}}"
        needs_scoping = len(instances) > 1
        for slide_id, value in instances:
            rat: dict = {
                "containsText": {"text": token_str, "matchCase": True},
                "replaceText": value,
            }
            if needs_scoping:
                rat["pageObjectIds"] = [slide_id]
            requests.append({"replaceAllText": rat})

        # Phase 4a: font-fit single-token shapes (original slides only).
        if token_key in cfg.single_token_shapes:
            spec = cfg.single_token_shapes[token_key]
            original = next(
                (val for sid, val in instances if not sid.startswith("SLIDES_API")),
                None,
            )
            if original is not None:
                fitted_pt = calculate_font_size(
                    original, spec["max_chars"], spec["default_pt"]
                )
                if fitted_pt != spec["default_pt"]:
                    font_fit_requests.append(
                        make_update_text_style_request(spec["shape_id"], fitted_pt)
                    )

    # Phase 4b: font-fit multi-token shapes (smallest fit across all tokens).
    multi_fit_done: set[str] = set()
    for token_key in token_usage:
        shape_id = cfg._multi_lookup.get(token_key)
        if not shape_id or shape_id in multi_fit_done:
            continue
        multi_fit_done.add(shape_id)

        spec = cfg.multi_token_shapes[shape_id]
        default_pt = spec["default_pt"]
        smallest_pt = default_pt
        for tk, max_chars in spec.get("tokens", {}).items():
            tk_instances = token_usage.get(tk, [])
            original = next(
                (val for sid, val in tk_instances if not sid.startswith("SLIDES_API")),
                None,
            )
            if original is None:
                continue
            fitted = calculate_font_size(original, max_chars, default_pt)
            if fitted < smallest_pt:
                smallest_pt = fitted
        if smallest_pt != default_pt:
            font_fit_requests.append(
                make_update_text_style_request(shape_id, smallest_pt)
            )

    # Phase 5: bullets (original slides only).
    bullet_requests: list[dict] = []
    seen_shape_ids: set[str] = set()
    for slide in slides:
        slide_id = slide["slide_id"]
        slide_type = slide["type"]
        if slide_id.startswith("SLIDES_API"):
            continue
        for field, bullet_type in slide.get("list_type", {}).items():
            preset = BULLET_PRESETS.get(bullet_type)
            if not preset:
                continue
            shape_id = cfg.bullet_shapes.get(f"{slide_type}-{field}")
            if not shape_id or shape_id in seen_shape_ids:
                continue
            seen_shape_ids.add(shape_id)
            bullet_requests.append({
                "createParagraphBullets": {
                    "objectId": shape_id,
                    "textRange": {"type": "ALL"},
                    "bulletPreset": preset,
                }
            })

    return requests + font_fit_requests + bullet_requests


# -- Mode: structure ----------------------------------------------------------

def compute_structure(cfg: TemplateConfig, slides: list[dict]) -> dict:
    """Compute deleteObject + duplicateObject requests from content dict."""
    type_to_id = cfg.slide_ids

    type_counts: dict[str, int] = {}
    for slide in slides:
        t = slide["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    unknown = set(type_counts) - set(cfg.template_order)
    if unknown:
        raise ValueError(
            f"Unknown slide types: {sorted(unknown)}. "
            f"Valid types: {cfg.template_order}"
        )

    requests: list[dict] = []

    # Delete unused template slides.
    for template_type in cfg.template_order:
        if template_type not in type_counts:
            requests.append({"deleteObject": {"objectId": type_to_id[template_type]}})

    # Duplicate types used more than once (scan content dict left-to-right).
    seen: set[str] = set()
    duplicate_order: list[str] = []
    for slide in slides:
        t = slide["type"]
        if t in seen:
            requests.append({"duplicateObject": {"objectId": type_to_id[t]}})
            duplicate_order.append(t)
        else:
            seen.add(t)

    kept_types = [t for t in cfg.template_order if t in type_counts]
    return {
        "requests": requests,
        "kept_types": kept_types,
        "duplicate_order": duplicate_order,
    }


# -- Mode: fill ---------------------------------------------------------------

def compute_fill(cfg: TemplateConfig, current_slide_ids: list[str],
                 slides: list[dict]) -> dict:
    """Auto-assign slide IDs, then compute reorder + token requests."""
    # Strip toolbox slides -- they are never deleted, filled, or moved.
    active_ids = [sid for sid in current_slide_ids if sid not in cfg.toolbox_set]

    unique_types = list(dict.fromkeys(slide["type"] for slide in slides))
    unknown = set(unique_types) - set(cfg.template_order)
    if unknown:
        raise ValueError(
            f"Unknown slide types: {sorted(unknown)}. Valid: {cfg.template_order}"
        )
    kept_in_template_order = sorted(unique_types, key=cfg.template_order.index)

    # Identify the type of every slide by scanning left-to-right.
    # Originals appear in template order; duplicates (SLIDES_API*) inherit the
    # type of the most recent original before them.
    original_idx = 0
    current_type: str | None = None
    type_to_ids: dict[str, list[str]] = {}
    for sid in active_ids:
        if not sid.startswith("SLIDES_API"):
            if original_idx >= len(kept_in_template_order):
                raise ValueError(
                    "Found more original (non-SLIDES_API) slides than expected "
                    f"({len(kept_in_template_order)} unique types). Did you pass "
                    "toolbox/hybrid slide IDs in --current-slides?"
                )
            current_type = kept_in_template_order[original_idx]
            original_idx += 1
        if current_type is None:
            raise ValueError(
                f"First slide ID '{sid}' is a SLIDES_API duplicate with no "
                "preceding original -- cannot determine its type."
            )
        type_to_ids.setdefault(current_type, []).append(sid)

    # Assign slide_ids to content dict entries (original first, then duplicates).
    type_usage: dict[str, int] = {}
    slide_id_map: list[dict] = []
    for slide in slides:
        t = slide["type"]
        idx = type_usage.get(t, 0)
        ids = type_to_ids.get(t, [])
        if idx >= len(ids):
            raise ValueError(
                f"Content dict needs {idx + 1} slides of type '{t}' but only "
                f"{len(ids)} exist in the presentation. Re-run --mode structure."
            )
        slide["slide_id"] = ids[idx]
        type_usage[t] = idx + 1
        slide_id_map.append({"type": t, "slide_id": slide["slide_id"]})

    desired_ids = [s["slide_id"] for s in slides]
    reorder_requests = compute_reorder(active_ids, desired_ids)
    token_requests = compute_tokens(cfg, slides)
    return {
        "requests": reorder_requests + token_requests,
        "slide_id_map": slide_id_map,
    }


# -- CLI ----------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generic branded-slides payload builder (config-driven)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--mode", choices=["reorder", "tokens", "structure", "fill"],
                        required=True)
    parser.add_argument("--config", help="Path to template-config.json (required "
                        "for tokens/structure/fill)")
    parser.add_argument("--current", help="[reorder] JSON array of current slide IDs")
    parser.add_argument("--desired", help="[reorder] JSON array of desired slide IDs")
    parser.add_argument("--input", help='[tokens/structure/fill] JSON content dict')
    parser.add_argument("--input-file", dest="input_file",
                        help="[tokens/structure/fill] Path to JSON content dict "
                        "(use when content has apostrophes that break shell quoting)")
    parser.add_argument("--current-slides",
                        help="[fill] JSON array of slide IDs after structure changes")
    parser.add_argument("--output", help="Write result JSON to this file instead of stdout")

    args = parser.parse_args()

    def get_input(mode_name: str) -> str:
        if args.input_file:
            return Path(args.input_file).read_text()
        if args.input:
            return args.input
        parser.error(f"--input or --input-file required for --mode {mode_name}")

    def get_config() -> TemplateConfig:
        if not args.config:
            parser.error(f"--config required for --mode {args.mode}")
        return TemplateConfig.load(args.config)

    if args.mode == "reorder":
        if not args.current or not args.desired:
            parser.error("--current and --desired required for --mode reorder")
        result = compute_reorder(json.loads(args.current), json.loads(args.desired))

    elif args.mode == "tokens":
        cfg = get_config()
        data = json.loads(get_input("tokens"))
        result = compute_tokens(cfg, data["slides"])

    elif args.mode == "structure":
        cfg = get_config()
        data = json.loads(get_input("structure"))
        result = compute_structure(cfg, data["slides"])

    elif args.mode == "fill":
        cfg = get_config()
        if not args.current_slides:
            parser.error("--current-slides required for --mode fill")
        data = json.loads(get_input("fill"))
        result = compute_fill(cfg, json.loads(args.current_slides), data["slides"])

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        req_count = len(result) if isinstance(result, list) else len(result.get("requests", []))
        print(f"Wrote {req_count} requests to {args.output}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
