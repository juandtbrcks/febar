-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Aseguradora FSI · Autos — Pipeline Medallion · Capas Bronce y Plata
-- MAGIC **Fuentes (sin copias intermedias ni extractos):**
-- MAGIC - `seguros_dwh_onprem.seguros_dwh.*` — DWH Seguros (proxy Oracle on-prem) vía Lakehouse Federation
-- MAGIC - `seguros_creditos_aws.seguros_creditos.*` — BD Créditos Personales (proxy AWS) vía Lakehouse Federation
-- MAGIC - `/Volumes/demo_catalog/seguros_demo/datalake_ds/app_autos/` — telemetría JSON de la app de autos (Auto Loader)
-- MAGIC
-- MAGIC **Bronce** = réplica cruda + metadatos de ingesta. **Plata** = tipado, normalizado y validado con *expectations*:
-- MAGIC `FAIL` (llaves primarias: la fuente está rota), `DROP` (registro inválido), `WARN` (sospechoso, se conserva y se mide).

-- COMMAND ----------
-- MAGIC %md ## Capa Bronce — DWH Seguros (federado)

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_productos COMMENT 'Bronce: catálogo de productos de autos (DWH on-prem)'
AS SELECT *, current_timestamp() AS _ingest_ts, 'dwh_onprem' AS _source FROM seguros_dwh_onprem.seguros_dwh.tb_productos;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_agentes COMMENT 'Bronce: agentes y canales (DWH on-prem)'
AS SELECT *, current_timestamp() AS _ingest_ts, 'dwh_onprem' AS _source FROM seguros_dwh_onprem.seguros_dwh.tb_agentes;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_clientes COMMENT 'Bronce: clientes asegurados (DWH on-prem) — contiene PII'
AS SELECT *, current_timestamp() AS _ingest_ts, 'dwh_onprem' AS _source FROM seguros_dwh_onprem.seguros_dwh.tb_clientes;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_cliente_consolidado_2011
COMMENT 'Bronce: tabla consolidada legacy 2011 (columnas duplicadas/inconsistentes). NO se promueve a plata: silver_clientes es el registro único.'
AS SELECT *, current_timestamp() AS _ingest_ts, 'dwh_onprem' AS _source FROM seguros_dwh_onprem.seguros_dwh.tb_cliente_consolidado_2011;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_polizas COMMENT 'Bronce: pólizas de autos (DWH on-prem)'
AS SELECT *, current_timestamp() AS _ingest_ts, 'dwh_onprem' AS _source FROM seguros_dwh_onprem.seguros_dwh.tb_polizas;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_vehiculos COMMENT 'Bronce: vehículos asegurados (DWH on-prem)'
AS SELECT *, current_timestamp() AS _ingest_ts, 'dwh_onprem' AS _source FROM seguros_dwh_onprem.seguros_dwh.tb_vehiculos;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_poliza_coberturas COMMENT 'Bronce: coberturas contratadas por póliza (DWH on-prem)'
AS SELECT *, current_timestamp() AS _ingest_ts, 'dwh_onprem' AS _source FROM seguros_dwh_onprem.seguros_dwh.tb_poliza_coberturas;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_conductores COMMENT 'Bronce: conductores habituales por póliza (DWH on-prem)'
AS SELECT *, current_timestamp() AS _ingest_ts, 'dwh_onprem' AS _source FROM seguros_dwh_onprem.seguros_dwh.tb_conductores;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_cotizaciones COMMENT 'Bronce: cotizaciones App/Web/Comparadores externos/Agentes (DWH on-prem)'
AS SELECT *, current_timestamp() AS _ingest_ts, 'dwh_onprem' AS _source FROM seguros_dwh_onprem.seguros_dwh.tb_cotizaciones;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_recibos COMMENT 'Bronce: recibos de prima / cobranza (DWH on-prem)'
AS SELECT *, current_timestamp() AS _ingest_ts, 'dwh_onprem' AS _source FROM seguros_dwh_onprem.seguros_dwh.tb_recibos;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_talleres COMMENT 'Bronce: talleres / red de reparación (DWH on-prem)'
AS SELECT *, current_timestamp() AS _ingest_ts, 'dwh_onprem' AS _source FROM seguros_dwh_onprem.seguros_dwh.tb_talleres;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_siniestros COMMENT 'Bronce: siniestros de autos (DWH on-prem)'
AS SELECT *, current_timestamp() AS _ingest_ts, 'dwh_onprem' AS _source FROM seguros_dwh_onprem.seguros_dwh.tb_siniestros;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_movtos_siniestro COMMENT 'Bronce: movimientos de siniestro — reservas, pagos, recuperaciones (DWH on-prem)'
AS SELECT *, current_timestamp() AS _ingest_ts, 'dwh_onprem' AS _source FROM seguros_dwh_onprem.seguros_dwh.tb_movtos_siniestro;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_valuaciones COMMENT 'Bronce: valuaciones de taller (DWH on-prem)'
AS SELECT *, current_timestamp() AS _ingest_ts, 'dwh_onprem' AS _source FROM seguros_dwh_onprem.seguros_dwh.tb_valuaciones;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_terceros_siniestro COMMENT 'Bronce: terceros involucrados en siniestros (DWH on-prem) — contiene PII'
AS SELECT *, current_timestamp() AS _ingest_ts, 'dwh_onprem' AS _source FROM seguros_dwh_onprem.seguros_dwh.tb_terceros_siniestro;

