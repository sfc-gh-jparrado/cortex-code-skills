---
name: openflow-oracle-s3-snowflake
description: "Crear flujos OpenFlow para extraer datos de Oracle, escribir a S3 como Avro, y cargar a Snowflake Iceberg con COPY INTO. Triggers: oracle to snowflake, oracle s3 snowflake, crear flujo oracle, replicar tabla oracle, ETL oracle snowflake, carga incremental oracle."
---

# OpenFlow: Oracle → S3 → Snowflake Iceberg

Skill para crear flujos de integración que extraen datos de Oracle, los escriben temporalmente en S3 como Avro, y los cargan a tablas Iceberg en Snowflake usando COPY INTO.

## Patrón de Arquitectura

```
┌─────────┐    ┌─────────┐    ┌─────────────────┐    ┌───────────────┐
│ Oracle  │───▸│  Avro   │───▸│  S3 Bucket      │───▸│  Snowflake    │
│ (Source)│    │ Format  │    │  (Stage Temp)   │    │  Iceberg Table│
└─────────┘    └─────────┘    └─────────────────┘    └───────────────┘
     │                                                       │
     └── ExecuteSQL ──▸ PutS3Object ──▸ COPY INTO ──────────┘
```

## Prerrequisitos

Antes de iniciar, verificar que existan:

1. **Runtime OpenFlow** configurado con EAI para acceso a Oracle y S3
2. **Driver JDBC Oracle** (ojdbc8.jar) subido como asset al Parameter Context
3. **Bucket S3** con permisos de escritura
4. **Tabla Iceberg destino** en Snowflake ya creada
5. **External Access Integration (EAI)** que permita conexión a Oracle y S3

---

## Workflow

### Paso 1: Recopilar Información del Usuario

**CHECKPOINT OBLIGATORIO** - Solicitar al usuario:

```
Para crear el flujo Oracle → S3 → Snowflake, necesito la siguiente información:

═══════════════════════════════════════════════════════════════════
                    CONFIGURACIÓN DE ORIGEN (ORACLE)
═══════════════════════════════════════════════════════════════════

1. Host Oracle (ej: oracle-db.example.com): 
2. Puerto Oracle (ej: 1521): 
3. Service Name o SID (ej: ORCL): 
4. Usuario Oracle: 
5. Schema Oracle (ej: USERSOI): 
6. Nombre de tabla origen (ej: SOI_PLANILLA): 
7. Columna(s) para particionar por fecha (ej: FECHA_MODIFICACION, FECHA_CREACION):
   (Se usará GREATEST de estas columnas como PARTITION_DATE)

═══════════════════════════════════════════════════════════════════
                    CONFIGURACIÓN DE S3 (STAGING)
═══════════════════════════════════════════════════════════════════

8. Bucket S3 (ej: my-etl-bucket): 
9. Prefijo/Path en S3 (ej: staging/oracle): 
10. Región AWS (ej: us-east-1): 
11. AWS Access Key ID: 
12. AWS Secret Access Key: 

═══════════════════════════════════════════════════════════════════
                    CONFIGURACIÓN DE DESTINO (SNOWFLAKE)
═══════════════════════════════════════════════════════════════════

13. Database Snowflake destino (ej: DB_ACH_POC): 
14. Schema Snowflake destino (ej: RAW_V1): 
15. Nombre tabla destino (ej: SOI_PLANILLA): 
16. Warehouse Snowflake (ej: ACH_WH): 
17. Role Snowflake (ej: OPENFLOW_ADMIN): 

═══════════════════════════════════════════════════════════════════
                    CONFIGURACIÓN DEL FLUJO
═══════════════════════════════════════════════════════════════════

18. Nombre del Process Group (ej: SOI_PLANILLA_RAW): 
19. Schedule de ejecución (ej: 0 0 * * * ? para cada hora): 
20. Max Rows Per FlowFile (recomendado: 500000): 
21. Fetch Size Oracle (recomendado: 50000): 

═══════════════════════════════════════════════════════════════════
                    CONFIGURACIÓN DEL RUNTIME
═══════════════════════════════════════════════════════════════════

22. Nombre del perfil nipyapi (verificar con cache de sesión): 

```

**NO CONTINUAR** hasta tener todos los valores.

---

### Paso 2: Validar Conexión a OpenFlow

```bash
# Verificar sesión activa
nipyapi --profile ${NIPYAPI_PROFILE} canvas get_root_pg_id
```

