---
name: cf-explain-pipeline-skill
description: "Explain exactly how a specific column/field in a dynamic table or view is calculated by tracing its full lineage — source columns, filters, joins, aggregations, CASE expressions, and transformations at every layer. Use when: explain field, how is column calculated, column lineage, field derivation, trace column, where does field come from, explain pipeline, field calculation, column transformation. Triggers: explain field, explain column, how is this field calculated, column lineage, trace field, where does this come from, field derivation, pipeline explanation, explain this column."
---

# Column/Field Pipeline Explainer

Given a specific column in a dynamic table or view, trace its full derivation pipeline — from the final output back through every intermediate layer to the original source columns. Produce a clear, detailed explanation of every transformation, filter, join condition, aggregation, and CASE expression that shapes the field's final value.

## Inputs

Collect these from the user before running:

1. **Fully qualified object name** — e.g., `DATABASE.SCHEMA.MY_DYNAMIC_TABLE` or `DATABASE.SCHEMA.MY_VIEW`
2. **Column name** — the specific field to explain (e.g., `TOTAL_REVENUE`, `CUSTOMER_STATUS`)

If the user provides an unqualified name, ask them to provide the full `DATABASE.SCHEMA.OBJECT` path, or use the current session context to resolve it.

## Workflow

### Step 1: Identify Object Type and Get DDL

Determine whether the object is a view, dynamic table, or regular table, and retrieve its definition.

**Get object type:**
```sql
SHOW OBJECTS LIKE '<object_name>' IN SCHEMA <database>.<schema>;
```

**Get the SQL definition:**
```sql
SELECT GET_DDL('<object_type>', '<database>.<schema>.<object_name>');
```

Where `<object_type>` is one of:
- `'DYNAMIC_TABLE'` — for dynamic tables
- `'VIEW'` — for views
- `'TABLE'` — for regular tables (will not have a transformation query, but may be the base layer)

If `GET_DDL` fails (e.g., insufficient privileges), fall back to:
```sql
SELECT VIEW_DEFINITION
FROM <database>.INFORMATION_SCHEMA.VIEWS
WHERE TABLE_SCHEMA = '<schema>'
  AND TABLE_NAME = '<object_name>';
```

Or for dynamic tables:
```sql
SELECT TEXT
FROM <database>.INFORMATION_SCHEMA.DYNAMIC_TABLES
WHERE SCHEMA_NAME = '<schema>'
  AND NAME = '<object_name>';
```

**Validate the column exists** in the target object:
```sql
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM <database>.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = '<schema>'
  AND TABLE_NAME = '<object_name>'
  AND COLUMN_NAME = '<column_name>';
```

If the column is not found, present the available columns and ask the user to pick one.

### Step 2: Get Column-Level Lineage

Use `SNOWFLAKE.CORE.GET_LINEAGE` to trace the column upstream through all layers:

```sql
SELECT *
FROM TABLE(
    SNOWFLAKE.CORE.GET_LINEAGE(
        '<database>.<schema>.<object_name>.<column_name>',
        'COLUMN',
        'UPSTREAM',
        5
    )
);
```

This returns the chain of source columns that feed into the target column, up to 5 levels deep. Each row is an edge: `SOURCE_COLUMN → TARGET_COLUMN` with the distance from the target.

**If GET_LINEAGE returns no rows** (e.g., lineage not available, account does not have Enterprise edition, or object is too new for lineage to be populated), fall back to manual SQL parsing in Step 3.

**If GET_LINEAGE returns an error** about insufficient privileges or edition requirements, note this to the user and proceed with manual SQL parsing.

### Step 3: Retrieve DDL for Every Upstream Layer

For each distinct upstream object found in the lineage (or referenced in the SQL from Step 1), retrieve its DDL:

```sql
SELECT GET_DDL('<type>', '<database>.<schema>.<object_name>');
```

Repeat for every intermediate view, dynamic table, or table in the chain until you reach base tables (tables with no further upstream transformation SQL).

Build a **layer map** — an ordered list from the final object back to the source tables:
```
Layer 0 (target):   DATABASE.SCHEMA.FINAL_DT          → column: TOTAL_REVENUE
Layer 1:            DATABASE.SCHEMA.INTERMEDIATE_VIEW  → column: REVENUE_SUM
Layer 2:            DATABASE.SCHEMA.RAW_ORDERS         → column: ORDER_AMOUNT
```

### Step 4: Analyze the Target Column Through Each Layer

For each layer's SQL definition, extract and document the following for the target column:

#### 4a. Column Expression
Identify the exact SQL expression that produces the column at this layer. Examples:
- Direct pass-through: `source.REVENUE AS TOTAL_REVENUE`
- Aggregation: `SUM(o.ORDER_AMOUNT) AS TOTAL_REVENUE`
- CASE expression: `CASE WHEN status = 'ACTIVE' THEN amount ELSE 0 END AS TOTAL_REVENUE`
- Arithmetic: `(unit_price * quantity) - discount AS TOTAL_REVENUE`
- Window function: `ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC)`
- Type cast: `CAST(raw_value AS NUMBER(18,2))`
- Function call: `COALESCE(primary_amount, fallback_amount)`

#### 4b. Filters (WHERE / HAVING)
List all WHERE and HAVING clauses that affect which rows contribute to this column's value. Be specific:
- `WHERE order_date >= '2024-01-01'`
- `WHERE status NOT IN ('CANCELED', 'REFUNDED')`
- `HAVING SUM(amount) > 1000`
- `QUALIFY ROW_NUMBER() ... = 1`

