# Guardian — Static Analysis Toolchain & Configuration

## Static Analysis Toolchain (11 Tools: 9 Core + 2 Conditional)

Guardian uses a curated set of **11 non-overlapping static analysis tools** (9 core tools that always apply + 2 conditional frontend tools) plus LLM review. Each tool covers a unique analysis domain with zero redundancy.

### Python Tools
| # | Tool | Purpose | Command |
|---|------|---------|---------|
| 1 | **ruff** | Lint + style (replaces pylint) | `ruff check <file> --output-format=full` |
| 2 | **mypy** | Static type checking | `mypy <file> --ignore-missing-imports` |
| 3 | **radon** | Complexity metrics (cyclomatic, Halstead, MI) | `radon cc <file> -a -s && radon hal <file> && radon mi <file> -s` |
| 4 | **vulture** | Dead code detection | `vulture <file>` |
| 5 | **pip-audit** | Dependency CVE scanning | `pip-audit` |

### SQL Tools
| # | Tool | Purpose | Command |
|---|------|---------|---------|
| 6 | **sqlfluff** | SQL linting (auto-detect dialect) | `sqlfluff lint <dir> --dialect <dialect>` |

**SQL dialect detection** (in order of precedence):
1. Check `.guardianrc.yaml` for `dialect:` setting
2. Check for `.sqlfluff` config file in the project
3. Check for `dbt_project.yml` and use its configured dialect
4. Scan SQL files for dialect-specific syntax:
   - `VARIANT`, `FLATTEN`, `SYSTEM$`, `CREATE AGENT`, `CREATE ALERT` -> `snowflake`
   - `SERIAL`, `RETURNING`, `ON CONFLICT` -> `postgres`
   - `STRUCT`, `UNNEST`, `SAFE_DIVIDE` -> `bigquery`
   - `DISTKEY`, `SORTKEY`, `DISTSTYLE` -> `redshift`
5. Default: `snowflake` (for Snowflake-centric teams)
6. If uncertain, ask the user

### YAML Tools
| # | Tool | Purpose | Command |
|---|------|---------|---------|
| 7 | **yamllint** | Syntax, formatting, line length | `yamllint <file>` |

### Security Tools (Cross-Language)
| # | Tool | Purpose | Command |
|---|------|---------|---------|
| 8 | **semgrep** | SAST security scanner (replaces bandit) | `semgrep scan --config auto --exclude="node_modules" --exclude=".venv" --exclude="__pycache__" .` |
| 9 | **gitleaks** | Secret/credential detection | `gitleaks detect --source . --no-git -v` |

### JS/TS/HTML Tools (Conditional -- only when applicable)
| # | Tool | Purpose | Command |
|---|------|---------|---------|
| 10 | **eslint** | JS/TS/React linting | `npx eslint <files>` |
| 11 | **htmlhint** | HTML validation | `htmlhint <files>` |

> **Note on eslint/htmlhint:** These tools are part of the toolchain but only run when JS/TS/HTML files exist in the project. If no such files are found, mark them as "N/A" in the report rather than skipping them silently.

### Removed Tools (Redundant)
- ~~pylint~~ → 100% overlap with ruff (ruff is faster + auto-fixable)
- ~~bandit~~ → 100% overlap with semgrep (semgrep is cross-language SAST)

---

## Default Exclusions

Always exclude these directories and files from scanning to avoid noise, false positives, and slow execution:

### Directories
- `node_modules/`, `.venv/`, `venv/`, `env/`, `.env/`
- `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`
- `build/`, `dist/`, `.eggs/`, `*.egg-info/`
- `.git/`, `.svn/`, `.hg/`
- `vendor/`, `third_party/`, `external/`
- `.tox/`, `.nox/`, `htmlcov/`, `coverage/`

### Files
- `.DS_Store`, `*.pyc`, `*.pyo`, `*.so`, `*.dylib`
- Lock files: `package-lock.json`, `yarn.lock`, `poetry.lock`, `Pipfile.lock`
- `.env` files: Flag as INFO if found (may contain secrets) but do NOT read contents

### Tool-Specific Exclusion Flags
- semgrep: `--exclude="node_modules" --exclude=".venv" --exclude="__pycache__" --exclude="build"`
- gitleaks: Respects `.gitleaksignore` if present in project root
- ruff/mypy/vulture: Only target project source `.py` files, not vendored code
- eslint: Uses `--ignore-pattern node_modules`
- htmlhint: Only target `.html`/`.htm` files explicitly (never glob `*`)

### Override
If a `.guardianrc.yaml` exists, its `exclude:` list is merged with these defaults.

---

## Project Configuration (Optional)

Teams can create a `.guardianrc.yaml` file in the project root to customize Guardian behavior per-project.

### Specification

```yaml
# .guardianrc.yaml -- Guardian project configuration (all fields optional)

# SQL dialect for sqlfluff (default: snowflake)
dialect: snowflake  # Options: snowflake, postgres, bigquery, redshift, mysql, tsql

# Additional directories/files to exclude (merged with defaults)
exclude:
  - tests/fixtures/
  - migrations/
  - generated/

# Disable specific tools for this project
tools:
  eslint: false      # No JS/TS in this project
  htmlhint: false    # No HTML in this project
  pip-audit: true    # Explicitly enable (all tools enabled by default)

# Minimum severity to include in report (default: INFO)
severity_threshold: INFO  # Options: CRITICAL, WARNING, INFO

# Output file name (default: GUARDIAN_ANALYSIS.MD)
output_file: GUARDIAN_ANALYSIS.MD

# Radon MI threshold overrides
radon_thresholds:
  critical_below: 20  # MI below this = CRITICAL
  warning_below: 40   # MI below this = WARNING
```

### Loading Config

In **Step 1**, before scanning files:
1. Check for `.guardianrc.yaml` in the project root
2. If found, read and apply configuration overrides
3. Merge `exclude:` with default exclusions
4. Override tool toggles, dialect, severity threshold, and output file name
5. If not found, use all defaults

---

