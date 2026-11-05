# Evidence · Lakeflow ingestion and medallion pipeline

_Captured 2026-11-05 13:49 CST from the live Databricks workspace via the SQL Statement Execution API. Results below are the actual query output._

Pipeline `seguros_medallion` (Lakeflow Declarative Pipelines): event log, row counts, expectations and quarantine.

## Pipeline updates (most recent first)

```sql
SELECT origin.update_id, timestamp, details:update_progress.state AS state
FROM event_log('<UUID>')
WHERE event_type = 'update_progress' AND details:update_progress.state IN ('COMPLETED','FAILED','RUNNING')
ORDER BY timestamp DESC LIMIT 6
```

| update_id | timestamp | state |
|---|---|---|
| <UUID> | 2026-11-05T14:48:29.428-05:00 | COMPLETED |
| <UUID> | 2026-11-05T14:45:14.055-05:00 | RUNNING |
| <UUID> | 2026-10-19T12:21:28.433-04:00 | COMPLETED |
| <UUID> | 2026-10-19T12:17:48.892-04:00 | RUNNING |
| <UUID> | 2026-10-19T12:13:20.981-04:00 | COMPLETED |
| <UUID> | 2026-10-19T12:08:11.242-04:00 | RUNNING |

## Rows written per table in the latest update

```sql
WITH last AS (SELECT origin.update_id u FROM event_log('<UUID>') WHERE event_type='create_update' ORDER BY timestamp DESC LIMIT 1)
SELECT origin.flow_name AS flow,
       max(CAST(details:flow_progress.metrics.num_output_rows AS BIGINT)) AS output_rows,
       max(details:flow_progress.status) AS status
FROM event_log('<UUID>'), last
WHERE event_type = 'flow_progress' AND origin.update_id = last.u AND details:flow_progress.metrics.num_output_rows IS NOT NULL
GROUP BY 1 ORDER BY 1
```

| flow | output_rows | status |
|---|---|---|
| demo_catalog.seguros_demo.act_factores_desarrollo | 30 | COMPLETED |
| demo_catalog.seguros_demo.act_reservas | 30 | COMPLETED |
| demo_catalog.seguros_demo.act_siniestralidad_periodo | 6 | COMPLETED |
| demo_catalog.seguros_demo.act_triangulo | 180 | COMPLETED |
| demo_catalog.seguros_demo.act_triangulo_observado | 105 | COMPLETED |
| demo_catalog.seguros_demo.bronze_agentes | 600 | COMPLETED |
| demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 | 62400 | COMPLETED |
| demo_catalog.seguros_demo.bronze_clientes | 60020 | COMPLETED |
| demo_catalog.seguros_demo.bronze_conductores | 111715 | COMPLETED |
| demo_catalog.seguros_demo.bronze_cotizaciones | 280201 | COMPLETED |
| demo_catalog.seguros_demo.bronze_creditos_personales | 25010 | COMPLETED |
| demo_catalog.seguros_demo.bronze_movtos_siniestro | 111515 | COMPLETED |
| demo_catalog.seguros_demo.bronze_poliza_coberturas | 725845 | COMPLETED |
| demo_catalog.seguros_demo.bronze_polizas | 100025 | COMPLETED |
| demo_catalog.seguros_demo.bronze_productos | 6 | COMPLETED |
| demo_catalog.seguros_demo.bronze_recibos | 458099 | COMPLETED |
| demo_catalog.seguros_demo.bronze_siniestros | 27674 | COMPLETED |
| demo_catalog.seguros_demo.bronze_talleres | 400 | COMPLETED |
| demo_catalog.seguros_demo.bronze_terceros_siniestro | 18609 | COMPLETED |
| demo_catalog.seguros_demo.bronze_valuaciones | 23813 | COMPLETED |
| demo_catalog.seguros_demo.bronze_vehiculos | 100000 | COMPLETED |
| demo_catalog.seguros_demo.cuarentena_registros | 748 | COMPLETED |
| demo_catalog.seguros_demo.dim_agente | 600 | COMPLETED |
| demo_catalog.seguros_demo.dim_cliente | 60000 | COMPLETED |
| demo_catalog.seguros_demo.dim_fecha | 2191 | COMPLETED |
| demo_catalog.seguros_demo.dim_producto | 6 | COMPLETED |
| demo_catalog.seguros_demo.dim_taller | 400 | COMPLETED |
| demo_catalog.seguros_demo.dim_vehiculo | 100000 | COMPLETED |
| demo_catalog.seguros_demo.fact_cotizaciones | 280201 | COMPLETED |
| demo_catalog.seguros_demo.fact_movtos_siniestro | 110870 | COMPLETED |
| demo_catalog.seguros_demo.fact_polizas | 100000 | COMPLETED |
| demo_catalog.seguros_demo.fact_siniestros | 27644 | COMPLETED |
| demo_catalog.seguros_demo.fact_telemetria_mensual | 128930 | COMPLETED |
| demo_catalog.seguros_demo.silver_agentes | 600 | COMPLETED |
| demo_catalog.seguros_demo.silver_app_fnol | 0 | RUNNING |
| demo_catalog.seguros_demo.silver_app_trip_summary | 0 | RUNNING |
| demo_catalog.seguros_demo.silver_clientes | 60000 | COMPLETED |
| demo_catalog.seguros_demo.silver_conductores | 111715 | COMPLETED |
| demo_catalog.seguros_demo.silver_cotizaciones | 280201 | COMPLETED |
| demo_catalog.seguros_demo.silver_creditos_personales | 25000 | COMPLETED |

