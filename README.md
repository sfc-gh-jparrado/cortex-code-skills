# Cortex Code Skills (Client-Shareable)

A curated, **client-shareable** collection of [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) skills.

These are generic, technical/utility skills that contain **no internal data, no customer data, and no proprietary go-to-market content**. They are safe to share publicly and reuse across projects.

> ⚠️ **IMPORTANT — READ BEFORE USE.** This content is provided **"AS IS", WITHOUT WARRANTY OF ANY KIND** and is **NOT an official Snowflake product** (not endorsed or supported by Snowflake Inc.). The authors accept **no liability** for any damages arising from its use. **You are solely responsible for reviewing, testing, and validating any skill before use**, and for any compute/service costs it incurs. By using anything in this repository you accept the full terms in **[DISCLAIMER.md](./DISCLAIMER.md)** and the **[Apache 2.0 LICENSE](./LICENSE)**.

## What is a skill?

A skill is a reusable capability for Cortex Code — a folder with a `SKILL.md` (instructions + trigger keywords) and optional supporting assets (templates, scripts, components). When a request matches a skill's domain, Cortex Code loads it to apply specialized workflows.

## Skills included

| Skill | Description |
|---|---|
| `snowflake-dashboard-viz` | Reusable D3 + React chart library and dark "fintech" design system for dashboards and data apps. |
| `reference-architecture-diagram` | Generate reference architecture diagrams as draw.io XML files. |
| `guardian` | Analyze code for quality issues, vulnerabilities, and best practices (Python, JS/TS, React, SQL, YAML). |
| `html-to-pdf` | Convert HTML documents to clean, presentation-ready PDFs. |
| `html-to-pptx` | Convert HTML documents into PowerPoint (.pptx) presentations. |
| `kaniko-spcs` | Build Docker container images inside Snowpark Container Services (SPCS) using Kaniko. |
| `demo-recording` | Generate demo recording assets: talk track, timed script, and AI voice-over. |
| `ontology-stack-builder` | Design and build ontology stacks (OWL/RDF/SKOS, knowledge graphs, taxonomies) over data. |
| `aws-mcp` | Set up and use the AWS Labs MCP servers from Cortex Code. |
| `cf-explain-pipeline-skill` | Explain how a column/field in a dynamic table or view is calculated by tracing its lineage. |
| `openflow-oracle-s3-snowflake` | Build OpenFlow pipelines: extract from Oracle, write to S3 as Avro, load to Snowflake Iceberg. |

## Installation

Clone into your Cortex Code skills directory:

```bash
git clone https://github.com/<owner>/<repo>.git
cp -r <repo>/skills/* ~/.snowflake/cortex/skills/
```

Or copy individual skill folders as needed. Restart Cortex Code so it picks up the new skills.

## License & disclaimer

- **License:** [Apache License 2.0](./LICENSE) — includes a Disclaimer of Warranty (§7) and Limitation of Liability (§8).
- **Full disclaimer (ES/EN):** [DISCLAIMER.md](./DISCLAIMER.md) — no warranty, not an official Snowflake product, user assumes all risk, indemnification.
- **Attribution notice:** [NOTICE.md](./NOTICE.md).

Provided **AS IS**, without warranty of any kind. Not an official Snowflake product. Use at your own risk — review and test before applying in any environment.
