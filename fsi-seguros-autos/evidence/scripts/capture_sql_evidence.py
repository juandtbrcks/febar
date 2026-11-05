"""Runs evidence queries on the SQL warehouse and writes the real results as Markdown (text, not screenshots).
Usage: python3 capture_sql_evidence.py <section> <output.md>
Sections: lakeflow, governance, ml, genai"""
import datetime, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from run_sql import run  # Statement Execution API on the demo warehouse

C = "demo_catalog"
ME = "<tu_usuario>"
PIPE = "<UUID>"


def md_table(cols, rows, limit=40):
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows[:limit]:
        out.append("| " + " | ".join("" if v is None else str(v).replace("|", "/").replace("\n", " ")[:160] for v in r) + " |")
    if len(rows) > limit:
        out.append(f"\n_{len(rows)} rows, first {limit} shown_")
    return "\n".join(out)


class Doc:
    def __init__(self, title, intro):
        ts = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
        self.parts = [f"# {title}\n", f"_Captured {ts} from the live Databricks workspace via the SQL Statement Execution API. Results below are the actual query output._\n", intro + "\n"]

    def q(self, heading, sql, note=None):
        cols, rows = run(sql)
        self.parts.append(f"## {heading}\n")
        if note:
            self.parts.append(note + "\n")
        self.parts.append("```sql\n" + sql.strip() + "\n```\n")
        self.parts.append(md_table(cols, rows) if cols else "_(statement executed, no result set)_")
        self.parts.append("")
        return rows

    def text(self, t):
        self.parts.append(t + "\n")

    def save(self, path):
        open(path, "w").write("\n".join(self.parts))
        print("wrote", path)


def lakeflow(d):
    d.q("Pipeline updates (most recent first)", f"""
SELECT origin.update_id, timestamp, details:update_progress.state AS state
FROM event_log('{PIPE}')
WHERE event_type = 'update_progress' AND details:update_progress.state IN ('COMPLETED','FAILED','RUNNING')
ORDER BY timestamp DESC LIMIT 6""")
    d.q("Rows written per table in the latest update", f"""
WITH last AS (SELECT origin.update_id u FROM event_log('{PIPE}') WHERE event_type='create_update' ORDER BY timestamp DESC LIMIT 1)
SELECT origin.flow_name AS flow,
       max(CAST(details:flow_progress.metrics.num_output_rows AS BIGINT)) AS output_rows,
       max(details:flow_progress.status) AS status
FROM event_log('{PIPE}'), last
WHERE event_type = 'flow_progress' AND origin.update_id = last.u AND details:flow_progress.metrics.num_output_rows IS NOT NULL
GROUP BY 1 ORDER BY 1""")
    d.q("Data-quality expectations (latest update): passed vs failed records per rule", f"""
WITH last AS (SELECT origin.update_id u FROM event_log('{PIPE}') WHERE event_type='create_update' ORDER BY timestamp DESC LIMIT 1),
exp AS (
  SELECT origin.flow_name flow, explode(from_json(details:flow_progress.data_quality.expectations,
         'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) e
  FROM event_log('{PIPE}'), last
  WHERE event_type='flow_progress' AND origin.update_id = last.u AND details:flow_progress.data_quality.expectations IS NOT NULL)
SELECT e.dataset, e.name AS expectation, sum(e.passed_records) passed, sum(e.failed_records) failed
FROM exp GROUP BY 1,2 HAVING sum(e.failed_records) > 0 OR e.dataset LIKE '%siniestros%' ORDER BY failed DESC""")
    d.q("Quarantine: records held back, by target table and failed rule (nothing is lost)", f"""
SELECT tabla_destino, reglas_fallidas, count(*) registros
FROM {C}.seguros_demo.cuarentena_registros GROUP BY ALL ORDER BY registros DESC""")
    d.q("Row counts across the medallion (bronze → silver → gold)", f"""
SELECT 'bronze_siniestros' t, count(*) n FROM {C}.seguros_demo.bronze_siniestros UNION ALL
SELECT 'silver_siniestros', count(*) FROM {C}.seguros_demo.silver_siniestros UNION ALL
SELECT 'fact_siniestros (gold)', count(*) FROM {C}.seguros_demo.fact_siniestros UNION ALL
SELECT 'bronze_polizas', count(*) FROM {C}.seguros_demo.bronze_polizas UNION ALL
SELECT 'fact_polizas (gold)', count(*) FROM {C}.seguros_demo.fact_polizas UNION ALL
SELECT 'bronze_app_trip_summary (Auto Loader)', count(*) FROM {C}.seguros_demo.bronze_app_trip_summary UNION ALL
SELECT 'bronze_app_fnol (Auto Loader)', count(*) FROM {C}.seguros_demo.bronze_app_fnol UNION ALL
SELECT 'act_triangulo (actuarial)', count(*) FROM {C}.seguros_demo.act_triangulo""")
    d.q("Federated sources read in place (Lakehouse Federation, no copy)", f"""
SELECT 'DWH clients (Oracle proxy)' fuente, count(*) n FROM seguros_dwh_onprem.seguros_dwh.tb_clientes UNION ALL
SELECT 'Personal loans (AWS proxy)', count(*) FROM seguros_creditos_aws.seguros_creditos.creditos_personales UNION ALL
SELECT 'Cross-system: clients with policy AND loan', count(*) FROM seguros_dwh_onprem.seguros_dwh.tb_clientes c
  JOIN seguros_creditos_aws.seguros_creditos.creditos_personales k ON upper(k.customer_rfc) = c.rfc""")


