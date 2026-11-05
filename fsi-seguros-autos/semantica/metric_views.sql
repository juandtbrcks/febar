-- =====================================================================
-- Aseguradora FSI · Autos — Capa semántica ejecutiva (UC Metric Views)
-- 4 vistas: cartera/rentabilidad · siniestros/fraude · comercial/canales · reservas actuariales
-- Versión YAML 1.1: cada dimensión/medida lleva formato (MXN, %, enteros) y sinónimos (español/inglés) que usan el dashboard y Genie.
-- Joins prefijados (dcliente/dproducto/...) por el bug del parser con substrings.
-- Las políticas ABAC de las tablas base aplican: cada usuario ve solo su región / PII según su rol.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) CARTERA Y RENTABILIDAD  (grano: póliza, con sus siniestros agregados)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW demo_catalog.seguros_demo.mv_cartera_rentabilidad
WITH METRICS
LANGUAGE YAML
COMMENT 'Cartera de autos FSI: prima emitida/devengada/cobrada, pólizas, exposición y rentabilidad técnica (siniestralidad, frecuencia, severidad).'
AS $$
version: 1.1
source: |
  SELECT p.*, COALESCE(s.num_siniestros, 0) num_siniestros, COALESCE(s.incurrido, 0) incurrido, COALESCE(s.pagado, 0) pagado
  FROM demo_catalog.seguros_demo.fact_polizas p
  LEFT JOIN (SELECT id_poliza, COUNT(*) num_siniestros, SUM(incurrido) incurrido, SUM(pagado) pagado
             FROM demo_catalog.seguros_demo.fact_siniestros GROUP BY id_poliza) s
    ON p.id_poliza = s.id_poliza
joins:
  - name: dproducto
    source: demo_catalog.seguros_demo.dim_producto
    'on': source.id_producto = dproducto.id_producto
  - name: dagente
    source: demo_catalog.seguros_demo.dim_agente
    'on': source.id_agente = dagente.id_agente
  - name: dcliente
    source: demo_catalog.seguros_demo.dim_cliente
    'on': source.id_cliente = dcliente.id_cliente
  - name: dvehiculo
    source: demo_catalog.seguros_demo.dim_vehiculo
    'on': source.id_vehiculo = dvehiculo.id_vehiculo
  - name: dfecha
    source: demo_catalog.seguros_demo.dim_fecha
    'on': source.fecha_emision_key = dfecha.fecha_key