_50 rows, first 40 shown_

## Data-quality expectations (latest update): passed vs failed records per rule

```sql
WITH last AS (SELECT origin.update_id u FROM event_log('<UUID>') WHERE event_type='create_update' ORDER BY timestamp DESC LIMIT 1),
exp AS (
  SELECT origin.flow_name flow, explode(from_json(details:flow_progress.data_quality.expectations,
         'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) e
  FROM event_log('<UUID>'), last
  WHERE event_type='flow_progress' AND origin.update_id = last.u AND details:flow_progress.data_quality.expectations IS NOT NULL)
SELECT e.dataset, e.name AS expectation, sum(e.passed_records) passed, sum(e.failed_records) failed
FROM exp GROUP BY 1,2 HAVING sum(e.failed_records) > 0 OR e.dataset LIKE '%siniestros%' ORDER BY failed DESC
```

| dataset | expectation | passed | failed |
|---|---|---|---|
| demo_catalog.seguros_demo.silver_valuaciones | presupuesto_razonable | 21205 | 2608 |
| demo_catalog.seguros_demo.silver_movtos_siniestro | pago_positivo | 110947 | 568 |
| demo_catalog.seguros_demo.silver_cotizaciones | edad_conductor_rng | 279907 | 294 |
| demo_catalog.seguros_demo.silver_movtos_siniestro | recuperacion_neg | 111438 | 77 |
| demo_catalog.seguros_demo.silver_clientes | curp_formato | 60012 | 8 |
| demo_catalog.seguros_demo.silver_polizas | vigencia_coherente | 100017 | 8 |
| demo_catalog.seguros_demo.silver_siniestros | cobertura_valida | 27668 | 6 |
| demo_catalog.seguros_demo.silver_polizas | prima_positiva | 100019 | 6 |
| demo_catalog.seguros_demo.silver_siniestros | estatus_valido | 27669 | 5 |
| demo_catalog.seguros_demo.silver_siniestros | reporte_post_ocurr | 27669 | 5 |
| demo_catalog.seguros_demo.silver_siniestros | monto_no_negativo | 27669 | 5 |
| demo_catalog.seguros_demo.silver_clientes | edad_valida | 60015 | 5 |
| demo_catalog.seguros_demo.silver_polizas | estatus_valido | 100020 | 5 |
| demo_catalog.seguros_demo.fact_siniestros | ocurrencia_en_vigencia | 27644 | 5 |
| demo_catalog.seguros_demo.fact_siniestros | fk_poliza_existe | 27644 | 5 |
| demo_catalog.seguros_demo.fact_siniestros | monto_vs_suma | 27644 | 5 |
| demo_catalog.seguros_demo.silver_siniestros | ocurrencia_no_futura | 27670 | 4 |
| demo_catalog.seguros_demo.silver_creditos_personales | monto_positivo | 25006 | 4 |
| demo_catalog.seguros_demo.silver_recibos | estatus_valido | 458095 | 4 |
| demo_catalog.seguros_demo.silver_clientes | genero_valido | 60016 | 4 |
| demo_catalog.seguros_demo.silver_recibos | pagado_con_fecha | 458095 | 4 |
| demo_catalog.seguros_demo.silver_creditos_personales | estatus_valido | 25007 | 3 |
| demo_catalog.seguros_demo.silver_polizas | forma_pago_valida | 100022 | 3 |
| demo_catalog.seguros_demo.silver_creditos_personales | saldo_no_neg | 25007 | 3 |
| demo_catalog.seguros_demo.silver_clientes | rfc_formato | 60017 | 3 |
| demo_catalog.seguros_demo.silver_polizas | emision_no_futura | 100022 | 3 |
| demo_catalog.seguros_demo.silver_creditos_personales | dpd_coherente | 25007 | 3 |
| demo_catalog.seguros_demo.silver_recibos | importe_positivo | 458097 | 2 |
| demo_catalog.seguros_demo.silver_siniestros | cerrado_con_fecha | 27674 | 0 |
| demo_catalog.seguros_demo.silver_siniestros | pk_siniestro | 27674 | 0 |
| demo_catalog.seguros_demo.fact_siniestros | incurrido_no_neg | 27649 | 0 |
| demo_catalog.seguros_demo.fact_siniestros | pk_siniestro | 27649 | 0 |

