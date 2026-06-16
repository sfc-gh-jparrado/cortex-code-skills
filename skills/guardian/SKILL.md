---
name: guardian
description: "Analyze AI-generated code for quality issues, vulnerabilities, and best practices. Use for ALL requests that mention: review code, code review, security audit, code quality, check vulnerabilities, best practices review, analyze code, guardian, run guardian, code analysis, security scan, vulnerability scan, lint, linting, static analysis, audit code, scan code. Supports Python, JavaScript/TypeScript, React, HTML, Snowflake SQL, YAML. Triggers: guardian, code review, review code, security audit, code quality, check vulnerabilities, static analysis, lint, audit code, scan code, code analysis."
---

# Guardian - Code Quality & Security Analyzer

## Trigger Word Detection

**IMPORTANT:** Before starting the workflow, check the user's message for **trigger words**.

### Auto-Run Trigger Words (skip straight to Step 1 → Step 5 with defaults)
If the user's message contains ANY of these trigger words/phrases, **run the full analysis automatically** on all files in the current working directory without asking scope questions:

- `review code`, `code review`, `security audit`, `code quality`, `check vulnerabilities`
- `best practices review`, `analyze code`, `run guardian`, `guardian analysis`
- `security scan`, `vulnerability scan`, `static analysis`, `audit code`, `scan code`
- `code analysis`, `lint`, `linting`, `run analysis`, `full analysis`
- `check code`, `inspect code`, `code health`, `code check`
- `code scan`, `review my code`, `analyze my code`, `check my code`

**When trigger words are detected:**
1. Skip Step 2 (scope selection) — use ALL categories
2. Auto-detect all code files in the working directory
3. Run the full static analysis toolchain (9 core + 2 conditional frontend tools) + LLM review
4. Generate `GUARDIAN_ANALYSIS.MD` in the project root
5. Generate `GUARDIAN_ANALYSIS.html` (Snowflake-themed visual dashboard) in the project root

### No Trigger Words Detected
If the user invoked `/guardian` but did NOT use any trigger words, **ask the user**:

> "Would you like me to run a full Guardian analysis on this project? This will run 11 static analysis tools (9 core + 2 conditional) + LLM review across all Python, SQL, YAML, JS/TS, and HTML files and generate a GUARDIAN_ANALYSIS.MD report."

Offer options:
- **Full analysis** — All files, all categories, all tools
- **Quick scan** — LLM review only (no static tools)
- **Custom** — Let me choose files and categories

---


**Load** `references/toolchain.md` for static analysis tool definitions, default exclusions, and project configuration options.

## Workflow

### Step 1: Identify Code to Review

**Goal:** Determine what code to analyze.

**Actions:**

1. If trigger words were detected, **auto-scan** the current working directory for all code files.
2. Otherwise, **ask** the user what code to review:
   - Specific file(s) or directory
   - Code pasted in the conversation
   - Recent changes (e.g., git diff)

3. **Read** the target code using available tools (Read, Glob, Grep).

4. **Determine** the language(s) and framework(s) present by scanning for file extensions:
   - `.py` → Python (enable ruff, mypy, radon, vulture, pip-audit)
   - `.sql` → SQL (enable sqlfluff)
   - `.yaml`, `.yml` → YAML (enable yamllint)
   - `.js`, `.jsx`, `.ts`, `.tsx` → JavaScript/TypeScript (enable eslint)
   - `.html`, `.htm` → HTML (enable htmlhint)
   - Always enable: semgrep, gitleaks (cross-language)

5. **Check for `.guardianrc.yaml`** in the project root and apply overrides if found.

6. **Check for `.env` files** — If found, flag as INFO in the report (may contain secrets) but do NOT read their contents.

**Output:** Code loaded, languages identified, tool selection determined.

### Step 2: Select Review Scope

**Goal:** Confirm what categories of analysis the user wants.

> **Skip this step if trigger words were detected** — use ALL categories.

