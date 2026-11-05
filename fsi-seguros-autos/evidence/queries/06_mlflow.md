# Evidence · MLflow model registry, training runs and agent evaluation

_Captured 2026-11-05 13:51 CST from the live workspace (REST APIs). Values are the real API output._

Fraud model versions in Unity Catalog, the champion/challenger gate, training metrics, and the SIU agent's evaluation and traces.

## Registered model versions (Unity Catalog)

Model `demo_catalog.seguros_ml.modelo_fraude_siniestros` · aliases: champion = v2, challenger = v5

| version | alias | created | status | test PR-AUC | test ROC-AUC | family | SIU labels used |
|---|---|---|---|---|---|---|---|
| 1 |  | 2026-10-15 15:54 | READY | 0.758 | 0.971 | xgboost |  |
| 2 | champion | 2026-10-15 16:35 | READY | 0.758 | 0.971 | xgboost |  |
| 3 |  | 2026-10-15 17:07 | READY | 0.735 | 0.966 | xgboost |  |
| 4 |  | 2026-10-15 17:15 | READY | 0.735 | 0.966 | xgboost |  |
| 5 | challenger | 2026-11-04 18:33 | READY | 0.737 | 0.968 | xgboost | 89 |

## Model selection (nested MLflow runs, latest training)

Parent run `seleccion_modelo_fraude` started 2026-11-04 18:32 · 12 candidate models

| run | family | valid PR-AUC | valid ROC-AUC | fraud captured @10% |
|---|---|---|---|---|
| xgboost_05 | xgboost | 0.74 | 0.973 | 88.8% |
| xgboost_04 | xgboost | 0.74 | 0.971 | 85.8% |
| xgboost_08 | xgboost | 0.739 | 0.973 | 88.8% |
| xgboost_06 | xgboost | 0.737 | 0.97 | 88.8% |
| xgboost_10 | xgboost | 0.735 | 0.97 | 88.8% |
| xgboost_02 | xgboost | 0.729 | 0.974 | 89.3% |
| xgboost_03 | xgboost | 0.724 | 0.974 | 89.9% |
| xgboost_09 | xgboost | 0.722 | 0.973 | 89.3% |
| random_forest_01 | random_forest | 0.71 | 0.974 | 87.6% |
| xgboost_11 | xgboost | 0.708 | 0.973 | 89.3% |
| xgboost_07 | xgboost | 0.703 | 0.975 | 89.3% |
| logistic_regression_00 | logistic_regression | 0.612 | 0.949 | 75.1% |

## SIU agent evaluation runs (mlflow.genai.evaluate)

| run | started | aggregate metrics |
|---|---|---|
| eval_agente_siu_gemini-3-8-flash_v3 | 2026-10-18 19:32 | {"correctness/mean": 1, "herramientas_esperadas/mean": 1, "relevance_to_query/mean": 0.8, "safety/mean": 1} |
| eval_agente_siu_gemini-3-8-flash_v2 | 2026-10-18 19:27 | {"correctness/mean": 1, "herramientas_esperadas/mean": 1, "relevance_to_query/mean": 0.9, "safety/mean": 1} |
| eval_agente_siu_gemini-3-8-flash | 2026-10-18 19:23 | {"correctness/mean": 1, "herramientas_esperadas/mean": 1, "relevance_to_query/mean": 1, "safety/mean": 1} |

## Latest SIU agent traces (MLflow Tracing): request, response preview and assessments

- **2026-11-05T17:43:33.445Z** · origin=`app` · state=OK · duration=9.264s
  - request: `{"pregunta": "¿Qué 5 siniestros debo revisar primero en la región Centro?"}`
  - response: "A continuación le presento los 5 siniestros abiertos con mayor prioridad de revisión por probabilidad de fraude en la **Región Centro**:\n\n---\n\n### **1. Siniestro: S202600022559**\n- **Cobertura:** Responsabilidad Civil\n- **Estado de ocurrencia:** Ciudad de México\n- **Monto reclamado:** $87,214.09 MXN\n- **Probabilidad de fraude:** **99.93%** (Riesgo Alto)\n- **Alertas principales:** Terceros involucrados que figuran en otros siniestros, reporte tardío y pocas fotografías en el reporte de 
  - assessments: (none)