Si falla, cargar `references/core-session.md` del skill openflow.

---

### Paso 3: Crear Parameter Context

Crear Parameter Context para almacenar configuración:

```bash
nipyapi --profile ${NIPYAPI_PROFILE} parameters create_parameter_context \
  --name "${PROCESS_GROUP_NAME}_Parameters" \
  --description "Parameters for ${PROCESS_GROUP_NAME} flow"
```

Agregar parámetro para driver Oracle (si no existe):

```bash
nipyapi --profile ${NIPYAPI_PROFILE} parameters add_parameter \
  --context_name "${PROCESS_GROUP_NAME}_Parameters" \
  --name "oracle_jdbc_driver" \
  --value "/nifi/configuration_resources/assets/${CONTEXT_ID}/ojdbc8-21.9.0.0.jar" \
  --sensitive false
```

---

### Paso 4: Crear Controller Services

#### 4.1 Oracle Connection Pool

```python
# Usar nipyapi Python para crear controller service
import nipyapi

nipyapi.profiles.switch('${NIPYAPI_PROFILE}')

# Crear Oracle DBCP Connection Pool
oracle_cs = nipyapi.canvas.create_controller(
    pg_id='${ROOT_PG_ID}',
    controller_type='org.apache.nifi.dbcp.DBCPConnectionPool',
    name='Oracle Connection Pool - ${TABLE_NAME}'
)

# Configurar propiedades
nipyapi.canvas.update_controller(
    controller=oracle_cs,
    update={
        'component': {
            'properties': {
                'Database Connection URL': 'jdbc:oracle:thin:@${ORACLE_HOST}:${ORACLE_PORT}:${ORACLE_SID}',
                'Database Driver Class Name': 'oracle.jdbc.OracleDriver',
                'Database Driver Locations': '#{oracle_jdbc_driver}',
                'Database User': '${ORACLE_USER}',
                'Password': '${ORACLE_PASSWORD}',
                'Max Total Connections': '10',
                'Max Wait Time': '1 min',
                'Minimum Idle Connections': '2',
                'Maximum Idle Connections': '5',
                'Validation query': 'SELECT 1 FROM DUAL'
            }
        }
    }
)
```

#### 4.2 AWS Credentials Provider

```python
aws_cs = nipyapi.canvas.create_controller(
    pg_id='${ROOT_PG_ID}',
    controller_type='org.apache.nifi.processors.aws.credentials.provider.service.AWSCredentialsProviderControllerService',
    name='AWS Credentials for S3 - ${TABLE_NAME}'
)

nipyapi.canvas.update_controller(
    controller=aws_cs,
    update={
        'component': {
            'properties': {
                'Use Default Credentials': 'false',
                'Access Key ID': '${AWS_ACCESS_KEY}',
                'Secret Access Key': '${AWS_SECRET_KEY}',
                'Assume Role STS Region': '${AWS_REGION}'
            }
        }
    }
)
```

#### 4.3 Snowflake Target Connection

```python
snowflake_cs = nipyapi.canvas.create_controller(
    pg_id='${ROOT_PG_ID}',
    controller_type='com.snowflake.openflow.runtime.services.snowflake.SnowflakeConnectionService',
    name='Snowflake Target - ${TABLE_NAME}'
)

nipyapi.canvas.update_controller(
    controller=snowflake_cs,
    update={
        'component': {
            'properties': {
                'Authentication Strategy': 'SNOWFLAKE_SESSION_TOKEN',
                'Warehouse': '${SNOWFLAKE_WAREHOUSE}',
                'Database Name': '${SNOWFLAKE_DATABASE}',
                'Schema': '${SNOWFLAKE_SCHEMA}',
                'Role': '${SNOWFLAKE_ROLE}',
                'Maximum Connections': '10'
            }
        }
    }
)
```

#### 4.4 Habilitar Controller Services

```bash
nipyapi --profile ${NIPYAPI_PROFILE} canvas schedule_controller \
  --controller_id ${ORACLE_CS_ID} --state ENABLED

nipyapi --profile ${NIPYAPI_PROFILE} canvas schedule_controller \
  --controller_id ${AWS_CS_ID} --state ENABLED

nipyapi --profile ${NIPYAPI_PROFILE} canvas schedule_controller \
  --controller_id ${SNOWFLAKE_CS_ID} --state ENABLED
```

---