dimensions:
  - name: Año Suscripción
    expr: source.anio_suscripcion
    synonyms: ['año de emisión', 'año póliza', 'underwriting year']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
      hide_group_separator: true
  - name: Trimestre Emisión
    expr: dfecha.trimestre
    synonyms: ['trimestre', 'quarter']
  - name: Mes Emisión
    expr: dfecha.mes
    synonyms: ['mes', 'month']
  - name: Año-Mes Emisión
    expr: dfecha.anio_mes
    synonyms: ['periodo', 'mes de emisión']
  - name: Paquete
    expr: dproducto.paquete
    synonyms: ['producto', 'plan', 'cobertura contratada', 'Amplia', 'Limitada', 'RC']
  - name: Canal de Venta
    expr: dagente.canal
    synonyms: ['canal', 'canal comercial', 'sales channel']
  - name: Región
    expr: source.region
    synonyms: ['zona', 'region']
  - name: Estado
    expr: dcliente.estado
    synonyms: ['entidad federativa', 'estado de la república']
  - name: Segmento Cliente
    expr: dcliente.segmento
    synonyms: ['segmento', 'tipo de cliente']
  - name: Rango Edad Cliente
    expr: dcliente.rango_edad
    synonyms: ['edad del cliente', 'grupo de edad']
  - name: Cliente con Crédito del Grupo
    expr: CASE WHEN dcliente.tiene_credito_grupo THEN 'Sí' ELSE 'No' END
    synonyms: ['tiene crédito', 'acreditado', 'venta cruzada', 'cross-sell', 'cliente del banco']
  - name: Estatus Crédito
    expr: dcliente.estatus_credito
    synonyms: ['situación del crédito', 'morosidad', 'crédito vencido', 'credit status']
  - name: Uso Vehículo
    expr: dvehiculo.uso
    synonyms: ['uso', 'tipo de uso', 'particular', 'comercial']
  - name: Marca
    expr: dvehiculo.marca
    synonyms: ['armadora', 'fabricante', 'brand']
  - name: Segmento Marca
    expr: dvehiculo.segmento_marca
    synonyms: ['gama', 'segmento del vehículo']
  - name: Antigüedad Vehículo
    expr: dvehiculo.rango_antiguedad
    synonyms: ['edad del auto', 'modelo', 'antigüedad del coche']
  - name: App Conectada
    expr: CASE WHEN dvehiculo.app_conectada THEN 'Sí' ELSE 'No' END
    synonyms: ['telemetría', 'app FSI', 'conectado']
  - name: Conductor Joven (<25)
    expr: CASE WHEN source.tiene_conductor_joven THEN 'Sí' ELSE 'No' END
    synonyms: ['conductor joven', 'menor de 25', 'young driver']
  - name: Forma de Pago
    expr: source.forma_pago
    synonyms: ['frecuencia de pago', 'mensual', 'anual']
  - name: Estatus Póliza
    expr: source.estatus
    synonyms: ['estatus', 'vigente', 'cancelada']
  - name: Renovación
    expr: CASE WHEN source.es_renovacion THEN 'Renovación' ELSE 'Nueva' END
    synonyms: ['nueva o renovación', 'renewal', 'tipo de venta']
measures:
  - name: Pólizas
    expr: COUNT(1)
    synonyms: ['número de pólizas', 'policies', 'contratos']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
  - name: Pólizas Vigentes
    expr: COUNT_IF(source.estatus = 'Vigente')
    synonyms: ['cartera vigente', 'pólizas activas', 'in force']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
  - name: Clientes Únicos
    expr: COUNT(DISTINCT source.id_cliente)
    synonyms: ['asegurados', 'número de clientes', 'customers']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
  - name: Prima Emitida
    expr: SUM(source.prima_neta_anual)
    synonyms: ['prima', 'ventas', 'primas emitidas', 'written premium', 'GWP']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Prima Devengada
    expr: SUM(source.prima_devengada)
    synonyms: ['prima ganada', 'earned premium']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Prima Cobrada
    expr: SUM(source.prima_cobrada)
    synonyms: ['cobranza', 'prima recaudada', 'collected premium']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Prima Promedio
    expr: AVG(source.prima_neta_anual)
    synonyms: ['ticket promedio', 'prima media', 'average premium']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
  - name: Suma Asegurada
    expr: SUM(source.suma_asegurada)
    synonyms: ['valor asegurado', 'sum insured']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Exposición (años-vehículo)
    expr: SUM(source.exposicion_anios)
    synonyms: ['exposición', 'años vehículo', 'earned exposure']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
  - name: Siniestros
    expr: SUM(source.num_siniestros)
    synonyms: ['número de siniestros', 'reclamaciones', 'claims']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
  - name: Costo Incurrido
    expr: SUM(source.incurrido)
    synonyms: ['incurrido', 'costo de siniestros', 'incurred losses']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Siniestralidad %
    expr: SUM(source.incurrido) / NULLIF(SUM(source.prima_devengada), 0)
    synonyms: ['siniestralidad', 'loss ratio', 'índice de siniestralidad', 'rentabilidad técnica']
    format:
      type: percentage
      decimal_places:
        type: exact
        places: 1
  - name: Frecuencia
    expr: SUM(source.num_siniestros) / NULLIF(SUM(source.exposicion_anios), 0)
    synonyms: ['frecuencia de siniestros', 'claim frequency']
    format:
      type: percentage
      decimal_places:
        type: exact
        places: 1
  - name: Severidad
    expr: SUM(source.incurrido) / NULLIF(SUM(source.num_siniestros), 0)
    synonyms: ['costo promedio por siniestro', 'severity']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
  - name: Tasa de Cancelación
    expr: COUNT_IF(source.estatus = 'Cancelada') / NULLIF(COUNT(1), 0)
    synonyms: ['cancelación', 'churn', 'pólizas canceladas']
    format:
      type: percentage
      decimal_places:
        type: exact
        places: 1
  - name: Recibos Vencidos
    expr: SUM(source.recibos_vencidos)
    synonyms: ['recibos pendientes', 'morosidad de primas', 'adeudos']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