-- COMMAND ----------
-- MAGIC %md ## Capa Bronce — Créditos (federado, AWS)

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW bronze_creditos_personales COMMENT 'Bronce: créditos personales (BD AWS)'
AS SELECT *, current_timestamp() AS _ingest_ts, 'creditos_aws' AS _source FROM seguros_creditos_aws.seguros_creditos.creditos_personales;

-- COMMAND ----------
-- MAGIC %md ## Capa Bronce — Data lake Ciencia de Datos (Auto Loader, incremental)

-- COMMAND ----------
CREATE OR REFRESH STREAMING TABLE bronze_app_trip_summary
COMMENT 'Bronce: resumen mensual de manejo por dispositivo (telemetría app de autos, JSON incremental)'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingest_ts
FROM STREAM read_files('/Volumes/demo_catalog/seguros_demo/datalake_ds/app_autos/trip_summary/', format => 'json');

-- COMMAND ----------
CREATE OR REFRESH STREAMING TABLE bronze_app_fnol
COMMENT 'Bronce: reporte de siniestro desde la app (FNOL) con GPS, fotos e impacto (JSON incremental)'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingest_ts
FROM STREAM read_files('/Volumes/demo_catalog/seguros_demo/datalake_ds/app_autos/fnol/', format => 'json');