### Paso 5: Crear Process Group

```bash
nipyapi --profile ${NIPYAPI_PROFILE} canvas create_process_group \
  --pg_id ${ROOT_PG_ID} \
  --name "${PROCESS_GROUP_NAME}" \
  --position '{"x": 500.0, "y": 300.0}'
```

Asignar Parameter Context al Process Group:

```python
pg = nipyapi.canvas.get_process_group('${PG_ID}')
nipyapi.canvas.update_process_group(
    pg,
    update={
        'component': {
            'parameter_context': {
                'id': '${PARAMETER_CONTEXT_ID}'
            }
        }
    }
)
```

---

### Paso 6: Crear Procesadores

Crear los 13 procesadores en orden. **Ejecutar uno por uno**.

#### 6.1 Generate Trigger

```python
proc_trigger = nipyapi.canvas.create_processor(
    pg_id='${PG_ID}',
    processor_type='org.apache.nifi.processors.standard.GenerateFlowFile',
    name='Generate Trigger',
    position={'x': -2000.0, 'y': 0.0},
    config={
        'properties': {
            'File Size': '0B',
            'Batch Size': '1',
            'Custom Text': 'START'
        },
        'scheduling_period': '${SCHEDULE_CRON}',
        'scheduling_strategy': 'CRON_DRIVEN'
    }
)
```

#### 6.2 Check Last Loaded Date (Snowflake)

```python
proc_check = nipyapi.canvas.create_processor(
    pg_id='${PG_ID}',
    processor_type='com.snowflake.openflow.runtime.processors.database.ExecuteSQLStatement',
    name='Check Last Loaded Date (Snowflake)',
    position={'x': -1600.0, 'y': 0.0},
    config={
        'properties': {
            'Connection Pooling Service': '${SNOWFLAKE_CS_ID}',
            'SQL': """SELECT COALESCE(TO_CHAR(MAX(PARTITION_DATE), 'YYYY-MM-DD'), '1900-01-01') AS LAST_LOADED_DATE, 
CASE WHEN COUNT(*) = 0 THEN 'FULL_LOAD' ELSE 'INCREMENTAL' END AS LOAD_TYPE 
FROM ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.${TABLE_NAME}""",
            'Max Batch Size': '1'
        }
    }
)
```

#### 6.3 Extract Load Info (Simple)

```python
proc_extract_info = nipyapi.canvas.create_processor(
    pg_id='${PG_ID}',
    processor_type='org.apache.nifi.processors.script.ExecuteScript',
    name='Extract Load Info (Simple)',
    position={'x': -1200.0, 'y': 0.0},
    config={
        'properties': {
            'Script Engine': 'Groovy',
            'Script Body': '''def ff = session.get()
if (!ff) return

def lastLoadedDate = "1900-01-01"
def loadType = "FULL_LOAD"

try {
    def dbcpService = context.getProperty('Database Connection').asControllerService(org.apache.nifi.dbcp.DBCPService)
    def conn = null
    def stmt = null
    def rs = null
    
    try {
        conn = dbcpService.getConnection()
        stmt = conn.createStatement()
        
        def sql = """
            SELECT 
                COALESCE(TO_CHAR(MAX(PARTITION_DATE), 'YYYY-MM-DD'), '1900-01-01') AS LAST_LOADED_DATE,
                CASE WHEN COUNT(*) = 0 THEN 'FULL_LOAD' ELSE 'INCREMENTAL' END AS LOAD_TYPE
            FROM ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.${TABLE_NAME}
        """
        
        rs = stmt.executeQuery(sql)
        
        if (rs.next()) {
            lastLoadedDate = rs.getString("LAST_LOADED_DATE")
            loadType = rs.getString("LOAD_TYPE")
        }
        
    } finally {
        if (rs != null) try { rs.close() } catch (Exception e) {}
        if (stmt != null) try { stmt.close() } catch (Exception e) {}
        if (conn != null) try { conn.close() } catch (Exception e) {}
    }
    
} catch (Exception e) {
    log.error("Error ejecutando query: " + e.getMessage(), e)
}

ff = session.putAttribute(ff, "last_loaded_date", lastLoadedDate)
ff = session.putAttribute(ff, "load_type", loadType)

session.transfer(ff, REL_SUCCESS)''',
            'Database Connection': '${SNOWFLAKE_CS_ID}'
        }
    }
)
```

#### 6.4 Route Load Type