$$;

-- ---------------------------------------------------------------------
-- 2) SINIESTROS Y FRAUDE  (grano: siniestro, con scoring del modelo @champion)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW demo_catalog.seguros_demo.mv_siniestros_fraude
WITH METRICS
LANGUAGE YAML
COMMENT 'Siniestros de autos FSI: costo (incurrido, pagado, reservas, recuperaciones), oportunidad de reporte y fraude (dictámenes SIU + modelo de riesgo).'
AS $$
version: 1.1
source: |
  SELECT s.*, sc.prob_fraude, sc.nivel_riesgo, sc.monto_en_riesgo
  FROM demo_catalog.seguros_demo.fact_siniestros s
  LEFT JOIN demo_catalog.seguros_ml.scoring_fraude_siniestros sc ON s.id_siniestro = sc.id_siniestro
joins:
  - name: dproducto
    source: demo_catalog.seguros_demo.dim_producto
    'on': source.id_producto = dproducto.id_producto
  - name: dvehiculo
    source: demo_catalog.seguros_demo.dim_vehiculo
    'on': source.id_vehiculo = dvehiculo.id_vehiculo
  - name: dtaller
    source: demo_catalog.seguros_demo.dim_taller
    'on': source.id_taller = dtaller.id_taller
  - name: dfecha
    source: demo_catalog.seguros_demo.dim_fecha
    'on': source.fecha_ocurrencia_key = dfecha.fecha_key
dimensions:
  - name: Año Ocurrencia
    expr: source.anio_ocurrencia
    synonyms: ['año del siniestro', 'accident year']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
      hide_group_separator: true
  - name: Trimestre Ocurrencia
    expr: dfecha.trimestre
    synonyms: ['trimestre', 'quarter']
  - name: Mes Ocurrencia
    expr: dfecha.mes
    synonyms: ['mes', 'month']
  - name: Año-Mes Ocurrencia
    expr: dfecha.anio_mes
    synonyms: ['periodo', 'mes del siniestro']
  - name: Cobertura
    expr: source.cobertura
    synonyms: ['ramo', 'tipo de cobertura', 'coverage']
  - name: Causa
    expr: source.causa
    synonyms: ['tipo de siniestro', 'motivo', 'choque', 'robo']
  - name: Canal de Reporte
    expr: source.canal_reporte
    synonyms: ['medio de reporte', 'cómo se reportó', 'FNOL']
  - name: Estatus Siniestro
    expr: source.estatus
    synonyms: ['estatus', 'abierto', 'cerrado', 'en investigación']
  - name: Región
    expr: source.region
    synonyms: ['zona', 'region']
  - name: Estado Ocurrencia
    expr: source.estado_ocurrencia
    synonyms: ['estado del siniestro', 'lugar del siniestro', 'entidad']
  - name: Paquete
    expr: dproducto.paquete
    synonyms: ['producto', 'plan', 'cobertura contratada', 'Amplia', 'Limitada', 'RC']
  - name: Uso Vehículo
    expr: dvehiculo.uso
    synonyms: ['uso', 'tipo de uso', 'particular', 'comercial']
  - name: Marca
    expr: dvehiculo.marca
    synonyms: ['armadora', 'fabricante', 'brand']
  - name: Tipo de Taller
    expr: COALESCE(dtaller.tipo_taller, 'Sin taller')
    synonyms: ['agencia o independiente', 'tipo de proveedor']
  - name: Taller
    expr: dtaller.nombre_taller
    synonyms: ['proveedor', 'nombre del taller', 'body shop']
  - name: Dictamen Fraude
    expr: CASE WHEN source.fraude_confirmado THEN 'Fraude confirmado' WHEN NOT source.fraude_confirmado THEN 'Sin fraude' ELSE 'En proceso' END
    synonyms: ['fraude', 'resultado SIU', 'dictamen']
  - name: Nivel Riesgo Fraude
    expr: COALESCE(source.nivel_riesgo, 'Cerrado (sin scoring)')
    synonyms: ['riesgo', 'score de fraude', 'prioridad SIU', 'semáforo']
