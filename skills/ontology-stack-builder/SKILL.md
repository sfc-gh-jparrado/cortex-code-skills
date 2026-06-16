---
name: ontology-stack-builder
version: "1.0"
description: "Design and build ontology stacks (OWL/RDF/SKOS, knowledge graphs, taxonomies) layered over Snowflake data. Use when: building an ontology, designing a knowledge graph, modeling a domain, creating a taxonomy or controlled vocabulary, mapping tables to ontology classes/properties, generating RDF/Turtle/OWL artifacts, aligning a semantic view with a formal ontology. Triggers: ontology, knowledge graph, KG, RDF, OWL, SKOS, Turtle, SPARQL, taxonomy, controlled vocabulary, domain model, semantic model to ontology, classes and properties, ontology stack."
---

# Ontology Stack Builder

Build a layered ontology stack on top of Snowflake data: domain model → classes/properties → instances → mappings to tables / semantic views.

## Workflow

### Step 1: Scope the domain
Ask the user:
1. Domain name and short description
2. Core entities (people, products, accounts, events, etc.)
3. Key relationships between entities
4. Existing source: tables, semantic view, or greenfield?
5. Output format(s): OWL/Turtle, JSON-LD, SKOS, or just a logical model

### Step 2: Draft the conceptual model
- List candidate Classes
- List Object Properties (entity → entity) and Datatype Properties (entity → literal)
- Define hierarchies (rdfs:subClassOf) and constraints
- Reuse standard vocabularies where possible (schema.org, FOAF, SKOS, Dublin Core, PROV-O)

### Step 3: Map to Snowflake
- For each Class, identify the source table or view
- For each Property, identify the source column or join path
- If a semantic view exists, align dimensions → datatype properties and relationships → object properties
- Capture URI strategy (e.g., `https://<org>/ontology/<class>/<id>`)

### Step 4: Generate artifacts
Produce:
- `ontology.ttl` (Turtle/OWL)
- `mappings.yaml` (class/property → Snowflake table.column)
- Optional: R2RML or SQL views that materialize triples
- Optional: SKOS concept scheme for controlled vocabularies

### Step 5: Validate
- Check class/property naming consistency (PascalCase classes, camelCase properties)
- Validate Turtle syntax (rdflib if available)
- Spot-check sample instances against source data

## Output

Save artifacts under the user's working directory (default `./ontology/`):
- `ontology/ontology.ttl`
- `ontology/mappings.yaml`
- `ontology/README.md` (overview + how to query)

## Notes
- Prefer reuse of upper ontologies before inventing new IRIs
- Keep one IRI namespace per project
- Document every class and property with `rdfs:label` and `rdfs:comment`
