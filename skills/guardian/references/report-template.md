# Guardian — Report Template

## [Project Name]
**Date:** [date] | **Toolchain:** 11 Static Analysis Tools (9 core + 2 conditional) + LLM Review

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Total Findings** | X |
| **Critical** | X |
| **Warning** | X |
| **Info** | X |
| **CVEs Found** | X in Y packages |
| **Secret Leaks** | X |

---

## Project Health Score

| Category | Score | Grade |
|----------|-------|-------|
| Security (CVEs, SAST, secrets) | X/100 | A-F |
| Code Quality (lint, types, dead code, complexity) | X/100 | A-F |
| Dependencies (CVE count, outdated packages) | X/100 | A-F |
| SQL Quality (sqlfluff violations) | X/100 | A-F |
| **Overall** | **X/100** | **A-F** |

Grading: A (90-100), B (80-89), C (70-79), D (60-69), F (below 60)
Deductions: -10 per CRITICAL, -3 per WARNING, -1 per INFO. Start at 100.

---

## Toolchain Results

### Tool Execution Summary

| # | Tool | Target | Findings | Status |
|---|------|--------|----------|--------|
| 1 | ruff | [files] | X issues | PASS/FAIL |
| 2 | semgrep | [files] | X findings | PASS/FAIL |
| 3 | mypy | [files] | X errors | PASS/FAIL |
| 4 | radon | [files] | MI: X (Grade) | PASS/FAIL |
| 5 | vulture | [files] | X dead code items | PASS/FAIL |
| 6 | pip-audit | environment | X CVEs in Y packages | PASS/FAIL |
| 7 | gitleaks | all files | X leaks | PASS/FAIL |
| 8 | sqlfluff | [files] | X violations | PASS/FAIL |
| 9 | yamllint | [files] | X issues | PASS/FAIL |
| 10 | eslint | [files or N/A] | X issues | PASS/FAIL/N/A |
| 11 | htmlhint | [files or N/A] | X issues | PASS/FAIL/N/A |

---

## Detailed Findings

### CRITICAL Findings

#### [C1] [Short Title]
- **File:** `path/to/file` line X
- **Category:** Security | Code Quality | ...
- **Source:** [tool name] + LLM / [tool name] / LLM
- **Issue:** [Description of the problem]
- **Risk:** [What could go wrong]
- **Fix:**
  ```language
  # Suggested fix
  ```

### WARNING Findings
[Same format as CRITICAL]

### INFO Findings
[Same format, lighter detail]

---

## Static Tool Details

### ruff (Python Lint & Style)
[Full ruff output with rule codes, lines, descriptions]

### pip-audit (Dependency CVEs)
[Table of all CVEs with package, version, CVE ID, fix version]
[Highlight packages directly used by the project]

### sqlfluff (SQL Linting)
[Summary by file and rule code]
[Note any PRS parse errors that are false positives for Snowflake-specific syntax]

### [Other tools...]

---

## Cross-Tool Correlation Matrix

| Finding | ruff | vulture | semgrep | pip-audit | sqlfluff | yamllint | LLM |
|---------|------|---------|---------|-----------|----------|----------|-----|
| [finding] | [X] | [X] | ... | ... | ... | ... | [X] |

---

## Recommendations (Priority Order)

### P0 - Immediate
1. [Critical fixes]

### P1 - Short Term
2. [Important improvements]

### P2 - Maintenance
3. [Nice-to-have cleanups]

---

## Changes Since Last Run (if previous report exists)

| Metric | Previous | Current | Delta |
|--------|----------|---------|-------|
| Critical | X | Y | +/- Z |
| Warning | X | Y | +/- Z |
| Info | X | Y | +/- Z |
| CVEs | X | Y | +/- Z |
| Overall Score | X | Y | +/- Z |
```

**Present** the report to the user AND write it to `GUARDIAN_ANALYSIS.MD`.

**MANDATORY STOPPING POINT**: Wait for user to review the report.