measures:
  - name: Siniestros
    expr: COUNT(1)
    synonyms: ['número de siniestros', 'reclamaciones', 'claims']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
  - name: Siniestros Abiertos
    expr: COUNT_IF(source.estatus IN ('Abierto', 'En investigación'))
    synonyms: ['pendientes', 'en trámite', 'open claims']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
  - name: Monto Reclamado
    expr: SUM(source.monto_reclamado)
    synonyms: ['reclamado', 'monto del reclamo', 'claimed amount']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Costo Incurrido
    expr: SUM(source.incurrido)
    synonyms: ['incurrido', 'costo de siniestros', 'incurred losses']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Pagado
    expr: SUM(source.pagado)
    synonyms: ['pagos', 'monto pagado', 'paid losses']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Reserva Pendiente
    expr: SUM(source.reserva_pendiente)
    synonyms: ['reserva', 'reserva de caso', 'case reserve', 'OSLR']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Recuperaciones
    expr: SUM(source.recuperaciones)
    synonyms: ['salvamentos', 'recobros', 'recoveries']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Severidad Promedio
    expr: SUM(source.incurrido) / NULLIF(COUNT(1), 0)
    synonyms: ['severidad', 'costo promedio por siniestro', 'severity']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
  - name: Horas Promedio a Reporte
    expr: AVG(source.horas_a_reporte)
    synonyms: ['tiempo de reporte', 'demora en reportar', 'reporting lag']
    format:
      type: number
      decimal_places:
        type: exact
        places: 1
  - name: '% Reportados por App'
    expr: COUNT_IF(source.canal_reporte = 'App') / NULLIF(COUNT(1), 0)
    synonyms: ['adopción app', 'reportes digitales', 'FNOL digital']
    format:
      type: percentage
      decimal_places:
        type: exact
        places: 1
  - name: Fraudes Confirmados
    expr: COUNT_IF(source.fraude_confirmado)
    synonyms: ['casos de fraude', 'fraudes', 'confirmed fraud']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
  - name: Tasa de Fraude
    expr: COUNT_IF(source.fraude_confirmado) / NULLIF(COUNT_IF(source.fraude_confirmado IS NOT NULL), 0)
    synonyms: ['% fraude', 'fraude', 'fraud rate']
    format:
      type: percentage
      decimal_places:
        type: exact
        places: 1
  - name: Monto Fraude Detectado
    expr: SUM(CASE WHEN source.fraude_confirmado THEN source.monto_reclamado END)
    synonyms: ['fraude evitado', 'ahorro por fraude', 'monto de fraude']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Siniestros Alto Riesgo
    expr: COUNT_IF(source.nivel_riesgo = 'Alto')
    synonyms: ['casos alto riesgo', 'bandeja SIU', 'sospechosos']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
  - name: Monto en Riesgo de Fraude
    expr: SUM(source.monto_en_riesgo)
    synonyms: ['exposición a fraude', 'monto en riesgo', 'dinero en riesgo']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Probabilidad Fraude Promedio
    expr: AVG(source.prob_fraude)
    synonyms: ['score promedio', 'probabilidad de fraude', 'fraud score']
    format:
      type: percentage
      decimal_places:
        type: exact
        places: 1
  - name: Presupuesto Taller vs Autorizado
    expr: SUM(source.monto_presupuesto_taller) / NULLIF(SUM(source.monto_autorizado), 0)
    synonyms: ['inflado de presupuestos', 'sobrecosto de taller', 'presupuesto vs autorizado']
    format:
      type: percentage
      decimal_places:
        type: exact
        places: 1
