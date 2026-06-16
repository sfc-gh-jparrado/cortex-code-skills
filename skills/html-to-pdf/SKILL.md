---
name: html-to-pdf
description: "Convert HTML documents to clean, customer-ready PDFs. Use when: generating PDF, converting HTML to PDF, creating printable documents, exporting proposals. Triggers: PDF, html to pdf, convert to pdf, print pdf, export pdf, generate pdf, customer-ready pdf."
---

# HTML to PDF Conversion

Convert HTML documents to clean, professional PDFs suitable for customer delivery. Uses Chrome headless mode with optimized print CSS.

## Prerequisites

- Google Chrome installed at `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` (macOS) or available as `google-chrome` / `chromium` on PATH (Linux)
- If Chrome is not found, check for Chromium or offer to use Playwright as a fallback

## Workflow

### Step 1: Identify the Source HTML File

Locate the HTML file to convert. Read it to understand its structure and existing styles.

- Note whether it already has a `@media print` CSS block
- Note whether it uses CSS custom properties, gradients, badges, or background colors that need print preservation
- Note the approximate document length to anticipate page count

### Step 2: Enhance Print CSS

If the document lacks print-optimized CSS, or has a minimal `@media print` block, add or replace it with the following template. Insert it at the end of the `<style>` block, before the closing `</style>` tag.

```css
@media print {
  @page {
    size: A4;
    margin: 15mm 12mm 20mm 12mm;
  }
  body {
    background: white;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .header {
    padding: 24px 30px;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .container {
    padding: 10px 0;
    max-width: 100%;
  }
  .section {
    box-shadow: none;
    border: none;
    break-inside: avoid;
    page-break-inside: avoid;
    margin-bottom: 16px;
  }
  .toc {
    box-shadow: none;
    border: none;
    break-inside: avoid;
  }
  .summary-grid { break-inside: avoid; }
  .stat-card {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .module-card {
    break-inside: avoid;
    page-break-inside: avoid;
  }
  table {
    font-size: 11px;
    break-inside: auto;
  }
  tr {
    break-inside: avoid;
    page-break-inside: avoid;
  }
  th {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .callout {
    break-inside: avoid;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .badge {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .coverage-fill {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  tr:hover { background: inherit; }
  a { text-decoration: none; }
  .footer { break-before: avoid; }
}
```

**Key principles for the print CSS:**

- **Color preservation**: Any element with a background color, gradient, or colored fill MUST have both `-webkit-print-color-adjust: exact` and `print-color-adjust: exact`. Without these, Chrome strips background colors in print mode.
- **Page breaks**: Use `break-inside: avoid` (modern) AND `page-break-inside: avoid` (legacy) on content blocks that should not split across pages (sections, cards, callouts, table rows). Use both properties for maximum browser compatibility.
- **Tables**: Allow tables themselves to break across pages (`break-inside: auto`) but prevent individual rows from splitting (`tr { break-inside: avoid }`).
- **Box shadows**: Remove box shadows in print (`box-shadow: none`). Do NOT replace with a border — see warning below.
- **Borders in print**: **Never use `border: 1px solid #ddd` (or any border) on container elements like `.section` or `.toc` in print CSS.** When these elements span page breaks, Chrome draws the left/right borders continuously across pages, creating a visible vertical line running down the margin of the entire PDF. Always use `border: none` for container elements in `@media print`.
- **Hover states**: Reset hover backgrounds (`tr:hover { background: inherit }`) to prevent phantom highlights.
- **Page size**: Default to A4 (`size: A4`) with comfortable margins. Use `size: letter` for US-focused documents if requested.

Adapt the selectors to match the actual class names in the target document. The template above covers common patterns; add additional selectors as needed for the specific document.

### Step 3: Locate Chrome

Find the Chrome binary:

```bash
# macOS
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Linux (try in order)
# google-chrome, google-chrome-stable, chromium-browser, chromium
```

If Chrome is not found, check for Playwright (`npx playwright install chromium`) as a fallback, or inform the user that Chrome is required.

### Step 4: Generate the PDF

Run Chrome in headless mode with the correct flags:

```bash
"${CHROME}" \
  --headless=new \
  --disable-gpu \
  --no-sandbox \
  --print-to-pdf="/path/to/output.pdf" \
  --no-pdf-header-footer \
  "file:///path/to/input.html"
```

**Critical flag details:**

| Flag | Purpose |
|------|---------|
| `--headless=new` | Modern headless mode (required). Do NOT use the old `--headless` flag alone — it uses the legacy headless mode which handles PDF differently. |
| `--disable-gpu` | Prevents GPU-related issues in headless mode |
| `--no-sandbox` | Required in some environments (Docker, CI) |
| `--print-to-pdf="..."` | Output PDF path. Use absolute path. |
| `--no-pdf-header-footer` | **Critical**: Removes Chrome's default header (date, title) and footer (URL, page numbers). Without this flag, Chrome prints distracting metadata on every page. Do NOT use the old `--print-to-pdf-no-header` flag — it does not work with `--headless=new`. |

**Common mistakes to avoid:**
- `--headless` (old) + `--print-to-pdf-no-header` (old) = headers/footers still appear
- `--headless=new` + `--print-to-pdf-no-header` (old) = flag mismatch, headers may appear
- `--headless=new` + `--no-pdf-header-footer` = **correct combination**

The input path MUST be a `file:///` URL with the absolute path to the HTML file.

**Default output naming:** If no output path is specified by the user, name the PDF the same as the HTML file with a `.pdf` extension, in the same directory.

### Step 5: Verify the PDF

After generation:

1. Check that the file was created and note its size
2. Read the first few pages of the PDF to verify:
   - Content renders correctly (text, tables, images)
   - Background colors and gradients are preserved
   - No Chrome metadata headers/footers (date, URL, page numbers)
   - Logo and branding elements render properly
   - Page breaks occur at reasonable points
3. Report the page count and file size to the user

### Step 6: Handle Errors

**Chrome not found:**
- Suggest installing Chrome or using Playwright as fallback
- Playwright command: `npx playwright pdf input.html output.pdf`

**GCM registration errors in stderr:**
- Messages like `[ERROR:gcm_channel.cc]` are harmless Chrome telemetry errors. They do NOT affect PDF output. Ignore them.

**Missing colors/backgrounds in PDF:**
- Add `-webkit-print-color-adjust: exact; print-color-adjust: exact;` to the affected elements
- Regenerate the PDF

**Content cut off or poorly paginated:**
- Add `break-inside: avoid` to sections that are splitting badly
- Consider reducing font size in `@media print` for dense tables
- Increase `@page` margins if content is too close to edges

**WeasyPrint as alternative (if Chrome unavailable):**
- WeasyPrint requires native libraries (`libpango`, `libgobject-2.0`). These are often missing even when WeasyPrint is pip-installed.
- If you see `OSError: cannot load library 'libgobject-2.0-0'`, WeasyPrint will not work without installing system packages (`brew install pango` on macOS, `apt install libpango-1.0-0` on Debian/Ubuntu).
- Prefer Chrome headless over WeasyPrint — it produces more accurate results for complex HTML with CSS gradients, flexbox, and grid layouts.

## Stopping Points

- After Step 2: Confirm print CSS changes before generating
- After Step 5: Present the verified PDF to the user

## Output

A clean, customer-ready PDF file with no browser metadata, preserved colors and branding, and proper page breaks.