**Ask** user to select review categories (default: all):

1. **Security** - Vulnerabilities, injection risks, secrets exposure, auth issues
2. **Code Quality** - Readability, maintainability, complexity, dead code
3. **Best Practices** - Language idioms, framework patterns, naming conventions
4. **Performance** - Inefficient patterns, memory issues, unnecessary operations
5. **Error Handling** - Missing try/catch, unhandled promises, edge cases
6. **Accessibility** (HTML/React) - ARIA, semantic HTML, keyboard navigation

**Default:** All categories. If user wants a quick review, run all.

### Step 3: Run Static Analysis Tools

**Goal:** Execute all applicable static analysis tools in parallel.

**Actions:**

1. **Check tool availability** — For each tool, verify it is installed:
   ```bash
   which ruff mypy radon vulture semgrep gitleaks sqlfluff yamllint 2>&1
   pip-audit --version 2>&1
   ```

2. **Install missing tools** — If any tool is missing, install it:
   ```bash
   pip install ruff mypy radon vulture pip-audit semgrep sqlfluff yamllint
   ```

   **gitleaks** (binary -- not available via pip):
   - macOS: `brew install gitleaks`
   - Linux: `sudo apt install gitleaks` or download from GitHub releases
   - Windows: `choco install gitleaks` or `scoop install gitleaks`
   - Fallback: Download binary from https://github.com/gitleaks/gitleaks/releases

   **eslint/htmlhint** (npm -- only if JS/TS/HTML files exist):
   ```bash
   npm install -g eslint htmlhint
   ```

   **Note:** semgrep requires Python 3.8+ and may show dependency conflict warnings with some Snowflake packages (non-blocking).

3. **Run all applicable tools IN PARALLEL** (use multiple Bash tool calls in a single message):

   **Always run (cross-language):**
   - `semgrep scan --config auto --exclude="node_modules" --exclude=".venv" --exclude="__pycache__" .`
   - `gitleaks detect --source . --no-git -v`

   **If Python files exist:**
   - `ruff check <files> --output-format=full`
   - `mypy <files> --ignore-missing-imports`
   - `radon cc <files> -a -s` + `radon hal <files>` + `radon mi <files> -s`
   - `vulture <files>`
   - `pip-audit`

   **If SQL files exist:**
   - `sqlfluff lint <dir> --dialect <detected_dialect>` (see SQL dialect detection above)

   **If YAML files exist:**
   - `yamllint <files>`

   **If JS/TS files exist:**
   - `npx eslint <files>` (requires eslint.config.js)

   **If HTML files exist:**
   - `htmlhint <files>` (only run on actual .html files, NOT .py or other extensions)

4. **Capture all output** for inclusion in the report.

5. **Handle tool failures gracefully:**
   - If a tool **fails to install**: Mark as `SKIPPED (install failed)` in the report, continue with remaining tools
   - If a tool **crashes or times out**: Mark as `ERROR` with the error message, continue with remaining tools
   - If a tool **produces no output** on valid targets: Mark as `PASS (clean)`
   - If a tool **returns unexpected output**: Capture raw output in the report for manual review
   - **NEVER block the entire analysis because one tool fails** -- always continue with remaining tools
   - Set timeouts: semgrep (180s), pip-audit (120s), sqlfluff (120s), gitleaks (60s), others (30s)

> **Important:** Run as many tools as possible in parallel to minimize total execution time. Tools are independent and have no dependencies on each other.

> **Large repos (1000+ files):** Warn the user that analysis may take several minutes. Consider scoping to specific directories if the user wants faster results.

### Step 4: Perform LLM Review

**Goal:** Analyze code for issues that static tools cannot detect.

**Read all project files** and review against these checklists:

#### Security Checklist
- Hardcoded secrets, API keys, passwords, tokens
- SQL injection, XSS, command injection vectors
- Insecure deserialization or eval() usage
- Missing input validation or sanitization
- Insecure dependencies or import patterns
- Exposed sensitive data in logs or error messages
- Missing authentication/authorization checks
- Insecure cryptographic practices
- Path traversal vulnerabilities
- CSRF/SSRF risks

