# Evidence · Unity Catalog governance

_Captured 2026-11-05 13:48 CST from the live Databricks workspace via the SQL Statement Execution API. Results below are the actual query output._

Governed tags, ABAC policies and the same query returning different answers per role.

## ABAC policies on the gold schema

```sql
SHOW POLICIES ON SCHEMA demo_catalog.seguros_demo
```

| Policy Name | Policy Type | Catalog | Schema | Table | Comment | on_securable_type | on_securable_fullname |
|---|---|---|---|---|---|---|---|
| seguros_filtro_region | ROW_FILTER | demo_catalog | seguros_demo |  | Agentes regionales solo ven filas de su región en tablas oficiales | SCHEMA | demo_catalog.seguros_demo |
| seguros_mask_curp | COLUMN_MASK | demo_catalog | seguros_demo |  | Enmascara columnas seguros_pii=curp en tablas oficiales según el rol del usuario | SCHEMA | demo_catalog.seguros_demo |
| seguros_mask_email | COLUMN_MASK | demo_catalog | seguros_demo |  | Enmascara columnas seguros_pii=email en tablas oficiales según el rol del usuario | SCHEMA | demo_catalog.seguros_demo |
| seguros_mask_nombre | COLUMN_MASK | demo_catalog | seguros_demo |  | Enmascara columnas seguros_pii=nombre en tablas oficiales según el rol del usuario | SCHEMA | demo_catalog.seguros_demo |
| seguros_mask_rfc | COLUMN_MASK | demo_catalog | seguros_demo |  | Enmascara columnas seguros_pii=rfc en tablas oficiales según el rol del usuario | SCHEMA | demo_catalog.seguros_demo |

## Governed tags on columns (PII, region, certification)

```sql
SELECT tag_name, tag_value, count(*) columnas
FROM demo_catalog.information_schema.column_tags
WHERE schema_name IN ('seguros_demo','seguros_ml') AND tag_name LIKE 'seguros_%'
GROUP BY ALL ORDER BY 1,2
```

| tag_name | tag_value | columnas |
|---|---|---|
| seguros_pii | curp | 5 |
| seguros_pii | email | 6 |
| seguros_pii | nombre | 13 |
| seguros_pii | rfc | 12 |
| seguros_pii | telefono | 8 |
| seguros_pii | vin_placas | 14 |
| seguros_region | region | 6 |

## Same query, three roles

The demo user's role is switched in `seguros_gobierno.usuarios_rol` and the **same** query is re-run. Unity Catalog ABAC policies (column masks + row filter) change the answer; the query text does not change.


## Role = SIU

```sql
SELECT current_user() usuario, demo_catalog.seguros_gobierno.rol_actual() rol, demo_catalog.seguros_gobierno.region_actual() region,
       count(*) clientes_visibles, count(DISTINCT region) regiones_visibles,
       max_by(nombre_completo, id_cliente) ejemplo_nombre, max_by(rfc, id_cliente) ejemplo_rfc, max_by(telefono, id_cliente) ejemplo_telefono
FROM demo_catalog.seguros_demo.dim_cliente
```

| usuario | rol | region | clientes_visibles | regiones_visibles | ejemplo_nombre | ejemplo_rfc | ejemplo_telefono |
|---|---|---|---|---|---|---|---|
| <tu_usuario> | SIU |  | 60000 | 6 | Roberto Ruiz Ortega | RUOR970628HTT | 9991764031 |

## Role = ACTUARIO

```sql
SELECT current_user() usuario, demo_catalog.seguros_gobierno.rol_actual() rol, demo_catalog.seguros_gobierno.region_actual() region,
       count(*) clientes_visibles, count(DISTINCT region) regiones_visibles,
       max_by(nombre_completo, id_cliente) ejemplo_nombre, max_by(rfc, id_cliente) ejemplo_rfc, max_by(telefono, id_cliente) ejemplo_telefono
FROM demo_catalog.seguros_demo.dim_cliente
```

| usuario | rol | region | clientes_visibles | regiones_visibles | ejemplo_nombre | ejemplo_rfc | ejemplo_telefono |
|---|---|---|---|---|---|---|---|
| <tu_usuario> | ACTUARIO |  | 60000 | 6 | R. R. O. | RUOR********* | 9991764031 |

## Role = AGENTE_REGIONAL · region Norte

```sql
SELECT current_user() usuario, demo_catalog.seguros_gobierno.rol_actual() rol, demo_catalog.seguros_gobierno.region_actual() region,
       count(*) clientes_visibles, count(DISTINCT region) regiones_visibles,
       max_by(nombre_completo, id_cliente) ejemplo_nombre, max_by(rfc, id_cliente) ejemplo_rfc, max_by(telefono, id_cliente) ejemplo_telefono
FROM demo_catalog.seguros_demo.dim_cliente
```

| usuario | rol | region | clientes_visibles | regiones_visibles | ejemplo_nombre | ejemplo_rfc | ejemplo_telefono |
|---|---|---|---|---|---|---|---|
| <tu_usuario> | AGENTE_REGIONAL | Norte | 10655 | 1 | Alejandro Reyes Ramos | RERA******W8S | 4427902919 |

## Sandbox copy made as ACTUARIO stays masked forever (no PII to recover)

```sql
SELECT count(*) filas, max(nombre_completo) ejemplo_nombre, max(rfc) ejemplo_rfc FROM demo_catalog.seguros_sandbox_ds.copia_clientes_ana
```

| filas | ejemplo_nombre | ejemplo_rfc |
|---|---|---|
| 60000 | Ó. Á. T. | VEVX********* |