$$;

-- ---------------------------------------------------------------------
-- 3) COMERCIAL Y CANALES  (grano: cotización)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW demo_catalog.seguros_demo.mv_comercial_canales
WITH METRICS
LANGUAGE YAML
COMMENT 'Embudo comercial de autos FSI: cotizaciones y conversión por canal (App, Web, Comparadores externos, Agentes, Tienda Aliada) y prima resultante.'
AS $$
version: 1.1
source: demo_catalog.seguros_demo.fact_cotizaciones
joins:
  - name: dproducto
    source: demo_catalog.seguros_demo.dim_producto
    'on': source.id_producto = dproducto.id_producto
  - name: dpoliza
    source: demo_catalog.seguros_demo.fact_polizas
    'on': source.id_poliza = dpoliza.id_poliza
  - name: dfecha
    source: demo_catalog.seguros_demo.dim_fecha
    'on': source.fecha_cotizacion_key = dfecha.fecha_key
dimensions:
  - name: Canal
    expr: source.canal
    synonyms: ['canal de venta', 'canal comercial', 'sales channel']
  - name: Sistema Origen
    expr: source.sistema_origen
    synonyms: ['sistema', 'fuente', 'plataforma de cotización']
  - name: Año
    expr: dfecha.anio
    synonyms: ['año de cotización', 'year']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
      hide_group_separator: true
  - name: Trimestre
    expr: dfecha.trimestre
    synonyms: ['quarter']
  - name: Mes
    expr: dfecha.mes
    synonyms: ['month']
  - name: Año-Mes
    expr: dfecha.anio_mes
    synonyms: ['periodo', 'mes de cotización']
  - name: Estado
    expr: source.estado
    synonyms: ['entidad federativa', 'estado de la república']
  - name: Paquete
    expr: dproducto.paquete
    synonyms: ['producto', 'plan', 'cobertura contratada', 'Amplia', 'Limitada', 'RC']
  - name: Marca
    expr: source.marca
    synonyms: ['armadora', 'fabricante', 'brand']
  - name: Rango Edad Conductor
    expr: CASE WHEN source.edad_conductor < 25 THEN '<25' WHEN source.edad_conductor < 35 THEN '25-34' WHEN source.edad_conductor < 50 THEN '35-49' WHEN source.edad_conductor < 65 THEN '50-64' ELSE '65+' END
    synonyms: ['edad del conductor', 'grupo de edad']
  - name: Antigüedad Vehículo
    expr: CASE WHEN 2026 - source.anio_modelo <= 2 THEN '0-2 años' WHEN 2026 - source.anio_modelo <= 5 THEN '3-5 años' WHEN 2026 - source.anio_modelo <= 10 THEN '6-10 años' ELSE '11+ años' END
    synonyms: ['edad del auto', 'modelo', 'antigüedad del coche']