#### Code Quality Checklist
- Functions exceeding 50 lines or high cyclomatic complexity
- Code duplication (DRY violations)
- Dead code or unreachable branches
- Inconsistent naming conventions
- Missing or misleading type annotations
- Overly complex conditionals or nesting
- Magic numbers or strings without constants
- Poor separation of concerns

#### Best Practices Checklist
- **Python**: PEP 8, type hints, context managers, f-strings, pathlib
- **JavaScript/TypeScript**: strict mode, const/let over var, optional chaining, nullish coalescing, proper async/await
- **React**: hooks rules, key props, memoization where needed, controlled components, effect cleanup
- **HTML**: semantic elements, proper nesting, doctype, charset, viewport meta
- **SQL**: consistent casing, parameterized queries, avoiding SELECT *, proper indexing hints
- **YAML**: document start markers, consistent indentation, no trailing spaces
- Framework-specific anti-patterns

#### Performance Checklist
- N+1 query patterns
- Unnecessary re-renders (React)
- Synchronous operations that should be async
- Missing caching opportunities
- Large bundle imports (import entire library vs specific modules)
- Inefficient data structures or algorithms
- Memory leaks (event listeners, intervals, subscriptions)
- Unnecessary SQL query execution (dead queries)

#### Error Handling Checklist
- Unhandled promise rejections
- Empty catch blocks
- Missing error boundaries (React)
- No graceful degradation
- Silent failures without logging
- Missing input validation at boundaries
- Bare SQL calls without try/except

#### Accessibility Checklist (HTML/React)
- Missing alt text on images
- Missing ARIA labels on interactive elements
- Non-semantic HTML (div soup)
- Missing keyboard navigation support
- Color contrast issues (if CSS present)
- Missing form labels

