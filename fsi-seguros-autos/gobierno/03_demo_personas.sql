-- FSI — Demo en vivo: misma consulta, tres roles. Cambia el rol y vuelve a correr la consulta.
-- Rol 1: Investigador antifraude (SIU) — ve todo
UPDATE demo_catalog.seguros_gobierno.usuarios_rol SET rol = 'SIU', region = NULL WHERE usuario = current_user();
SELECT demo_catalog.seguros_gobierno.rol_actual() rol, region, COUNT(*) OVER () clientes_visibles, nombre_completo, rfc, curp, email, telefono
FROM demo_catalog.seguros_demo.dim_cliente ORDER BY id_cliente LIMIT 2;
-- Rol 2: Actuario / BI — todas las regiones, PII enmascarada
UPDATE demo_catalog.seguros_gobierno.usuarios_rol SET rol = 'ACTUARIO', region = NULL WHERE usuario = current_user();
SELECT demo_catalog.seguros_gobierno.rol_actual() rol, region, COUNT(*) OVER () clientes_visibles, nombre_completo, rfc, curp, email, telefono
FROM demo_catalog.seguros_demo.dim_cliente ORDER BY id_cliente LIMIT 2;
-- Rol 3: Gerente regional Norte — solo su región, PII parcial
UPDATE demo_catalog.seguros_gobierno.usuarios_rol SET rol = 'AGENTE_REGIONAL', region = 'Norte' WHERE usuario = current_user();
SELECT demo_catalog.seguros_gobierno.rol_actual() rol, region, COUNT(*) OVER () clientes_visibles, nombre_completo, rfc, curp, email, telefono
FROM demo_catalog.seguros_demo.dim_cliente ORDER BY id_cliente LIMIT 2;
SELECT region, COUNT(*) siniestros, ROUND(SUM(incurrido)/1e6,1) incurrido_mdp FROM demo_catalog.seguros_demo.fact_siniestros GROUP BY region;
-- Volver a SIU
UPDATE demo_catalog.seguros_gobierno.usuarios_rol SET rol = 'SIU', region = NULL WHERE usuario = current_user();
