# Seguros de Autos en Databricks — Una sola fuente de verdad gobernada (demo FSI)

Demo de punta a punta para un **cliente del sector financiero (aseguradora, ramo Autos, México)** construido en
**Databricks on Azure**. Muestra cómo pasar de un DWH legacy con muchas copias y extractos a **una sola fuente de verdad
gobernada**: los datos no se copian, se vuelven confiables, nada se pierde, y el negocio, la actuaría, la IA y los
agentes consumen los mismos números con el gobierno viajando con el dato a cada usuario.

> **Todo es sintético.** El nombre del cliente, los datos y los volúmenes son ficticios (generados con `generate_data.py`, seed fijo).
> Los identificadores del workspace se reemplazaron por placeholders (`<WAREHOUSE_ID>`, `<tu_usuario>`, …).
> English version: [README_en.md](README_en.md)

![Arquitectura](diagrama/arquitectura.png)

---

## Qué incluye

| Capa | Capacidad de Databricks | Carpeta / archivo |
|---|---|---|
| **Fuentes** | DWH "Oracle on-prem" y BD de créditos "AWS" simulados en PostgreSQL; telemetría JSON de la app; PDFs de presupuestos | `generate_data.py`, `ddl_dwh.sql`, `ddl_creditos.sql`, `load_pg.py`, `inyectar_sucios_pg.py`, `documentos/generar_presupuestos.py` |
| **Ingesta sin copiar** | Lakehouse Federation (2 foreign catalogs) + Auto Loader sobre Volumes | `federacion/01_conexiones_federacion.sql`, `pipeline1_bronze_silver.sql` |
| **Medallion** | Lakeflow Declarative Pipeline: Bronce → Plata (expectations FAIL/DROP/WARN) → Oro (modelo estrella) + **cuarentena** + **actuarial** (triángulos chain-ladder, IBNR) | `pipeline1_bronze_silver.sql`, `pipeline2_star.sql`, `pipeline3_cuarentena.sql` (generado por `gen_cuarentena.py`), `actuarial/`, `workspace_export/pipeline_medallion.json` |
| **Gobierno "sin extractos"** | Governed tags (PII, región, certificación), políticas **ABAC** (masking + row filters), sandbox de ciencia de datos, auditoría y linaje | `gobierno/01..05_*.sql`, `gobierno/README.md` |
| **IA sobre documentos** | `ai_parse_document` + `ai_query` (Claude) con `responseFormat` JSON schema → validación de presupuestos de taller | `documentos/01_extraccion_presupuestos.sql` |
| **ML de fraude** | Feature Engineering in UC, MLflow (runs anidados, `mlflow.evaluate`, SHAP), UC Model Registry con alias **champion/challenger** y compuerta de calidad, scoring batch | `ml/01_features_entrenamiento.py`, `ml/02_scoring_batch.py`, `workspace_export/job_mlops.json` |
| **Capa semántica y BI** | 4 **metric views** (YAML v1.1), **AI/BI Dashboard** de 4 páginas con filtros globales (año, región, canal), **Genie space** | `semantica/`, `workspace_export/dashboard.lvdash.json`, `workspace_export/genie_space.json` |
| **Agente investigador de fraude (SIU)** | Databricks App (Streamlit + **LangGraph**), herramientas = funciones de UC ejecutadas **on-behalf-of** del usuario (ABAC aplica), LLM vía **model service de UC / AI Gateway**, human-in-the-loop, MLflow Tracing | `agente/01_funciones_agente.sql`, `agente/app/`, `workspace_export/app_config.json` |
| **Evaluación y monitoreo del agente** | `mlflow.genai.evaluate` con jueces LLM personalizados (`make_judge`), scorers de código, monitoreo en producción | `agente/eval/` |
| **Agent Bricks** | El mismo agente en Agent Runtime (Session Store, aprobación como 2ª invocación) | `agente/agentbricks/` |
| **Lakebase** | Postgres administrado: **synced table** (reverse ETL) de la bandeja, **expediente** del investigador (casos, notas, bitácora) con **RLS**, **memoria del agente** (checkpointer LangGraph) y **CDF Lakebase → Delta** para cerrar el ciclo (veredictos → reentrenamiento) | `lakebase/`, `agente/app/lakebase.py`, `workspace_export/lakebase_*.json` |
| **Diagrama** | Arquitectura de referencia (PNG) | `diagrama/arquitectura.png` |

## Arquitectura (resumen)

```
Fuentes (PostgreSQL: "Oracle on-prem" + "AWS", JSON app, PDFs)
   │  Lakehouse Federation (sin copiar) · Auto Loader · AI Functions
   ▼
Lakeflow Declarative Pipeline: Bronce → Plata (+cuarentena) → Oro estrella → Actuarial
   │
   ├─► Metric views ─► AI/BI Dashboard · Genie
   ├─► Feature Store + MLflow ─► Job MLOps (entrena → scoring → serving → sync Lakebase)
   └─► Funciones UC ─► App Agente SIU (LangGraph + model service UC) ─► MLflow Tracing/Evaluación
                                   │
                         Lakebase (synced table · expediente con RLS · memoria del agente)
                                   │  CDF Lakebase → Delta
                                   ▼
                         seguros_siu_expediente (veredictos) ─► reentrenamiento + Genie
Unity Catalog gobierna todo: tags, ABAC, linaje, auditoría, Discover.
```

## Requisitos