```python
proc_route = nipyapi.canvas.create_processor(
    pg_id='${PG_ID}',
    processor_type='org.apache.nifi.processors.standard.RouteOnAttribute',
    name='Route Load Type',
    position={'x': -800.0, 'y': 0.0},
    config={
        'properties': {
            'Routing Strategy': 'Route to Property name',
            'full_load': "${load_type:equals('FULL_LOAD')}",
            'incremental': "${load_type:equals('INCREMENTAL')}"
        }
    }
)
```

#### 6.5 Set Full Load Marker

```python
proc_full_load = nipyapi.canvas.create_processor(
    pg_id='${PG_ID}',
    processor_type='org.apache.nifi.processors.attributes.UpdateAttribute',
    name='Set Full Load Marker',
    position={'x': -400.0, 'y': -200.0},
    config={
        'properties': {
            'PARTITION_DATE': 'ALL'
        }
    }
)
```

#### 6.6 Delete Last Day Data

```python
proc_delete = nipyapi.canvas.create_processor(
    pg_id='${PG_ID}',
    processor_type='org.apache.nifi.processors.standard.PutSQL',
    name='Delete Last Day Data',
    position={'x': -400.0, 'y': 200.0},
    config={
        'properties': {
            'JDBC Connection Pool': '${SNOWFLAKE_CS_ID}',
            'SQL Statement': """DELETE FROM ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.${TABLE_NAME} 
WHERE PARTITION_DATE = TO_DATE('${"$"}{last_loaded_date}', 'YYYY-MM-DD')""",
            'Support Fragmented Transactions': 'false',
            'Rollback On Failure': 'false'
        },
        'auto_terminated_relationships': ['failure', 'retry']
    }
)
```

#### 6.7 Get Distinct Dates

```python
proc_dates = nipyapi.canvas.create_processor(
    pg_id='${PG_ID}',
    processor_type='org.apache.nifi.processors.standard.ExecuteSQL',
    name='Get Distinct Dates',
    position={'x': 0.0, 'y': 200.0},
    config={
        'properties': {
            'Database Connection Pooling Service': '${ORACLE_CS_ID}',
            'SQL Query': """SELECT DISTINCT TO_CHAR(GREATEST(
    ${PARTITION_DATE_COLUMNS_COALESCE}
), 'YYYY-MM-DD') AS PARTITION_DATE
FROM ${ORACLE_SCHEMA}.${ORACLE_TABLE}
WHERE GREATEST(
    ${PARTITION_DATE_COLUMNS_COALESCE}
) >= TO_DATE('${"$"}{last_loaded_date}', 'YYYY-MM-DD')
ORDER BY PARTITION_DATE""",
            'Max Rows Per FlowFile': '1',
            'Output Batch Size': '1',
            'Fetch Size': '0',
            'Content Output Strategy': 'EMPTY'
        }
    }
)
```

#### 6.8 Extract PARTITION_DATE

```python
proc_extract_date = nipyapi.canvas.create_processor(
    pg_id='${PG_ID}',
    processor_type='org.apache.nifi.processors.script.ExecuteScript',
    name='Extract PARTITION_DATE',
    position={'x': 400.0, 'y': 200.0},
    config={
        'properties': {
            'Script Engine': 'Groovy',
            'Script Body': '''import org.apache.avro.file.DataFileStream
import org.apache.avro.generic.GenericDatumReader
import org.apache.avro.generic.GenericRecord

def flowFile = session.get()
if (!flowFile) return

try {
    def dateValue = null
    
    session.read(flowFile, { inputStream ->
        def reader = new DataFileStream(inputStream, new GenericDatumReader())
        if (reader.hasNext()) {
            def record = reader.next()
            dateValue = record.get("PARTITION_DATE")?.toString()
        }
        reader.close()
    } as org.apache.nifi.processor.io.InputStreamCallback)
    
    if (dateValue) {
        flowFile = session.putAttribute(flowFile, "PARTITION_DATE", dateValue)
        session.transfer(flowFile, REL_SUCCESS)
    } else {
        session.transfer(flowFile, REL_FAILURE)
    }
} catch (Exception e) {
    log.error("Error: " + e.getMessage())
    session.transfer(flowFile, REL_FAILURE)
}'''
        }
    }
)
```

#### 6.9 Query Oracle Data