-- COMMAND ----------
-- MAGIC %md ## Capa Plata — Catálogos

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW silver_productos (
  CONSTRAINT pk_producto EXPECT (id_producto IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT ramo_autos  EXPECT (ramo = 'Autos') ON VIOLATION DROP ROW
) COMMENT 'Plata: productos de autos'
AS SELECT CAST(id_producto AS INT) id_producto, cve_producto, nombre_producto, ramo, subramo FROM bronze_productos;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW silver_agentes (
  CONSTRAINT pk_agente   EXPECT (id_agente IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT canal_valido EXPECT (canal IN ('Agente','Banca Seguros','Tienda Aliada','Digital','Broker')) ON VIOLATION DROP ROW
) COMMENT 'Plata: agentes y canales de venta'
AS SELECT CAST(id_agente AS INT) id_agente, cve_agente, trim(nombre_agente) nombre_agente, canal, oficina, region,
          fecha_alta, activo
FROM bronze_agentes;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW silver_talleres (
  CONSTRAINT pk_taller   EXPECT (id_taller IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT tipo_valido EXPECT (tipo IN ('Agencia','Multimarca','Independiente')) ON VIOLATION DROP ROW
) COMMENT 'Plata: talleres de la red'
AS SELECT CAST(id_taller AS INT) id_taller, nombre_taller, tipo, estado, municipio FROM bronze_talleres;

-- COMMAND ----------
-- MAGIC %md ## Capa Plata — Clientes y emisión

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW silver_clientes (
  CONSTRAINT pk_cliente     EXPECT (id_cliente IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT rfc_formato    EXPECT (rfc RLIKE '^[A-Z&Ñ]{4}[0-9]{6}[A-Z0-9]{3}$') ON VIOLATION DROP ROW,
  CONSTRAINT curp_formato   EXPECT (curp RLIKE '^[A-Z]{4}[0-9]{6}[HM][A-Z]{5}[0-9A-Z][0-9]$') ON VIOLATION DROP ROW,
  CONSTRAINT edad_valida    EXPECT (edad BETWEEN 18 AND 100) ON VIOLATION DROP ROW,
  CONSTRAINT genero_valido  EXPECT (genero IN ('M','F')) ON VIOLATION DROP ROW,
  CONSTRAINT email_formato  EXPECT (email RLIKE '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$'),
  CONSTRAINT telefono_10dig EXPECT (telefono RLIKE '^[0-9]{10}$'),
  CONSTRAINT cp_5dig        EXPECT (codigo_postal RLIKE '^[0-9]{5}$')
) COMMENT 'Plata: registro único de cliente (golden record) — contiene PII'
AS SELECT
  CAST(id_cliente AS INT) id_cliente,
  initcap(trim(nombre)) nombre, initcap(trim(apellido_paterno)) apellido_paterno, initcap(trim(apellido_materno)) apellido_materno,
  concat_ws(' ', initcap(trim(nombre)), initcap(trim(apellido_paterno)), initcap(trim(apellido_materno))) nombre_completo,
  upper(trim(rfc)) rfc, upper(trim(curp)) curp, fecha_nacimiento,
  CAST(floor(months_between(DATE'2026-10-13', fecha_nacimiento) / 12) AS INT) edad,
  genero, lower(trim(email)) email, regexp_replace(telefono, '[^0-9]', '') telefono,
  estado, municipio, codigo_postal, fecha_alta, segmento
FROM bronze_clientes;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW silver_polizas (
  CONSTRAINT pk_poliza          EXPECT (id_poliza IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT fk_cliente         EXPECT (id_cliente IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT vigencia_coherente EXPECT (fin_vigencia > inicio_vigencia) ON VIOLATION DROP ROW,
  CONSTRAINT prima_positiva     EXPECT (prima_neta_anual > 0) ON VIOLATION DROP ROW,
  CONSTRAINT suma_positiva      EXPECT (suma_asegurada > 0) ON VIOLATION DROP ROW,
  CONSTRAINT estatus_valido     EXPECT (estatus IN ('Vigente','Vencida','Cancelada')) ON VIOLATION DROP ROW,
  CONSTRAINT forma_pago_valida  EXPECT (forma_pago IN ('Anual','Semestral','Trimestral','Mensual')) ON VIOLATION DROP ROW,
  CONSTRAINT emision_no_futura  EXPECT (fecha_emision <= DATE'2026-10-13') ON VIOLATION DROP ROW,
  CONSTRAINT cancelacion_en_vig EXPECT (fecha_cancelacion IS NULL OR fecha_cancelacion BETWEEN inicio_vigencia AND fin_vigencia),
  CONSTRAINT cancelada_con_fecha EXPECT (estatus <> 'Cancelada' OR fecha_cancelacion IS NOT NULL)
) COMMENT 'Plata: pólizas de autos'
AS SELECT
  CAST(id_poliza AS BIGINT) id_poliza, num_poliza, CAST(id_cliente AS INT) id_cliente, CAST(id_producto AS INT) id_producto,
  CAST(id_agente AS INT) id_agente, fecha_emision, inicio_vigencia, fin_vigencia,
  CAST(suma_asegurada AS DECIMAL(14,2)) suma_asegurada, CAST(prima_neta_anual AS DECIMAL(12,2)) prima_neta_anual,
  forma_pago, estatus, fecha_cancelacion, es_renovacion
FROM bronze_polizas;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW silver_vehiculos (
  CONSTRAINT pk_vehiculo    EXPECT (id_vehiculo IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT fk_poliza      EXPECT (id_poliza IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT anio_valido    EXPECT (anio_modelo BETWEEN 1990 AND 2027) ON VIOLATION DROP ROW,
  CONSTRAINT valor_positivo EXPECT (valor_comercial > 0) ON VIOLATION DROP ROW,
  CONSTRAINT uso_valido     EXPECT (uso IN ('Particular','Plataforma','Carga ligera')) ON VIOLATION DROP ROW,
  CONSTRAINT vin_17         EXPECT (length(num_serie_vin) = 17 AND num_serie_vin NOT RLIKE '[IOQ]')
) COMMENT 'Plata: vehículos asegurados'
AS SELECT CAST(id_vehiculo AS BIGINT) id_vehiculo, CAST(id_poliza AS BIGINT) id_poliza, marca, submarca,
          CAST(anio_modelo AS INT) anio_modelo, uso, CAST(valor_comercial AS DECIMAL(12,2)) valor_comercial,
          upper(num_serie_vin) num_serie_vin, upper(placas) placas, app_conectada
FROM bronze_vehiculos;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW silver_poliza_coberturas (
  CONSTRAINT pk_poliza_cob  EXPECT (id_poliza IS NOT NULL AND id_cobertura IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT prima_no_neg   EXPECT (prima_cobertura >= 0) ON VIOLATION DROP ROW,
  CONSTRAINT deducible_rng  EXPECT (deducible_pct BETWEEN 0 AND 100) ON VIOLATION DROP ROW,
  CONSTRAINT suma_no_neg    EXPECT (suma_asegurada IS NULL OR suma_asegurada > 0)
) COMMENT 'Plata: coberturas contratadas por póliza'
AS SELECT CAST(id_poliza AS BIGINT) id_poliza, CAST(id_cobertura AS INT) id_cobertura,
          CAST(suma_asegurada AS DECIMAL(14,2)) suma_asegurada, CAST(deducible_pct AS DOUBLE) deducible_pct,
          CAST(prima_cobertura AS DECIMAL(12,2)) prima_cobertura
FROM bronze_poliza_coberturas;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW silver_conductores (
  CONSTRAINT pk_conductor        EXPECT (id_conductor IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT edad_conducir       EXPECT (edad BETWEEN 18 AND 90) ON VIOLATION DROP ROW,
  CONSTRAINT licencia_coherente  EXPECT (anios_licencia BETWEEN 0 AND edad - 16),
  CONSTRAINT titular_con_cliente EXPECT (NOT es_titular OR id_cliente IS NOT NULL)
) COMMENT 'Plata: conductores habituales'
AS SELECT CAST(id_conductor AS BIGINT) id_conductor, CAST(id_poliza AS BIGINT) id_poliza, CAST(id_cliente AS INT) id_cliente,
          es_titular, CAST(edad AS INT) edad, genero, CAST(anios_licencia AS INT) anios_licencia, tipo_licencia, codigo_postal
FROM bronze_conductores;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW silver_cotizaciones (
  CONSTRAINT pk_cotizacion        EXPECT (id_cotizacion IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT prima_positiva       EXPECT (prima_cotizada > 0) ON VIOLATION DROP ROW,
  CONSTRAINT fecha_no_futura      EXPECT (fecha_cotizacion <= DATE'2026-10-13') ON VIOLATION DROP ROW,
  CONSTRAINT canal_valido         EXPECT (canal IN ('App Autos FSI','Portal Web','Comparador Externo','Agente','Módulo Tienda Aliada')) ON VIOLATION DROP ROW,
  CONSTRAINT convertida_con_poliza EXPECT (NOT convertida OR id_poliza IS NOT NULL),
  CONSTRAINT edad_conductor_rng   EXPECT (edad_conductor BETWEEN 18 AND 90)
) COMMENT 'Plata: cotizaciones de todos los canales (incluye integraciones externas)'
AS SELECT CAST(id_cotizacion AS BIGINT) id_cotizacion, fecha_cotizacion, canal, sistema_origen, codigo_postal, estado,
          marca, submarca, CAST(anio_modelo AS INT) anio_modelo, CAST(edad_conductor AS INT) edad_conductor,
          CAST(id_producto AS INT) id_producto, CAST(prima_cotizada AS DECIMAL(12,2)) prima_cotizada, convertida,
          CAST(id_poliza AS BIGINT) id_poliza
FROM bronze_cotizaciones;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW silver_recibos (
  CONSTRAINT pk_recibo           EXPECT (id_recibo IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT importe_positivo    EXPECT (importe > 0) ON VIOLATION DROP ROW,
  CONSTRAINT estatus_valido      EXPECT (estatus IN ('Pagado','Pendiente','Cancelado')) ON VIOLATION DROP ROW,
  CONSTRAINT pagado_con_fecha    EXPECT (estatus <> 'Pagado' OR fecha_pago IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT pago_no_anticipado  EXPECT (fecha_pago IS NULL OR fecha_pago >= date_sub(fecha_vencimiento, 60))
) COMMENT 'Plata: recibos de prima (cobranza)'
AS SELECT CAST(id_recibo AS BIGINT) id_recibo, CAST(id_poliza AS BIGINT) id_poliza, CAST(num_recibo AS INT) num_recibo,
          fecha_vencimiento, fecha_pago, CAST(importe AS DECIMAL(12,2)) importe, estatus,
          CASE WHEN fecha_pago IS NOT NULL THEN datediff(fecha_pago, fecha_vencimiento) END dias_pago_vs_vencimiento
FROM bronze_recibos;

-- COMMAND ----------
-- MAGIC %md ## Capa Plata — Siniestros

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW silver_siniestros (
  CONSTRAINT pk_siniestro          EXPECT (id_siniestro IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT reporte_post_ocurr    EXPECT (fecha_reporte >= fecha_ocurrencia) ON VIOLATION DROP ROW,
  CONSTRAINT ocurrencia_no_futura  EXPECT (fecha_ocurrencia <= TIMESTAMP'2026-10-13 23:59:59') ON VIOLATION DROP ROW,
  CONSTRAINT monto_no_negativo     EXPECT (monto_reclamado >= 0) ON VIOLATION DROP ROW,
  CONSTRAINT cobertura_valida      EXPECT (cobertura IN ('Daños Materiales','Responsabilidad Civil','Robo Total','Cristales','Gastos Médicos Ocupantes')) ON VIOLATION DROP ROW,
  CONSTRAINT estatus_valido        EXPECT (estatus IN ('Abierto','Cerrado','Rechazado','En investigación')) ON VIOLATION DROP ROW,
  CONSTRAINT cerrado_con_fecha     EXPECT (estatus NOT IN ('Cerrado','Rechazado') OR fecha_cierre IS NOT NULL)
) COMMENT 'Plata: siniestros de autos (solo la entidad siniestro; el cruce con la póliza se valida en oro, fact_siniestros)'
AS SELECT
  CAST(s.id_siniestro AS BIGINT) id_siniestro, s.num_siniestro, CAST(s.id_poliza AS BIGINT) id_poliza,
  CAST(s.id_ajustador AS INT) id_ajustador, CAST(s.id_taller AS INT) id_taller,
  CAST(s.fecha_ocurrencia AS TIMESTAMP) fecha_ocurrencia, CAST(s.fecha_reporte AS TIMESTAMP) fecha_reporte,
  s.cobertura, s.causa, s.estado_ocurrencia, s.canal_reporte,
  CAST(s.monto_reclamado AS DECIMAL(14,2)) monto_reclamado, CAST(s.reserva_inicial AS DECIMAL(14,2)) reserva_inicial,
  CAST(s.deducible AS DECIMAL(12,2)) deducible, s.reporte_autoridad, CAST(s.num_terceros AS INT) num_terceros,
  s.estatus, s.fecha_cierre, s.fraude_confirmado,
  ROUND((unix_timestamp(CAST(s.fecha_reporte AS TIMESTAMP)) - unix_timestamp(CAST(s.fecha_ocurrencia AS TIMESTAMP))) / 3600, 1) horas_a_reporte,
  hour(CAST(s.fecha_ocurrencia AS TIMESTAMP)) IN (22, 23, 0, 1, 2, 3, 4) ocurrencia_nocturna
FROM bronze_siniestros s;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW silver_movtos_siniestro (
  CONSTRAINT pk_movimiento    EXPECT (id_movimiento IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT tipo_valido      EXPECT (tipo_movimiento IN ('Pago','Ajuste Reserva','Recuperación')) ON VIOLATION DROP ROW,
  CONSTRAINT pago_positivo    EXPECT (tipo_movimiento <> 'Pago' OR importe > 0) ON VIOLATION DROP ROW,
  CONSTRAINT recuperacion_neg EXPECT (tipo_movimiento <> 'Recuperación' OR importe < 0) ON VIOLATION DROP ROW,
  CONSTRAINT fecha_no_futura  EXPECT (fecha_movimiento <= DATE'2026-10-13') ON VIOLATION DROP ROW
) COMMENT 'Plata: movimientos de siniestro (reservas, pagos, recuperaciones)'
AS SELECT CAST(id_movimiento AS BIGINT) id_movimiento, CAST(id_siniestro AS BIGINT) id_siniestro, fecha_movimiento,
          tipo_movimiento, CAST(importe AS DECIMAL(14,2)) importe
FROM bronze_movtos_siniestro;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW silver_valuaciones (
  CONSTRAINT pk_valuacion         EXPECT (id_valuacion IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT autorizado_positivo  EXPECT (monto_autorizado > 0) ON VIOLATION DROP ROW,
  CONSTRAINT pct_originales_rng   EXPECT (pct_piezas_originales BETWEEN 0 AND 1) ON VIOLATION DROP ROW,
  CONSTRAINT piezas_positivas     EXPECT (num_piezas > 0) ON VIOLATION DROP ROW,
  CONSTRAINT presupuesto_razonable EXPECT (monto_presupuesto_taller <= monto_autorizado * 1.3)
) COMMENT 'Plata: valuaciones de taller — la regla WARN presupuesto_razonable marca posibles inflados'
AS SELECT CAST(id_valuacion AS BIGINT) id_valuacion, CAST(id_siniestro AS BIGINT) id_siniestro, CAST(id_taller AS INT) id_taller,
          fecha_valuacion, CAST(monto_presupuesto_taller AS DECIMAL(14,2)) monto_presupuesto_taller,
          CAST(monto_autorizado AS DECIMAL(14,2)) monto_autorizado, CAST(num_piezas AS INT) num_piezas,
          CAST(pct_piezas_originales AS DOUBLE) pct_piezas_originales, CAST(horas_mano_obra AS DOUBLE) horas_mano_obra,
          CAST(dias_reparacion AS INT) dias_reparacion,
          ROUND(monto_presupuesto_taller / monto_autorizado, 3) ratio_presupuesto_autorizado
FROM bronze_valuaciones;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW silver_terceros_siniestro (
  CONSTRAINT pk_tercero      EXPECT (id_tercero IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT tipo_valido     EXPECT (tipo_tercero IN ('Vehículo','Peatón','Propiedad')) ON VIOLATION DROP ROW,
  CONSTRAINT monto_no_neg    EXPECT (monto_reclamado_tercero >= 0) ON VIOLATION DROP ROW,
  CONSTRAINT telefono_10dig  EXPECT (telefono_tercero RLIKE '^[0-9]{10}$'),
  CONSTRAINT vehiculo_placas EXPECT (tipo_tercero <> 'Vehículo' OR placas_tercero IS NOT NULL)
) COMMENT 'Plata: terceros involucrados — contiene PII'
AS SELECT CAST(id_tercero AS BIGINT) id_tercero, CAST(id_siniestro AS BIGINT) id_siniestro, tipo_tercero,
          initcap(trim(nombre_tercero)) nombre_tercero, regexp_replace(telefono_tercero, '[^0-9]', '') telefono_tercero,
          upper(placas_tercero) placas_tercero, aseguradora_tercero,
          CAST(monto_reclamado_tercero AS DECIMAL(14,2)) monto_reclamado_tercero
FROM bronze_terceros_siniestro;

-- COMMAND ----------
-- MAGIC %md ## Capa Plata — Créditos (AWS): normalización cross-source

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW silver_creditos_personales (
  CONSTRAINT pk_credito      EXPECT (credito_id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT rfc_formato     EXPECT (rfc RLIKE '^[A-Z&Ñ]{4}[0-9]{6}[A-Z0-9]{3}$') ON VIOLATION DROP ROW,
  CONSTRAINT monto_positivo  EXPECT (monto_original > 0) ON VIOLATION DROP ROW,
  CONSTRAINT saldo_no_neg    EXPECT (saldo >= 0) ON VIOLATION DROP ROW,
  CONSTRAINT estatus_valido  EXPECT (estatus IN ('Al corriente','Atrasado','Vencido','Liquidado')) ON VIOLATION DROP ROW,
  CONSTRAINT dpd_coherente   EXPECT ((estatus IN ('Al corriente','Liquidado')) = (dias_atraso = 0)),
  CONSTRAINT tasa_razonable  EXPECT (tasa_anual_pct BETWEEN 5 AND 80)
) COMMENT 'Plata: créditos personales normalizados a la nomenclatura del grupo (RFC en mayúsculas, estatus en español)'
AS SELECT
  CAST(credito_id AS BIGINT) credito_id, CAST(customer_id AS INT) id_cliente,
  upper(trim(customer_rfc)) rfc,
  customer_rfc <> upper(trim(customer_rfc)) rfc_corregido,
  product producto, origination_date fecha_originacion, CAST(term_months AS INT) plazo_meses,
  CAST(amount AS DECIMAL(14,2)) monto_original, CAST(rate_pct AS DOUBLE) tasa_anual_pct,
  CAST(balance AS DECIMAL(14,2)) saldo, CAST(days_past_due AS INT) dias_atraso,
  CASE status WHEN 'current' THEN 'Al corriente' WHEN 'delinquent' THEN 'Atrasado'
              WHEN 'default' THEN 'Vencido' WHEN 'paid_off' THEN 'Liquidado' END estatus
FROM bronze_creditos_personales;

-- COMMAND ----------
-- MAGIC %md ## Capa Plata — Telemetría app (streaming incremental)

-- COMMAND ----------
CREATE OR REFRESH STREAMING TABLE silver_app_trip_summary (
  CONSTRAINT poliza_presente EXPECT (id_poliza IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT km_no_negativo  EXPECT (km_recorridos >= 0) ON VIOLATION DROP ROW,
  CONSTRAINT score_0a100     EXPECT (score_manejo BETWEEN 0 AND 100) ON VIOLATION DROP ROW,
  CONSTRAINT nocturno_pct    EXPECT (pct_manejo_nocturno BETWEEN 0 AND 1) ON VIOLATION DROP ROW,
  CONSTRAINT km_razonable    EXPECT (km_recorridos <= 15000)
) COMMENT 'Plata: resumen mensual de manejo por póliza (app de autos)'
AS SELECT
  CAST(id_poliza AS BIGINT) id_poliza, device_id, to_date(concat(mes, '-01')) mes,
  CAST(km_recorridos AS DOUBLE) km_recorridos, CAST(num_viajes AS INT) num_viajes,
  CAST(frenados_bruscos AS INT) frenados_bruscos, CAST(excesos_velocidad AS INT) excesos_velocidad,
  CAST(pct_manejo_nocturno AS DOUBLE) pct_manejo_nocturno, CAST(uso_celular_min AS DOUBLE) uso_celular_min,
  CAST(score_manejo AS INT) score_manejo,
  ROUND(CAST(frenados_bruscos AS DOUBLE) / NULLIF(km_recorridos, 0) * 100, 2) frenados_por_100km,
  _source_file, _ingest_ts
FROM STREAM(bronze_app_trip_summary);

-- COMMAND ----------
CREATE OR REFRESH STREAMING TABLE silver_app_fnol (
  CONSTRAINT siniestro_presente EXPECT (num_siniestro IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT gps_en_mexico      EXPECT (gps_lat BETWEEN 14.5 AND 32.8 AND gps_lon BETWEEN -118.5 AND -86.5) ON VIOLATION DROP ROW,
  CONSTRAINT fotos_no_negativas EXPECT (fotos_adjuntas >= 0) ON VIOLATION DROP ROW,
  CONSTRAINT impacto_razonable  EXPECT (impacto_detectado_g BETWEEN 0 AND 15),
  CONSTRAINT ubicacion_coincide EXPECT (distancia_km_ubicacion_declarada <= 5)
) COMMENT 'Plata: FNOL de la app — la regla WARN ubicacion_coincide marca GPS lejano a la ubicación declarada'
AS SELECT
  num_siniestro, CAST(id_poliza AS BIGINT) id_poliza, device_id, CAST(event_ts AS TIMESTAMP) fecha_reporte_app,
  CAST(gps_lat AS DOUBLE) gps_lat, CAST(gps_lon AS DOUBLE) gps_lon,
  CAST(distancia_km_ubicacion_declarada AS DOUBLE) distancia_km_ubicacion_declarada,
  CAST(fotos_adjuntas AS INT) fotos_adjuntas, CAST(video_adjunto AS BOOLEAN) video_adjunto,
  CAST(velocidad_previa_kmh AS DOUBLE) velocidad_previa_kmh, CAST(impacto_detectado_g AS DOUBLE) impacto_detectado_g,
  app_version, _source_file, _ingest_ts
FROM STREAM(bronze_app_fnol);
