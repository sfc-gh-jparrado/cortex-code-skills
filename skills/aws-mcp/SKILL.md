---
name: aws-mcp
description: Trabajar con AWS desde Cortex Code usando los servidores MCP de AWS Labs autenticados con SSO auto-refrescado. Invocar cuando el usuario pida cualquier operacion AWS (S3, EC2, IAM, CloudWatch, costos, S3 Tables, AWS CLI, documentacion AWS).
---

# Cuando usar

Siempre que el usuario pida algo relacionado con AWS:
- Listar/inspeccionar recursos (S3, EC2, IAM, Lambda, RDS, etc.)
- Consultar logs o metricas de CloudWatch
- Costos / Cost Explorer
- S3 Tables (Iceberg)
- Buscar documentacion oficial de AWS
- Ejecutar comandos AWS CLI / API

# Setup activo

- **Cuenta AWS**: 484577546576
- **Perfil AWS local**: `contributor-484577546576`
- **SSO portal**: https://d-92676189c4.awsapps.com/start (region us-west-2)
- **Region por defecto recursos**: us-east-1
- **Rol**: Contributor (AWSReservedSSO_Contributor_f053e0d1b8e89c3a)

## MCPs configurados (en ~/.snowflake/cortex/mcp.json)
1. `awslabs.core-mcp-server` - orquestador
2. `awslabs.aws-api-mcp-server` - AWS CLI/API generico
3. `awslabs.aws-documentation-mcp-server` - busqueda en docs.aws.amazon.com
4. `awslabs.cost-explorer-mcp-server` - costos
5. `awslabs.cloudwatch-mcp-server` - logs y metricas
6. `awslabs.s3-tables-mcp-server` - S3 Tables / Iceberg

## Auto-refresh SSO
Hook `PreToolUse` configurado en `~/.snowflake/cortex/hooks.json`:
- Matcher: `mcp__awslabs.*`
- Script: `~/.snowflake/cortex/hooks/aws-sso-refresh.sh`
- Antes de cada call a un MCP de AWS, verifica `sts get-caller-identity`. Si falla, dispara `aws sso login` (abre navegador) y permite continuar.
- Log del hook: `~/.snowflake/cortex/logs/aws-sso-hook.log`

# Como proceder

1. **Usar directamente** los tools `mcp_awslabs_*` sin pre-chequeo manual de SSO. El hook se encarga.
2. Si una llamada falla por error de credenciales:
   - Revisar `~/.snowflake/cortex/logs/aws-sso-hook.log`
   - Reintentar la operacion (el hook ya habra disparado el login).
3. Si el navegador no se abre o el login falla repetidamente:
   - Pedir al usuario que ejecute manualmente: `aws sso login --profile contributor-484577546576`
4. Para queries cross-region, usar el parametro `region` del MCP en lugar de cambiar el default.

# Restricciones

- **No proponer access keys de larga duracion** como solucion a expiraciones.
- **Respetar el rol Contributor**: si una accion falla por permisos IAM, informar al usuario en vez de intentar workarounds.
- **No exponer credenciales** en logs ni en mensajes.

# Troubleshooting

| Problema | Solucion |
|---|---|
| MCP devuelve "ExpiredToken" o "Unable to locate credentials" | Reintentar; el hook deberia disparar SSO. Si no, revisar log. |
| Hook no se dispara | Verificar `cat ~/.snowflake/cortex/hooks.json` y que Cortex Code se reinicio tras crearlo. |
| Browser no abre en macOS | El hook escribe el URL al log; abrirlo manualmente. |
| Sesion expira muy rapido | Pedir a admin de Identity Center subir duracion del Permission Set Contributor a 12h. |