measures:
  - name: Cotizaciones
    expr: COUNT(1)
    synonyms: ['quotes', 'número de cotizaciones', 'solicitudes']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
  - name: Cotizaciones Convertidas
    expr: COUNT_IF(source.convertida)
    synonyms: ['ventas', 'pólizas vendidas', 'conversiones']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
  - name: Tasa de Conversión
    expr: COUNT_IF(source.convertida) / NULLIF(COUNT(1), 0)
    synonyms: ['conversión', 'conversion rate', 'efectividad', 'cierre']
    format:
      type: percentage
      decimal_places:
        type: exact
        places: 1
  - name: Prima Cotizada Promedio
    expr: AVG(source.prima_cotizada)
    synonyms: ['precio cotizado', 'cotización promedio']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
  - name: Prima Emitida (convertidas)
    expr: SUM(dpoliza.prima_neta_anual)
    synonyms: ['prima vendida', 'prima de cotizaciones convertidas']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Brecha de Precio No Convertidas
    expr: AVG(CASE WHEN NOT source.convertida THEN source.prima_cotizada END) / NULLIF(AVG(CASE WHEN source.convertida THEN source.prima_cotizada END), 0) - 1
    synonyms: ['diferencia de precio', 'precio vs competencia', 'price gap']
    format:
      type: percentage
      decimal_places:
        type: exact
        places: 1
$$;

-- ---------------------------------------------------------------------
-- 4) RESERVAS ACTUARIALES  (grano: cobertura × periodo de ocurrencia, valuación 2026-09-30)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW demo_catalog.seguros_demo.mv_reservas_actuariales
WITH METRICS
LANGUAGE YAML
COMMENT 'Reservas de siniestros de autos al 2026-09-30 (chain-ladder sobre pagos): pagado, reserva de caso constituida, último estimado, reserva requerida, IBNR y suficiencia por cobertura y periodo de ocurrencia (oct–sep).'
AS $$
version: 1.1
source: demo_catalog.seguros_demo.act_reservas
dimensions:
  - name: Cobertura
    expr: source.cobertura
    synonyms: ['ramo', 'tipo de cobertura', 'coverage']
  - name: Periodo de Ocurrencia
    expr: source.periodo_etiqueta
    synonyms: ['periodo', 'año de ocurrencia', 'accident period', 'origen']
  - name: Año Cierre Periodo
    expr: source.periodo_ocurrencia
    synonyms: ['año de origen', 'accident year', 'periodo actuarial']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
      hide_group_separator: true
  - name: Edad (meses)
    expr: source.edad_meses
    synonyms: ['desarrollo', 'development age', 'antigüedad del periodo']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
measures:
  - name: Siniestros Reportados
    expr: SUM(source.siniestros_reportados)
    synonyms: ['siniestros', 'número de siniestros', 'reported claims']
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
  - name: Pagado
    expr: SUM(source.pagado)
    synonyms: ['pagos', 'monto pagado', 'paid losses']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Reserva de Caso
    expr: SUM(source.reserva_caso)
    synonyms: ['reserva constituida', 'case reserve', 'reserva pendiente']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Incurrido Reportado
    expr: SUM(source.incurrido_reportado)
    synonyms: ['incurrido', 'reported incurred']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Último Estimado
    expr: SUM(source.ultimo_estimado)
    synonyms: ['ultimate', 'costo final estimado', 'proyección']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Reserva Requerida
    expr: SUM(source.reserva_requerida)
    synonyms: ['reserva necesaria', 'required reserve']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: IBNR
    expr: SUM(source.ibnr)
    synonyms: ['ocurridos no reportados', 'SONR', 'incurred but not reported']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Suficiencia de Reserva
    expr: SUM(source.suficiencia_reserva)
    synonyms: ['excedente de reserva', 'capital inmovilizado', 'redundancia', 'reserve adequacy']
    format:
      type: currency
      currency_code: MXN
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact
  - name: Suficiencia %
    expr: SUM(source.suficiencia_reserva) / NULLIF(SUM(source.reserva_requerida), 0)
    synonyms: ['% suficiencia', 'suficiencia de reservas', 'adequacy ratio']
    format:
      type: percentage
      decimal_places:
        type: exact
        places: 1
  - name: '% Desarrollado'
    expr: SUM(source.pagado) / NULLIF(SUM(source.ultimo_estimado), 0)
    synonyms: ['madurez', '% pagado del último', 'development %']
    format:
      type: percentage
      decimal_places:
        type: exact
        places: 1
$$;
