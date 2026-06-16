---
name: reference-architecture-diagram
description: "Generate Snowflake-branded reference architecture diagrams as draw.io XML files. Use when: creating architecture diagrams, draw.io diagrams, reference architectures, solution architecture visuals. Triggers: architecture diagram, reference architecture, draw.io, drawio, solution diagram, arch diagram, create diagram."
---

# Reference Architecture Diagram Generator

Generate implementation-ready `.drawio` architecture diagrams with correct Snowflake branding, layout, and styling.

## Setup

1. **Load** `references/snowflake_brand_colors.md` for color palette
2. **Load** `references/reference_architecture_guide.md` for layout/styling specs

## Workflow

### Step 1: Gather Requirements

**Ask** the user:

```
To create your architecture diagram:
1. **Project/customer name** — used in title and file name
2. **Architecture type** — What pattern?
   - Modern Data Platform (ingestion → processing → consumption)
   - AI/ML with Cortex (data → Cortex services → apps)
   - Data Sharing & Marketplace (provider → share → consumers)
   - Custom (describe your flow)
3. **Components** — What specific services/tools? (e.g., Snowpipe, Dynamic Tables, Cortex Analyst, Streamlit)
4. **External systems** — Sources or targets outside Snowflake? (e.g., S3, Kafka, Tableau)
```

**⚠️ STOP**: Confirm component list and flow before generating.

### Step 2: Plan the Layout

Organize components into zones (left-to-right flow):

| Zone | Position | X Range (of 1400px) |
|------|----------|---------------------|
| Sources | Far Left | 40–190 |
| Ingestion | Left-Center | 270–450 |
| Platform | Center | 530–930 |
| Processing | Right-Center | 1010–1190 |
| Consumption | Far Right | 1210–1360 |

**Actions:**
1. Assign each component to a zone
2. Stack components vertically within zones (40-60px spacing)
3. Plan connection arrows between components

Present the layout plan to the user.

**⚠️ STOP**: Get approval on layout before generating XML.

### Step 3: Generate draw.io XML

**Goal:** Write a complete `.drawio` file with all components, connections, and styling.

#### draw.io XML Structure

A `.drawio` file is XML with this skeleton:

```xml
<mxfile host="app.diagrams.net" type="device">
  <diagram id="arch" name="Architecture">
    <mxGraphModel dx="1422" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1400" pageHeight="900" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <!-- Zone containers, components, and connections go here -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

#### XML Style Strings

**Zone container:**
```
style="rounded=1;whiteSpace=wrap;html=1;arcSize=6;fillColor=#003545;opacity=10;strokeColor=#11567F;strokeWidth=1;dashed=0;verticalAlign=top;align=center;fontSize=16;fontStyle=1;fontFamily=Inter;fontColor=#11567F;"
```

**Snowflake component (rectangle with icon):**
```
style="rounded=1;whiteSpace=wrap;html=1;arcSize=8;fillColor=#29B5E8;strokeColor=#11567F;strokeWidth=2;fontColor=#FFFFFF;fontSize=12;fontFamily=Inter;"
```

**External component:**
```
style="rounded=1;whiteSpace=wrap;html=1;arcSize=4;fillColor=#F5F5F5;strokeColor=#666666;strokeWidth=1;dashed=1;fontColor=#333333;fontSize=12;fontFamily=Inter;"
```

**Cortex AI/ML component:**
```
style="rounded=1;whiteSpace=wrap;html=1;arcSize=8;fillColor=#1B74E4;strokeColor=#0F4FA8;strokeWidth=2;fontColor=#FFFFFF;fontSize=12;fontFamily=Inter;"
```

**Data flow arrow (curved):**
```
style="curved=1;rounded=0;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;strokeColor=#71D3DC;strokeWidth=2;fontFamily=Inter;"
```

**Control flow arrow (curved, dashed):**
```
style="curved=1;rounded=0;dashed=1;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;strokeColor=#8A999E;strokeWidth=1;fontFamily=Inter;"
```

**AI/ML flow arrow (curved):**
```
style="curved=1;rounded=0;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;strokeColor=#1B74E4;strokeWidth=2;fontFamily=Inter;"
```

**Title text:**
```
style="text;html=1;align=center;verticalAlign=middle;resizable=0;points=[];autosize=1;fontSize=24;fontStyle=1;fontFamily=Inter;fontColor=#000000;"
```

#### XML Element Patterns

**Zone container cell:**
```xml
<mxCell id="zone_platform" value="Snowflake Platform" style="[zone style]" vertex="1" parent="1">
  <mxGeometry x="530" y="80" width="400" height="780" as="geometry" />
</mxCell>
```

**Component cell (inside a zone):**
```xml
<mxCell id="comp_dyntable" value="Dynamic Tables" style="[snowflake component style]" vertex="1" parent="1">
  <mxGeometry x="560" y="200" width="160" height="50" as="geometry" />
</mxCell>
```

**Connection (arrow):**
```xml
<mxCell id="edge_1" value="" style="[data flow arrow style]" edge="1" parent="1" source="comp_snowpipe" target="comp_raw_db">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

#### Generation Rules

1. **IDs**: Use descriptive IDs — `zone_sources`, `comp_snowpipe`, `edge_pipe_to_raw`
2. **Positioning**: Place zones at x positions per the layout table; components inside zones stacked vertically with 60px spacing, starting at zone y+60
3. **Component size**: 160x50px standard, 180x60px for important components
4. **Zone height**: Accommodate all stacked components + 60px top/bottom padding
5. **Title**: Place at top-center — x=400, y=20, spanning width
6. **Connections**: Use `source` and `target` attributes referencing component IDs; arrows flow left-to-right
7. **Line routing**: ALL connections MUST use `curved=1` (smooth curves, never orthogonal/right-angle). Every edge MUST include explicit `exitX`, `exitY`, `entryX`, `entryY` snap points (typically exit right side at `exitX=1;exitY=0.5` and enter left side at `entryX=0;entryY=0.5`). Do NOT include `<Array>` waypoints in edge geometry — omit them so lines auto-route cleanly to their snap points

**Write** the complete `.drawio` file to disk using the naming convention:
```
{project}-{type}-architecture.drawio
```

### Step 4: Validate

Run through this checklist after generation:

- [ ] All Snowflake components use `#29B5E8` fill
- [ ] External systems use `#F5F5F5` or `#8A999E`
- [ ] Cortex/AI components use `#1B74E4` (Cortex Blue)
- [ ] Data flow arrows use `#71D3DC`
- [ ] All connection lines are curved (`curved=1`), no orthogonal edges
- [ ] All edges have explicit entry/exit snap points (no stale waypoints)
- [ ] Left-to-right flow is clear
- [ ] Zones visually separated
- [ ] All components labeled
- [ ] Connections have correct source/target IDs
- [ ] File is valid XML (parseable)

Present the final file path and a summary of what was generated.

**⚠️ STOP**: Ask user if they want modifications.

### Step 5: Iterate (if requested)

Apply requested changes:
- Add/remove components
- Adjust layout or spacing
- Change colors or styling
- Add annotations or legends

Re-validate after each change.

## Stopping Points

- ✋ Step 1: After gathering requirements (confirm component list)
- ✋ Step 2: After layout plan (approve before XML generation)
- ✋ Step 4: After generation (review and request changes)

## Output

A `.drawio` file in the current working directory, ready to open in draw.io or import to Lucidchart. File follows Snowflake brand guidelines with proper colors, layout, and typography.