#### 4c. Joins
Document every JOIN that connects the source data for this column:
- Join type (INNER, LEFT, RIGHT, FULL, CROSS)
- Join condition (ON clause)
- Which table contributes the column vs. which table is being joined for filtering/enrichment

#### 4d. Aggregations / GROUP BY
If the column involves aggregation:
- The aggregate function (SUM, COUNT, AVG, MIN, MAX, LISTAGG, etc.)
- The GROUP BY columns that define the aggregation grain
- Any DISTINCT within the aggregate

#### 4e. CTEs and Subqueries
If the SQL uses CTEs (WITH clauses) or subqueries, trace the column through each CTE step. Document which CTE produces the column and how.

### Step 5: Present the Explanation

Format the output as a structured, readable explanation. Use this format:

```
# Field Explanation: <COLUMN_NAME>
**Object:** <fully qualified object name>
**Data Type:** <data type from INFORMATION_SCHEMA>
**Layers:** <number of transformation layers>

---

## Layer-by-Layer Derivation

### Layer 0: <FINAL_OBJECT_NAME> (Dynamic Table / View)
**Expression:**
  `SUM(intermediate.revenue_amount) AS TOTAL_REVENUE`

**Aggregation:** SUM grouped by `customer_id`, `fiscal_quarter`

**Filters:**
  - `WHERE intermediate.is_valid = TRUE`
  - `WHERE intermediate.order_date >= DATEADD(YEAR, -2, CURRENT_DATE)`

**Joins:**
  - INNER JOIN `dim_customer` ON `intermediate.customer_id = dim_customer.id`
    (join is for enrichment only — column value comes from `intermediate`)

---

### Layer 1: <INTERMEDIATE_VIEW_NAME> (View)
**Expression:**
  `(o.unit_price * o.quantity) - COALESCE(o.discount, 0) AS revenue_amount`

**Filters:**
  - `WHERE o.status != 'CANCELED'`

**Joins:**
  - LEFT JOIN `dim_product` ON `o.product_id = dim_product.id`
    (not used in this column's calculation)

---

### Layer 2: <SOURCE_TABLE> (Table — base layer)
**Source Columns:**
  - `unit_price` (NUMBER(18,2))
  - `quantity` (INTEGER)
  - `discount` (NUMBER(18,2), NULLABLE)
  - `status` (VARCHAR)

---

## Summary

**In plain English:**
TOTAL_REVENUE is calculated by taking each order's `unit_price × quantity - discount`
(excluding canceled orders), then summing per customer per fiscal quarter.
Only orders from the last 2 years with `is_valid = TRUE` are included.

**Source columns that ultimately feed this field:**
- `SOURCE_DB.SCHEMA.ORDERS.UNIT_PRICE`
- `SOURCE_DB.SCHEMA.ORDERS.QUANTITY`
- `SOURCE_DB.SCHEMA.ORDERS.DISCOUNT`

**Filters that affect which rows are included:**
1. `status != 'CANCELED'` (applied at Layer 1)
2. `is_valid = TRUE` (applied at Layer 0)
3. `order_date >= 2 years ago` (applied at Layer 0)

**Aggregation grain:** Per `customer_id`, `fiscal_quarter`
```

### Formatting Rules

1. **Be precise about SQL** — quote the exact expressions from the DDL, don't paraphrase
2. **Distinguish filtering vs. enrichment joins** — if a JOIN doesn't contribute to the column's value but only filters or adds other columns, say so
3. **Call out implicit behaviors** — e.g., INNER JOIN acts as a filter (rows without a match are excluded)
4. **Note NULLability** — if COALESCE, NVL, or IFNULL is used, explain what happens when the source is NULL
5. **Include the plain English summary** — this is the most important part for the user; write it as if explaining to a business analyst
6. **If the SQL is very complex** (100+ lines, many CTEs), present a simplified summary first, then offer to show the full layer-by-layer detail

### Step 6: Offer Follow-Up

After presenting the explanation, offer:
- "Would you like me to explain a different column in this same object?"
- "Would you like me to trace the downstream impact of this column (what objects consume it)?"
- "Would you like me to generate a visual lineage diagram?"

For downstream tracing, use:
```sql
SELECT *
FROM TABLE(
    SNOWFLAKE.CORE.GET_LINEAGE(
        '<database>.<schema>.<object_name>.<column_name>',
        'COLUMN',
        'DOWNSTREAM',
        5
    )
);
```

## Stopping Points

- After Step 1: If column is not found, present available columns for user to pick
- After Step 5: Present explanation and offer follow-ups

## Notes

- `SNOWFLAKE.CORE.GET_LINEAGE` requires Enterprise Edition. If not available, the skill falls back to manual DDL parsing.
- Lineage data may take up to 3 hours to appear for newly created or modified objects.
- `GET_DDL` requires appropriate privileges (OWNERSHIP or SELECT depending on object type).
- For dynamic tables, the SQL definition is the query that defines the table — this is the primary source of transformation logic.
- For views, the SQL definition is the CREATE VIEW statement's AS clause.
- Regular tables are base layers — they have no transformation SQL, only column definitions.
- If a layer references a UDF or stored procedure, note that the UDF's internal logic is not automatically expanded. Offer to retrieve the UDF definition with `GET_DDL('FUNCTION', ...)` if needed.
