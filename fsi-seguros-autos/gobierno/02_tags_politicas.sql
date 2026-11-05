-- FSI — Gobierno: governed tags (PII, región, certificación) + políticas ABAC
-- Idempotente: re-ejecutar tras un full-refresh de los pipelines.

-- ============ 1. Tags de PII en todas las capas (descubrimiento / clasificación)
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.dim_cliente ALTER COLUMN nombre_completo SET TAGS ('seguros_pii' = 'nombre');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.dim_cliente ALTER COLUMN rfc SET TAGS ('seguros_pii' = 'rfc');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.dim_cliente ALTER COLUMN curp SET TAGS ('seguros_pii' = 'curp');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.dim_cliente ALTER COLUMN email SET TAGS ('seguros_pii' = 'email');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.dim_cliente ALTER COLUMN telefono SET TAGS ('seguros_pii' = 'telefono');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.dim_vehiculo ALTER COLUMN num_serie_vin SET TAGS ('seguros_pii' = 'vin_placas');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.dim_vehiculo ALTER COLUMN placas SET TAGS ('seguros_pii' = 'vin_placas');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.silver_clientes ALTER COLUMN nombre SET TAGS ('seguros_pii' = 'nombre');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.silver_clientes ALTER COLUMN apellido_paterno SET TAGS ('seguros_pii' = 'nombre');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.silver_clientes ALTER COLUMN apellido_materno SET TAGS ('seguros_pii' = 'nombre');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.silver_clientes ALTER COLUMN nombre_completo SET TAGS ('seguros_pii' = 'nombre');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.silver_clientes ALTER COLUMN rfc SET TAGS ('seguros_pii' = 'rfc');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.silver_clientes ALTER COLUMN curp SET TAGS ('seguros_pii' = 'curp');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.silver_clientes ALTER COLUMN email SET TAGS ('seguros_pii' = 'email');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.silver_clientes ALTER COLUMN telefono SET TAGS ('seguros_pii' = 'telefono');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.silver_vehiculos ALTER COLUMN num_serie_vin SET TAGS ('seguros_pii' = 'vin_placas');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.silver_vehiculos ALTER COLUMN placas SET TAGS ('seguros_pii' = 'vin_placas');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.silver_terceros_siniestro ALTER COLUMN nombre_tercero SET TAGS ('seguros_pii' = 'nombre');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.silver_terceros_siniestro ALTER COLUMN telefono_tercero SET TAGS ('seguros_pii' = 'telefono');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.silver_terceros_siniestro ALTER COLUMN placas_tercero SET TAGS ('seguros_pii' = 'vin_placas');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.silver_creditos_personales ALTER COLUMN rfc SET TAGS ('seguros_pii' = 'rfc');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_clientes ALTER COLUMN nombre SET TAGS ('seguros_pii' = 'nombre');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_clientes ALTER COLUMN apellido_paterno SET TAGS ('seguros_pii' = 'nombre');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_clientes ALTER COLUMN apellido_materno SET TAGS ('seguros_pii' = 'nombre');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_clientes ALTER COLUMN rfc SET TAGS ('seguros_pii' = 'rfc');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_clientes ALTER COLUMN curp SET TAGS ('seguros_pii' = 'curp');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_clientes ALTER COLUMN email SET TAGS ('seguros_pii' = 'email');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_clientes ALTER COLUMN telefono SET TAGS ('seguros_pii' = 'telefono');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 ALTER COLUMN nombre_cliente SET TAGS ('seguros_pii' = 'nombre');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 ALTER COLUMN nom_cte SET TAGS ('seguros_pii' = 'nombre');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 ALTER COLUMN nombre_completo SET TAGS ('seguros_pii' = 'nombre');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 ALTER COLUMN rfc SET TAGS ('seguros_pii' = 'rfc');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 ALTER COLUMN rfc_cliente SET TAGS ('seguros_pii' = 'rfc');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 ALTER COLUMN rfc_cte_ant SET TAGS ('seguros_pii' = 'rfc');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 ALTER COLUMN curp SET TAGS ('seguros_pii' = 'curp');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 ALTER COLUMN curp_cte SET TAGS ('seguros_pii' = 'curp');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 ALTER COLUMN email SET TAGS ('seguros_pii' = 'email');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 ALTER COLUMN correo_e SET TAGS ('seguros_pii' = 'email');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 ALTER COLUMN mail_contacto SET TAGS ('seguros_pii' = 'email');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 ALTER COLUMN tel SET TAGS ('seguros_pii' = 'telefono');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 ALTER COLUMN telefono_casa SET TAGS ('seguros_pii' = 'telefono');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 ALTER COLUMN tel_contacto_1 SET TAGS ('seguros_pii' = 'telefono');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_vehiculos ALTER COLUMN num_serie_vin SET TAGS ('seguros_pii' = 'vin_placas');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_vehiculos ALTER COLUMN placas SET TAGS ('seguros_pii' = 'vin_placas');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_terceros_siniestro ALTER COLUMN nombre_tercero SET TAGS ('seguros_pii' = 'nombre');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_terceros_siniestro ALTER COLUMN telefono_tercero SET TAGS ('seguros_pii' = 'telefono');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_terceros_siniestro ALTER COLUMN placas_tercero SET TAGS ('seguros_pii' = 'vin_placas');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_creditos_personales ALTER COLUMN customer_rfc SET TAGS ('seguros_pii' = 'rfc');

