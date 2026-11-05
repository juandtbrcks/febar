# Evidence · ML fraud model and scoring

_Captured 2026-11-05 13:45 CST from the live Databricks workspace via the SQL Statement Execution API. Results below are the actual query output._

Feature table, batch scoring with SHAP reasons, and SIU verdicts used as labels.

## Feature table (Feature Engineering in Unity Catalog)

```sql
SELECT count(*) siniestros, count(DISTINCT id_siniestro) llaves_unicas FROM demo_catalog.seguros_ml.features_fraude_siniestro
```

| siniestros | llaves_unicas |
|---|---|
| 36726 | 36726 |

## Batch scoring of open claims by risk tier

```sql
SELECT nivel_riesgo, count(*) siniestros, round(avg(prob_fraude),3) prob_media, round(sum(monto_reclamado)/1e6,2) mxn_m_reclamado,
       round(sum(monto_en_riesgo)/1e6,2) mxn_m_en_riesgo, max(modelo_version) modelo_version, max(fecha_scoring) fecha_scoring
FROM demo_catalog.seguros_ml.scoring_fraude_siniestros GROUP BY 1 ORDER BY prob_media DESC
```

| nivel_riesgo | siniestros | prob_media | mxn_m_reclamado | mxn_m_en_riesgo | modelo_version | fecha_scoring |
|---|---|---|---|---|---|---|
| Alto | 167 | 0.494 | 14.35 | 6.75 | 2 | 2026-11-04T19:34:07.619-05:00 |
| Medio | 410 | 0.013 | 26.67 | 0.38 | 2 | 2026-11-04T19:34:07.619-05:00 |
| Bajo | 3145 | 0.0 | 118.37 | 0.06 | 2 | 2026-11-04T19:34:07.619-05:00 |

## Top 5 claims with the model's SHAP reasons (real model output)

```sql
SELECT num_siniestro, region, cobertura, round(prob_fraude,3) prob_fraude, nivel_riesgo, razon_1, razon_2, razon_3
FROM demo_catalog.seguros_ml.scoring_fraude_siniestros ORDER BY prob_fraude DESC LIMIT 5
```

| num_siniestro | region | cobertura | prob_fraude | nivel_riesgo | razon_1 | razon_2 | razon_3 |
|---|---|---|---|---|---|---|---|
| S202600017785 | Noroeste | Robo Total | 0.999 | Alto | Reporte tardío | Ocurrió de noche | Agente con alta siniestralidad |
| S202600005219 | Norte | Responsabilidad Civil | 0.999 | Alto | Terceros que aparecen en otros siniestros | GPS de la app lejos de la ubicación declarada | Pocas fotos en el reporte de la app |
| S202600015068 | Sureste | Robo Total | 0.999 | Alto | Reporte tardío | GPS de la app lejos de la ubicación declarada | Poco tiempo desde el inicio de vigencia |
| S202600008236 | Centro | Daños Materiales | 0.999 | Alto | Pocas fotos en el reporte de la app | Terceros que aparecen en otros siniestros | Poco tiempo desde el inicio de vigencia |
| S202600022559 | Centro | Responsabilidad Civil | 0.999 | Alto | Reporte tardío | Terceros que aparecen en otros siniestros | Pocas fotos en el reporte de la app |

## Model vs SIU verdict (human labels that flow back for retraining)

```sql
SELECT nivel_riesgo_apertura, veredicto, count(*) casos, round(avg(prob_fraude_apertura),3) prob_media
FROM demo_catalog.seguros_siu_expediente.etiquetas_siu GROUP BY ALL ORDER BY 1,2
```

| nivel_riesgo_apertura | veredicto | casos | prob_media |
|---|---|---|---|
| Alto | fraude | 21 | 0.770 |
| Alto | legitimo | 28 | 0.268 |
| Medio | fraude | 2 | 0.029 |
| Medio | legitimo | 38 | 0.018 |
