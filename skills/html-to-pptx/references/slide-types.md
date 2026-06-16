# Slide Type Catalog

Complete python-pptx patterns for each slide type used in Snowflake-branded presentations.

## 1. Title Slide

Dark header band (top ~56% of slide), colorstack title, subtitle below, logo top-right, keyword pills at bottom.

```python
slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout
add_background(slide, SF_WHITE)

# Dark blue header band
add_rect(slide, Inches(0), Inches(0), SLIDE_W, Inches(4.2), SF_MID_BLUE)

# Logo (official white PNG) -- top-right of header
logo_path = "<project_dir>/snowflake_logo_white.png"
logo_w = Inches(3.0)
logo_h = Inches(0.69)  # preserve aspect ratio 1221x279
logo_left = SLIDE_W - logo_w - Inches(0.8)
logo_top = Inches(0.4)
slide.shapes.add_picture(logo_path, logo_left, logo_top, logo_w, logo_h)

# Title with colorstack (first word in SF_BLUE, rest in white)
txBox = slide.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(10), Inches(1.5))
tf = txBox.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
accent_run = p.add_run()
accent_run.text = "FIRST WORD "
accent_run.font.size = Pt(44)
accent_run.font.color.rgb = SF_BLUE
accent_run.font.bold = True
accent_run.font.name = "Calibri"
main_run = p.add_run()
main_run.text = "REST OF TITLE"
main_run.font.size = Pt(44)
main_run.font.color.rgb = SF_WHITE
main_run.font.bold = True
main_run.font.name = "Calibri"

# Subtitle
add_text_box(slide, Inches(0.8), Inches(3.2), Inches(10), Inches(0.7),
             "Subtitle text here.",
             font_size=20, color=RGBColor(0xCC, 0xDD, 0xEE))

# Keyword pills (optional, for 2-4 key themes)
pill_data = [
    ("KEYWORD1", SF_BLUE),
    ("KEYWORD2", SF_STAR_BLUE),
    ("KEYWORD3", SF_MID_BLUE),
]
for i, (label, color) in enumerate(pill_data):
    x = Inches(0.8 + i * 3.2)
    add_rounded_rect(slide, x, Inches(5.0), Inches(2.8), Inches(0.7), color)
    add_text_box(slide, x, Inches(5.0), Inches(2.8), Inches(0.7),
                 label, font_size=20, color=SF_WHITE, bold=True,
                 alignment=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
```

**Colorstack rule:** Split the `<h1>` text. The first semantically distinct word(s) use `SF_BLUE`, the rest use `SF_WHITE`. For example: "WHY " (blue) + "SNOWFLAKE CORTEX AGENTS" (white).

## 2. Problem / Intro Slide

Big opening statement with body text. Good for the "why this matters" framing.

```python
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_background(slide, SF_WHITE)

# Top accent bar
add_rect(slide, Inches(0), Inches(0), SLIDE_W, Inches(0.08), SF_BLUE)

# Section label (small, uppercase)
add_text_box(slide, Inches(0.8), Inches(0.5), Inches(5), Inches(0.5),
             "THE CHALLENGE", font_size=14, color=SF_BLUE, bold=True)

# Big statement
add_text_box(slide, Inches(0.8), Inches(1.2), Inches(11), Inches(1.5),
             "Main impactful statement here.",
             font_size=36, color=SF_DARK, bold=True)

# Left accent line
add_rect(slide, Inches(0.8), Inches(3.2), Inches(0.06), Inches(2.5), SF_BLUE)

# Body text
add_text_box(slide, Inches(1.2), Inches(3.2), Inches(10), Inches(2.5),
             "Supporting narrative text...",
             font_size=20, color=SF_BODY)
```

## 3. Executive Summary Slide (Multi-Column Cards)

2-4 pillar cards side by side. Each card has a colored header bar, title, tagline, and bullets.

