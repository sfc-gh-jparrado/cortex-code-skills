"""
Font-fit calculation for branded Google Slides decks.

After replaceAllText, every modified shape loses TEXT_AUTOFIT (reset to NONE
by the Google Slides API). This module calculates a fitting font size so
updateTextStyle can restore the visual intent.

Formula:
    new_size = floor(default_size x (max_chars / actual_chars))

Only fires when actual_chars > max_chars. Clamps to min_font_size (8pt)
to prevent unreadably tiny text.

This module is generic and template-agnostic: it is reused verbatim by both
the local CoCo path (build_payload.py) and the server-side CoWork path
(cowork/build_deck_proc.py).
"""

import math


def calculate_font_size(
    content: str,
    max_chars: int,
    default_font_size: int,
    min_font_size: int = 8,
) -> int:
    """Return the fitted font size for content in a shape.

    Args:
        content: The actual text being placed in the shape.
        max_chars: Empirical char limit for the shape (from template-config.json).
        default_font_size: The shape's original font size in points.
        min_font_size: Floor to prevent illegibly tiny text. Default 8pt.

    Returns:
        Fitted font size in points. Unchanged if content fits within max_chars.
    """
    actual = len(content)
    if actual <= max_chars or max_chars <= 0:
        return default_font_size
    fitted = math.floor(default_font_size * (max_chars / actual))
    return max(fitted, min_font_size)


def make_update_text_style_request(
    object_id: str,
    font_size_pt: int,
) -> dict:
    """Build a Slides API updateTextStyle request for a font size change.

    Args:
        object_id: The shape's objectId.
        font_size_pt: Font size in points to apply.

    Returns:
        A dict suitable for inclusion in a batch_update_presentation request.
    """
    return {
        "updateTextStyle": {
            "objectId": object_id,
            "textRange": {"type": "ALL"},
            "style": {
                "fontSize": {"magnitude": font_size_pt, "unit": "PT"}
            },
            "fields": "fontSize",
        }
    }


if __name__ == "__main__":
    # Quick sanity check
    cases = [
        ("Short text under limit", "This is short.", 120, 42),
        ("Exactly at limit", "x" * 120, 120, 42),
        ("50% over limit", "x" * 180, 120, 42),
        ("3x over limit", "x" * 360, 120, 42),
        ("Extreme - hits floor", "x" * 3000, 120, 42),
    ]
    print(f"{'Case':<30} {'actual':>6} {'max':>5} {'default':>8} {'fitted':>7}")
    print("-" * 60)
    for label, content, max_c, default in cases:
        fitted = calculate_font_size(content, max_c, default)
        print(f"{label:<30} {len(content):>6} {max_c:>5} {default:>8} {fitted:>7}")
