-- FSI — Gobierno: auditoría y linaje ("¿quién vio qué, quién copió qué, quién intentó sacar datos?")
-- Nota: system.access.audit y el linaje tienen latencia de minutos a ~1 h.
-- Workspace compartido: todas las consultas se limitan a los usuarios del demo (seguros_gobierno.usuarios_rol)
-- para no mostrar actividad de otras personas.

-- 1. ¿Quién consultó tablas del demo en los últimos 7 días?
SELECT user_identity.email usuario, request_params.full_name_arg tabla, COUNT(*) accesos, MAX(event_time) ultimo_acceso
FROM system.access.audit
WHERE event_date >= current_date() - 7 AND service_name = 'unityCatalog'
  AND user_identity.email IN (SELECT usuario FROM demo_catalog.seguros_gobierno.usuarios_rol)
  AND action_name IN ('getTable', 'generateTemporaryTableCredential')
  AND request_params.full_name_arg LIKE 'demo_catalog.seguros_demo.%'
  AND request_params.full_name_arg NOT LIKE 'demo_catalog.seguros_demo.\_\_%'   -- internos del pipeline (staging/materialization)
  AND request_params.full_name_arg NOT LIKE '%.event\_log\_%'
GROUP BY ALL ORDER BY accesos DESC LIMIT 25;

-- 2. Intentos de extracción: descargas / exportaciones de resultados (notebooks, SQL, dashboards)
SELECT event_time, user_identity.email usuario, service_name, action_name, source_ip_address
FROM system.access.audit
WHERE event_date >= current_date() - 30
  AND (action_name ILIKE '%download%' OR action_name ILIKE '%export%')
  AND user_identity.email IN (SELECT usuario FROM demo_catalog.seguros_gobierno.usuarios_rol)
  AND service_name <> 'filesystem'            -- excluye URLs internas de almacenamiento
ORDER BY event_time DESC LIMIT 25;

-- 3. Cambios de gobierno: políticas ABAC, tags y permisos
SELECT event_time, user_identity.email usuario, action_name,
       COALESCE(request_params.full_name_arg, request_params.name, request_params.securable_full_name) objeto
FROM system.access.audit
WHERE event_date >= current_date() - 7 AND service_name = 'unityCatalog'
  AND user_identity.email IN (SELECT usuario FROM demo_catalog.seguros_gobierno.usuarios_rol)
  AND (action_name ILIKE '%Policy%' OR action_name ILIKE '%TagAssignment%' OR action_name = 'updatePermissions')
  AND action_name NOT ILIKE 'get%' AND action_name NOT ILIKE 'list%'   -- solo cambios, no lecturas
  AND to_json(request_params) ILIKE '%seguros%'
ORDER BY event_time DESC LIMIT 25;

-- 4. ¿Alguien creó conexiones / catálogos federados nuevos? (re-ingesta de fuentes = duplicación)
SELECT event_time, user_identity.email usuario, action_name, request_params.name objeto
FROM system.access.audit
WHERE event_date >= current_date() - 30 AND service_name = 'unityCatalog'
  AND user_identity.email IN (SELECT usuario FROM demo_catalog.seguros_gobierno.usuarios_rol)
  AND action_name IN ('createConnection', 'createCatalog')
  AND to_json(request_params) ILIKE '%seguros%'
ORDER BY event_time DESC;

-- 5. Linaje: ¿quién copió datos oficiales hacia otro lado? (tablas creadas a partir de dim_cliente)
SELECT event_time, created_by usuario, source_table_full_name origen, target_table_full_name destino, entity_type
FROM system.access.table_lineage
WHERE source_table_full_name = 'demo_catalog.seguros_demo.dim_cliente'
  AND created_by IN (SELECT usuario FROM demo_catalog.seguros_gobierno.usuarios_rol)
  AND target_table_full_name IS NOT NULL
  AND target_table_full_name NOT LIKE 'demo_catalog.seguros_demo.%'
ORDER BY event_time DESC LIMIT 25;

-- 6. Consultas ejecutadas sobre datos de clientes (texto SQL, duración, filas leídas)
SELECT start_time, executed_by usuario, statement_type, ROUND(total_duration_ms / 1000, 1) seg,
       read_rows filas_leidas, substr(statement_text, 1, 120) consulta
FROM system.query.history
WHERE start_time >= current_date() - 7 AND executed_by IN (SELECT usuario FROM demo_catalog.seguros_gobierno.usuarios_rol)
  AND statement_text ILIKE '%seguros_demo.dim_cliente%'
ORDER BY start_time DESC LIMIT 25;
