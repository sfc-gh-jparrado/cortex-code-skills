# Content guide (neutral)

Guidance the agent applies when drafting deck content. This is brand-neutral on
purpose -- edit it to match the customer's voice once their template is onboarded.

## Titles

- Lead with the point, not the topic. Prefer "Revenue grew 40% on new markets"
  over "Revenue update".
- Keep slide titles to ~6-8 words. Cover titles can be punchier (3-6 words); push
  detail into the subtitle.
- Every title should pass the "so what?" test: it states a takeaway, not a label.

## Subtitles

- One sentence, one clause. Outcome-oriented. Roughly 8-16 words.
- Avoid restating the title. Add the "why it matters" or the supporting detail.

## Body

- Complete thoughts, not fragments. 1 idea per line.
- ~15-30 words per bullet/line. Trim filler.
- Use plain `\n`-separated lines. Do **not** type bullet characters
  (`-`, `*`, the dot) -- the template's own list formatting renders bullets.
- Never emit `\n\n` (double newline) -- it creates an empty paragraph and overflows.
- Numbers/stats slides: keep the big number short (e.g. `40%`, `>10M`); put words
  in the supporting line, not the number box.

## Structure

- Open with context or the problem, not the solution.
- Alternate layouts for visual variety; avoid 3+ identical text-only slides in a row.
- The last content slide before the closing should carry a clear call to action.
- Practical limit ~20 slides; suggest splitting longer decks by section.

## Tier 1 vs Tier 2

- **Tier 1** (no shape catalog): the agent has no programmatic font-fit, so respect
  length. If a field looks long, shorten it or recommend the Tier 2 upgrade.
- **Tier 2** (shape catalog present): font-fit and bullet presets apply automatically
  on original (non-duplicated) slides. Duplicated slides still need shorter content.

## Never

- Placeholder filler: "Lorem ipsum", "Item 1", "TBD".
- Replacing a colored-background box with an empty string (it collapses/disappears).
- Inventing brand claims, logos, or metrics that weren't provided.
