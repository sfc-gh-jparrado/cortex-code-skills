# Checklist de Validación del Flujo

## Pre-Creación

### Infraestructura Oracle
- [ ] Host Oracle accesible desde el runtime OpenFlow
- [ ] Puerto Oracle abierto (típicamente 1521)
- [ ] Usuario Oracle con permisos SELECT en la tabla origen
- [ ] Driver JDBC Oracle (ojdbc8.jar) subido como asset

### Infraestructura S3
- [ ] Bucket S3 creado
- [ ] IAM user o role con permisos `s3:PutObject`, `s3:DeleteObject`
- [ ] Access Key y Secret Key disponibles
- [ ] Bucket accesible desde la región del runtime

### Infraestructura Snowflake
- [ ] Database y Schema destino creados
- [ ] Tabla Iceberg destino creada con columna PARTITION_DATE
- [ ] External Volume configurado para Iceberg
- [ ] Stage interno AVRO_TMP creado
- [ ] Role con permisos necesarios (SELECT, INSERT, DELETE, USAGE)
- [ ] Warehouse asignado

### OpenFlow Runtime
- [ ] Runtime activo y saludable
- [ ] EAI configurada para acceso a Oracle
- [ ] EAI configurada para acceso a S3
- [ ] Perfil nipyapi válido

---

## Post-Creación

### Controller Services
- [ ] Oracle Connection Pool - Estado: ENABLED
- [ ] AWS Credentials Provider - Estado: ENABLED
- [ ] Snowflake Target Connection - Estado: ENABLED

### Procesadores
- [ ] Generate Trigger - VALID
- [ ] Check Last Loaded Date (Snowflake) - VALID
- [ ] Extract Load Info (Simple) - VALID
- [ ] Route Load Type - VALID
- [ ] Set Full Load Marker - VALID
- [ ] Delete Last Day Data - VALID
- [ ] Get Distinct Dates - VALID
- [ ] Extract PARTITION_DATE - VALID
- [ ] Query Oracle Data - VALID
- [ ] Write to S3 Stage - VALID
- [ ] Clear FlowFile Content - VALID
- [ ] Set Stage Path - VALID
- [ ] COPY INTO Iceberg - VALID

### Conexiones
- [ ] 13 conexiones creadas correctamente
- [ ] Ninguna conexión con FlowFiles en queue (inicial)

### Verificación de Flujo
```bash
# Comando para verificar procesadores inválidos
nipyapi --profile ${PROFILE} canvas list_invalid_processors --pg_id ${PG_ID}
# Esperado: lista vacía []

# Comando para verificar estado
nipyapi --profile ${PROFILE} ci get_status --process_group_id ${PG_ID}
# Esperado: invalid_count = 0
```

---

## Primera Ejecución (FULL_LOAD)

### Antes de Iniciar
- [ ] Verificar que la tabla destino está vacía o lista para carga inicial
- [ ] Confirmar schedule del trigger (o ejecutar manualmente)

### Durante la Ejecución
- [ ] Monitorear bulletins para errores
- [ ] Verificar que los FlowFiles avanzan por el flujo
- [ ] Revisar logs de Oracle para queries ejecutándose

### Después de la Ejecución
- [ ] Verificar conteo de registros en Snowflake
- [ ] Comparar conteo con Oracle (debe coincidir)
- [ ] Verificar distribución por PARTITION_DATE
- [ ] Confirmar que archivos en S3 fueron eliminados (PURGE=TRUE)

---

## Ejecuciones Incrementales

### Verificar Comportamiento
- [ ] load_type = 'INCREMENTAL' en atributos del FlowFile
- [ ] DELETE ejecuta correctamente para last_loaded_date
- [ ] Solo se procesan fechas >= last_loaded_date
- [ ] Datos nuevos aparecen en Snowflake

### Métricas a Revisar
- [ ] Tiempo de ejecución dentro de parámetros esperados
- [ ] Uso de warehouse Snowflake
- [ ] No hay acumulación en queues

---

## Troubleshooting Checklist

### Si Oracle falla con timeout
- [ ] Verificar conectividad de red (EAI)
- [ ] Reducir FETCH_SIZE
- [ ] Agregar índices en columnas de filtro
- [ ] Revisar paralelismo del hint

### Si S3 falla con Access Denied
- [ ] Verificar Access Key / Secret Key
- [ ] Verificar bucket name y región
- [ ] Verificar IAM policy incluye el bucket path completo

### Si COPY INTO falla
- [ ] Verificar que columnas coinciden (case insensitive)
- [ ] Verificar que stage_path es correcto
- [ ] Verificar permisos en el stage
- [ ] Revisar FILE_FORMAT

### Si el flujo se queda en loop
- [ ] Verificar que PARTITION_DATE no es NULL
- [ ] Verificar que la condición WHERE es correcta
- [ ] Revisar auto-terminate de relaciones failure