def governance(d):
    d.q("ABAC policies on the gold schema", f"SHOW POLICIES ON SCHEMA {C}.seguros_demo")
    d.q("Governed tags on columns (PII, region, certification)", f"""
SELECT tag_name, tag_value, count(*) columnas
FROM {C}.information_schema.column_tags
WHERE schema_name IN ('seguros_demo','seguros_ml') AND tag_name LIKE 'seguros_%'
GROUP BY ALL ORDER BY 1,2""")
    d.text("## Same query, three roles\n\nThe demo user's role is switched in `seguros_gobierno.usuarios_rol` and the **same** query is re-run. "
           "Unity Catalog ABAC policies (column masks + row filter) change the answer; the query text does not change.\n")
    probe = f"""SELECT current_user() usuario, {C}.seguros_gobierno.rol_actual() rol, {C}.seguros_gobierno.region_actual() region,
       count(*) clientes_visibles, count(DISTINCT region) regiones_visibles,
       max_by(nombre_completo, id_cliente) ejemplo_nombre, max_by(rfc, id_cliente) ejemplo_rfc, max_by(telefono, id_cliente) ejemplo_telefono
FROM {C}.seguros_demo.dim_cliente"""
    try:
        for rol, region in [("SIU", None), ("ACTUARIO", None), ("AGENTE_REGIONAL", "Norte")]:
            reg = "NULL" if region is None else f"'{region}'"
            run(f"UPDATE {C}.seguros_gobierno.usuarios_rol SET rol = '{rol}', region = {reg} WHERE usuario = '{ME}'")
            d.q(f"Role = {rol}" + (f" · region {region}" if region else ""), probe)
    finally:
        run(f"UPDATE {C}.seguros_gobierno.usuarios_rol SET rol = 'SIU', region = NULL WHERE usuario = '{ME}'")
    d.q("Sandbox copy made as ACTUARIO stays masked forever (no PII to recover)", f"""
SELECT count(*) filas, max(nombre_completo) ejemplo_nombre, max(rfc) ejemplo_rfc FROM {C}.seguros_sandbox_ds.copia_clientes_ana""")