```python
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_background(slide, SF_WHITE)
add_rect(slide, Inches(0), Inches(0), SLIDE_W, Inches(0.08), SF_BLUE)

# Headline
add_text_box(slide, Inches(0.8), Inches(0.4), Inches(11), Inches(0.8),
             "Headline Across All Pillars",
             font_size=34, color=SF_MID_BLUE, bold=True)

# Calculate column layout
num_cols = 3  # adjust for 2-4 columns
total_width = 11.7  # usable width in inches
gap = 0.4
col_w_val = (total_width - gap * (num_cols - 1)) / num_cols
col_w = Inches(col_w_val)
col_gap = Inches(gap)
col_start_x = Inches(0.8)
col_top = Inches(1.6)

pillar_defs = [
    {
        "name": "PILLAR NAME",
        "color": SF_BLUE,          # header bar color
        "bg": RGBColor(0xD6, 0xF0, 0xFB),  # card background (light tint of color)
        "tagline": "Short tagline",
        "bullets": ["Bullet point 1", "Bullet point 2"],
    },
    # ... repeat for each pillar
]

for i, pil in enumerate(pillar_defs):
    cx = col_start_x + i * (col_w + col_gap)

    # Card background
    add_rounded_rect(slide, cx, col_top, col_w, Inches(5.0), pil["bg"])

    # Colored header bar
    add_rect(slide, cx, col_top, col_w, Inches(0.65), pil["color"])

    # Pillar name in header
    add_text_box(slide, cx, col_top, col_w, Inches(0.65),
                 pil["name"], font_size=22, color=SF_WHITE, bold=True,
                 alignment=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

    # Tagline
    add_text_box(slide, cx + Inches(0.25), col_top + Inches(0.9),
                 col_w - Inches(0.5), Inches(0.7),
                 pil["tagline"], font_size=18, color=SF_DARK, bold=True)

    # Bullets
    add_bullet_list(slide, cx + Inches(0.25), col_top + Inches(1.7),
                    col_w - Inches(0.5), Inches(3.0),
                    pil["bullets"], font_size=15, color=SF_BODY,
                    bullet_color=pil["color"])
```

**Light tint colors for card backgrounds:**
- SF_BLUE tint: `RGBColor(0xD6, 0xF0, 0xFB)`
- SF_STAR_BLUE tint: `RGBColor(0xD6, 0xF4, 0xF6)`
- SF_MID_BLUE tint: `RGBColor(0xD6, 0xE4, 0xEE)`
- SF_ORANGE tint: `RGBColor(0xFB, 0xE8, 0xD6)`

## 4. Detail Slide (Icon + Heading + Bullets)

Single-topic deep dive. Icon circle top-left, heading, intro line, bullet list.

```python
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_background(slide, SF_WHITE)

# Top accent bar (use the pillar's brand color)
accent_color = SF_BLUE  # or SF_STAR_BLUE, SF_MID_BLUE
add_rect(slide, Inches(0), Inches(0), SLIDE_W, Inches(0.08), accent_color)

# Icon circle
icon_bg = RGBColor(0xD6, 0xF0, 0xFB)  # light tint matching accent
icon_circle = slide.shapes.add_shape(
    MSO_SHAPE.OVAL, Inches(0.8), Inches(0.6), Inches(0.9), Inches(0.9))
icon_circle.fill.solid()
icon_circle.fill.fore_color.rgb = icon_bg
icon_circle.line.fill.background()

# Icon emoji inside circle
add_text_box(slide, Inches(0.8), Inches(0.6), Inches(0.9), Inches(0.9),
             "\u26A1", font_size=32, color=accent_color,
             alignment=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

# Heading
add_text_box(slide, Inches(2.0), Inches(0.7), Inches(5), Inches(0.7),
             "SECTION TITLE", font_size=36, color=SF_DARK, bold=True)

# Intro line
add_text_box(slide, Inches(0.8), Inches(1.8), Inches(11), Inches(0.6),
             "One-line summary of this section.",
             font_size=22, color=SF_BODY)

# Bullet list
bullets = [
    "Key point one with detail",
    "Key point two with detail",
    "Key point three with detail",
    "Key point four with detail",
]
add_bullet_list(slide, Inches(0.8), Inches(2.8), Inches(11), Inches(4),
                bullets, font_size=18, color=SF_BODY, bullet_color=accent_color)
```

**Icon suggestions by topic:**
- Easy/Speed: `\u26A1` (lightning)
- Connected/Integration: `\U0001F517` (link)
- Trusted/Security: `\U0001F6E1` (shield)
- Data/Analytics: `\U0001F4CA` (chart)
- AI/Intelligence: `\U0001F9E0` (brain)
- Settings/Config: `\u2699` (gear)

## 5. Comparison Table Slide

Table with header row, alternating row colors, and check/cross/partial indicators.

```python
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_background(slide, SF_WHITE)
add_rect(slide, Inches(0), Inches(0), SLIDE_W, Inches(0.08), SF_BLUE)

add_text_box(slide, Inches(0.8), Inches(0.4), Inches(10), Inches(0.7),
             "TABLE TITLE", font_size=28, color=SF_MID_BLUE, bold=True)

rows = 7  # header + data rows
cols = 4
tbl_shape = slide.shapes.add_table(
    rows, cols, Inches(0.8), Inches(1.3), Inches(11.7), Inches(5.2))
table = tbl_shape.table

# Set column widths (adjust per content)
table.columns[0].width = Inches(2.2)
table.columns[1].width = Inches(3.5)
table.columns[2].width = Inches(3.0)
table.columns[3].width = Inches(3.0)

# Style header row
headers = ["Capability", "Snowflake", "Competitor A", "Competitor B"]
for ci, h in enumerate(headers):
    cell = table.cell(0, ci)
    cell.fill.solid()
    cell.fill.fore_color.rgb = SF_MID_BLUE
    p = cell.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    run.text = h
    run.font.size = Pt(13)
    run.font.color.rgb = SF_WHITE
    run.font.bold = True
    run.font.name = "Calibri"
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE

# Style data rows with indicator coloring
# For each cell, check the content prefix:
#   "\u2713" (check) -> SF_GREEN symbol, SF_MID_BLUE text (Snowflake col) or SF_BODY (others)
#   "\u2717" (cross) -> SF_GRAY symbol and text
#   "~" (partial)    -> SF_ORANGE symbol, SF_BODY text
# First column (labels): SF_DARK, bold
# Alternating row backgrounds: odd=SF_WHITE, even=SF_LIGHT

# Remove default table borders for cleaner look:
from pptx.oxml.ns import qn
tbl_el = table._tbl
tbl_pr = tbl_el.find(qn("a:tblPr"))
if tbl_pr is None:
    tbl_pr = tbl_el.makeelement(qn("a:tblPr"), {})
    tbl_el.insert(0, tbl_pr)
tbl_pr.set("bandRow", "0")
```