## Quarantine: records held back, by target table and failed rule (nothing is lost)

```sql
SELECT tabla_destino, reglas_fallidas, count(*) registros
FROM demo_catalog.seguros_demo.cuarentena_registros GROUP BY ALL ORDER BY registros DESC
```

| tabla_destino | reglas_fallidas | registros |
|---|---|---|
| silver_movtos_siniestro | ["pago_positivo"] | 568 |
| silver_movtos_siniestro | ["recuperacion_neg"] | 77 |
| silver_clientes | ["curp_formato"] | 8 |
| silver_polizas | ["vigencia_coherente"] | 8 |
| silver_polizas | ["prima_positiva"] | 6 |
| silver_siniestros | ["cobertura_valida"] | 6 |
| silver_clientes | ["edad_valida"] | 5 |
| silver_polizas | ["estatus_valido"] | 5 |
| silver_siniestros | ["monto_no_negativo"] | 5 |
| silver_siniestros | ["reporte_post_ocurr"] | 5 |
| silver_siniestros | ["estatus_valido"] | 5 |
| fact_siniestros | ["fk_poliza_existe"] | 5 |
| silver_clientes | ["genero_valido"] | 4 |
| silver_recibos | ["estatus_valido"] | 4 |
| silver_recibos | ["pagado_con_fecha"] | 4 |
| silver_siniestros | ["ocurrencia_no_futura"] | 4 |
| silver_creditos_personales | ["monto_positivo"] | 4 |
| silver_app_fnol | ["gps_en_mexico"] | 4 |
| silver_clientes | ["rfc_formato"] | 3 |
| silver_polizas | ["forma_pago_valida"] | 3 |
| silver_polizas | ["emision_no_futura"] | 3 |
| silver_creditos_personales | ["saldo_no_neg"] | 3 |
| silver_creditos_personales | ["estatus_valido"] | 3 |
| silver_recibos | ["importe_positivo"] | 2 |
| silver_app_fnol | ["fotos_no_negativas"] | 2 |
| silver_app_fnol | ["siniestro_presente"] | 2 |

## Row counts across the medallion (bronze → silver → gold)

```sql
SELECT 'bronze_siniestros' t, count(*) n FROM demo_catalog.seguros_demo.bronze_siniestros UNION ALL
SELECT 'silver_siniestros', count(*) FROM demo_catalog.seguros_demo.silver_siniestros UNION ALL
SELECT 'fact_siniestros (gold)', count(*) FROM demo_catalog.seguros_demo.fact_siniestros UNION ALL
SELECT 'bronze_polizas', count(*) FROM demo_catalog.seguros_demo.bronze_polizas UNION ALL
SELECT 'fact_polizas (gold)', count(*) FROM demo_catalog.seguros_demo.fact_polizas UNION ALL
SELECT 'bronze_app_trip_summary (Auto Loader)', count(*) FROM demo_catalog.seguros_demo.bronze_app_trip_summary UNION ALL
SELECT 'bronze_app_fnol (Auto Loader)', count(*) FROM demo_catalog.seguros_demo.bronze_app_fnol UNION ALL
SELECT 'act_triangulo (actuarial)', count(*) FROM demo_catalog.seguros_demo.act_triangulo
```

| t | n |
|---|---|
| silver_siniestros | 27649 |
| fact_siniestros (gold) | 27644 |
| fact_polizas (gold) | 100000 |
| bronze_siniestros | 27674 |
| bronze_polizas | 100025 |
| bronze_app_trip_summary (Auto Loader) | 128930 |
| bronze_app_fnol (Auto Loader) | 7094 |
| act_triangulo (actuarial) | 180 |

## Federated sources read in place (Lakehouse Federation, no copy)

```sql
SELECT 'DWH clients (Oracle proxy)' fuente, count(*) n FROM seguros_dwh_onprem.seguros_dwh.tb_clientes UNION ALL
SELECT 'Personal loans (AWS proxy)', count(*) FROM seguros_creditos_aws.seguros_creditos.creditos_personales UNION ALL
SELECT 'Cross-system: clients with policy AND loan', count(*) FROM seguros_dwh_onprem.seguros_dwh.tb_clientes c
  JOIN seguros_creditos_aws.seguros_creditos.creditos_personales k ON upper(k.customer_rfc) = c.rfc
```

| fuente | n |
|---|---|
| DWH clients (Oracle proxy) | 60020 |
| Personal loans (AWS proxy) | 25010 |
| Cross-system: clients with policy AND loan | 14963 |