- **2026-11-05T17:43:18.218Z** · origin=`app` · state=OK · duration=12.123s
  - request: `{"pregunta": "¿Qué 5 siniestros debo revisar primero en la región Centro?"}`
  - response: "A continuación le presento los 5 siniestros abiertos con mayor probabilidad de fraude identificados por el modelo en la **Región Centro**, ordenados por nivel de riesgo:\n\n---\n\n### **1. Siniestro: S202600022559**\n- **Cobertura:** Responsabilidad Civil\n- **Estado:** Ciudad de México\n- **Monto Reclamado:** $87,214.09 MXN\n- **Probabilidad de Fraude:** **99.93%** (Riesgo Alto)\n- **Principales Señales:**\n  - Reporte tardío del siniestro.\n  - Terceros involucrados que figuran en otros sinie
  - assessments: (none)
- **2026-10-19T23:11:17.132Z** · origin=`app` · state=OK · duration=12.919s
  - request: `{"pregunta": "¿Qué 5 siniestros debo revisar primero en la región Centro?"}`
  - response: "De acuerdo con el modelo de detección de fraude del SIU, estos son los **5 siniestros prioritarios** para revisión en la **Región Centro**:\n\n---\n\n### 1. Siniestro `S202600022559`\n* **Cobertura:** Responsabilidad Civil\n* **Ubicación:** Ciudad de México\n* **Monto Reclamado:** $87,214.09 MXN\n* **Probabilidad de Fraude:** **99.93%** (Riesgo Alto)\n* **Principales Alertas:** Reporte tardío, terceros involucrados que aparecen recurrentemente en otros siniestros y escasez de fotografías en el 
  - assessments: criterio_siu="cumple"; relevancia="yes"; fundamentacion_dictamen="fundamentado"; seguridad="yes"
- **2026-10-19T20:13:48.616Z** · origin=`prueba` · state=OK · duration=4.230s
  - request: `{"pregunta": "Sí, abre un caso de investigación para este siniestro."}`
  - response: "[PENDIENTE DE APROBACIÓN DEL INVESTIGADOR: abrir caso {\"prioridad\": \"Alta\", \"recomendacion\": \"Realizar inspección física para cotejo de VIN en chasis, auditar presupuesto del taller por discrepancia de +44.2%, investigar posible colusión con tercero recurrente y validar registro meteorológico oficial del evento de inundación.\", \"num_siniestro\": \"S202600000146\", \"monto_en_riesgo\": 180374.33, \"resumen\": \"Siniestro por inundación con 94.63% de probabilidad de fraude. Presenta inco
  - assessments: (none)
- **2026-10-19T20:13:27.992Z** · origin=`prueba` · state=OK · duration=20.623s
  - request: `{"pregunta": "Investiga el siniestro S202600000146"}`
  - response: "### **DICTAMEN PRELIMINAR DE INVESTIGACIÓN SIU**\n**Siniestro:** `S202600000146`  \n**Vehículo:** Volkswagen Vento 2014  \n**Asegurado:** Alberto Ramírez Navarro (RFC: `RANA8912267R1`)  \n**Taller:** Carrocerías Jiménez Express (Puebla)\n\n---\n\n### **1. Resumen**\nSiniestro reportado por causa de **inundación** en el estado de Puebla con un monto reclamado de **$120,452.79 MXN** (74.45% del valor comercial del vehículo). El modelo de detección asigna una **probabilidad de fraude de 94.63% (Ni
  - assessments: (none)
- **2026-10-19T20:05:12.899Z** · origin=`app` · state=ERROR · duration=1.512s
  - request: `{"pregunta": "Investiga el siniestro S202600000146"}`
  - response: 
  - assessments: criterio_siu="no_cumple"; seguridad="yes"; fundamentacion_dictamen="fundamentado"; relevancia="no"
