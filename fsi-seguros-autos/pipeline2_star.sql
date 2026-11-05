-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Aseguradora FSI · Autos — Pipeline Medallion · Capa Oro: Modelo Estrella + Actuarial
-- MAGIC Lee de `demo_catalog.seguros_demo.silver_*` y construye dimensiones conformadas + hechos.
-- MAGIC
-- MAGIC | Hecho | Grano | Uso |
-- MAGIC |---|---|---|
-- MAGIC | `fact_polizas` | póliza | prima emitida/devengada, exposición, cartera |
-- MAGIC | `fact_siniestros` | siniestro | incurrido, siniestralidad, señales de fraude |
-- MAGIC | `fact_movtos_siniestro` | movimiento | triángulos de desarrollo (actuaría) |
-- MAGIC | `fact_cotizaciones` | cotización | embudo comercial por canal (incl. comparadores) |
-- MAGIC | `fact_telemetria_mensual` | póliza × mes | manejo (app) vs siniestralidad |
-- MAGIC
-- MAGIC **Actuarial (reservas por chain-ladder):** `act_triangulo`, `act_factores_desarrollo`, `act_reservas`, `act_siniestralidad_periodo`.
-- MAGIC
-- MAGIC Fecha de corte del demo: **2026-10-13**.

-- COMMAND ----------
-- MAGIC %md ## Dimensiones

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW dim_fecha
COMMENT 'Dimensión calendario 2021-2026'
AS SELECT
  CAST(date_format(f, 'yyyyMMdd') AS INT) fecha_key, f fecha, year(f) anio, quarter(f) trimestre, month(f) mes,
  date_format(f, 'yyyy-MM') anio_mes,
  element_at(array('Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'), month(f)) nombre_mes,
  weekofyear(f) semana,
  element_at(array('Domingo','Lunes','Martes','Miércoles','Jueves','Viernes','Sábado'), dayofweek(f)) dia_semana,
  dayofweek(f) IN (1, 7) es_fin_de_semana
FROM (SELECT explode(sequence(DATE'2021-01-01', DATE'2026-12-31', INTERVAL 1 DAY)) f);

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW dim_cliente (
  CONSTRAINT pk_cliente EXPECT (id_cliente IS NOT NULL) ON VIOLATION FAIL UPDATE
) COMMENT 'Dimensión cliente — enriquecida con su posición de crédito (BD AWS) vía RFC, sin duplicar sistemas. Contiene PII.'
AS WITH cred AS (
  SELECT rfc, COUNT(*) num_creditos, SUM(saldo) saldo_credito,
         MAX(CASE estatus WHEN 'Vencido' THEN 3 WHEN 'Atrasado' THEN 2 WHEN 'Al corriente' THEN 1 ELSE 0 END) peor_estatus_n
  FROM demo_catalog.seguros_demo.silver_creditos_personales GROUP BY rfc
)
SELECT
  c.id_cliente, c.nombre_completo, c.rfc, c.curp, c.email, c.telefono, c.genero, c.fecha_nacimiento, c.edad,
  CASE WHEN c.edad < 25 THEN '18-24' WHEN c.edad < 35 THEN '25-34' WHEN c.edad < 45 THEN '35-44'
       WHEN c.edad < 55 THEN '45-54' WHEN c.edad < 65 THEN '55-64' ELSE '65+' END rango_edad,
  c.estado, c.municipio, c.codigo_postal,
  CASE WHEN c.estado IN ('Ciudad de México','Estado de México','Puebla','Morelos') THEN 'Centro'
       WHEN c.estado IN ('Jalisco','Michoacán') THEN 'Occidente'
       WHEN c.estado IN ('Nuevo León','Chihuahua','Coahuila','Tamaulipas') THEN 'Norte'
       WHEN c.estado IN ('Guanajuato','Querétaro','San Luis Potosí','Aguascalientes') THEN 'Bajío'
       WHEN c.estado IN ('Veracruz','Yucatán','Quintana Roo') THEN 'Sureste'
       WHEN c.estado IN ('Baja California','Sonora','Sinaloa') THEN 'Noroeste' ELSE 'Otra' END region,
  c.segmento, c.fecha_alta,
  CAST(floor(months_between(DATE'2026-10-13', c.fecha_alta) / 12) AS INT) antiguedad_anios,
  cr.rfc IS NOT NULL tiene_credito_grupo,
  COALESCE(cr.num_creditos, 0) num_creditos,
  COALESCE(cr.saldo_credito, 0) saldo_credito,
  CASE cr.peor_estatus_n WHEN 3 THEN 'Vencido' WHEN 2 THEN 'Atrasado' WHEN 1 THEN 'Al corriente'
       WHEN 0 THEN 'Liquidado' ELSE 'Sin crédito' END estatus_credito