```python
proc_query = nipyapi.canvas.create_processor(
    pg_id='${PG_ID}',
    processor_type='org.apache.nifi.processors.standard.ExecuteSQL',
    name='Query Oracle Data',
    position={'x': 800.0, 'y': 0.0},
    config={
        'properties': {
            'Database Connection Pooling Service': '${ORACLE_CS_ID}',
            'SQL Query': """SELECT /*+ PARALLEL(2) */ 
    ${COLUMN_LIST},
    GREATEST(
        ${PARTITION_DATE_COLUMNS_COALESCE}
    ) AS PARTITION_DATE
FROM ${ORACLE_SCHEMA}.${ORACLE_TABLE}
WHERE '${"$"}{PARTITION_DATE}' = 'ALL'
   OR GREATEST(
    ${PARTITION_DATE_COLUMNS_COALESCE}
) = TO_DATE('${"$"}{PARTITION_DATE}', 'YYYY-MM-DD')""",
            'Max Wait Time': '60 mins',
            'Max Rows Per FlowFile': '${MAX_ROWS_PER_FLOWFILE}',
            'Output Batch Size': '10000',
            'Fetch Size': '${FETCH_SIZE}',
            'Content Output Strategy': 'EMPTY'
        }
    }
)
```

#### 6.10 Write to S3 Stage

```python
proc_s3 = nipyapi.canvas.create_processor(
    pg_id='${PG_ID}',
    processor_type='org.apache.nifi.processors.aws.s3.PutS3Object',
    name='Write to S3 Stage',
    position={'x': 1200.0, 'y': 0.0},
    config={
        'properties': {
            'Bucket': '${S3_BUCKET}',
            'Object Key': '${S3_PREFIX}/${TABLE_NAME}/${"$"}{PARTITION_DATE}/${"$"}{uuid}',
            'Region': '${AWS_REGION}',
            'AWS Credentials Provider Service': '${AWS_CS_ID}',
            'Storage Class': 'STANDARD'
        }
    }
)
```

#### 6.11 Clear FlowFile Content

```python
proc_clear = nipyapi.canvas.create_processor(
    pg_id='${PG_ID}',
    processor_type='org.apache.nifi.processors.standard.ReplaceText',
    name='Clear FlowFile Content',
    position={'x': 1600.0, 'y': 0.0},
    config={
        'properties': {
            'Replacement Strategy': 'Regex Replace',
            'Search Value': '(?s)(^.*$)',
            'Replacement Value': '',
            'Evaluation Mode': 'Entire text'
        }
    }
)
```

#### 6.12 Set Stage Path

```python
proc_stage = nipyapi.canvas.create_processor(
    pg_id='${PG_ID}',
    processor_type='org.apache.nifi.processors.attributes.UpdateAttribute',
    name='Set Stage Path',
    position={'x': 2000.0, 'y': 0.0},
    config={
        'properties': {
            'stage_path': '@${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.AVRO_TMP/${TABLE_NAME}/${"$"}{PARTITION_DATE}/${"$"}{uuid}'
        }
    }
)
```

#### 6.13 COPY INTO Iceberg

```python
proc_copy = nipyapi.canvas.create_processor(
    pg_id='${PG_ID}',
    processor_type='com.snowflake.openflow.runtime.processors.database.ExecuteSQLStatement',
    name='COPY INTO Iceberg',
    position={'x': 2400.0, 'y': 0.0},
    config={
        'properties': {
            'Connection Pooling Service': '${SNOWFLAKE_CS_ID}',
            'SQL': """COPY INTO ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.${TABLE_NAME}
FROM ${"$"}{stage_path}
FILE_FORMAT = (TYPE = 'AVRO')
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
PURGE = TRUE""",
            'Max Batch Size': '1'
        }
    }
)
```

---

### Paso 7: Crear Conexiones

Crear las conexiones entre procesadores en este orden:

