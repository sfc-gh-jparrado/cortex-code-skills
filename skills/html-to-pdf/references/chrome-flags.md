# Chrome Headless PDF Flags Reference

Quick reference for Chrome headless PDF generation flags.

## Correct Command (Modern)

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new \
  --disable-gpu \
  --no-sandbox \
  --print-to-pdf="/absolute/path/output.pdf" \
  --no-pdf-header-footer \
  "file:///absolute/path/input.html"
```

## Flag Compatibility Matrix

| Headless Flag | Header/Footer Flag | Result |
|---|---|---|
| `--headless=new` | `--no-pdf-header-footer` | Clean PDF, no metadata |
| `--headless=new` | `--print-to-pdf-no-header` | **BROKEN** — old flag ignored, metadata appears |
| `--headless=new` | *(none)* | Chrome adds date, title, URL, page numbers |
| `--headless` (old) | `--print-to-pdf-no-header` | **BROKEN** — metadata still appears |
| `--headless` (old) | `--no-pdf-header-footer` | Flag not recognized by old headless |

**Rule: Always use `--headless=new` with `--no-pdf-header-footer`.**

## Additional Useful Flags

| Flag | Purpose |
|---|---|
| `--print-to-pdf-no-header` | **DEPRECATED** — do not use |
| `--virtual-time-budget=5000` | Wait 5s for JS rendering before PDF capture |
| `--run-all-compositor-stages-before-draw` | Ensure all rendering completes |
| `--window-size=1280,720` | Set viewport (affects responsive CSS) |

## Chrome Binary Locations

| OS | Path |
|---|---|
| macOS | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` |
| Linux (Chrome) | `google-chrome` or `google-chrome-stable` |
| Linux (Chromium) | `chromium-browser` or `chromium` |
| Windows | `C:\Program Files\Google\Chrome\Application\chrome.exe` |

## Print CSS Essentials

For background colors to render in PDF, the HTML **must** include:

```css
-webkit-print-color-adjust: exact;
print-color-adjust: exact;
```

Apply to `body` and any element with background colors, gradients, or colored fills.

## Harmless Errors to Ignore

These stderr messages do NOT affect PDF output:

- `[ERROR:gcm_channel.cc(...)] GCM channel request failed.`
- `[ERROR:command_buffer_proxy_impl.cc(...)] ...`
- `[WARNING:gpu_process_host.cc(...)] ...`