-- ============ 2. Columna de región (filtro de filas)
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.dim_cliente ALTER COLUMN region SET TAGS ('seguros_region' = 'region');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.fact_polizas ALTER COLUMN region SET TAGS ('seguros_region' = 'region');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.fact_siniestros ALTER COLUMN region SET TAGS ('seguros_region' = 'region');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.dim_agente ALTER COLUMN region_agente SET TAGS ('seguros_region' = 'region');

-- ============ 3. Certificación de tablas: oro = oficial; tabla legacy = no usar
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.dim_fecha SET TAGS ('seguros_certificacion' = 'oficial');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.dim_cliente SET TAGS ('seguros_certificacion' = 'oficial');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.dim_producto SET TAGS ('seguros_certificacion' = 'oficial');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.dim_agente SET TAGS ('seguros_certificacion' = 'oficial');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.dim_taller SET TAGS ('seguros_certificacion' = 'oficial');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.dim_vehiculo SET TAGS ('seguros_certificacion' = 'oficial');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.fact_polizas SET TAGS ('seguros_certificacion' = 'oficial');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.fact_siniestros SET TAGS ('seguros_certificacion' = 'oficial');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.fact_movtos_siniestro SET TAGS ('seguros_certificacion' = 'oficial');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.fact_cotizaciones SET TAGS ('seguros_certificacion' = 'oficial');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.fact_telemetria_mensual SET TAGS ('seguros_certificacion' = 'oficial');
-- actuarial (reservas chain-ladder)
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.act_triangulo SET TAGS ('seguros_certificacion' = 'oficial');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.act_factores_desarrollo SET TAGS ('seguros_certificacion' = 'oficial');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.act_reservas SET TAGS ('seguros_certificacion' = 'oficial');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.act_siniestralidad_periodo SET TAGS ('seguros_certificacion' = 'oficial');
ALTER MATERIALIZED VIEW demo_catalog.seguros_demo.bronze_cliente_consolidado_2011 SET TAGS ('seguros_certificacion' = 'legacy_no_usar');

-- ============ 4. Políticas ABAC (una regla por tipo de PII; aplica a toda tabla oficial con la columna etiquetada)
CREATE OR REPLACE POLICY seguros_mask_rfc ON SCHEMA demo_catalog.seguros_demo
COMMENT 'Enmascara columnas seguros_pii=rfc en tablas oficiales según el rol del usuario'
COLUMN MASK demo_catalog.seguros_gobierno.mask_rfc
TO `account users`
FOR TABLES WHEN has_tag_value('seguros_certificacion', 'oficial')
MATCH COLUMNS has_tag_value('seguros_pii', 'rfc') AS c
ON COLUMN c;
CREATE OR REPLACE POLICY seguros_mask_curp ON SCHEMA demo_catalog.seguros_demo
COMMENT 'Enmascara columnas seguros_pii=curp en tablas oficiales según el rol del usuario'
COLUMN MASK demo_catalog.seguros_gobierno.mask_curp
TO `account users`
FOR TABLES WHEN has_tag_value('seguros_certificacion', 'oficial')
MATCH COLUMNS has_tag_value('seguros_pii', 'curp') AS c
ON COLUMN c;
CREATE OR REPLACE POLICY seguros_mask_nombre ON SCHEMA demo_catalog.seguros_demo
COMMENT 'Enmascara columnas seguros_pii=nombre en tablas oficiales según el rol del usuario'
COLUMN MASK demo_catalog.seguros_gobierno.mask_nombre
TO `account users`
FOR TABLES WHEN has_tag_value('seguros_certificacion', 'oficial')
MATCH COLUMNS has_tag_value('seguros_pii', 'nombre') AS c
ON COLUMN c;
CREATE OR REPLACE POLICY seguros_mask_email ON SCHEMA demo_catalog.seguros_demo
COMMENT 'Enmascara columnas seguros_pii=email en tablas oficiales según el rol del usuario'
COLUMN MASK demo_catalog.seguros_gobierno.mask_email
TO `account users`
FOR TABLES WHEN has_tag_value('seguros_certificacion', 'oficial')
MATCH COLUMNS has_tag_value('seguros_pii', 'email') AS c
ON COLUMN c;
CREATE OR REPLACE POLICY seguros_mask_telefono ON SCHEMA demo_catalog.seguros_demo
COMMENT 'Enmascara columnas seguros_pii=telefono en tablas oficiales según el rol del usuario'
COLUMN MASK demo_catalog.seguros_gobierno.mask_telefono
TO `account users`
FOR TABLES WHEN has_tag_value('seguros_certificacion', 'oficial')
MATCH COLUMNS has_tag_value('seguros_pii', 'telefono') AS c
ON COLUMN c;
CREATE OR REPLACE POLICY seguros_mask_vin_placas ON SCHEMA demo_catalog.seguros_demo
COMMENT 'Enmascara columnas seguros_pii=vin_placas en tablas oficiales según el rol del usuario'
COLUMN MASK demo_catalog.seguros_gobierno.mask_vin_placas
TO `account users`
FOR TABLES WHEN has_tag_value('seguros_certificacion', 'oficial')
MATCH COLUMNS has_tag_value('seguros_pii', 'vin_placas') AS c
ON COLUMN c;
CREATE OR REPLACE POLICY seguros_filtro_region ON SCHEMA demo_catalog.seguros_demo
COMMENT 'Agentes regionales solo ven filas de su región en tablas oficiales'
ROW FILTER demo_catalog.seguros_gobierno.filtro_region
TO `account users`
FOR TABLES WHEN has_tag_value('seguros_certificacion', 'oficial')
MATCH COLUMNS has_tag_value('seguros_region', 'region') AS r
USING COLUMNS (r);
