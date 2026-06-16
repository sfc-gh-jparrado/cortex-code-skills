# Cortex Code Skills (Compartibles con Clientes)

Una colección curada y **compartible con clientes** de skills de [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code).

Son skills genéricos, técnicos y de utilidad que **no contienen datos internos, datos de clientes ni contenido propietario de go-to-market**. Son seguros para compartir públicamente y reutilizar entre proyectos.

> ⚠️ **IMPORTANTE — LEER ANTES DE USAR.** Este contenido se proporciona **"TAL CUAL" (AS IS), SIN GARANTÍA DE NINGÚN TIPO** y **NO es un producto oficial de Snowflake** (no está respaldado ni soportado por Snowflake Inc.). Los autores **no asumen responsabilidad alguna** por daños derivados de su uso. **Eres el único responsable de revisar, probar y validar cualquier skill antes de usarlo**, así como de los costos de cómputo/servicios que genere. Al usar cualquier elemento de este repositorio aceptas íntegramente los términos de **[DISCLAIMER.md](./DISCLAIMER.md)** y de la **[LICENCIA Apache 2.0](./LICENSE)**.

## ¿Qué es un skill?

Un skill es una capacidad reutilizable para Cortex Code: una carpeta con un `SKILL.md` (instrucciones + palabras clave de activación) y, opcionalmente, recursos de apoyo (plantillas, scripts, componentes). Cuando una solicitud coincide con el dominio de un skill, Cortex Code lo carga para aplicar flujos de trabajo especializados.

## Skills incluidos

| Skill | Descripción |
|---|---|
| `snowflake-dashboard-viz` | Librería reutilizable de gráficos D3 + React y design system oscuro estilo "fintech" para dashboards y data apps. |
| `reference-architecture-diagram` | Genera diagramas de arquitectura de referencia como archivos XML de draw.io. |
| `guardian` | Analiza código en busca de problemas de calidad, vulnerabilidades y buenas prácticas (Python, JS/TS, React, SQL, YAML). |
| `html-to-pdf` | Convierte documentos HTML en PDFs limpios y listos para presentar. |
| `html-to-pptx` | Convierte documentos HTML en presentaciones de PowerPoint (.pptx). |
| `kaniko-spcs` | Construye imágenes de contenedor Docker dentro de Snowpark Container Services (SPCS) usando Kaniko. |
| `demo-recording` | Genera recursos para grabar demos: talk track, guion cronometrado y voz en off con IA. |
| `aws-mcp` | Configura y usa los servidores MCP de AWS Labs desde Cortex Code. |
| `cf-explain-pipeline-skill` | Explica cómo se calcula una columna/campo en una tabla dinámica o vista, trazando su linaje. |
| `openflow-oracle-s3-snowflake` | Construye pipelines de OpenFlow: extrae de Oracle, escribe a S3 como Avro y carga a Snowflake Iceberg. |

## Instalación

Clónalo en tu directorio de skills de Cortex Code:

```bash
git clone https://github.com/<owner>/<repo>.git
cp -r <repo>/skills/* ~/.snowflake/cortex/skills/
```

O copia carpetas de skills individuales según necesites. Reinicia Cortex Code para que detecte los nuevos skills.

## Licencia y aviso legal

- **Licencia:** [Apache License 2.0](./LICENSE) — incluye la Renuncia de Garantía (§7) y la Limitación de Responsabilidad (§8). *(El texto de la licencia se conserva en inglés porque su validez legal depende del texto canónico oficial de Apache.)*
- **Aviso legal completo (ES/EN):** [DISCLAIMER.md](./DISCLAIMER.md) — sin garantía, no es producto oficial de Snowflake, el usuario asume todo el riesgo, indemnización.
- **Aviso de atribución:** [NOTICE.md](./NOTICE.md).

Se proporciona **TAL CUAL (AS IS)**, sin garantía de ningún tipo. No es un producto oficial de Snowflake. Úsalo bajo tu propio riesgo: revisa y prueba antes de aplicarlo en cualquier entorno.
