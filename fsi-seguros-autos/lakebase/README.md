# FSI SIU — Expediente operativo en Lakebase

**Lakebase Autoscaling** proyecto `seguros-siu` (PG 17, 0.5–2 CU) · base `siu` · endpoint `<LAKEBASE_HOST>`
Catálogo UC: `seguros_siu_lakebase` (la base `siu` registrada en Unity Catalog). App: `seguros-agente-siu` (recurso Lakebase `lakebase`, SP de la app).

```
 LAKEHOUSE (Delta, ABAC)                         LAKEBASE (Postgres, RLS)                        APP seguros-agente-siu
 scoring_fraude_siniestros ─┐
 docs_validacion_presup. ───┴─► bandeja_siu_serving ══ synced table ══► serving.bandeja_siu ─► app.bandeja (por región) ─► Bandeja SIU (ms)
     (job ML: scoring → MERGE → sync)      (CDF, sin PII)  (TRIGGERED)
                                                                          siu.casos / siu.notas / ◄── notas, estatus, casos
                                                                          siu.historial_estatus       aprobados en el agente
                                                                          agente.checkpoints*  ◄────── memoria LangGraph
 seguros_siu_expediente.lb_*_history ◄══ CDF Lakebase→Delta (Beta) ══════ siu.*                       + agente.sesiones
   └► vistas casos / notas / historial_estatus / etiquetas_siu ─► reentrenamiento (etiquetas) · Genie
```

## Piezas
| # | Qué | Dónde |
|---|---|---|
| 1 | **Reverse ETL**: bandeja sin PII, Delta con CDF → synced table TRIGGERED (pipeline `<UUID>`) | `01_serving_bandeja.sql` · tareas `serving_bandeja_siu` + `sync_lakebase_bandeja` del job `seguros_fraude_siniestros_mlops` |
| 2 | **Expediente SIU**: casos (4 estatus, veredicto, asignado), notas, bitácora de estatus por trigger `SECURITY DEFINER`; RLS | `02_ddl_operativo.sql`, `03_vistas_permisos.sql` |
| 3 | **Memoria del agente**: `PostgresSaver` (LangGraph) en schema `agente` (lo crea el SP con `setup()`) + `agente.sesiones` (RLS por usuario) | `agente/app/lakebase.py` |
| 4 | **Lakebase → Delta**: CDF config `siu_expediente` (schema `siu` → `demo_catalog.seguros_siu_expediente.lb_*_history`) + vistas de estado actual + `etiquetas_siu` → entrenamiento (etiquetas SIU **solo en train**; test = hold-out histórico) y Genie | `05_vistas_expediente_uc.sql`, `ml/01_features_entrenamiento.py` |

Historial sintético: `04_sembrar_historial.py` (160 casos, 383 notas, 89 veredictos, investigadores ficticios `@siu.seguros-demo.mx`; veredicto ~ prob. del modelo + ruido → **decirlo en el demo**). Deja libre `S202600000146` y ~70 siniestros Alto sin caso.

## Gobierno (cómo se aplican los roles en Postgres)
- Identidad/rol/región vienen de **Unity Catalog** (`rol_actual()`, `region_actual()` vía OBO). La app abre cada transacción con `SET LOCAL app_ctx.usuario/rol/region` y **Postgres RLS** las hace cumplir:
  - ver bandeja/casos/notas → solo la región del usuario (`'*'` = todas; sin contexto = **0 filas**).
  - abrir y cambiar estatus de casos → solo rol `SIU`. Notas → en tu región y firmadas con tu propio usuario (nadie firma por otro).
  - la app **no** tiene INSERT en `historial_estatus` (solo lo escribe el trigger); su SELECT es sobre la vista `app.bandeja`, no sobre la synced table.
- GOTCHA: el **owner se salta el RLS** → para probar como owner usar `SET LOCAL ROLE rls_tester` (rol NOLOGIN con los permisos de la app).
- La bandeja **no lleva PII**: a la capa operativa solo baja lo necesario (minimización). La PII sigue en el lakehouse bajo ABAC.

## Guion (≈5 min, después del guion del agente)
1. **Bandeja en ms**: "⚡ Leída de Lakebase en X ms" vs el warehouse en frío. Mismos scores del modelo, sincronizados por el job MLOps.
2. **Notas**: elegir un siniestro → *Expediente* → agregar una nota. Pedir al agente "Investiga …" → llama `expediente_siu` y **cita la nota del investigador** en el dictamen.
3. **Caso + memoria**: "Sí, abre un caso" → tarjeta de aprobación → **cerrar la pestaña** → volver a abrir → *Mis investigaciones* → ✋ la aprobación sigue pendiente (checkpointer en Lakebase) → Aprobar → caso en `siu.casos` con bitácora.
4. **Flujo de trabajo**: pestaña *Casos* → En investigación → Cerrado - Fraude confirmado (bitácora por trigger). Cambiar rol a AGENTE_REGIONAL Norte → solo ve Norte, el botón Guardar queda bloqueado y Postgres lo rechaza (RLS).
5. **Ciclo**: en UC `demo_catalog.seguros_siu_expediente.casos` aparece el cambio en segundos (CDF, sin ETL) → Genie: "¿Qué tanto confirma el SIU los siniestros que el modelo marca como riesgo alto?" → el job MLOps reentrena con `etiquetas_siu` (param `etiquetas_siu_lakebase` en MLflow).

## Operación
- `./pg.sh` = psql con tu identidad OAuth. `./pg.sh -c "SELECT …"`.
- Regenerar historial: `python3 04_sembrar_historial.py > /tmp/s.sql && ./pg.sh -q -f /tmp/s.sql`.
- CDF: `databricks postgres list-cdf-statuses projects/seguros-siu/branches/production/databases/siu/cdf-configs/siu_expediente -p DEFAULT`.
  GOTCHA: requiere **REPLICA IDENTITY FULL**; las tablas que quedaron SKIPPED al crear el config NO se re-evalúan → borrar y recrear el config.
- Sync manual: `databricks pipelines start-update <UUID> -p DEFAULT`.
- La tabla de serving se refresca con **MERGE** (no CREATE OR REPLACE) para conservar el CDF y el sync incremental.
