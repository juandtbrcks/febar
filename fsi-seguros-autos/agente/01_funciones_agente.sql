-- FSI — Herramientas del Agente Investigador SIU (funciones de Unity Catalog)
-- Se ejecutan con la identidad de quien pregunta → aplican las mismas políticas ABAC (región / PII) que en el resto del demo.

CREATE OR REPLACE FUNCTION demo_catalog.seguros_ml.agente_bandeja_siu(
  region_filtro STRING DEFAULT NULL COMMENT 'Región (Centro, Norte, Occidente, Noroeste, Sureste, Bajío...). NULL = todas las que el usuario puede ver',
  top_n INT DEFAULT 10 COMMENT 'Número de siniestros a devolver'
)
RETURNS TABLE (num_siniestro STRING, cobertura STRING, region STRING, estado_ocurrencia STRING, monto_reclamado DOUBLE,
               prob_fraude DOUBLE, nivel_riesgo STRING, razones_modelo STRING, inconsistencias_documentales STRING)
COMMENT 'Bandeja priorizada del SIU: siniestros ABIERTOS ordenados por probabilidad de fraude del modelo, con razones y, si existen, inconsistencias detectadas por IA en los presupuestos del taller.'
RETURN
  SELECT num_siniestro, cobertura, region, estado_ocurrencia, monto_reclamado, prob_fraude, nivel_riesgo, razones_modelo, inconsistencias_documentales
  FROM (
    SELECT s.num_siniestro, s.cobertura, s.region, s.estado_ocurrencia, CAST(s.monto_reclamado AS DOUBLE) monto_reclamado,
           ROUND(s.prob_fraude, 4) prob_fraude, s.nivel_riesgo, concat_ws(' · ', s.razon_1, s.razon_2, s.razon_3) razones_modelo,
           array_join(d.motivos, ' · ') inconsistencias_documentales,
           row_number() OVER (ORDER BY s.prob_fraude DESC, s.monto_reclamado DESC) rn
    FROM demo_catalog.seguros_ml.scoring_fraude_siniestros s
    LEFT JOIN demo_catalog.seguros_demo.docs_validacion_presupuestos d ON s.id_siniestro = d.id_siniestro AND d.num_inconsistencias > 0
    WHERE region_filtro IS NULL OR lower(s.region) = lower(region_filtro)
  ) WHERE rn <= top_n;

CREATE OR REPLACE FUNCTION demo_catalog.seguros_ml.agente_detalle_siniestro(
  num_siniestro STRING COMMENT 'Número de siniestro, p. ej. S202600000146'
)
RETURNS TABLE (num_siniestro STRING, estatus STRING, cobertura STRING, causa STRING, region STRING, estado_ocurrencia STRING,
               fecha_ocurrencia TIMESTAMP, horas_a_reporte DOUBLE, dias_desde_inicio_vigencia INT, ocurrencia_nocturna BOOLEAN,
               canal_reporte STRING, reporte_autoridad BOOLEAN, monto_reclamado DOUBLE, ratio_monto_valor_vehiculo DOUBLE,
               num_terceros INT, terceros_recurrentes BIGINT, fotos_adjuntas INT, distancia_km_ubicacion_declarada DOUBLE,
               paquete STRING, vehiculo STRING, prob_fraude DOUBLE, nivel_riesgo STRING, razones_modelo STRING)
COMMENT 'Ficha de un siniestro: datos del evento, señales operativas de fraude (reporte tardío, inicio de vigencia, nocturno, terceros recurrentes, app) y la calificación del modelo de fraude con sus razones.'
RETURN
  SELECT f.num_siniestro, f.estatus, f.cobertura, f.causa, f.region, f.estado_ocurrencia, f.fecha_ocurrencia,
         CAST(f.horas_a_reporte AS DOUBLE), f.dias_desde_inicio_vigencia, f.ocurrencia_nocturna, f.canal_reporte, f.reporte_autoridad,
         CAST(f.monto_reclamado AS DOUBLE), CAST(f.ratio_monto_valor_vehiculo AS DOUBLE), f.num_terceros, f.terceros_recurrentes,
         f.fotos_adjuntas, f.distancia_km_ubicacion_declarada, p.paquete, concat_ws(' ', v.marca, v.submarca, CAST(v.anio_modelo AS STRING)),
         ROUND(s.prob_fraude, 4), s.nivel_riesgo, concat_ws(' · ', s.razon_1, s.razon_2, s.razon_3)
  FROM demo_catalog.seguros_demo.fact_siniestros f
  LEFT JOIN demo_catalog.seguros_demo.dim_producto p ON f.id_producto = p.id_producto
  LEFT JOIN demo_catalog.seguros_demo.dim_vehiculo v ON f.id_vehiculo = v.id_vehiculo
  LEFT JOIN demo_catalog.seguros_ml.scoring_fraude_siniestros s ON f.id_siniestro = s.id_siniestro
  WHERE f.num_siniestro = agente_detalle_siniestro.num_siniestro;

CREATE OR REPLACE FUNCTION demo_catalog.seguros_ml.agente_evidencia_documental(
  num_siniestro STRING COMMENT 'Número de siniestro'
)
RETURNS TABLE (num_siniestro STRING, nombre_taller STRING, fecha_emision DATE, total_documento DOUBLE, total_capturado DOUBLE,
               monto_autorizado DOUBLE, diferencia_pct DOUBLE, num_inconsistencias INT, inconsistencias STRING)
