/**
 * extract_catalog.gs -- OPTIONAL Tier 2 onboarding for the creacion-google-slides skill.
 *
 * The Google Workspace MCP only exposes slide text and slide objectIds, not the
 * internal shape objectIds, font sizes, or placeholder types. Those are needed
 * for programmatic font-fit and bullet formatting. This Apps Script reads them
 * directly from the Slides API and prints a JSON catalog you paste back to CoCo.
 *
 * HOW TO RUN (one time per template):
 *   1. Open your tokenized master deck in Google Slides
 *      (the COPY that CoCo created during onboarding, not your original).
 *   2. Extensions > Apps Script.
 *   3. Paste this whole file, save.
 *   4. Set PRESENTATION_ID below to your master deck's ID
 *      (the long string in its URL: /presentation/d/<THIS>/edit).
 *   5. Run extractCatalog. Authorize when prompted.
 *   6. View > Logs (or Execution log). Copy the JSON and paste it back to CoCo,
 *      saying: "here is the Tier 2 shape catalog".
 *
 * CoCo merges this into template-config.json as the shape_catalog, unlocking
 * font-fit, bullets, and autofit repair (full parity with the Snowflake deck skill).
 */

// EDIT THIS: your tokenized master deck's presentation ID.
var PRESENTATION_ID = 'PASTE_YOUR_MASTER_PRESENTATION_ID_HERE';

function extractCatalog() {
  var pres = Slides.Presentations.get(PRESENTATION_ID);
  var out = {
    presentation_id: PRESENTATION_ID,
    title: pres.title || '',
    slides: []
  };

  (pres.slides || []).forEach(function (slide, sIdx) {
    var slideEntry = {
      slide_index: sIdx,
      slide_id: slide.objectId,
      shapes: []
    };
    (slide.pageElements || []).forEach(function (el) {
      if (!el.shape || !el.shape.text) return;

      // Collect text + tokens present in this shape.
      var fullText = '';
      var defaultPt = null;
      (el.shape.text.textElements || []).forEach(function (te) {
        if (te.textRun && te.textRun.content) {
          fullText += te.textRun.content;
          if (defaultPt === null &&
              te.textRun.style &&
              te.textRun.style.fontSize &&
              te.textRun.style.fontSize.magnitude) {
            defaultPt = te.textRun.style.fontSize.magnitude;
          }
        }
      });
      fullText = fullText.replace(/\s+$/, '');
      if (!fullText) return;

      // Find {{TOKEN}} occurrences already injected in Tier 1.
      var tokens = (fullText.match(/\{\{[^}]+\}\}/g) || []).map(function (t) {
        return t.replace(/[{}]/g, '');
      });

      var ph = (el.shape.placeholder && el.shape.placeholder.type) || null;
      var size = el.size || {};
      var w = size.width ? size.width.magnitude : null;
      var h = size.height ? size.height.magnitude : null;
      var tx = el.transform ? el.transform.translateX : null;
      var ty = el.transform ? el.transform.translateY : null;

      slideEntry.shapes.push({
        shape_id: el.objectId,
        placeholder: ph,
        default_pt: defaultPt,
        text: fullText,
        tokens: tokens,
        x: tx, y: ty, w: w, h: h
      });
    });
    out.slides.push(slideEntry);
  });

  Logger.log(JSON.stringify(out, null, 2));
  return out;
}