## 6. Stats Slide

Large numbers with labels, arranged in a grid.

```python
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_background(slide, SF_WHITE)
add_rect(slide, Inches(0), Inches(0), SLIDE_W, Inches(0.08), SF_BLUE)

add_text_box(slide, Inches(0.8), Inches(0.4), Inches(10), Inches(0.7),
             "BY THE NUMBERS", font_size=28, color=SF_MID_BLUE, bold=True)

stats = [
    ("200+", "Partner Integrations", SF_BLUE),
    ("10x", "Faster Development", SF_STAR_BLUE),
    ("100%", "Data Stays In Place", SF_MID_BLUE),
]

num_stats = len(stats)
card_w = Inches(3.4)
gap = Inches(0.4)
start_x = Inches(0.8)
card_top = Inches(2.0)

for i, (number, label, color) in enumerate(stats):
    cx = start_x + i * (card_w + gap)

    # Card background
    add_rounded_rect(slide, cx, card_top, card_w, Inches(3.5), SF_LIGHT)

    # Accent bar at top of card
    add_rect(slide, cx, card_top, card_w, Inches(0.08), color)

    # Big number
    add_text_box(slide, cx, card_top + Inches(0.5), card_w, Inches(1.5),
                 number, font_size=60, color=color, bold=True,
                 alignment=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

    # Label
    add_text_box(slide, cx + Inches(0.2), card_top + Inches(2.2),
                 card_w - Inches(0.4), Inches(1.0),
                 label, font_size=18, color=SF_BODY,
                 alignment=PP_ALIGN.CENTER)
```

## 7. CTA / Closing Slide

Dark background, big call-to-action text, button, logo, copyright.

```python
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_background(slide, SF_MID_BLUE)

# Logo (official white PNG) -- top-right, slightly larger
logo_w = Inches(4.0)
logo_h = Inches(0.91)  # preserve aspect ratio 1221x279
logo_left = SLIDE_W - logo_w - Inches(0.8)
logo_top = Inches(0.5)
slide.shapes.add_picture(logo_path, logo_left, logo_top, logo_w, logo_h)

# Big CTA text
add_text_box(slide, Inches(0.8), Inches(2.0), Inches(10), Inches(1.2),
             "Ready to get started?",
             font_size=44, color=SF_WHITE, bold=True)

# CTA button
add_rounded_rect(slide, Inches(0.8), Inches(4.5), Inches(4), Inches(0.85), SF_BLUE)
add_text_box(slide, Inches(0.8), Inches(4.5), Inches(4), Inches(0.85),
             "GET STARTED \u2192", font_size=22, color=SF_WHITE, bold=True,
             alignment=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

# Copyright footer
add_text_box(slide, Inches(0.8), Inches(6.5), Inches(10), Inches(0.5),
             "\u00A9 2026 Snowflake Inc. All Rights Reserved.",
             font_size=12, color=RGBColor(0x88, 0xAA, 0xBB))
```

## 8. Callout Slide

Highlight a key quote, stat, or insight.

```python
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_background(slide, SF_WHITE)
add_rect(slide, Inches(0), Inches(0), SLIDE_W, Inches(0.08), SF_BLUE)

# Centered callout box
box_w = Inches(10)
box_h = Inches(3.5)
box_left = (SLIDE_W - box_w) / 2
box_top = Inches(2.0)

add_rounded_rect(slide, box_left, box_top, box_w, box_h, SF_LIGHT)

# Left accent bar inside callout
add_rect(slide, box_left + Inches(0.2), box_top + Inches(0.3),
         Inches(0.08), box_h - Inches(0.6), SF_BLUE)

# Callout text
add_text_box(slide, box_left + Inches(0.6), box_top + Inches(0.4),
             box_w - Inches(1.2), box_h - Inches(0.8),
             "Key insight or quote goes here.",
             font_size=28, color=SF_MID_BLUE, bold=True)
```