- Workspace de Databricks (probado en Azure) con Unity Catalog, serverless, Databricks Apps y Lakebase Autoscaling.
- Un servidor PostgreSQL accesible (simula las fuentes legacy).
- Databricks CLI ≥ 0.285 (`databricks postgres …`) y Python 3.10+ (`psycopg2` para `load_pg.py`).
- Un SQL warehouse (su ID va en `run_sql.py`, `semantica/build_*.py` y `app.yaml`).

## Placeholders a reemplazar

| Placeholder | Qué es |
|---|---|
| `demo_catalog` | Catálogo de UC donde vive el demo (schemas `seguros_demo`, `seguros_ml`, `seguros_gobierno`, `seguros_sandbox_ds`, `seguros_siu_expediente`) |
| `<tu_usuario>` | Tu usuario del workspace (rutas `/Workspace/Users/<tu_usuario>/…` y experimentos MLflow) |
| `<WAREHOUSE_ID>` | ID del SQL warehouse |
| `<PG_HOST>` / `<PG_SERVIDOR>` / `<PG_USER>` / `<SECRET_SCOPE>` | PostgreSQL fuente y secret scope con su contraseña |
| `<LAKEBASE_HOST>` | Host del endpoint de Lakebase (`databricks postgres list-endpoints …`) |
| `<WORKSPACE_HOST>`, `<WORKSPACE_ID>`, `<ID>`, `<UUID>` | Identificadores propios de tu workspace (dashboards, Genie, jobs, service principals) |

## Orden de despliegue

1. **Datos sintéticos** — `python3 generate_data.py` (CSV + JSON en `./data`) y `python3 documentos/generar_presupuestos.py` (PDFs).
2. **Fuentes legacy** — `PGPASSWORD=… python3 load_pg.py` (crea `dwh_seguros` y `creditos_aws`). Opcional: `inyectar_sucios_pg.py` (registros sucios para la cuarentena).
3. **Federación** — `federacion/01_conexiones_federacion.sql`.
4. **Volumes** — sube `data/telemetria/*` a `/Volumes/demo_catalog/seguros_demo/datalake_ds/app_autos/` y los PDFs a `documentos_siniestros/presupuestos/`.
5. **Pipeline** — importa `pipeline1/2/3_*.sql` como notebooks y crea el pipeline con `workspace_export/pipeline_medallion.json` (serverless). Corre un full refresh.
6. **Gobierno** — `gobierno/01_roles_funciones.sql` → `02_tags_politicas.sql` → (`04_permisos.sql` es plantilla) → `03_demo_personas.sql` para cambiar de rol en vivo. Ver `gobierno/README.md`.
7. **IA sobre documentos** — `documentos/01_extraccion_presupuestos.sql`.
8. **ML** — importa `ml/*.py` como notebooks y crea el job con `workspace_export/job_mlops.json` (cluster ML single-user).
9. **Capa semántica** — `semantica/metric_views.sql` (+ `reaplicar_tags_mv.sql`), `python3 semantica/build_dashboard.py`, `python3 semantica/build_genie.py`. La versión final del dashboard (con filtros globales) es `workspace_export/dashboard.lvdash.json` — impórtala; `build_dashboard.py` genera la versión base sin filtros.
10. **Agente** — `agente/01_funciones_agente.sql`; despliega `agente/app/` como Databricks App (recursos: SQL warehouse + Lakebase; scope de usuario `sql`); otorga al service principal EXECUTE sobre el model service y CAN_EDIT sobre el experimento. Evaluación: `agente/eval/`. Variante Agent Bricks: `agente/agentbricks/README.md`.
11. **Lakebase** — sigue `lakebase/README.md`: proyecto + base `siu`, `01_serving_bandeja.sql`, synced table, `02_ddl_operativo.sql`, `03_vistas_permisos.sql`, `04_sembrar_historial.py`, CDF config y `05_vistas_expediente_uc.sql`.

## Guion sugerido (≈ 45–60 min)

1. **El problema**: muchas copias, extractos y números distintos por área.
2. **Sin copiar**: Lakehouse Federation; join entre "on-prem" y "AWS" en una consulta.
3. **Confiable**: expectations y cuarentena ("nada se pierde"); oro certificado.
4. **Gobierno en vivo**: misma consulta, tres roles (investigador, actuario, agente regional) → PII y regiones distintas, sin cambiar el código.
5. **Negocio**: dashboard y Genie sobre metric views (una sola definición de siniestralidad, IBNR, conversión).
6. **IA**: modelo de fraude con champion/challenger; PDFs leídos con IA.
7. **Agente**: investiga un siniestro, propone abrir un caso, el humano aprueba; traces y jueces LLM.
8. **Lakebase**: bandeja en milisegundos, notas del investigador, la aprobación sobrevive a cerrar la app, los veredictos regresan como etiquetas.

## Notas y gotchas

- Las métricas del modelo (PR-AUC alto) se deben a que los datos son sintéticos — dilo en el demo.
- El historial del SIU en Lakebase (`04_sembrar_historial.py`) es sintético; los veredictos se sortean con la probabilidad del modelo.
- ABAC: las tablas con políticas leídas desde cómputo dedicado bloquean self-joins → `spark.databricks.remoteFiltering.blockSelfJoins=false`.
- Lakebase CDF requiere `REPLICA IDENTITY FULL`; las tablas omitidas al crear el config no se re-evalúan (recrear el config).
- El owner de las tablas en Postgres se salta el RLS: prueba con un rol sin privilegios (`SET LOCAL ROLE …`).
- Más detalle en los README de cada carpeta (`gobierno/`, `actuarial/`, `agente/`, `lakebase/`, `demo_en_vivo/`).
