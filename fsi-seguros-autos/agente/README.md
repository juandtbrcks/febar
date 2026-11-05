# FSI — Agente Investigador SIU (LangGraph + model service de Unity Catalog)

**App:** `seguros-agente-siu` → https://<APP_URL> (SP <UUID>; recreada 2026-11-04, la anterior `seguros-agente-siu` fue borrada)
**Código:** `app/` (subido a `/Workspace/Users/<tu_usuario>/seguros_demo/agente/app`) — `databricks apps deploy seguros-agente-siu --source-code-path <ruta>`.

| Pieza | Detalle |
|---|---|
| LLM | Model service UC `demo_catalog.seguros_ml.model_service_demo_agente` (→ `databricks-gemini-3-8-flash`), vía AI Gateway `/ai-gateway/mlflow/v1` (API OpenAI). Inference table `model_service_demo_agente_payload`. |
| Grafo | LangGraph: `modelo` ⇄ `herramientas`; `abrir_caso_investigacion` hace `interrupt()` (human-in-the-loop) y solo escribe si se aprueba. Checkpointer en memoria por sesión. |
| Herramientas | Funciones UC en `demo_catalog.seguros_ml` (`agente/01_funciones_agente.sql`): `agente_bandeja_siu`, `agente_detalle_siniestro`, `agente_evidencia_documental`, `agente_historial_cliente`, `agente_perfil_taller`. Escritura: tabla `casos_investigacion`. |
| Identidad | Herramientas con el token del **usuario** (on-behalf-of, scope `sql`) → ABAC por rol/región/PII. LLM y tracing con el **service principal** de la app (EXECUTE en el model service, CAN_EDIT en el experimento). |
| Observabilidad | MLflow Tracing → experimento `/Users/<tu_usuario>/seguros_agente_siu`. |

## Gotchas
- Gemini 3.8 Flash **no acepta `temperature`**.
- Gemini devuelve `thoughtSignature` en tool calls y `content` como lista de partes → los mensajes se guardan crudos (dicts) y se reenvían tal cual; `texto()` extrae el texto visible.
- Mientras hay una aprobación pendiente la app bloquea el chat (un mensaje nuevo saltaría el `interrupt`).

## Guion (4 min)
1. Bandeja SIU (izquierda) — mismos scores del modelo + ⚠️ si el PDF del taller tiene inconsistencias.
2. "Investiga S202600000146" → el agente llama 4 herramientas en paralelo y entrega dictamen (VIN distinto, +44 % en presupuesto, tercero recurrente; atenuantes).
3. "Sí, abre un caso" → tarjeta de aprobación → Aprobar → caso en `casos_investigacion` con quién lo aprobó.
4. Gobierno: cambiar rol a AGENTE_REGIONAL Norte (`gobierno/03_demo_personas.sql`) → recargar: el agente solo ve el Norte y la PII sale enmascarada, sin cambiar una línea del agente.
5. Model service: cambiar el ruteo a otro modelo (p. ej. Claude) desde Unity Catalog sin redesplegar; mostrar traces en MLflow y la inference table.

## Evaluación y monitoreo con MLflow (`eval/`)
- **`01_evaluacion_agente`** (notebook): dataset de evaluación en UC `demo_catalog.seguros_ml.eval_agente_siu` (10 casos con `expected_facts` y `expected_tools`,
  incluye casos difíciles: siniestro inexistente, pedir CURP/teléfono, fuera de alcance, abrir caso) → `mlflow.genai.evaluate` con:
  - Integrados: `Correctness` (vs hechos esperados), `RelevanceToQuery`, `Safety`.
  - **Jueces de negocio (Claude Sonnet 4.6 califica a Gemini):**
    - `fundamentacion_dictamen` — juez sobre el **trace completo**: ¿cada cifra/nombre de la respuesta sale de las salidas de las herramientas? (anti-alucinación).
    - `criterio_siu` — lineamientos del SIU: estructura del dictamen, preliminar/decisión del investigador, no reconstruir PII enmascarada, no abrir casos sin aprobación, declinar fuera de alcance.
  - Código: `herramientas_esperadas` (¿usó las herramientas correctas?, leyendo los spans TOOL).
- **Resultados (v3):** fundamentación 10/10 · criterio SIU 10/10 · correctness 100 % · herramientas 100 % · safety 100 % · relevancia 80 %
  (los 2 "no" son negativas correctas — clima y CURP — que el juez genérico castiga; por eso el juez de negocio).
- **Iteración del juez (contar en el demo — "evaluar al evaluador"):** v1 `criterio_siu` 7/10 → las 3 fallas eran del juez (exigía dictamen en listas
  y en siniestros sin datos; castigaba mostrar RFC que la herramienta sí devolvió) → instrucciones afinadas → v3 10/10. Siguiente paso real:
  alinear el juez con etiquetas humanas del SIU (MLflow judge alignment).
- **`02_monitoreo_produccion`** (notebook): registra `fundamentacion_dictamen`, `criterio_siu`, `relevancia`, `seguridad` en el experimento con muestreo 100 %
  y filtro `tags.origen = 'app'` → califican automáticamente cada trace nuevo de la app (no las corridas de evaluación, `origen = eval`).
- **App:** cada respuesta es un trace con usuario y sesión (`mlflow.trace.user` / `mlflow.trace.session`); 👍/👎 → `satisfaccion_investigador` (feedback HUMAN).
- Dónde verlo: experimento `/Users/<tu_usuario>/seguros_agente_siu` → Evaluations (comparar v1/v2/v3) y Traces (jueces de producción + feedback).
- Conocido: 1 `SCORER_ERROR` esporádico del juez de trace en el caso con aprobación pendiente (v2), no se repitió en v3.
