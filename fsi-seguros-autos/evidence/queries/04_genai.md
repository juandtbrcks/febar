# Evidence · Gen AI (documents, agent tools, model service)

_Captured 2026-11-05 13:46 CST from the live Databricks workspace via the SQL Statement Execution API. Results below are the actual query output._

LLM extraction from PDFs, governed agent tools and the model-service inference table.

## AI on documents: ai_parse_document + ai_query over body-shop PDFs

```sql
SELECT count(*) pdfs, sum(CASE WHEN num_inconsistencias > 0 THEN 1 ELSE 0 END) con_inconsistencias,
       sum(CAST(vin_no_coincide AS INT)) vin_no_coincide, sum(CAST(total_no_coincide AS INT)) total_alterado,
       sum(CAST(fecha_previa_siniestro AS INT)) fecha_previa
FROM demo_catalog.seguros_demo.docs_validacion_presupuestos
```

| pdfs | con_inconsistencias | vin_no_coincide | total_alterado | fecha_previa |
|---|---|---|---|---|
| 240 | 83 | 29 | 53 | 23 |

## Sample extractions (fields read by the LLM from the PDF vs system of record)

```sql
SELECT num_siniestro, nombre_taller, total_documento, total_capturado, dif_total_pct, vin_no_coincide, array_join(motivos, ' · ') motivos
FROM demo_catalog.seguros_demo.docs_validacion_presupuestos WHERE num_inconsistencias > 0 ORDER BY dif_total_pct DESC LIMIT 5
```

| num_siniestro | nombre_taller | total_documento | total_capturado | dif_total_pct | vin_no_coincide | motivos |
|---|---|---|---|---|---|---|
| S202600000146 | Carrocerías Jiménez Express | 180374.33 | 125065.76 | 0.4422 | true | Total del documento distinto al capturado · VIN distinto al vehículo asegurado |
| S202600017448 | Agencia Toyota Gustavo A. Madero | 27722.88 | 19236.67 | 0.4411 | false | Total del documento distinto al capturado |
| S202500001176 | Agencia Toyota Toluca | 117046.83 | 81548.93 | 0.4353 | false | Total del documento distinto al capturado · Documento fechado antes del siniestro |
| S202600001093 | Autocentro Romero Express | 89031.64 | 62563.31 | 0.4231 | false | Total del documento distinto al capturado |
| S202600007970 | Taller Pérez Express | 35450.33 | 24909.94 | 0.4231 | false | Total del documento distinto al capturado · Documento fechado antes del siniestro |

## Documents vs model risk tier

```sql
SELECT nivel_riesgo_modelo, count(*) pdfs, round(avg(CASE WHEN num_inconsistencias > 0 THEN 1 ELSE 0 END)*100,1) pct_con_inconsistencias
FROM demo_catalog.seguros_demo.docs_validacion_presupuestos GROUP BY 1 ORDER BY 3 DESC
```

| nivel_riesgo_modelo | pdfs | pct_con_inconsistencias |
|---|---|---|
| Alto | 70 | 68.6 |
| Cerrado | 60 | 33.3 |
| Medio | 50 | 16.0 |
| Bajo | 60 | 11.7 |

## Agent tool (UC function) called with the user's identity

```sql
SELECT num_siniestro, region, round(prob_fraude,3) prob_fraude, nivel_riesgo, razones_modelo, inconsistencias_documentales
FROM demo_catalog.seguros_ml.agente_bandeja_siu(top_n => 5)
```

| num_siniestro | region | prob_fraude | nivel_riesgo | razones_modelo | inconsistencias_documentales |
|---|---|---|---|---|---|
| S202600022559 | Centro | 0.999 | Alto | Reporte tardío · Terceros que aparecen en otros siniestros · Pocas fotos en el reporte de la app |  |
| S202600008236 | Centro | 0.999 | Alto | Pocas fotos en el reporte de la app · Terceros que aparecen en otros siniestros · Poco tiempo desde el inicio de vigencia |  |
| S202600015068 | Sureste | 0.999 | Alto | Reporte tardío · GPS de la app lejos de la ubicación declarada · Poco tiempo desde el inicio de vigencia |  |
| S202600027553 | Bajío | 0.999 | Alto | Terceros que aparecen en otros siniestros · GPS de la app lejos de la ubicación declarada · Pocas fotos en el reporte de la app |  |
| S202600017785 | Noroeste | 0.999 | Alto | Reporte tardío · Ocurrió de noche · Agente con alta siniestralidad |  |

## Model-service inference table (every LLM call is logged)

```sql
SELECT date(event_time) dia, destination_model modelo, count(*) llamadas, round(avg(latency_ms)) latencia_ms_prom,
       sum(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) ok
FROM demo_catalog.seguros_ml.model_service_demo_agente_payload GROUP BY 1, 2 ORDER BY 1 DESC LIMIT 12
```

| dia | modelo | llamadas | latencia_ms_prom | ok |
|---|---|---|---|---|
| 2026-11-05 | system.ai.databricks-gemini-3-8-flash | 4 | 4579.0 | 4 |
| 2026-10-20 | system.ai.databricks-gemini-3-8-flash | 4 | 8713.0 | 4 |
| 2026-10-19 | system.ai.databricks-gpt-6-1-sol | 25 | 2181.0 | 16 |
| 2026-10-19 | system.ai.databricks-gemini-3-8-flash | 29 | 3736.0 | 17 |
| 2026-10-18 | system.ai.databricks-gemini-3-8-flash | 80 | 3732.0 | 78 |
