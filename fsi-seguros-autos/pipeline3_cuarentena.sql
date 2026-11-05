-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Aseguradora FSI · Autos — Pipeline Medallion · Cuarentena de calidad
-- MAGIC **Archivo GENERADO por `gen_cuarentena.py`** a partir de las expectations `ON VIOLATION DROP ROW` de plata (no editar a mano).
-- MAGIC - `cuarentena_registros`: cada registro que una regla DROP descartó, con las reglas que falló y el registro completo (JSON)
-- MAGIC   para que el equipo de datos lo corrija en la fuente. Nada se pierde en silencio.

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW cuarentena_registros
COMMENT 'Cuarentena: registros descartados por las expectations DROP (plata y oro), con reglas fallidas y registro en JSON. Contiene PII en `registro`: acceso solo para el equipo de calidad de datos'
AS SELECT *, size(reglas_fallidas) num_reglas_fallidas, current_timestamp() fecha_deteccion FROM (
  SELECT 'silver_productos' tabla_destino, 'Plata' capa, 'bronze_productos' tabla_origen, CAST(concat_ws('|', id_producto) AS STRING) llave,
         filter(array(IF(NOT COALESCE(ramo = 'Autos', FALSE), 'ramo_autos', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT CAST(id_producto AS INT) id_producto, cve_producto, nombre_producto, ramo, subramo FROM bronze_productos) x
  WHERE NOT COALESCE(ramo = 'Autos', FALSE)
  UNION ALL
  SELECT 'silver_agentes' tabla_destino, 'Plata' capa, 'bronze_agentes' tabla_origen, CAST(concat_ws('|', id_agente) AS STRING) llave,
         filter(array(IF(NOT COALESCE(canal IN ('Agente','Banca Seguros','Tienda Aliada','Digital','Broker'), FALSE), 'canal_valido', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT CAST(id_agente AS INT) id_agente, cve_agente, trim(nombre_agente) nombre_agente, canal, oficina, region,
          fecha_alta, activo
FROM bronze_agentes) x
  WHERE NOT COALESCE(canal IN ('Agente','Banca Seguros','Tienda Aliada','Digital','Broker'), FALSE)
  UNION ALL
  SELECT 'silver_talleres' tabla_destino, 'Plata' capa, 'bronze_talleres' tabla_origen, CAST(concat_ws('|', id_taller) AS STRING) llave,
         filter(array(IF(NOT COALESCE(tipo IN ('Agencia','Multimarca','Independiente'), FALSE), 'tipo_valido', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT CAST(id_taller AS INT) id_taller, nombre_taller, tipo, estado, municipio FROM bronze_talleres) x
  WHERE NOT COALESCE(tipo IN ('Agencia','Multimarca','Independiente'), FALSE)
  UNION ALL
  SELECT 'silver_clientes' tabla_destino, 'Plata' capa, 'bronze_clientes' tabla_origen, CAST(concat_ws('|', id_cliente) AS STRING) llave,
         filter(array(IF(NOT COALESCE(rfc RLIKE '^[A-Z&Ñ]{4}[0-9]{6}[A-Z0-9]{3}$', FALSE), 'rfc_formato', NULL),
         IF(NOT COALESCE(curp RLIKE '^[A-Z]{4}[0-9]{6}[HM][A-Z]{5}[0-9A-Z][0-9]$', FALSE), 'curp_formato', NULL),
         IF(NOT COALESCE(edad BETWEEN 18 AND 100, FALSE), 'edad_valida', NULL),
         IF(NOT COALESCE(genero IN ('M','F'), FALSE), 'genero_valido', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT
  CAST(id_cliente AS INT) id_cliente,
  initcap(trim(nombre)) nombre, initcap(trim(apellido_paterno)) apellido_paterno, initcap(trim(apellido_materno)) apellido_materno,
  concat_ws(' ', initcap(trim(nombre)), initcap(trim(apellido_paterno)), initcap(trim(apellido_materno))) nombre_completo,
  upper(trim(rfc)) rfc, upper(trim(curp)) curp, fecha_nacimiento,
  CAST(floor(months_between(DATE'2026-10-13', fecha_nacimiento) / 12) AS INT) edad,
  genero, lower(trim(email)) email, regexp_replace(telefono, '[^0-9]', '') telefono,
  estado, municipio, codigo_postal, fecha_alta, segmento
FROM bronze_clientes) x
  WHERE NOT COALESCE(rfc RLIKE '^[A-Z&Ñ]{4}[0-9]{6}[A-Z0-9]{3}$', FALSE)
     OR NOT COALESCE(curp RLIKE '^[A-Z]{4}[0-9]{6}[HM][A-Z]{5}[0-9A-Z][0-9]$', FALSE)
     OR NOT COALESCE(edad BETWEEN 18 AND 100, FALSE)
     OR NOT COALESCE(genero IN ('M','F'), FALSE)
  UNION ALL
  SELECT 'silver_polizas' tabla_destino, 'Plata' capa, 'bronze_polizas' tabla_origen, CAST(concat_ws('|', id_poliza) AS STRING) llave,
         filter(array(IF(NOT COALESCE(id_cliente IS NOT NULL, FALSE), 'fk_cliente', NULL),
         IF(NOT COALESCE(fin_vigencia > inicio_vigencia, FALSE), 'vigencia_coherente', NULL),
         IF(NOT COALESCE(prima_neta_anual > 0, FALSE), 'prima_positiva', NULL),
         IF(NOT COALESCE(suma_asegurada > 0, FALSE), 'suma_positiva', NULL),
         IF(NOT COALESCE(estatus IN ('Vigente','Vencida','Cancelada'), FALSE), 'estatus_valido', NULL),
         IF(NOT COALESCE(forma_pago IN ('Anual','Semestral','Trimestral','Mensual'), FALSE), 'forma_pago_valida', NULL),
         IF(NOT COALESCE(fecha_emision <= DATE'2026-10-13', FALSE), 'emision_no_futura', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT
  CAST(id_poliza AS BIGINT) id_poliza, num_poliza, CAST(id_cliente AS INT) id_cliente, CAST(id_producto AS INT) id_producto,
  CAST(id_agente AS INT) id_agente, fecha_emision, inicio_vigencia, fin_vigencia,
  CAST(suma_asegurada AS DECIMAL(14,2)) suma_asegurada, CAST(prima_neta_anual AS DECIMAL(12,2)) prima_neta_anual,
  forma_pago, estatus, fecha_cancelacion, es_renovacion
FROM bronze_polizas) x
  WHERE NOT COALESCE(id_cliente IS NOT NULL, FALSE)
     OR NOT COALESCE(fin_vigencia > inicio_vigencia, FALSE)
     OR NOT COALESCE(prima_neta_anual > 0, FALSE)
     OR NOT COALESCE(suma_asegurada > 0, FALSE)
     OR NOT COALESCE(estatus IN ('Vigente','Vencida','Cancelada'), FALSE)
     OR NOT COALESCE(forma_pago IN ('Anual','Semestral','Trimestral','Mensual'), FALSE)
     OR NOT COALESCE(fecha_emision <= DATE'2026-10-13', FALSE)
  UNION ALL
  SELECT 'silver_vehiculos' tabla_destino, 'Plata' capa, 'bronze_vehiculos' tabla_origen, CAST(concat_ws('|', id_vehiculo) AS STRING) llave,
         filter(array(IF(NOT COALESCE(id_poliza IS NOT NULL, FALSE), 'fk_poliza', NULL),
         IF(NOT COALESCE(anio_modelo BETWEEN 1990 AND 2027, FALSE), 'anio_valido', NULL),
         IF(NOT COALESCE(valor_comercial > 0, FALSE), 'valor_positivo', NULL),
         IF(NOT COALESCE(uso IN ('Particular','Plataforma','Carga ligera'), FALSE), 'uso_valido', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT CAST(id_vehiculo AS BIGINT) id_vehiculo, CAST(id_poliza AS BIGINT) id_poliza, marca, submarca,
          CAST(anio_modelo AS INT) anio_modelo, uso, CAST(valor_comercial AS DECIMAL(12,2)) valor_comercial,
          upper(num_serie_vin) num_serie_vin, upper(placas) placas, app_conectada
FROM bronze_vehiculos) x
  WHERE NOT COALESCE(id_poliza IS NOT NULL, FALSE)
     OR NOT COALESCE(anio_modelo BETWEEN 1990 AND 2027, FALSE)
     OR NOT COALESCE(valor_comercial > 0, FALSE)
     OR NOT COALESCE(uso IN ('Particular','Plataforma','Carga ligera'), FALSE)
  UNION ALL
  SELECT 'silver_poliza_coberturas' tabla_destino, 'Plata' capa, 'bronze_poliza_coberturas' tabla_origen, CAST(concat_ws('|', id_poliza, id_cobertura) AS STRING) llave,
         filter(array(IF(NOT COALESCE(prima_cobertura >= 0, FALSE), 'prima_no_neg', NULL),
         IF(NOT COALESCE(deducible_pct BETWEEN 0 AND 100, FALSE), 'deducible_rng', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT CAST(id_poliza AS BIGINT) id_poliza, CAST(id_cobertura AS INT) id_cobertura,
          CAST(suma_asegurada AS DECIMAL(14,2)) suma_asegurada, CAST(deducible_pct AS DOUBLE) deducible_pct,
          CAST(prima_cobertura AS DECIMAL(12,2)) prima_cobertura
FROM bronze_poliza_coberturas) x
  WHERE NOT COALESCE(prima_cobertura >= 0, FALSE)
     OR NOT COALESCE(deducible_pct BETWEEN 0 AND 100, FALSE)
  UNION ALL
  SELECT 'silver_conductores' tabla_destino, 'Plata' capa, 'bronze_conductores' tabla_origen, CAST(concat_ws('|', id_conductor) AS STRING) llave,
         filter(array(IF(NOT COALESCE(edad BETWEEN 18 AND 90, FALSE), 'edad_conducir', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT CAST(id_conductor AS BIGINT) id_conductor, CAST(id_poliza AS BIGINT) id_poliza, CAST(id_cliente AS INT) id_cliente,
          es_titular, CAST(edad AS INT) edad, genero, CAST(anios_licencia AS INT) anios_licencia, tipo_licencia, codigo_postal
FROM bronze_conductores) x
  WHERE NOT COALESCE(edad BETWEEN 18 AND 90, FALSE)
  UNION ALL
  SELECT 'silver_cotizaciones' tabla_destino, 'Plata' capa, 'bronze_cotizaciones' tabla_origen, CAST(concat_ws('|', id_cotizacion) AS STRING) llave,
         filter(array(IF(NOT COALESCE(prima_cotizada > 0, FALSE), 'prima_positiva', NULL),
         IF(NOT COALESCE(fecha_cotizacion <= DATE'2026-10-13', FALSE), 'fecha_no_futura', NULL),
         IF(NOT COALESCE(canal IN ('App Autos FSI','Portal Web','Comparador Externo','Agente','Módulo Tienda Aliada'), FALSE), 'canal_valido', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT CAST(id_cotizacion AS BIGINT) id_cotizacion, fecha_cotizacion, canal, sistema_origen, codigo_postal, estado,
          marca, submarca, CAST(anio_modelo AS INT) anio_modelo, CAST(edad_conductor AS INT) edad_conductor,
          CAST(id_producto AS INT) id_producto, CAST(prima_cotizada AS DECIMAL(12,2)) prima_cotizada, convertida,
          CAST(id_poliza AS BIGINT) id_poliza
FROM bronze_cotizaciones) x
  WHERE NOT COALESCE(prima_cotizada > 0, FALSE)
     OR NOT COALESCE(fecha_cotizacion <= DATE'2026-10-13', FALSE)
     OR NOT COALESCE(canal IN ('App Autos FSI','Portal Web','Comparador Externo','Agente','Módulo Tienda Aliada'), FALSE)
  UNION ALL
  SELECT 'silver_recibos' tabla_destino, 'Plata' capa, 'bronze_recibos' tabla_origen, CAST(concat_ws('|', id_recibo) AS STRING) llave,
         filter(array(IF(NOT COALESCE(importe > 0, FALSE), 'importe_positivo', NULL),
         IF(NOT COALESCE(estatus IN ('Pagado','Pendiente','Cancelado'), FALSE), 'estatus_valido', NULL),
         IF(NOT COALESCE(estatus <> 'Pagado' OR fecha_pago IS NOT NULL, FALSE), 'pagado_con_fecha', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT CAST(id_recibo AS BIGINT) id_recibo, CAST(id_poliza AS BIGINT) id_poliza, CAST(num_recibo AS INT) num_recibo,
          fecha_vencimiento, fecha_pago, CAST(importe AS DECIMAL(12,2)) importe, estatus,
          CASE WHEN fecha_pago IS NOT NULL THEN datediff(fecha_pago, fecha_vencimiento) END dias_pago_vs_vencimiento
FROM bronze_recibos) x
  WHERE NOT COALESCE(importe > 0, FALSE)
     OR NOT COALESCE(estatus IN ('Pagado','Pendiente','Cancelado'), FALSE)
     OR NOT COALESCE(estatus <> 'Pagado' OR fecha_pago IS NOT NULL, FALSE)
  UNION ALL
  SELECT 'silver_siniestros' tabla_destino, 'Plata' capa, 'bronze_siniestros' tabla_origen, CAST(concat_ws('|', id_siniestro) AS STRING) llave,
         filter(array(IF(NOT COALESCE(fecha_reporte >= fecha_ocurrencia, FALSE), 'reporte_post_ocurr', NULL),
         IF(NOT COALESCE(fecha_ocurrencia <= TIMESTAMP'2026-10-13 23:59:59', FALSE), 'ocurrencia_no_futura', NULL),
         IF(NOT COALESCE(monto_reclamado >= 0, FALSE), 'monto_no_negativo', NULL),
         IF(NOT COALESCE(cobertura IN ('Daños Materiales','Responsabilidad Civil','Robo Total','Cristales','Gastos Médicos Ocupantes'), FALSE), 'cobertura_valida', NULL),
         IF(NOT COALESCE(estatus IN ('Abierto','Cerrado','Rechazado','En investigación'), FALSE), 'estatus_valido', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT
  CAST(s.id_siniestro AS BIGINT) id_siniestro, s.num_siniestro, CAST(s.id_poliza AS BIGINT) id_poliza,
  CAST(s.id_ajustador AS INT) id_ajustador, CAST(s.id_taller AS INT) id_taller,
  CAST(s.fecha_ocurrencia AS TIMESTAMP) fecha_ocurrencia, CAST(s.fecha_reporte AS TIMESTAMP) fecha_reporte,
  s.cobertura, s.causa, s.estado_ocurrencia, s.canal_reporte,
  CAST(s.monto_reclamado AS DECIMAL(14,2)) monto_reclamado, CAST(s.reserva_inicial AS DECIMAL(14,2)) reserva_inicial,
  CAST(s.deducible AS DECIMAL(12,2)) deducible, s.reporte_autoridad, CAST(s.num_terceros AS INT) num_terceros,
  s.estatus, s.fecha_cierre, s.fraude_confirmado,
  ROUND((unix_timestamp(CAST(s.fecha_reporte AS TIMESTAMP)) - unix_timestamp(CAST(s.fecha_ocurrencia AS TIMESTAMP))) / 3600, 1) horas_a_reporte,
  hour(CAST(s.fecha_ocurrencia AS TIMESTAMP)) IN (22, 23, 0, 1, 2, 3, 4) ocurrencia_nocturna
FROM bronze_siniestros s) x
  WHERE NOT COALESCE(fecha_reporte >= fecha_ocurrencia, FALSE)
     OR NOT COALESCE(fecha_ocurrencia <= TIMESTAMP'2026-10-13 23:59:59', FALSE)
     OR NOT COALESCE(monto_reclamado >= 0, FALSE)
     OR NOT COALESCE(cobertura IN ('Daños Materiales','Responsabilidad Civil','Robo Total','Cristales','Gastos Médicos Ocupantes'), FALSE)
     OR NOT COALESCE(estatus IN ('Abierto','Cerrado','Rechazado','En investigación'), FALSE)
  UNION ALL
  SELECT 'silver_movtos_siniestro' tabla_destino, 'Plata' capa, 'bronze_movtos_siniestro' tabla_origen, CAST(concat_ws('|', id_movimiento) AS STRING) llave,
         filter(array(IF(NOT COALESCE(tipo_movimiento IN ('Pago','Ajuste Reserva','Recuperación'), FALSE), 'tipo_valido', NULL),
         IF(NOT COALESCE(tipo_movimiento <> 'Pago' OR importe > 0, FALSE), 'pago_positivo', NULL),
         IF(NOT COALESCE(tipo_movimiento <> 'Recuperación' OR importe < 0, FALSE), 'recuperacion_neg', NULL),
         IF(NOT COALESCE(fecha_movimiento <= DATE'2026-10-13', FALSE), 'fecha_no_futura', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT CAST(id_movimiento AS BIGINT) id_movimiento, CAST(id_siniestro AS BIGINT) id_siniestro, fecha_movimiento,
          tipo_movimiento, CAST(importe AS DECIMAL(14,2)) importe
FROM bronze_movtos_siniestro) x
  WHERE NOT COALESCE(tipo_movimiento IN ('Pago','Ajuste Reserva','Recuperación'), FALSE)
     OR NOT COALESCE(tipo_movimiento <> 'Pago' OR importe > 0, FALSE)
     OR NOT COALESCE(tipo_movimiento <> 'Recuperación' OR importe < 0, FALSE)
     OR NOT COALESCE(fecha_movimiento <= DATE'2026-10-13', FALSE)
  UNION ALL
  SELECT 'silver_valuaciones' tabla_destino, 'Plata' capa, 'bronze_valuaciones' tabla_origen, CAST(concat_ws('|', id_valuacion) AS STRING) llave,
         filter(array(IF(NOT COALESCE(monto_autorizado > 0, FALSE), 'autorizado_positivo', NULL),
         IF(NOT COALESCE(pct_piezas_originales BETWEEN 0 AND 1, FALSE), 'pct_originales_rng', NULL),
         IF(NOT COALESCE(num_piezas > 0, FALSE), 'piezas_positivas', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT CAST(id_valuacion AS BIGINT) id_valuacion, CAST(id_siniestro AS BIGINT) id_siniestro, CAST(id_taller AS INT) id_taller,
          fecha_valuacion, CAST(monto_presupuesto_taller AS DECIMAL(14,2)) monto_presupuesto_taller,
          CAST(monto_autorizado AS DECIMAL(14,2)) monto_autorizado, CAST(num_piezas AS INT) num_piezas,
          CAST(pct_piezas_originales AS DOUBLE) pct_piezas_originales, CAST(horas_mano_obra AS DOUBLE) horas_mano_obra,
          CAST(dias_reparacion AS INT) dias_reparacion,
          ROUND(monto_presupuesto_taller / monto_autorizado, 3) ratio_presupuesto_autorizado
FROM bronze_valuaciones) x
  WHERE NOT COALESCE(monto_autorizado > 0, FALSE)
     OR NOT COALESCE(pct_piezas_originales BETWEEN 0 AND 1, FALSE)
     OR NOT COALESCE(num_piezas > 0, FALSE)
  UNION ALL
  SELECT 'silver_terceros_siniestro' tabla_destino, 'Plata' capa, 'bronze_terceros_siniestro' tabla_origen, CAST(concat_ws('|', id_tercero) AS STRING) llave,
         filter(array(IF(NOT COALESCE(tipo_tercero IN ('Vehículo','Peatón','Propiedad'), FALSE), 'tipo_valido', NULL),
         IF(NOT COALESCE(monto_reclamado_tercero >= 0, FALSE), 'monto_no_neg', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT CAST(id_tercero AS BIGINT) id_tercero, CAST(id_siniestro AS BIGINT) id_siniestro, tipo_tercero,
          initcap(trim(nombre_tercero)) nombre_tercero, regexp_replace(telefono_tercero, '[^0-9]', '') telefono_tercero,
          upper(placas_tercero) placas_tercero, aseguradora_tercero,
          CAST(monto_reclamado_tercero AS DECIMAL(14,2)) monto_reclamado_tercero
FROM bronze_terceros_siniestro) x
  WHERE NOT COALESCE(tipo_tercero IN ('Vehículo','Peatón','Propiedad'), FALSE)
     OR NOT COALESCE(monto_reclamado_tercero >= 0, FALSE)
  UNION ALL
  SELECT 'silver_creditos_personales' tabla_destino, 'Plata' capa, 'bronze_creditos_personales' tabla_origen, CAST(concat_ws('|', credito_id) AS STRING) llave,
         filter(array(IF(NOT COALESCE(rfc RLIKE '^[A-Z&Ñ]{4}[0-9]{6}[A-Z0-9]{3}$', FALSE), 'rfc_formato', NULL),
         IF(NOT COALESCE(monto_original > 0, FALSE), 'monto_positivo', NULL),
         IF(NOT COALESCE(saldo >= 0, FALSE), 'saldo_no_neg', NULL),
         IF(NOT COALESCE(estatus IN ('Al corriente','Atrasado','Vencido','Liquidado'), FALSE), 'estatus_valido', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT
  CAST(credito_id AS BIGINT) credito_id, CAST(customer_id AS INT) id_cliente,
  upper(trim(customer_rfc)) rfc,
  customer_rfc <> upper(trim(customer_rfc)) rfc_corregido,
  product producto, origination_date fecha_originacion, CAST(term_months AS INT) plazo_meses,
  CAST(amount AS DECIMAL(14,2)) monto_original, CAST(rate_pct AS DOUBLE) tasa_anual_pct,
  CAST(balance AS DECIMAL(14,2)) saldo, CAST(days_past_due AS INT) dias_atraso,
  CASE status WHEN 'current' THEN 'Al corriente' WHEN 'delinquent' THEN 'Atrasado'
              WHEN 'default' THEN 'Vencido' WHEN 'paid_off' THEN 'Liquidado' END estatus
FROM bronze_creditos_personales) x
  WHERE NOT COALESCE(rfc RLIKE '^[A-Z&Ñ]{4}[0-9]{6}[A-Z0-9]{3}$', FALSE)
     OR NOT COALESCE(monto_original > 0, FALSE)
     OR NOT COALESCE(saldo >= 0, FALSE)
     OR NOT COALESCE(estatus IN ('Al corriente','Atrasado','Vencido','Liquidado'), FALSE)
  UNION ALL
  SELECT 'silver_app_trip_summary' tabla_destino, 'Plata' capa, 'bronze_app_trip_summary' tabla_origen, CAST(CAST(NULL AS STRING) AS STRING) llave,
         filter(array(IF(NOT COALESCE(id_poliza IS NOT NULL, FALSE), 'poliza_presente', NULL),
         IF(NOT COALESCE(km_recorridos >= 0, FALSE), 'km_no_negativo', NULL),
         IF(NOT COALESCE(score_manejo BETWEEN 0 AND 100, FALSE), 'score_0a100', NULL),
         IF(NOT COALESCE(pct_manejo_nocturno BETWEEN 0 AND 1, FALSE), 'nocturno_pct', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT
  CAST(id_poliza AS BIGINT) id_poliza, device_id, to_date(concat(mes, '-01')) mes,
  CAST(km_recorridos AS DOUBLE) km_recorridos, CAST(num_viajes AS INT) num_viajes,
  CAST(frenados_bruscos AS INT) frenados_bruscos, CAST(excesos_velocidad AS INT) excesos_velocidad,
  CAST(pct_manejo_nocturno AS DOUBLE) pct_manejo_nocturno, CAST(uso_celular_min AS DOUBLE) uso_celular_min,
  CAST(score_manejo AS INT) score_manejo,
  ROUND(CAST(frenados_bruscos AS DOUBLE) / NULLIF(km_recorridos, 0) * 100, 2) frenados_por_100km,
  _source_file, _ingest_ts
FROM bronze_app_trip_summary) x
  WHERE NOT COALESCE(id_poliza IS NOT NULL, FALSE)
     OR NOT COALESCE(km_recorridos >= 0, FALSE)
     OR NOT COALESCE(score_manejo BETWEEN 0 AND 100, FALSE)
     OR NOT COALESCE(pct_manejo_nocturno BETWEEN 0 AND 1, FALSE)
  UNION ALL
  SELECT 'silver_app_fnol' tabla_destino, 'Plata' capa, 'bronze_app_fnol' tabla_origen, CAST(coalesce(num_siniestro, device_id) AS STRING) llave,
         filter(array(IF(NOT COALESCE(num_siniestro IS NOT NULL, FALSE), 'siniestro_presente', NULL),
         IF(NOT COALESCE(gps_lat BETWEEN 14.5 AND 32.8 AND gps_lon BETWEEN -118.5 AND -86.5, FALSE), 'gps_en_mexico', NULL),
         IF(NOT COALESCE(fotos_adjuntas >= 0, FALSE), 'fotos_no_negativas', NULL)), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM (SELECT
  num_siniestro, CAST(id_poliza AS BIGINT) id_poliza, device_id, CAST(event_ts AS TIMESTAMP) fecha_reporte_app,
  CAST(gps_lat AS DOUBLE) gps_lat, CAST(gps_lon AS DOUBLE) gps_lon,
  CAST(distancia_km_ubicacion_declarada AS DOUBLE) distancia_km_ubicacion_declarada,
  CAST(fotos_adjuntas AS INT) fotos_adjuntas, CAST(video_adjunto AS BOOLEAN) video_adjunto,
  CAST(velocidad_previa_kmh AS DOUBLE) velocidad_previa_kmh, CAST(impacto_detectado_g AS DOUBLE) impacto_detectado_g,
  app_version, _source_file, _ingest_ts
FROM bronze_app_fnol) x
  WHERE NOT COALESCE(num_siniestro IS NOT NULL, FALSE)
     OR NOT COALESCE(gps_lat BETWEEN 14.5 AND 32.8 AND gps_lon BETWEEN -118.5 AND -86.5, FALSE)
     OR NOT COALESCE(fotos_adjuntas >= 0, FALSE)
  UNION ALL
  SELECT 'fact_siniestros' tabla_destino, 'Oro' capa, 'silver_siniestros' tabla_origen, CAST(s.id_siniestro AS STRING) llave,
         array('fk_poliza_existe') reglas_fallidas, to_json(struct(s.*)) registro
  FROM demo_catalog.seguros_demo.silver_siniestros s LEFT ANTI JOIN demo_catalog.seguros_demo.silver_polizas p ON s.id_poliza = p.id_poliza
);