```python
connections = [
    ('Generate Trigger', 'Check Last Loaded Date (Snowflake)', ['success']),
    ('Check Last Loaded Date (Snowflake)', 'Extract Load Info (Simple)', ['success']),
    ('Extract Load Info (Simple)', 'Route Load Type', ['success']),
    ('Route Load Type', 'Set Full Load Marker', ['full_load']),
    ('Route Load Type', 'Delete Last Day Data', ['incremental']),
    ('Set Full Load Marker', 'Query Oracle Data', ['success']),
    ('Delete Last Day Data', 'Get Distinct Dates', ['success']),
    ('Get Distinct Dates', 'Extract PARTITION_DATE', ['success']),
    ('Extract PARTITION_DATE', 'Query Oracle Data', ['success']),
    ('Query Oracle Data', 'Write to S3 Stage', ['success']),
    ('Write to S3 Stage', 'Clear FlowFile Content', ['success']),
    ('Clear FlowFile Content', 'Set Stage Path', ['success']),
    ('Set Stage Path', 'COPY INTO Iceberg', ['success'])
]

for source_name, dest_name, relationships in connections:
    source_proc = nipyapi.canvas.get_processor(source_name, pg_id='${PG_ID}')
    dest_proc = nipyapi.canvas.get_processor(dest_name, pg_id='${PG_ID}')
    
    nipyapi.canvas.create_connection(
        source=source_proc,
        destination=dest_proc,
        relationships=relationships,
        name=relationships[0]
    )
```

---

### Paso 8: Configurar Auto-Terminate

Auto-terminar relaciones de fallo no conectadas:

```python
# Query Oracle Data - failure a Funnel o auto-terminate
# Otras relaciones failure/retry auto-terminadas en la creación
```

---

### Paso 9: Verificar y Validar

```bash
# Verificar que no hay procesadores inválidos
nipyapi --profile ${NIPYAPI_PROFILE} canvas list_invalid_processors --pg_id ${PG_ID}

# Verificar estado del flujo
nipyapi --profile ${NIPYAPI_PROFILE} ci get_status --process_group_id ${PG_ID}
```

---

### Paso 10: Iniciar el Flujo

**CHECKPOINT OBLIGATORIO** - Mostrar resumen y pedir confirmación:

```
═══════════════════════════════════════════════════════════════════
                    RESUMEN DEL FLUJO CREADO
═══════════════════════════════════════════════════════════════════

Process Group: ${PROCESS_GROUP_NAME}
Procesadores: 13
Conexiones: 13

ORIGEN (Oracle):
  - Host: ${ORACLE_HOST}:${ORACLE_PORT}
  - Schema.Table: ${ORACLE_SCHEMA}.${ORACLE_TABLE}

STAGING (S3):
  - Bucket: ${S3_BUCKET}
  - Path: ${S3_PREFIX}/${TABLE_NAME}/

DESTINO (Snowflake):
  - Database: ${SNOWFLAKE_DATABASE}
  - Schema: ${SNOWFLAKE_SCHEMA}
  - Table: ${TABLE_NAME}

SCHEDULE: ${SCHEDULE_CRON}

═══════════════════════════════════════════════════════════════════

¿Desea iniciar el flujo ahora? (Si/No)
```

Si el usuario confirma:

```bash
nipyapi --profile ${NIPYAPI_PROFILE} ci start_flow --process_group_id ${PG_ID}
```

---

## Troubleshooting

### Error: ORA-12154 TNS could not resolve

**Causa:** String de conexión incorrecta
**Solución:** Verificar formato: `jdbc:oracle:thin:@HOST:PORT:SID` o `jdbc:oracle:thin:@HOST:PORT/SERVICE_NAME`

### Error: Access Denied S3

**Causa:** Credenciales AWS incorrectas o bucket sin permisos
**Solución:** Verificar IAM policy incluye `s3:PutObject` en el bucket

### Error: Snowflake SESSION_TOKEN

**Causa:** Solo funciona en deployments SPCS
**Solución:** En BYOC usar KEY_PAIR authentication

### Error: COPY INTO failed

**Causa:** Schema mismatch entre Avro y tabla destino
**Solución:** Verificar que todas las columnas en el SELECT existen en la tabla Iceberg

---

## Notas Importantes

1. **El flujo usa PARTITION_DATE** como columna de partición calculada usando GREATEST de las columnas de fecha especificadas

2. **Carga Incremental**: Elimina datos del último día antes de recargar para evitar duplicados

3. **S3 como Stage Temporal**: Los archivos se eliminan automáticamente con PURGE = TRUE en COPY INTO

4. **Formato Avro**: ExecuteSQL genera Avro nativo, no requiere conversión adicional

5. **Paralelismo Oracle**: El hint `/*+ PARALLEL(2) */` optimiza queries grandes

---

## Output

- Process Group funcional en OpenFlow
- Controller Services configurados y habilitados
- Flujo de datos Oracle → S3 → Snowflake operativo
- Soporte para carga inicial (FULL_LOAD) e incremental
