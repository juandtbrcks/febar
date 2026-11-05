-- =====================================================================================
-- Pieza 4 · Lakebase → lakehouse. El CDF config `siu_expediente` escribe el historial de cambios de Postgres
-- (lb_*_history: insert/update/delete con LSN) en demo_catalog.seguros_siu_expediente, sin ETL.
-- Aquí: vistas de ESTADO ACTUAL (último cambio por llave) + etiquetas del SIU para reentrenar el modelo.
-- =====================================================================================
CREATE OR REPLACE VIEW demo_catalog.seguros_siu_expediente.casos
COMMENT 'Estado actual de los casos SIU (operados en Lakebase seguros-siu, replicados por CDF). Un registro por caso.'
AS SELECT * EXCEPT (_pg_change_type, _pg_lsn, _pg_xid, _timestamp, _sort_by, rn), _timestamp AS replicado_en
FROM (SELECT *, row_number() OVER (PARTITION BY id_caso ORDER BY _pg_lsn DESC, _sort_by DESC) rn
      FROM demo_catalog.seguros_siu_expediente.lb_casos_history)
WHERE rn = 1 AND _pg_change_type <> 'delete';

CREATE OR REPLACE VIEW demo_catalog.seguros_siu_expediente.notas
COMMENT 'Notas de los investigadores SIU y dictámenes del agente (Lakebase → CDF). Texto libre: puede contener datos sensibles.'
AS SELECT * EXCEPT (_pg_change_type, _pg_lsn, _pg_xid, _timestamp, _sort_by, rn), _timestamp AS replicado_en
FROM (SELECT *, row_number() OVER (PARTITION BY id_nota ORDER BY _pg_lsn DESC, _sort_by DESC) rn
      FROM demo_catalog.seguros_siu_expediente.lb_notas_history)
WHERE rn = 1 AND _pg_change_type <> 'delete';

CREATE OR REPLACE VIEW demo_catalog.seguros_siu_expediente.historial_estatus
COMMENT 'Bitácora de cambios de estatus de los casos SIU (trigger en Lakebase → CDF).'
AS SELECT * EXCEPT (_pg_change_type, _pg_lsn, _pg_xid, _timestamp, _sort_by, rn)
FROM (SELECT *, row_number() OVER (PARTITION BY id ORDER BY _pg_lsn DESC, _sort_by DESC) rn
      FROM demo_catalog.seguros_siu_expediente.lb_historial_estatus_history)
WHERE rn = 1 AND _pg_change_type <> 'delete';

-- Etiquetas humanas: veredicto del SIU sobre siniestros que el modelo calificó (abiertos) → reentrenamiento
CREATE OR REPLACE VIEW demo_catalog.seguros_siu_expediente.etiquetas_siu
COMMENT 'Veredictos del SIU (fraude/legítimo) por siniestro, con el score del modelo al abrir el caso. Fuente de etiquetas para el job seguros_fraude_siniestros_mlops y para medir el modelo contra la decisión humana.'
AS SELECT f.id_siniestro, c.num_siniestro, c.region, c.id_caso, c.veredicto, CAST(c.veredicto = 'fraude' AS INT) AS fraude,
          c.prob_fraude_apertura, c.nivel_riesgo_apertura, c.modelo_version, c.monto_en_riesgo, c.asignado_a, c.fecha_creacion, c.fecha_cierre
FROM demo_catalog.seguros_siu_expediente.casos c
JOIN demo_catalog.seguros_demo.fact_siniestros f ON f.num_siniestro = c.num_siniestro
WHERE c.veredicto IS NOT NULL;
