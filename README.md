# Cortex Code Skills (Client-Shareable)

A curated, **client-shareable** collection of [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) skills.

These are generic, technical/utility skills that contain **no internal data, no customer data, and no proprietary go-to-market content**. They are safe to share publicly and reuse across projects.

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

See [NOTICE.md](./NOTICE.md). Provided as-is, without warranty.
