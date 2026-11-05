-- CREATE OR REPLACE de una metric view borra sus etiquetas: correr después de metric_views.sql
ALTER VIEW demo_catalog.seguros_demo.mv_cartera_rentabilidad SET TAGS ('Seguros' = '', 'system.certification_status' = 'certified');
ALTER VIEW demo_catalog.seguros_demo.mv_siniestros_fraude SET TAGS ('Seguros' = '', 'system.certification_status' = 'certified');
ALTER VIEW demo_catalog.seguros_demo.mv_comercial_canales SET TAGS ('Seguros' = '', 'system.certification_status' = 'certified');
ALTER VIEW demo_catalog.seguros_demo.mv_reservas_actuariales SET TAGS ('Seguros' = '', 'system.certification_status' = 'certified');
SELECT table_name, tag_name, tag_value FROM demo_catalog.information_schema.table_tags WHERE schema_name='seguros_demo' AND table_name LIKE 'mv\_%' ORDER BY 1, 2