COMMENT 'Resultado de la lectura con IA (ai_parse_document + ai_query) del presupuesto del taller en PDF, validado contra los sistemas: total, VIN, placas, fecha y taller. Vacío si no hay documento.'
RETURN
  SELECT num_siniestro, nombre_taller, fecha_emision, CAST(total_documento AS DOUBLE), CAST(total_capturado AS DOUBLE),
         CAST(monto_autorizado AS DOUBLE), ROUND(dif_total_pct * 100, 1), num_inconsistencias, array_join(motivos, ' · ')
  FROM demo_catalog.seguros_demo.docs_validacion_presupuestos
  WHERE num_siniestro = agente_evidencia_documental.num_siniestro;

CREATE OR REPLACE FUNCTION demo_catalog.seguros_ml.agente_historial_cliente(
  num_siniestro STRING COMMENT 'Número de siniestro cuyo asegurado se quiere revisar'
)
RETURNS TABLE (nombre_completo STRING, rfc STRING, segmento STRING, region STRING, antiguedad_anios INT,
               tiene_credito_grupo BOOLEAN, saldo_credito DOUBLE, estatus_credito STRING, polizas INT,
               siniestros_totales BIGINT, siniestros_ultimos_12m BIGINT, incurrido_total DOUBLE, fraudes_confirmados_previos BIGINT)
COMMENT 'Perfil del asegurado del siniestro: antigüedad, posición de crédito en el grupo (cruce con la BD de créditos), pólizas e historial de siniestros y fraudes. La PII se muestra o enmascara según el rol de quien pregunta.'
RETURN
  WITH c AS (SELECT id_cliente FROM demo_catalog.seguros_demo.fact_siniestros WHERE num_siniestro = agente_historial_cliente.num_siniestro)
  SELECT d.nombre_completo, d.rfc, d.segmento, d.region, CAST(d.antiguedad_anios AS INT), d.tiene_credito_grupo,
         CAST(d.saldo_credito AS DOUBLE), d.estatus_credito,
         (SELECT CAST(COUNT(*) AS INT) FROM demo_catalog.seguros_demo.fact_polizas p WHERE p.id_cliente = d.id_cliente),
         COUNT(f.id_siniestro), COUNT_IF(f.fecha_ocurrencia >= TIMESTAMP'2025-10-13'), CAST(COALESCE(SUM(f.incurrido), 0) AS DOUBLE),
         COUNT_IF(f.fraude_confirmado)
  FROM demo_catalog.seguros_demo.dim_cliente d
  JOIN c ON d.id_cliente = c.id_cliente
  LEFT JOIN demo_catalog.seguros_demo.fact_siniestros f ON f.id_cliente = d.id_cliente
  GROUP BY ALL;

CREATE OR REPLACE FUNCTION demo_catalog.seguros_ml.agente_perfil_taller(
  num_siniestro STRING COMMENT 'Número de siniestro cuyo taller se quiere revisar'
)
RETURNS TABLE (nombre_taller STRING, tipo_taller STRING, estado_taller STRING, siniestros_atendidos BIGINT,
               tasa_fraude_confirmado_pct DOUBLE, ratio_presupuesto_promedio DOUBLE, pct_presupuestos_inflados DOUBLE,
               tasa_fraude_promedio_red_pct DOUBLE)
COMMENT 'Perfil del taller que atiende el siniestro frente a la red: tasa de fraude confirmado, presupuesto promedio vs autorizado y % de presupuestos >130 % del autorizado (señal de red de talleres coludidos).'
RETURN
  WITH t AS (SELECT id_taller FROM demo_catalog.seguros_demo.fact_siniestros WHERE num_siniestro = agente_perfil_taller.num_siniestro),
  red AS (SELECT ROUND(AVG(CASE WHEN fraude_confirmado THEN 100.0 ELSE 0 END), 1) tasa FROM demo_catalog.seguros_demo.fact_siniestros
          WHERE id_taller IS NOT NULL AND estatus IN ('Cerrado', 'Rechazado'))
  SELECT d.nombre_taller, d.tipo_taller, d.estado_taller, COUNT(f.id_siniestro),
         ROUND(AVG(CASE WHEN f.estatus IN ('Cerrado', 'Rechazado') THEN CASE WHEN f.fraude_confirmado THEN 100.0 ELSE 0 END END), 1),
         ROUND(AVG(CAST(f.ratio_presupuesto_autorizado AS DOUBLE)), 2),
         ROUND(AVG(CASE WHEN f.ratio_presupuesto_autorizado > 1.3 THEN 100.0 ELSE 0 END), 1),
         MAX(red.tasa)
  FROM t
  JOIN demo_catalog.seguros_demo.dim_taller d ON d.id_taller = t.id_taller
  LEFT JOIN demo_catalog.seguros_demo.fact_siniestros f ON f.id_taller = d.id_taller
  CROSS JOIN red
  GROUP BY d.nombre_taller, d.tipo_taller, d.estado_taller;

-- Casos abiertos por el agente (solo tras aprobación humana en la app)
CREATE TABLE IF NOT EXISTS demo_catalog.seguros_ml.casos_investigacion (
  id_caso STRING, num_siniestro STRING, prioridad STRING, resumen STRING, recomendacion STRING, monto_en_riesgo DOUBLE,
  creado_por STRING, aprobado_por STRING, fecha_creacion TIMESTAMP, estatus STRING, origen STRING
) COMMENT 'Casos de investigación SIU abiertos desde el Agente Investigador (human-in-the-loop: el investigador aprueba antes de escribir)';
