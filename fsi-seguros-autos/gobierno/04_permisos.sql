-- FSI — Gobierno: modelo de permisos (mínimo privilegio, sin copias en el schema oficial)
-- PLANTILLA: requiere grupos de CUENTA (seguros_*). En el workspace demo no existen; los roles en vivo se
-- simulan con demo_catalog.seguros_gobierno.usuarios_rol. Solo la sección del sandbox se ejecuta en el demo.
-- Consumo: solo SELECT sobre tablas oficiales (oro). Nadie de consumo puede CREATE TABLE en seguros_demo.
-- Bronce/plata y fuentes federadas: solo ingeniería de datos. Crear conexiones a las fuentes: solo admins del metastore.
-- Ciencia de datos: sandbox propio para experimentar + lectura del data lake (Volume).

GRANT USE CATALOG ON CATALOG demo_catalog TO `seguros_actuarios`;
GRANT USE SCHEMA ON SCHEMA demo_catalog.seguros_demo TO `seguros_actuarios`;
GRANT USE CATALOG ON CATALOG demo_catalog TO `seguros_siu`;
GRANT USE SCHEMA ON SCHEMA demo_catalog.seguros_demo TO `seguros_siu`;
GRANT USE CATALOG ON CATALOG demo_catalog TO `seguros_agentes`;
GRANT USE SCHEMA ON SCHEMA demo_catalog.seguros_demo TO `seguros_agentes`;
GRANT USE CATALOG ON CATALOG demo_catalog TO `seguros_ciencia_datos`;
GRANT USE SCHEMA ON SCHEMA demo_catalog.seguros_demo TO `seguros_ciencia_datos`;
GRANT USE CATALOG ON CATALOG demo_catalog TO `seguros_ingenieria_datos`;
GRANT USE SCHEMA ON SCHEMA demo_catalog.seguros_demo TO `seguros_ingenieria_datos`;

-- Consumo: solo la capa oficial
GRANT SELECT ON TABLE demo_catalog.seguros_demo.dim_fecha TO `seguros_actuarios`, `seguros_siu`, `seguros_agentes`, `seguros_ciencia_datos`;
GRANT SELECT ON TABLE demo_catalog.seguros_demo.dim_cliente TO `seguros_actuarios`, `seguros_siu`, `seguros_agentes`, `seguros_ciencia_datos`;
GRANT SELECT ON TABLE demo_catalog.seguros_demo.dim_producto TO `seguros_actuarios`, `seguros_siu`, `seguros_agentes`, `seguros_ciencia_datos`;
GRANT SELECT ON TABLE demo_catalog.seguros_demo.dim_agente TO `seguros_actuarios`, `seguros_siu`, `seguros_agentes`, `seguros_ciencia_datos`;
GRANT SELECT ON TABLE demo_catalog.seguros_demo.dim_taller TO `seguros_actuarios`, `seguros_siu`, `seguros_agentes`, `seguros_ciencia_datos`;
GRANT SELECT ON TABLE demo_catalog.seguros_demo.dim_vehiculo TO `seguros_actuarios`, `seguros_siu`, `seguros_agentes`, `seguros_ciencia_datos`;
GRANT SELECT ON TABLE demo_catalog.seguros_demo.fact_polizas TO `seguros_actuarios`, `seguros_siu`, `seguros_agentes`, `seguros_ciencia_datos`;
GRANT SELECT ON TABLE demo_catalog.seguros_demo.fact_siniestros TO `seguros_actuarios`, `seguros_siu`, `seguros_agentes`, `seguros_ciencia_datos`;
GRANT SELECT ON TABLE demo_catalog.seguros_demo.fact_movtos_siniestro TO `seguros_actuarios`, `seguros_siu`, `seguros_agentes`, `seguros_ciencia_datos`;
GRANT SELECT ON TABLE demo_catalog.seguros_demo.fact_cotizaciones TO `seguros_actuarios`, `seguros_siu`, `seguros_agentes`, `seguros_ciencia_datos`;
GRANT SELECT ON TABLE demo_catalog.seguros_demo.fact_telemetria_mensual TO `seguros_actuarios`, `seguros_siu`, `seguros_agentes`, `seguros_ciencia_datos`;

-- Ingeniería de datos: dueña del pipeline y de las fuentes
GRANT SELECT, MODIFY, CREATE TABLE, CREATE MATERIALIZED VIEW, REFRESH ON SCHEMA demo_catalog.seguros_demo TO `seguros_ingenieria_datos`;
GRANT READ VOLUME, WRITE VOLUME ON VOLUME demo_catalog.seguros_demo.datalake_ds TO `seguros_ingenieria_datos`;
GRANT USE CATALOG, USE SCHEMA, SELECT ON CATALOG seguros_dwh_onprem TO `seguros_ingenieria_datos`;
GRANT USE CATALOG, USE SCHEMA, SELECT ON CATALOG seguros_creditos_aws TO `seguros_ingenieria_datos`;

-- Ciencia de datos: lectura del data lake + sandbox para experimentar (no en el schema oficial)
GRANT READ VOLUME ON VOLUME demo_catalog.seguros_demo.datalake_ds TO `seguros_ciencia_datos`;
CREATE SCHEMA IF NOT EXISTS demo_catalog.seguros_sandbox_ds COMMENT 'Sandbox de Ciencia de Datos: features, experimentos y modelos. No es fuente oficial.';
ALTER SCHEMA demo_catalog.seguros_sandbox_ds SET TAGS ('seguros_certificacion' = 'sandbox');
GRANT USE SCHEMA, CREATE TABLE, CREATE FUNCTION, CREATE MODEL, CREATE VOLUME ON SCHEMA demo_catalog.seguros_sandbox_ds TO `seguros_ciencia_datos`;

-- Verificación
SHOW GRANTS `seguros_actuarios` ON TABLE demo_catalog.seguros_demo.dim_cliente;
SHOW GRANTS `seguros_actuarios` ON TABLE demo_catalog.seguros_demo.silver_clientes;

-- Cuarentena de calidad (pipeline seguros_medallion): contiene el registro completo (con PII) → solo equipo de calidad de datos y SIU
GRANT SELECT ON TABLE demo_catalog.seguros_demo.cuarentena_registros TO `seguros_calidad_datos`, `seguros_siu`;
