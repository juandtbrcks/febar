-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Aseguradora FSI · Autos — IA sobre documentos de siniestros
-- MAGIC Presupuestos de reparación en PDF (emitidos por talleres) → **`ai_parse_document`** (lectura del PDF, incluidas tablas)
-- MAGIC → **`ai_query`** con salida JSON estructurada → **validación contra los sistemas** (valuación capturada, vehículo asegurado,
-- MAGIC fecha del siniestro, taller). Todo en SQL, gobernado por Unity Catalog, sin sacar los documentos a otra herramienta.
-- MAGIC
-- MAGIC Fuente: Volume `demo_catalog.seguros_demo.documentos_siniestros/presupuestos/` (240 PDFs sintéticos).

-- COMMAND ----------
-- MAGIC %md ## 1. Lectura del PDF (`ai_parse_document`)

-- COMMAND ----------
CREATE OR REPLACE TABLE demo_catalog.seguros_demo.docs_presupuestos_parseados
COMMENT 'Presupuestos de taller (PDF) leídos con ai_parse_document: estructura del documento + texto plano'
AS WITH p AS (
  SELECT path, regexp_extract(path, '([^/]+)$', 1) archivo, modificationTime fecha_carga,
         ai_parse_document(content, map('version', '2.0')) parsed
  FROM read_files('/Volumes/demo_catalog/seguros_demo/documentos_siniestros/presupuestos/', format => 'binaryFile')
)
SELECT path, archivo, fecha_carga, parsed,
       concat_ws('\n', transform(CAST(parsed:document:elements AS ARRAY<VARIANT>), e -> CAST(e:content AS STRING))) texto
FROM p;

-- COMMAND ----------
-- MAGIC %md ## 2. Extracción estructurada (`ai_query` + JSON schema)