FROM demo_catalog.seguros_demo.silver_clientes c
LEFT JOIN cred cr ON c.rfc = cr.rfc;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW dim_producto COMMENT 'Dimensión producto (paquete de autos)'
AS SELECT id_producto, cve_producto, nombre_producto, subramo,
          CASE id_producto WHEN 1 THEN 'Amplia' WHEN 2 THEN 'Limitada' WHEN 3 THEN 'RC' WHEN 4 THEN 'Plataformas'
                           WHEN 5 THEN 'Flotilla' WHEN 6 THEN 'Amplia Plus' END paquete
FROM demo_catalog.seguros_demo.silver_productos;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW dim_agente COMMENT 'Dimensión agente / canal de venta'
AS SELECT id_agente, cve_agente, nombre_agente, canal, oficina, region region_agente, fecha_alta, activo
FROM demo_catalog.seguros_demo.silver_agentes;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW dim_taller COMMENT 'Dimensión taller (red de reparación)'
AS SELECT id_taller, nombre_taller, tipo tipo_taller, estado estado_taller, municipio municipio_taller
FROM demo_catalog.seguros_demo.silver_talleres;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW dim_vehiculo (
  CONSTRAINT pk_vehiculo EXPECT (id_vehiculo IS NOT NULL) ON VIOLATION FAIL UPDATE
) COMMENT 'Dimensión vehículo asegurado'
AS SELECT
  id_vehiculo, id_poliza, marca, submarca, anio_modelo,
  2026 - anio_modelo antiguedad_anios,
  CASE WHEN 2026 - anio_modelo <= 2 THEN '0-2 años' WHEN 2026 - anio_modelo <= 5 THEN '3-5 años'
       WHEN 2026 - anio_modelo <= 10 THEN '6-10 años' ELSE '11+ años' END rango_antiguedad,
  uso, valor_comercial,
  CASE WHEN valor_comercial < 200000 THEN '< $200K' WHEN valor_comercial < 400000 THEN '$200K-$400K'
       WHEN valor_comercial < 700000 THEN '$400K-$700K' ELSE '$700K+' END rango_valor,
  CASE WHEN marca IN ('BMW','Mercedes-Benz') THEN 'Premium' ELSE 'Masivo' END segmento_marca,
  app_conectada, num_serie_vin, placas
FROM demo_catalog.seguros_demo.silver_vehiculos;