def ml(d):
    d.q("Feature table (Feature Engineering in Unity Catalog)", f"""
SELECT count(*) siniestros, count(DISTINCT id_siniestro) llaves_unicas FROM {C}.seguros_ml.features_fraude_siniestro""")
    d.q("Batch scoring of open claims by risk tier", f"""
SELECT nivel_riesgo, count(*) siniestros, round(avg(prob_fraude),3) prob_media, round(sum(monto_reclamado)/1e6,2) mxn_m_reclamado,
       round(sum(monto_en_riesgo)/1e6,2) mxn_m_en_riesgo, max(modelo_version) modelo_version, max(fecha_scoring) fecha_scoring
FROM {C}.seguros_ml.scoring_fraude_siniestros GROUP BY 1 ORDER BY prob_media DESC""")
    d.q("Top 5 claims with the model's SHAP reasons (real model output)", f"""
SELECT num_siniestro, region, cobertura, round(prob_fraude,3) prob_fraude, nivel_riesgo, razon_1, razon_2, razon_3
FROM {C}.seguros_ml.scoring_fraude_siniestros ORDER BY prob_fraude DESC LIMIT 5""")
    d.q("Model vs SIU verdict (human labels that flow back for retraining)", f"""
SELECT nivel_riesgo_apertura, veredicto, count(*) casos, round(avg(prob_fraude_apertura),3) prob_media
FROM {C}.seguros_siu_expediente.etiquetas_siu GROUP BY ALL ORDER BY 1,2""")


def genai(d):
    d.q("AI on documents: ai_parse_document + ai_query over body-shop PDFs", f"""
SELECT count(*) pdfs, sum(CASE WHEN num_inconsistencias > 0 THEN 1 ELSE 0 END) con_inconsistencias,
       sum(CAST(vin_no_coincide AS INT)) vin_no_coincide, sum(CAST(total_no_coincide AS INT)) total_alterado,
       sum(CAST(fecha_previa_siniestro AS INT)) fecha_previa
FROM {C}.seguros_demo.docs_validacion_presupuestos""")
    d.q("Sample extractions (fields read by the LLM from the PDF vs system of record)", f"""
SELECT num_siniestro, nombre_taller, total_documento, total_capturado, dif_total_pct, vin_no_coincide, array_join(motivos, ' · ') motivos
FROM {C}.seguros_demo.docs_validacion_presupuestos WHERE num_inconsistencias > 0 ORDER BY dif_total_pct DESC LIMIT 5""")
    d.q("Documents vs model risk tier", f"""
SELECT nivel_riesgo_modelo, count(*) pdfs, round(avg(CASE WHEN num_inconsistencias > 0 THEN 1 ELSE 0 END)*100,1) pct_con_inconsistencias
FROM {C}.seguros_demo.docs_validacion_presupuestos GROUP BY 1 ORDER BY 3 DESC""")
    d.q("Agent tool (UC function) called with the user's identity", f"""
SELECT num_siniestro, region, round(prob_fraude,3) prob_fraude, nivel_riesgo, razones_modelo, inconsistencias_documentales
FROM {C}.seguros_ml.agente_bandeja_siu(top_n => 5)""")
    d.q("Model-service inference table (every LLM call is logged)", f"""
SELECT date(event_time) dia, destination_model modelo, count(*) llamadas, round(avg(latency_ms)) latencia_ms_prom,
       sum(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) ok
FROM {C}.seguros_ml.model_service_demo_agente_payload GROUP BY 1, 2 ORDER BY 1 DESC LIMIT 12""")


SECTIONS = {
    "lakeflow": ("Evidence · Lakeflow ingestion and medallion pipeline", "Pipeline `seguros_medallion` (Lakeflow Declarative Pipelines): event log, row counts, expectations and quarantine.", lakeflow),
    "governance": ("Evidence · Unity Catalog governance", "Governed tags, ABAC policies and the same query returning different answers per role.", governance),
    "ml": ("Evidence · ML fraud model and scoring", "Feature table, batch scoring with SHAP reasons, and SIU verdicts used as labels.", ml),
    "genai": ("Evidence · Gen AI (documents, agent tools, model service)", "LLM extraction from PDFs, governed agent tools and the model-service inference table.", genai),
}

if __name__ == "__main__":
    title, intro, fn = SECTIONS[sys.argv[1]]
    doc = Doc(title, intro)
    fn(doc)
    doc.save(sys.argv[2])