#### Cross-File Consistency Checklist (LLM-only)
- Name mismatches between files (e.g., semantic view names, table references)
- Inconsistent model/API version references
- Missing integration between components (e.g., buttons that don't trigger backend actions)
- Orphaned code that references deleted or renamed entities

### Step 5: Classify Findings & Generate Report

**Goal:** Combine static tool results + LLM findings into a single structured report.

**Severity Levels:**

| Severity | Criteria | Action |
|----------|----------|--------|
| **CRITICAL** | Security vulnerabilities, data exposure, auth bypass, injection risks, high-severity CVEs, dead code causing wasted compute | Must fix before deployment |
| **WARNING** | Code quality issues, missing error handling, performance problems, medium CVEs, style violations | Should fix soon |
| **INFO** | Style improvements, minor best practice suggestions, optimization hints, formatting issues | Nice to have |

**Output file:** Write the report to `GUARDIAN_ANALYSIS.MD` in the project root.

**Re-Run Behavior:**
- If `GUARDIAN_ANALYSIS.MD` already exists, **rename it** to `GUARDIAN_ANALYSIS_<YYYY-MM-DD_HHMMSS>.MD` before writing the new report
- Add a **"Changes Since Last Run"** section to the new report comparing finding counts with the previous run (if a previous report was backed up)
- This preserves history so teams can track improvement over time

**Report Template:**

```markdown
# Guardian Analysis Report

**Load** `references/report-template.md` for the full report structure and section templates.

### Step 5b: Generate HTML Visual Dashboard

**Goal:** Create a self-contained HTML dashboard (`GUARDIAN_ANALYSIS.html`) that visualizes the markdown report with Snowflake brand theming. No external dependencies — all CSS and JS are embedded in a single file.

**Trigger:** Runs automatically after `GUARDIAN_ANALYSIS.MD` is written in Step 5.

**Output file:** `GUARDIAN_ANALYSIS.html` in the same directory as `GUARDIAN_ANALYSIS.MD`.

**Re-Run Behavior:** If `GUARDIAN_ANALYSIS.html` already exists, overwrite it (HTML is always regenerated from the latest markdown).

#### Snowflake Color Palette (CSS Custom Properties)

```css
:root {
  --sf-blue: #29B5E8;        /* primary brand blue */
  --sf-navy: #11567F;        /* dark navy */
  --sf-deep-navy: #0D3B66;   /* deepest navy, header gradient */
  --sf-light-blue: #E3F5FC;  /* light blue tint */
  --sf-snow: #F4F7FA;        /* snow gray background */
  --sf-critical: #E63946;    /* red */
  --sf-warning: #F4A261;     /* amber */
  --sf-info: #29B5E8;        /* blue (same as brand) */
  --sf-pass: #2EC4B6;        /* teal green */
}
```

Grade colors for health bars: A = `#2EC4B6`, B = `#3B82F6`, C = `#F4A261`, D = `#E67E22`, F = `#E63946`

#### HTML Structure

Build the HTML with these sections in order:

1. **Header** — Dark navy gradient (`linear-gradient(135deg, --sf-navy, --sf-deep-navy)`), SVG snowflake icon (hexagonal lattice pattern with blue nodes), project name, date, and toolchain label reading "11 Static Analysis Tools (9 core + 2 conditional) + LLM Review"
2. **Sticky Navigation Bar** — White background, 6 anchor links (Summary, Health Score, Toolchain, Findings, Correlation, Recommendations), blue underline on active/hover, scroll spy to auto-highlight
3. **Executive Summary** — CSS Grid (`repeat(auto-fit, minmax(160px, 1fr))`) of 6 stat cards: Total Findings, Critical, Warning, Info, CVEs Found, Secret Leaks. Each card has a colored top border matching severity and a large numeric value
4. **Project Health Score** — Two-column grid: left column has an SVG radial gauge (overall score), right column has horizontal bar charts for each category (Security, Code Quality, Dependencies, SQL Quality, YAML Quality if applicable). Grade letter displayed beside each bar
5. **Tool Execution Summary** — HTML table with navy header row. Columns: #, Tool, Target, Findings, Status. Status uses badge spans: `.badge-pass` (green), `.badge-fail` (red), `.badge-na` (gray)
6. **Detailed Findings** — Three groups (Critical, Warning, Info), each with a colored group header. Individual findings are expandable accordion items with `onclick="this.classList.toggle('open')"`. Each finding shows: severity ID badge, title, chevron icon. Expanded body shows: Source, File, Category, Issue, Risk, Fix (with code blocks where applicable). Left border color matches severity
7. **Cross-Tool Correlation Matrix** — Table with tool names as column headers and finding descriptions as rows. Non-empty cells rendered as blue dot indicators (`<span class="dot">`)
8. **Recommendations** — Three priority sections (P0 Immediate, P1 Short Term, P2 Maintenance). Each section has a colored label badge and a list of recommendation cards with colored left borders (P0=red, P1=amber, P2=blue)
9. **Footer** — Centered text: "Guardian Analysis — Generated by Cortex Code - Snowflake"

#### Data Extraction Rules (Markdown to HTML)

Parse `GUARDIAN_ANALYSIS.MD` section by section:

| Markdown Source | HTML Target | Extraction |
|---|---|---|
| Executive Summary table | Stat cards | Extract metric/value pairs from the markdown table rows |
| Project Health Score table | SVG gauge + bar charts | Extract category/score/grade; use Overall row for gauge |
| Tool Execution Summary table | HTML table with badges | Extract rows; map PASS/FAIL/N/A to badge classes |
| `### CRITICAL Findings` / `### WARNING Findings` / `### INFO Findings` | Accordion groups | Parse `[C/W/I][N]` headers, extract fields (File, Source, Issue, Risk, Fix) |
| Cross-Tool Correlation Matrix table | Dot-indicator table | Non-empty cells (e.g., `[X]`) become `<span class="dot">` |
| `### P0` / `### P1` / `### P2` sections | Priority card lists | Extract numbered items with bold titles |

#### SVG Radial Gauge Calculation

```
radius = 78
circumference = 2 * pi * 78 = ~490
stroke-dasharray = "490"
stroke-dashoffset = circumference * (1 - overallScore / 100)
stroke color = grade color (A=#2EC4B6, B=#3B82F6, C=#F4A261, D=#E67E22, F=#E63946)
```

Center text shows the numeric score and grade letter.

#### Interactive Features

- **Smooth scroll navigation:** Each nav link calls `el.scrollIntoView({ behavior: 'smooth', block: 'start' })` and sets `.active` class
- **Scroll spy:** `IntersectionObserver` with `rootMargin: '-20% 0px -80% 0px'` auto-highlights the nav link for the visible section
- **Findings accordion:** `onclick="this.classList.toggle('open')"` on each `.finding` div. CSS: `.finding.open .finding-body { display: block }` and `.finding.open .finding-chevron { transform: rotate(90deg) }`

#### Responsive and Print Styles

- **Mobile (max-width 768px):** Single-column health grid, 3-column stat cards, narrower bar labels
- **Print (`@media print`):** Hide nav bar, expand all finding bodies (`display: block !important`), disable hover transforms, white background

#### Card Hover Effects

Cards use `transition: transform 0.2s, box-shadow 0.2s` with `:hover { transform: translateY(-2px); box-shadow: var(--shadow-lg) }` for subtle lift effect.

### Step 6: Apply Fixes (Optional)

**Goal:** Help user fix identified issues if requested.

**Actions:**

1. **Ask** which findings the user wants fixed
2. **Apply** fixes using Edit/MultiEdit tools
3. **Verify** fixes don't introduce new issues
4. **Re-run** affected static tools to confirm resolution
5. **Update** `GUARDIAN_ANALYSIS.MD` with fix status

**MANDATORY STOPPING POINT**: Get approval before applying each batch of fixes.

---

## Key Principles

1. **Static tools and LLM review are complementary:**
   - Tools excel at: formatting, conventions, known CVE patterns, type safety, dead imports
   - LLM excels at: business logic, cross-file consistency, missing error handling, semantic dead code, architectural issues

2. **Always run tools in parallel** to minimize execution time.

3. **Never remove a tool just because it has no targets in the current project.** Only remove tools if they have 100% overlap with another tool.

4. **pip-audit is often the highest-value tool** — dependency CVEs are invisible to all other tools.

5. **vulture catches semantic dead code** that ruff's unused-import detection misses (e.g., variables assigned but never read).

6. **sqlfluff PRS errors on Snowflake-specific syntax** (AGENT, ALERT, SYSTEM$) are expected false positives — note them in the report but do not count as real violations.

7. **radon Maintainability Index thresholds:** MI below 20 = CRITICAL, 20-40 = WARNING, 40+ = PASS (Grade A).

8. **htmlhint should ONLY run on .html files** — running it on .py or other files produces false positives.

9. **Focus on actionable findings, not style nitpicks** — when reviewing AI-generated code, pay extra attention to hallucinated APIs, incorrect library usage, and plausible-but-wrong patterns.

10. **Never flag working code as broken without evidence** — if unsure about a finding, mark it as INFO with a note to verify.

---

## Stopping Points

- After Step 5 + 5b: User reviews markdown report and HTML dashboard before any changes
- After Step 6: User approves each batch of fixes

## Output

- **Markdown Report:** `GUARDIAN_ANALYSIS.MD` in the project root
- **HTML Dashboard:** `GUARDIAN_ANALYSIS.html` in the project root (Snowflake-themed visual)
- Both files contain:
  - Static tool results (all 11 tools)
  - LLM findings categorized by severity (CRITICAL / WARNING / INFO)
  - Cross-tool correlation matrix
  - Specific file and line references
  - Suggested fixes with code snippets
  - Prioritized recommendations