-- COMMAND ----------
CREATE OR REPLACE TABLE demo_catalog.seguros_demo.docs_presupuestos_extraidos
COMMENT 'Campos extraídos de cada presupuesto con ai_query (Claude) y salida JSON estricta'
AS WITH x AS (
  SELECT archivo, path,
         ai_query(
           'databricks-claude-sonnet-4-6',
           concat('Eres un analista de siniestros de autos. Extrae los datos del siguiente presupuesto de reparación ',
                  'emitido por un taller. Fechas en formato YYYY-MM-DD; montos como número sin $ ni comas; ',
                  'num_refacciones = número de renglones de refacciones (sin mano de obra). Si un dato no aparece, usa null.\n\n',
                  texto),
           responseFormat => '{"type":"json_schema","json_schema":{"name":"presupuesto","strict":true,"schema":{"type":"object","properties":{
             "num_siniestro":{"type":["string","null"]},"folio":{"type":["string","null"]},"fecha_emision":{"type":["string","null"]},
             "nombre_taller":{"type":["string","null"]},"rfc_taller":{"type":["string","null"]},
             "marca_modelo":{"type":["string","null"]},"placas":{"type":["string","null"]},"vin":{"type":["string","null"]},
             "num_refacciones":{"type":["integer","null"]},"horas_mano_obra":{"type":["number","null"]},
             "subtotal":{"type":["number","null"]},"iva":{"type":["number","null"]},"total":{"type":["number","null"]}},
             "required":["num_siniestro","folio","fecha_emision","nombre_taller","rfc_taller","marca_modelo","placas","vin",
                         "num_refacciones","horas_mano_obra","subtotal","iva","total"],"additionalProperties":false}}}'
         ) respuesta
  FROM demo_catalog.seguros_demo.docs_presupuestos_parseados
), j AS (
  SELECT archivo, path, respuesta,
         from_json(respuesta, 'num_siniestro STRING, folio STRING, fecha_emision STRING, nombre_taller STRING, rfc_taller STRING,
                    marca_modelo STRING, placas STRING, vin STRING, num_refacciones INT, horas_mano_obra DOUBLE,
                    subtotal DOUBLE, iva DOUBLE, total DOUBLE') d
  FROM x
)
SELECT archivo, path, d.num_siniestro, d.folio, try_to_date(d.fecha_emision) fecha_emision, d.nombre_taller, d.rfc_taller,
       d.marca_modelo, upper(d.placas) placas, upper(d.vin) vin, d.num_refacciones, d.horas_mano_obra,
       CAST(d.subtotal AS DECIMAL(14,2)) subtotal, CAST(d.iva AS DECIMAL(14,2)) iva, CAST(d.total AS DECIMAL(14,2)) total,
       respuesta respuesta_modelo, current_timestamp() fecha_extraccion
FROM j;

-- COMMAND ----------
-- MAGIC %md ## 3. Validación documento vs sistemas → inconsistencias para el SIU

-- COMMAND ----------
CREATE OR REPLACE TABLE demo_catalog.seguros_demo.docs_validacion_presupuestos
COMMENT 'Cada presupuesto validado contra valuación capturada, vehículo asegurado, fecha del siniestro y taller; motivos de inconsistencia + nivel de riesgo del modelo de fraude'
AS WITH b AS (
  SELECT e.*, s.id_siniestro, to_date(s.fecha_ocurrencia) fecha_ocurrencia, s.cobertura, s.estatus, fs.region,
         v.monto_presupuesto_taller total_capturado, v.monto_autorizado, t.nombre_taller nombre_taller_sistema, t.tipo tipo_taller,
         ve.placas placas_sistema, ve.num_serie_vin vin_sistema, sc.nivel_riesgo, sc.prob_fraude
  FROM demo_catalog.seguros_demo.docs_presupuestos_extraidos e
  JOIN demo_catalog.seguros_demo.silver_siniestros s ON e.num_siniestro = s.num_siniestro
  JOIN demo_catalog.seguros_demo.fact_siniestros fs ON s.id_siniestro = fs.id_siniestro
  JOIN demo_catalog.seguros_demo.silver_valuaciones v ON s.id_siniestro = v.id_siniestro
  JOIN demo_catalog.seguros_demo.silver_talleres t ON v.id_taller = t.id_taller
  JOIN demo_catalog.seguros_demo.silver_vehiculos ve ON s.id_poliza = ve.id_poliza
  LEFT JOIN demo_catalog.seguros_ml.scoring_fraude_siniestros sc ON s.id_siniestro = sc.id_siniestro
), f AS (
  SELECT *,
         ROUND(total / NULLIF(total_capturado, 0) - 1, 4) dif_total_pct,
         abs(total / NULLIF(total_capturado, 0) - 1) > 0.02 total_no_coincide,
         vin <> vin_sistema vin_no_coincide,
         placas <> placas_sistema placas_no_coincide,
         fecha_emision < fecha_ocurrencia fecha_previa_siniestro,
         lower(trim(nombre_taller)) <> lower(trim(nombre_taller_sistema)) taller_no_coincide,
         abs(subtotal + iva - total) > 1 aritmetica_incorrecta
  FROM b
)
SELECT archivo, path, id_siniestro, num_siniestro, region, cobertura, estatus, fecha_ocurrencia, fecha_emision,
       nombre_taller, tipo_taller, vin, vin_sistema, placas, placas_sistema,
       total total_documento, total_capturado, monto_autorizado, dif_total_pct,
       total_no_coincide, vin_no_coincide, placas_no_coincide, fecha_previa_siniestro, taller_no_coincide, aritmetica_incorrecta,
       filter(array(IF(total_no_coincide, 'Total del documento distinto al capturado', NULL),
                    IF(vin_no_coincide, 'VIN distinto al vehículo asegurado', NULL),
                    IF(placas_no_coincide, 'Placas distintas al vehículo asegurado', NULL),
                    IF(fecha_previa_siniestro, 'Documento fechado antes del siniestro', NULL),
                    IF(taller_no_coincide, 'Taller distinto al registrado', NULL),
                    IF(aritmetica_incorrecta, 'Subtotal + IVA no cuadra con el total', NULL)), m -> m IS NOT NULL) motivos,
       CAST(total_no_coincide AS INT) + CAST(vin_no_coincide AS INT) + CAST(placas_no_coincide AS INT)
         + CAST(fecha_previa_siniestro AS INT) + CAST(taller_no_coincide AS INT) + CAST(aritmetica_incorrecta AS INT) num_inconsistencias,
       GREATEST(total - monto_autorizado, 0) exceso_vs_autorizado,
       COALESCE(nivel_riesgo, 'Cerrado') nivel_riesgo_modelo, prob_fraude
FROM f;

-- COMMAND ----------
-- MAGIC %md ## 4. Gobierno: mismas políticas que el resto del demo (PII enmascarada por rol, filtro por región)

-- COMMAND ----------
ALTER TABLE demo_catalog.seguros_demo.docs_validacion_presupuestos SET TAGS ('seguros_certificacion' = 'oficial');
ALTER TABLE demo_catalog.seguros_demo.docs_validacion_presupuestos ALTER COLUMN vin SET TAGS ('seguros_pii' = 'vin_placas');
ALTER TABLE demo_catalog.seguros_demo.docs_validacion_presupuestos ALTER COLUMN vin_sistema SET TAGS ('seguros_pii' = 'vin_placas');
ALTER TABLE demo_catalog.seguros_demo.docs_validacion_presupuestos ALTER COLUMN placas SET TAGS ('seguros_pii' = 'vin_placas');
ALTER TABLE demo_catalog.seguros_demo.docs_validacion_presupuestos ALTER COLUMN placas_sistema SET TAGS ('seguros_pii' = 'vin_placas');
ALTER TABLE demo_catalog.seguros_demo.docs_validacion_presupuestos ALTER COLUMN region SET TAGS ('seguros_region' = 'region');
ALTER TABLE demo_catalog.seguros_demo.docs_presupuestos_extraidos ALTER COLUMN vin SET TAGS ('seguros_pii' = 'vin_placas');
ALTER TABLE demo_catalog.seguros_demo.docs_presupuestos_extraidos ALTER COLUMN placas SET TAGS ('seguros_pii' = 'vin_placas');
