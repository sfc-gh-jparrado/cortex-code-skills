# Reference Architecture Guide — Full Specification

## Layout Standards

### Flow Direction
Left-to-right for all diagrams:

| Zone | Position | Contents |
|------|----------|----------|
| **Sources** | Far Left | External systems, APIs, files, databases |
| **Ingestion** | Left-Center | Connectors, Snowpipe, Kafka, stages |
| **Platform** | Center | Snowflake core (databases, warehouses, Cortex) |
| **Processing** | Right-Center | Dynamic Tables, Tasks, Streams, Notebooks |
| **Consumption** | Far Right | Streamlit, BI tools, APIs, Data Sharing |

### Spacing
- Component spacing: 40-60px
- Zone spacing: 80-100px
- Margin: 40px from canvas edge
- Grid: 10px snap
- Canvas: 1400x900px standard

## Component Styling

### Snowflake Components
| Property | Value |
|----------|-------|
| Fill | `#29B5E8` |
| Border | `#11567F`, 2px solid |
| Corner radius | 8px |
| Shadow | Optional subtle drop shadow |
| Label font | 12-14px Regular |

### External Components
| Property | Value |
|----------|-------|
| Fill | `#F5F5F5` or `#8A999E` |
| Border | `#666666`, 1px dashed |
| Corner radius | 4px |

### Connection Lines
| Type | Style |
|------|-------|
| Data flow | `#71D3DC`, 2px solid, arrow end |
| Control flow | `#8A999E`, 1px dashed |
| AI/ML flow | `#1B74E4`, 2px solid |

### Zone Containers
| Property | Value |
|----------|-------|
| Fill | `#003545` at 10% opacity |
| Border | `#11567F`, 1px solid |
| Corner radius | 12px |
| Padding | 20px internal |

## Typography
| Element | Size | Weight |
|---------|------|--------|
| Diagram title | 24-28px | Bold |
| Zone labels | 16-18px | Semi-bold |
| Component labels | 12-14px | Regular |
| Annotations | 10-12px | Regular/Italic |

Font: Inter, Helvetica Neue, Arial, sans-serif

## Icon Guidelines
- Official Snowflake product icons at 48x48px or 64x64px
- Categories: Core Platform, Data Engineering, Cortex AI/ML, Apps & Sharing, External Systems
- External systems: Cloud provider icons or neutral shapes in `#8A999E`

## Architecture Patterns

### Pattern 1: Modern Data Platform
Sources → Ingestion (Snowpipe, Kafka) → Platform (Raw DB, Dynamic Tables, Gold Layer) → Consumption (Streamlit, BI)

### Pattern 2: AI/ML with Cortex
Data Sources → Stages/Semantic Models → Cortex Search/Analyst/ML Registry → Agent/Streamlit App
Color emphasis: `#1B74E4` for all Cortex components

### Pattern 3: Data Sharing & Marketplace
Provider Account → Secure Shares/Marketplace → Consumer Accounts
Layout: Hub-and-spoke from center

## File Naming
```
{project}-{diagram-type}-architecture.drawio
```
Examples: `finance-reporting-data-platform.drawio`, `customer-360-cortex-architecture.drawio`

## Checklist
- [ ] Snowflake components use `#29B5E8`
- [ ] External systems use `#8A999E`
- [ ] Cortex/AI uses `#1B74E4`
- [ ] Data flow arrows use `#71D3DC`
- [ ] Left-to-right flow
- [ ] Zones visually separated (80-100px)
- [ ] Components aligned to grid
- [ ] All labels readable
- [ ] Legend included if multiple line styles
- [ ] Saved as `.drawio`
