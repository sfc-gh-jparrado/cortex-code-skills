# Ejemplos de SQL para Columnas de Partición

## Cálculo de PARTITION_DATE

El flujo usa una columna calculada `PARTITION_DATE` que representa la fecha más reciente de modificación del registro. Esto permite cargas incrementales eficientes.

### Patrón con GREATEST y COALESCE

```sql
GREATEST(
    COALESCE(FECHA_CREACION, TO_DATE('1900-01-01', 'YYYY-MM-DD')),
    COALESCE(FECHA_MODIFICACION, TO_DATE('1900-01-01', 'YYYY-MM-DD')),
    COALESCE(FECHA_ACTUALIZACION, TO_DATE('1900-01-01', 'YYYY-MM-DD'))
) AS PARTITION_DATE
```

### Ejemplo 1: Tabla con dos columnas de fecha

```sql
-- Columnas: CREATED_DATE, MODIFIED_DATE
GREATEST(
    COALESCE(CREATED_DATE, TO_DATE('1900-01-01', 'YYYY-MM-DD')),
    COALESCE(MODIFIED_DATE, TO_DATE('1900-01-01', 'YYYY-MM-DD'))
) AS PARTITION_DATE
```

### Ejemplo 2: Tabla con una sola columna de fecha

```sql
-- Columna: TRANSACTION_DATE
COALESCE(TRANSACTION_DATE, TO_DATE('1900-01-01', 'YYYY-MM-DD')) AS PARTITION_DATE
```

### Ejemplo 3: Tabla con timestamp

```sql
-- Columnas: CREATED_AT (timestamp), UPDATED_AT (timestamp)
GREATEST(
    COALESCE(TRUNC(CREATED_AT), TO_DATE('1900-01-01', 'YYYY-MM-DD')),
    COALESCE(TRUNC(UPDATED_AT), TO_DATE('1900-01-01', 'YYYY-MM-DD'))
) AS PARTITION_DATE
```

## Consulta para Obtener Fechas Distintas

Esta consulta obtiene las fechas únicas que necesitan ser cargadas:

```sql
SELECT DISTINCT TO_CHAR(GREATEST(
    COALESCE(FECHA_CREACION, TO_DATE('1900-01-01', 'YYYY-MM-DD')),
    COALESCE(FECHA_MODIFICACION, TO_DATE('1900-01-01', 'YYYY-MM-DD'))
), 'YYYY-MM-DD') AS PARTITION_DATE
FROM ${ORACLE_SCHEMA}.${ORACLE_TABLE}
WHERE GREATEST(
    COALESCE(FECHA_CREACION, TO_DATE('1900-01-01', 'YYYY-MM-DD')),
    COALESCE(FECHA_MODIFICACION, TO_DATE('1900-01-01', 'YYYY-MM-DD'))
) >= TO_DATE('${last_loaded_date}', 'YYYY-MM-DD')
ORDER BY PARTITION_DATE
```

## Consulta Principal de Extracción

### Con Paralelismo Oracle

```sql
SELECT /*+ PARALLEL(2) */ 
    ID,
    NOMBRE,
    DESCRIPCION,
    VALOR,
    ESTADO,
    FECHA_CREACION,
    FECHA_MODIFICACION,
    GREATEST(
        COALESCE(FECHA_CREACION, TO_DATE('1900-01-01', 'YYYY-MM-DD')),
        COALESCE(FECHA_MODIFICACION, TO_DATE('1900-01-01', 'YYYY-MM-DD'))
    ) AS PARTITION_DATE
FROM ${ORACLE_SCHEMA}.${ORACLE_TABLE}
WHERE '${PARTITION_DATE}' = 'ALL'
   OR GREATEST(
        COALESCE(FECHA_CREACION, TO_DATE('1900-01-01', 'YYYY-MM-DD')),
        COALESCE(FECHA_MODIFICACION, TO_DATE('1900-01-01', 'YYYY-MM-DD'))
    ) = TO_DATE('${PARTITION_DATE}', 'YYYY-MM-DD')
```

### Sin Columnas BLOB/CLOB

Para tablas con columnas BLOB o CLOB que no se necesitan:

```sql
SELECT /*+ PARALLEL(2) */ 
    ID,
    NOMBRE,
    -- Excluir BLOB: DOCUMENTO_BLOB
    NULL AS DOCUMENTO_BLOB,  -- Placeholder para mantener schema
    DESCRIPCION,
    FECHA_CREACION,
    GREATEST(
        COALESCE(FECHA_CREACION, TO_DATE('1900-01-01', 'YYYY-MM-DD'))
    ) AS PARTITION_DATE
FROM ${ORACLE_SCHEMA}.${ORACLE_TABLE}
WHERE '${PARTITION_DATE}' = 'ALL'
   OR TRUNC(FECHA_CREACION) = TO_DATE('${PARTITION_DATE}', 'YYYY-MM-DD')
```

## Verificación en Snowflake

### Verificar última fecha cargada

```sql
SELECT 
    COALESCE(TO_CHAR(MAX(PARTITION_DATE), 'YYYY-MM-DD'), '1900-01-01') AS LAST_LOADED_DATE,
    CASE WHEN COUNT(*) = 0 THEN 'FULL_LOAD' ELSE 'INCREMENTAL' END AS LOAD_TYPE
FROM ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.${TABLE_NAME}
```

### Verificar conteo por partición

```sql
SELECT 
    PARTITION_DATE,
    COUNT(*) AS RECORD_COUNT
FROM ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.${TABLE_NAME}
GROUP BY PARTITION_DATE
ORDER BY PARTITION_DATE DESC
LIMIT 30
```

### Eliminar datos de una fecha específica (para recarga)

```sql
DELETE FROM ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.${TABLE_NAME}
WHERE PARTITION_DATE = TO_DATE('${last_loaded_date}', 'YYYY-MM-DD')
```
