-- =====================================================================================
-- Pieza 1 · Reverse ETL — tabla de serving de la Bandeja SIU (lakehouse → Lakebase)
-- Fuente gobernada: scoring_fraude_siniestros (modelo) + docs_validacion_presupuestos (IA sobre PDFs)
-- Sin PII (solo número de siniestro, región, cobertura, montos y señales) → minimización de datos en la capa operativa.
-- Change Data Feed ON → la synced table en Lakebase se actualiza incrementalmente (modo TRIGGERED).
-- Se refresca con MERGE (no CREATE OR REPLACE) para conservar el CDF; corre como 3ª tarea del job de ML.
-- =====================================================================================
CREATE TABLE IF NOT EXISTS demo_catalog.seguros_ml.bandeja_siu_serving (
  num_siniestro STRING NOT NULL,
  id_siniestro BIGINT,
  region STRING,
  cobertura STRING,
  estado_ocurrencia STRING,
  canal_reporte STRING,
  fecha_ocurrencia TIMESTAMP,
  monto_reclamado DOUBLE,
  prob_fraude DOUBLE,
  nivel_riesgo STRING,
  monto_en_riesgo DOUBLE,
  razones_modelo STRING,
  inconsistencias_documentales STRING,
  num_inconsistencias INT,
  id_taller INT,
  modelo_version INT,
  fecha_scoring TIMESTAMP,
  CONSTRAINT bandeja_siu_serving_pk PRIMARY KEY (num_siniestro)
)
COMMENT 'Serving de la Bandeja SIU (siniestros abiertos calificados por el modelo de fraude + inconsistencias documentales). Sin PII. Se sincroniza a Lakebase (seguros-siu/siu.serving.bandeja_siu) para la app del SIU.'
TBLPROPERTIES (delta.enableChangeDataFeed = true);

MERGE INTO demo_catalog.seguros_ml.bandeja_siu_serving t
USING (
  SELECT s.num_siniestro, s.id_siniestro, s.region, s.cobertura, s.estado_ocurrencia, s.canal_reporte, s.fecha_ocurrencia,
         CAST(s.monto_reclamado AS DOUBLE) monto_reclamado, ROUND(s.prob_fraude, 4) prob_fraude, s.nivel_riesgo,
         ROUND(s.monto_en_riesgo, 2) monto_en_riesgo, concat_ws(' · ', s.razon_1, s.razon_2, s.razon_3) razones_modelo,
         array_join(d.motivos, ' · ') inconsistencias_documentales, coalesce(d.num_inconsistencias, 0) num_inconsistencias,
         s.id_taller, s.modelo_version, s.fecha_scoring
  FROM demo_catalog.seguros_ml.scoring_fraude_siniestros s
  LEFT JOIN demo_catalog.seguros_demo.docs_validacion_presupuestos d ON s.id_siniestro = d.id_siniestro AND d.num_inconsistencias > 0
) s
ON t.num_siniestro = s.num_siniestro
WHEN MATCHED AND (t.prob_fraude <=> s.prob_fraude AND t.nivel_riesgo <=> s.nivel_riesgo AND t.inconsistencias_documentales <=> s.inconsistencias_documentales
                  AND t.modelo_version <=> s.modelo_version AND t.monto_reclamado <=> s.monto_reclamado) = FALSE THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE;