-- COMMAND ----------
-- MAGIC %md ## Hechos

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW fact_polizas (
  CONSTRAINT pk_poliza        EXPECT (id_poliza IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT devengada_rng    EXPECT (prima_devengada BETWEEN 0 AND prima_neta_anual + 0.01) ON VIOLATION FAIL UPDATE,
  CONSTRAINT con_vehiculo     EXPECT (id_vehiculo IS NOT NULL)
) COMMENT 'Hecho póliza: prima emitida/devengada, exposición (años-vehículo), conductores, coberturas y cobranza'
AS WITH cond AS (
  SELECT id_poliza, COUNT(*) num_conductores, MIN(edad) edad_conductor_min, MAX(CAST(edad < 25 AS INT)) = 1 tiene_conductor_joven
  FROM demo_catalog.seguros_demo.silver_conductores GROUP BY id_poliza
), cob AS (
  SELECT id_poliza, COUNT(*) num_coberturas, MAX(CAST(id_cobertura = 1 AS INT)) = 1 cubre_danios_materiales,
         MAX(CAST(id_cobertura = 2 AS INT)) = 1 cubre_robo_total
  FROM demo_catalog.seguros_demo.silver_poliza_coberturas GROUP BY id_poliza
), rec AS (
  SELECT id_poliza, SUM(CASE WHEN estatus = 'Pagado' THEN importe ELSE 0 END) prima_cobrada,
         COUNT_IF(estatus = 'Pendiente' AND fecha_vencimiento < DATE'2026-10-13') recibos_vencidos
  FROM demo_catalog.seguros_demo.silver_recibos GROUP BY id_poliza
), base AS (
  SELECT p.*, v.id_vehiculo,
         LEAST(COALESCE(p.fecha_cancelacion, p.fin_vigencia), p.fin_vigencia, DATE'2026-10-13') fin_efectiva
  FROM demo_catalog.seguros_demo.silver_polizas p
  LEFT JOIN demo_catalog.seguros_demo.silver_vehiculos v ON p.id_poliza = v.id_poliza
)
SELECT
  b.id_poliza, b.num_poliza, b.id_cliente, b.id_producto, b.id_agente, b.id_vehiculo, dc.region,
  CAST(date_format(b.fecha_emision, 'yyyyMMdd') AS INT) fecha_emision_key,
  CAST(date_format(b.inicio_vigencia, 'yyyyMMdd') AS INT) inicio_vigencia_key,
  b.fecha_emision, b.inicio_vigencia, b.fin_vigencia, b.fecha_cancelacion, year(b.inicio_vigencia) anio_suscripcion,
  b.forma_pago, b.estatus, b.es_renovacion,
  b.suma_asegurada, b.prima_neta_anual,
  GREATEST(datediff(b.fin_efectiva, b.inicio_vigencia), 0) dias_expuestos,
  ROUND(GREATEST(datediff(b.fin_efectiva, b.inicio_vigencia), 0) / 365.0, 4) exposicion_anios,
  ROUND(b.prima_neta_anual * LEAST(1.0, GREATEST(datediff(b.fin_efectiva, b.inicio_vigencia), 0)
        / datediff(b.fin_vigencia, b.inicio_vigencia)), 2) prima_devengada,
  COALESCE(r.prima_cobrada, 0) prima_cobrada, COALESCE(r.recibos_vencidos, 0) recibos_vencidos,
  c.num_conductores, c.edad_conductor_min, c.tiene_conductor_joven,
  k.num_coberturas, k.cubre_danios_materiales, k.cubre_robo_total
FROM base b
LEFT JOIN cond c ON b.id_poliza = c.id_poliza
LEFT JOIN cob k ON b.id_poliza = k.id_poliza
LEFT JOIN rec r ON b.id_poliza = r.id_poliza
LEFT JOIN dim_cliente dc ON b.id_cliente = dc.id_cliente;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW fact_siniestros (
  CONSTRAINT pk_siniestro           EXPECT (id_siniestro IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT fk_poliza_existe       EXPECT (id_cliente IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT ocurrencia_en_vigencia EXPECT (to_date(fecha_ocurrencia) BETWEEN inicio_vigencia AND fin_vigencia),
  CONSTRAINT monto_vs_suma          EXPECT (monto_reclamado <= suma_asegurada * 1.05),
  CONSTRAINT incurrido_no_neg       EXPECT (incurrido >= 0)
) COMMENT 'Hecho siniestro: pagado, reserva pendiente, recuperaciones, incurrido + señales operativas de fraude (taller, terceros recurrentes, app). Valida la integridad siniestro ⇄ póliza (existencia, vigencia, suma asegurada)'
AS WITH mov AS (
  SELECT id_siniestro,
         SUM(CASE WHEN tipo_movimiento = 'Pago' THEN importe ELSE 0 END) pagado,
         SUM(CASE WHEN tipo_movimiento = 'Ajuste Reserva' THEN importe ELSE 0 END)
           - SUM(CASE WHEN tipo_movimiento = 'Pago' THEN importe ELSE 0 END) reserva_pendiente,
         -SUM(CASE WHEN tipo_movimiento = 'Recuperación' THEN importe ELSE 0 END) recuperaciones
  FROM demo_catalog.seguros_demo.silver_movtos_siniestro GROUP BY id_siniestro
), tel_rec AS (  -- teléfonos de terceros que aparecen en 3+ siniestros distintos
  SELECT telefono_tercero FROM demo_catalog.seguros_demo.silver_terceros_siniestro
  GROUP BY telefono_tercero HAVING COUNT(DISTINCT id_siniestro) >= 3
), ter AS (
  SELECT t.id_siniestro, COUNT(*) terceros_registrados, COUNT(r.telefono_tercero) terceros_recurrentes,
         SUM(t.monto_reclamado_tercero) monto_reclamado_terceros
  FROM demo_catalog.seguros_demo.silver_terceros_siniestro t
  LEFT JOIN tel_rec r ON t.telefono_tercero = r.telefono_tercero
  GROUP BY t.id_siniestro
), prev AS (  -- siniestros previos del mismo cliente
  SELECT s.id_siniestro,
         COUNT(*) OVER (PARTITION BY p.id_cliente ORDER BY s.fecha_ocurrencia ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) siniestros_previos_cliente
  FROM demo_catalog.seguros_demo.silver_siniestros s
  JOIN demo_catalog.seguros_demo.silver_polizas p ON s.id_poliza = p.id_poliza
)
SELECT
  s.id_siniestro, s.num_siniestro, s.id_poliza, p.id_cliente, p.id_agente, p.id_producto, v.id_vehiculo, dc.region,
  s.id_ajustador, s.id_taller,
  CAST(date_format(s.fecha_ocurrencia, 'yyyyMMdd') AS INT) fecha_ocurrencia_key,
  CAST(date_format(s.fecha_reporte, 'yyyyMMdd') AS INT) fecha_reporte_key,
  s.fecha_ocurrencia, s.fecha_reporte, s.fecha_cierre, year(s.fecha_ocurrencia) anio_ocurrencia,
  s.cobertura, s.causa, s.estado_ocurrencia, s.canal_reporte, s.estatus,
  s.monto_reclamado, s.reserva_inicial, s.deducible, p.inicio_vigencia, p.fin_vigencia, p.suma_asegurada,
  COALESCE(m.pagado, 0) pagado, COALESCE(m.reserva_pendiente, 0) reserva_pendiente,
  COALESCE(m.recuperaciones, 0) recuperaciones,
  GREATEST(COALESCE(m.pagado, 0) + COALESCE(m.reserva_pendiente, 0) - COALESCE(m.recuperaciones, 0), 0) incurrido,
  -- señales de fraude
  datediff(to_date(s.fecha_ocurrencia), p.inicio_vigencia) dias_desde_inicio_vigencia,
  datediff(to_date(s.fecha_ocurrencia), p.inicio_vigencia) <= 30 primeros_30_dias,
  s.horas_a_reporte, s.ocurrencia_nocturna, s.reporte_autoridad, s.num_terceros,
  COALESCE(t.terceros_recurrentes, 0) terceros_recurrentes, COALESCE(t.monto_reclamado_terceros, 0) monto_reclamado_terceros,
  COALESCE(pr.siniestros_previos_cliente, 0) siniestros_previos_cliente,
  ROUND(s.monto_reclamado / NULLIF(v.valor_comercial, 0), 4) ratio_monto_valor_vehiculo,
  va.monto_presupuesto_taller, va.monto_autorizado, va.ratio_presupuesto_autorizado, va.pct_piezas_originales,
  f.distancia_km_ubicacion_declarada, f.fotos_adjuntas, f.video_adjunto, f.impacto_detectado_g,
  s.fraude_confirmado
FROM demo_catalog.seguros_demo.silver_siniestros s
LEFT JOIN demo_catalog.seguros_demo.silver_polizas p ON s.id_poliza = p.id_poliza
LEFT JOIN demo_catalog.seguros_demo.silver_vehiculos v ON s.id_poliza = v.id_poliza
LEFT JOIN mov m ON s.id_siniestro = m.id_siniestro
LEFT JOIN ter t ON s.id_siniestro = t.id_siniestro
LEFT JOIN prev pr ON s.id_siniestro = pr.id_siniestro
LEFT JOIN demo_catalog.seguros_demo.silver_valuaciones va ON s.id_siniestro = va.id_siniestro
LEFT JOIN demo_catalog.seguros_demo.silver_app_fnol f ON s.num_siniestro = f.num_siniestro
LEFT JOIN dim_cliente dc ON p.id_cliente = dc.id_cliente;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW fact_movtos_siniestro (
  CONSTRAINT pk_movimiento  EXPECT (id_movimiento IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT desarrollo_pos EXPECT (meses_desarrollo >= 0)
) COMMENT 'Hecho movimiento de siniestro con año de ocurrencia y mes de desarrollo — base de triángulos actuariales'
AS SELECT
  m.id_movimiento, m.id_siniestro, s.id_poliza, p.id_producto, s.cobertura,
  CAST(date_format(m.fecha_movimiento, 'yyyyMMdd') AS INT) fecha_movimiento_key,
  m.fecha_movimiento, m.tipo_movimiento, m.importe,
  year(s.fecha_ocurrencia) anio_ocurrencia,
  CAST(months_between(trunc(m.fecha_movimiento, 'MM'), trunc(to_date(s.fecha_ocurrencia), 'MM')) AS INT) meses_desarrollo,
  CAST(floor(months_between(trunc(m.fecha_movimiento, 'MM'), trunc(to_date(s.fecha_ocurrencia), 'MM')) / 12) AS INT) + 1 anio_desarrollo
FROM demo_catalog.seguros_demo.silver_movtos_siniestro m
JOIN demo_catalog.seguros_demo.silver_siniestros s ON m.id_siniestro = s.id_siniestro
JOIN demo_catalog.seguros_demo.silver_polizas p ON s.id_poliza = p.id_poliza;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW fact_cotizaciones (
  CONSTRAINT pk_cotizacion EXPECT (id_cotizacion IS NOT NULL) ON VIOLATION FAIL UPDATE
) COMMENT 'Hecho cotización: embudo comercial por canal, incluidas integraciones externas (comparadores)'
AS SELECT
  id_cotizacion, CAST(date_format(fecha_cotizacion, 'yyyyMMdd') AS INT) fecha_cotizacion_key, fecha_cotizacion,
  canal, sistema_origen, estado, marca, submarca, anio_modelo, edad_conductor, id_producto,
  prima_cotizada, convertida, id_poliza
FROM demo_catalog.seguros_demo.silver_cotizaciones;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW fact_telemetria_mensual (
  CONSTRAINT pk_poliza_mes EXPECT (id_poliza IS NOT NULL AND mes IS NOT NULL) ON VIOLATION FAIL UPDATE
) COMMENT 'Hecho póliza × mes: comportamiento de manejo (app) junto a siniestros del mes — base para seguro basado en uso'
AS WITH sin_mes AS (
  SELECT id_poliza, trunc(to_date(fecha_ocurrencia), 'MM') mes, COUNT(*) num_siniestros
  FROM demo_catalog.seguros_demo.silver_siniestros GROUP BY ALL
)
SELECT
  t.id_poliza, p.id_cliente, p.id_producto, v.id_vehiculo,
  CAST(date_format(t.mes, 'yyyyMMdd') AS INT) mes_key, t.mes,
  t.km_recorridos, t.num_viajes, t.frenados_bruscos, t.excesos_velocidad, t.pct_manejo_nocturno,
  t.uso_celular_min, t.score_manejo, t.frenados_por_100km,
  CASE WHEN t.score_manejo >= 85 THEN 'Excelente' WHEN t.score_manejo >= 70 THEN 'Bueno'
       WHEN t.score_manejo >= 55 THEN 'Regular' ELSE 'Riesgoso' END nivel_manejo,
  COALESCE(s.num_siniestros, 0) num_siniestros
FROM demo_catalog.seguros_demo.silver_app_trip_summary t
JOIN demo_catalog.seguros_demo.silver_polizas p ON t.id_poliza = p.id_poliza
LEFT JOIN demo_catalog.seguros_demo.silver_vehiculos v ON t.id_poliza = v.id_poliza
LEFT JOIN sin_mes s ON t.id_poliza = s.id_poliza AND t.mes = s.mes;

-- COMMAND ----------
-- MAGIC %md ## Actuarial — Triángulos de desarrollo y reservas (chain-ladder)
-- MAGIC - **Periodo de ocurrencia** = 12 meses que cierran el 30-sep (p. ej. 2026 = oct-2025 a sep-2026), para que cada diagonal
-- MAGIC   sea una evaluación completa a 12, 24, 36… meses. Valuación: **2026-09-30** (cierre del 3er trimestre).
-- MAGIC - Montos **netos de recuperaciones**. Pagado = pagos − recuperaciones; incurrido = pagado + reserva de caso.
-- MAGIC - Factores edad-a-edad ponderados por volumen; sin factor de cola (los pagos de RC terminan antes de 60 meses).

-- COMMAND ----------
CREATE OR REFRESH PRIVATE MATERIALIZED VIEW act_triangulo_observado
COMMENT 'Privada: triángulo observado (pagado/incurrido acumulado y siniestros reportados) por cobertura × periodo × desarrollo'
AS WITH mov AS (
  SELECT m.id_siniestro, m.cobertura, m.tipo_movimiento, m.importe,
         year(add_months(to_date(s.fecha_ocurrencia), 3)) periodo_ocurrencia,
         year(add_months(m.fecha_movimiento, 3)) - year(add_months(to_date(s.fecha_ocurrencia), 3)) + 1 periodo_desarrollo
  FROM fact_movtos_siniestro m
  JOIN fact_siniestros s ON m.id_siniestro = s.id_siniestro
  WHERE m.fecha_movimiento <= DATE'2026-09-30'
), incr AS (
  SELECT cobertura, periodo_ocurrencia, periodo_desarrollo,
         SUM(CASE WHEN tipo_movimiento IN ('Pago', 'Recuperación') THEN importe ELSE 0 END) pagado,
         SUM(CASE WHEN tipo_movimiento IN ('Ajuste Reserva', 'Recuperación') THEN importe ELSE 0 END) incurrido
  FROM mov GROUP BY ALL
), rep AS (
  SELECT cobertura, periodo_ocurrencia, periodo_desarrollo, COUNT(*) siniestros_nuevos
  FROM (SELECT id_siniestro, cobertura, periodo_ocurrencia, MIN(periodo_desarrollo) periodo_desarrollo FROM mov GROUP BY ALL)
  GROUP BY ALL
), grid AS (
  SELECT c.cobertura, p.periodo_ocurrencia, d periodo_desarrollo
  FROM (SELECT DISTINCT cobertura FROM incr) c
  CROSS JOIN (SELECT DISTINCT periodo_ocurrencia FROM incr) p
  LATERAL VIEW explode(sequence(1, 2026 - p.periodo_ocurrencia + 1)) t AS d
)
SELECT g.cobertura, g.periodo_ocurrencia, g.periodo_desarrollo,
       COALESCE(i.pagado, 0) pagado_incremental,
       SUM(COALESCE(i.pagado, 0)) OVER w pagado_acumulado,
       SUM(COALESCE(i.incurrido, 0)) OVER w incurrido_acumulado,
       SUM(COALESCE(r.siniestros_nuevos, 0)) OVER w siniestros_reportados
FROM grid g
LEFT JOIN incr i USING (cobertura, periodo_ocurrencia, periodo_desarrollo)
LEFT JOIN rep r USING (cobertura, periodo_ocurrencia, periodo_desarrollo)
WINDOW w AS (PARTITION BY g.cobertura, g.periodo_ocurrencia ORDER BY g.periodo_desarrollo);

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW act_factores_desarrollo
COMMENT 'Factores edad-a-edad (chain-ladder, ponderados por volumen) y factor a último por cobertura'
AS WITH f AS (
  SELECT a.cobertura, a.periodo_desarrollo, SUM(b.pagado_acumulado) / NULLIF(SUM(a.pagado_acumulado), 0) factor,
         COUNT(*) periodos_base
  FROM act_triangulo_observado a
  JOIN act_triangulo_observado b ON a.cobertura = b.cobertura AND a.periodo_ocurrencia = b.periodo_ocurrencia
   AND b.periodo_desarrollo = a.periodo_desarrollo + 1
  GROUP BY ALL
), todos AS (
  SELECT d.cobertura, d.periodo_desarrollo, COALESCE(f.factor, 1.0) factor_edad_a_edad, COALESCE(f.periodos_base, 0) periodos_base
  FROM (SELECT DISTINCT cobertura, periodo_desarrollo FROM act_triangulo_observado) d
  LEFT JOIN f USING (cobertura, periodo_desarrollo)
)
SELECT cobertura, periodo_desarrollo, periodo_desarrollo * 12 edad_meses, ROUND(factor_edad_a_edad, 4) factor_edad_a_edad,
       ROUND(exp(SUM(ln(GREATEST(factor_edad_a_edad, 1e-6))) OVER (PARTITION BY cobertura ORDER BY periodo_desarrollo DESC)), 4) factor_a_ultimo,
       ROUND(1 / exp(SUM(ln(GREATEST(factor_edad_a_edad, 1e-6))) OVER (PARTITION BY cobertura ORDER BY periodo_desarrollo DESC)), 4) pct_desarrollado,
       periodos_base
FROM todos;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW act_reservas (
  CONSTRAINT reserva_caso_no_neg EXPECT (reserva_caso >= 0)
) COMMENT 'Reservas al 2026-09-30 por cobertura × periodo de ocurrencia: pagado, reserva de caso, último estimado (chain-ladder), IBNR y suficiencia (caso − requerida; >0 = reserva de caso sobrada)'
AS SELECT
  t.cobertura, t.periodo_ocurrencia,
  concat('oct-', t.periodo_ocurrencia - 1, ' a sep-', t.periodo_ocurrencia) periodo_etiqueta,
  t.periodo_desarrollo * 12 edad_meses, t.siniestros_reportados,
  ROUND(t.pagado_acumulado, 2) pagado,
  ROUND(t.incurrido_acumulado - t.pagado_acumulado, 2) reserva_caso,
  ROUND(t.incurrido_acumulado, 2) incurrido_reportado,
  f.factor_a_ultimo,
  ROUND(t.pagado_acumulado * f.factor_a_ultimo, 2) ultimo_estimado,
  ROUND(t.pagado_acumulado * f.factor_a_ultimo - t.pagado_acumulado, 2) reserva_requerida,
  ROUND(t.pagado_acumulado * f.factor_a_ultimo - t.incurrido_acumulado, 2) ibnr,
  ROUND(t.incurrido_acumulado - t.pagado_acumulado * f.factor_a_ultimo, 2) suficiencia_reserva
FROM act_triangulo_observado t
JOIN act_factores_desarrollo f ON t.cobertura = f.cobertura AND t.periodo_desarrollo = f.periodo_desarrollo
WHERE t.periodo_desarrollo = 2026 - t.periodo_ocurrencia + 1;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW act_triangulo
COMMENT 'Triángulo de pagos acumulados completado: celdas observadas + proyectadas por chain-ladder (para heatmap)'
AS WITH obs AS (
  SELECT cobertura, periodo_ocurrencia, periodo_desarrollo, pagado_acumulado, incurrido_acumulado, siniestros_reportados
  FROM act_triangulo_observado
), proy AS (
  SELECT r.cobertura, r.periodo_ocurrencia, r.d periodo_desarrollo,
         r.pagado * fa.factor_a_ultimo / fd.factor_a_ultimo pagado_acumulado
  FROM (SELECT *, explode(sequence(edad_meses DIV 12 + 1, 6)) d FROM act_reservas WHERE edad_meses DIV 12 < 6) r
  JOIN act_factores_desarrollo fa ON r.cobertura = fa.cobertura AND fa.periodo_desarrollo = r.edad_meses DIV 12
  JOIN act_factores_desarrollo fd ON r.cobertura = fd.cobertura AND fd.periodo_desarrollo = r.d
)
SELECT c.cobertura, c.periodo_ocurrencia, concat('oct-', c.periodo_ocurrencia - 1, ' a sep-', c.periodo_ocurrencia) periodo_etiqueta,
       c.periodo_desarrollo, c.periodo_desarrollo * 12 edad_meses, c.tipo_celda,
       ROUND(c.pagado_acumulado, 2) pagado_acumulado, ROUND(c.incurrido_acumulado, 2) incurrido_acumulado, c.siniestros_reportados,
       ROUND(c.pagado_acumulado / NULLIF(r.ultimo_estimado, 0), 4) pct_del_ultimo
FROM (
  SELECT cobertura, periodo_ocurrencia, periodo_desarrollo, 'Observado' tipo_celda, pagado_acumulado, incurrido_acumulado, siniestros_reportados FROM obs
  UNION ALL
  SELECT cobertura, periodo_ocurrencia, periodo_desarrollo, 'Proyectado', pagado_acumulado, NULL, NULL FROM proy
) c
JOIN act_reservas r ON c.cobertura = r.cobertura AND c.periodo_ocurrencia = r.periodo_ocurrencia;

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW act_siniestralidad_periodo
COMMENT 'Siniestralidad por periodo de ocurrencia: reportada (incurrido) vs última estimada (chain-ladder) sobre prima devengada'
AS WITH prima AS (
  SELECT y periodo_ocurrencia,
         SUM(p.prima_neta_anual * GREATEST(datediff(LEAST(p.fin_efectiva, make_date(y, 10, 1)), GREATEST(p.inicio_vigencia, make_date(y - 1, 10, 1))), 0)
             / datediff(p.fin_vigencia, p.inicio_vigencia)) prima_devengada
  FROM (SELECT inicio_vigencia, fin_vigencia, prima_neta_anual,
               LEAST(COALESCE(fecha_cancelacion, fin_vigencia), fin_vigencia, DATE'2026-10-01') fin_efectiva
        FROM fact_polizas) p
  LATERAL VIEW explode(sequence(2021, 2026)) t AS y
  GROUP BY y
), res AS (
  SELECT periodo_ocurrencia, MAX(periodo_etiqueta) periodo_etiqueta, MAX(edad_meses) edad_meses,
         SUM(pagado) pagado, SUM(reserva_caso) reserva_caso, SUM(incurrido_reportado) incurrido_reportado,
         SUM(ultimo_estimado) ultimo_estimado, SUM(reserva_requerida) reserva_requerida, SUM(ibnr) ibnr,
         SUM(suficiencia_reserva) suficiencia_reserva
  FROM act_reservas GROUP BY periodo_ocurrencia
)
SELECT r.*, ROUND(p.prima_devengada, 2) prima_devengada,
       ROUND(r.incurrido_reportado / p.prima_devengada, 4) siniestralidad_reportada,
       ROUND(r.ultimo_estimado / p.prima_devengada, 4) siniestralidad_ultima
FROM res r JOIN prima p USING (periodo_ocurrencia);
