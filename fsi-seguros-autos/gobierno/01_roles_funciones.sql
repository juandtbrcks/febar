-- FSI — Gobierno: roles de demo + funciones de enmascaramiento / filtrado de filas
-- Los roles se resuelven en tiempo de consulta: grupo de cuenta (producción) o tabla de mapeo (demo en vivo).

CREATE SCHEMA IF NOT EXISTS demo_catalog.seguros_gobierno
COMMENT 'FSI — objetos de gobierno: roles, funciones de masking y filtros de fila usados por las políticas ABAC';

-- Mapeo usuario -> rol (en producción esto lo resuelven grupos: seguros_siu, seguros_actuarios, seguros_agentes_<region>)
CREATE TABLE IF NOT EXISTS demo_catalog.seguros_gobierno.usuarios_rol (
  usuario STRING NOT NULL COMMENT 'email del usuario',
  rol     STRING NOT NULL COMMENT 'SIU | ACTUARIO | AGENTE_REGIONAL',
  region  STRING          COMMENT 'región asignada (solo AGENTE_REGIONAL)'
) COMMENT 'Asignación de rol para el demo; cambiar el rol aquí cambia lo que el usuario ve, al instante';

MERGE INTO demo_catalog.seguros_gobierno.usuarios_rol t
USING (SELECT '<tu_usuario>' usuario, 'SIU' rol, CAST(NULL AS STRING) region) s
ON t.usuario = s.usuario
WHEN NOT MATCHED THEN INSERT *;

-- Rol efectivo del usuario actual (grupo de cuenta > tabla de mapeo > rol por omisión)
CREATE OR REPLACE FUNCTION demo_catalog.seguros_gobierno.rol_actual()
RETURNS STRING
COMMENT 'Rol efectivo del usuario que consulta'
RETURN CASE
  WHEN is_account_group_member('seguros_siu') THEN 'SIU'
  ELSE COALESCE((SELECT MAX(rol) FROM demo_catalog.seguros_gobierno.usuarios_rol WHERE usuario = current_user()), 'ACTUARIO')
END;

CREATE OR REPLACE FUNCTION demo_catalog.seguros_gobierno.region_actual()
RETURNS STRING
COMMENT 'Región asignada al usuario que consulta (NULL = todas)'
RETURN (SELECT MAX(region) FROM demo_catalog.seguros_gobierno.usuarios_rol WHERE usuario = current_user());

-- ---------------------------------------------------------------- masks por tipo de PII
CREATE OR REPLACE FUNCTION demo_catalog.seguros_gobierno.mask_rfc(v STRING)
RETURNS STRING COMMENT 'RFC: SIU completo; agente prefijo+homoclave; resto solo prefijo'
RETURN CASE demo_catalog.seguros_gobierno.rol_actual()
  WHEN 'SIU' THEN v
  WHEN 'AGENTE_REGIONAL' THEN concat(substr(v, 1, 4), '******', substr(v, -3))
  ELSE concat(substr(v, 1, 4), '*********') END;

CREATE OR REPLACE FUNCTION demo_catalog.seguros_gobierno.mask_curp(v STRING)
RETURNS STRING COMMENT 'CURP: solo SIU la ve completa'
RETURN CASE WHEN demo_catalog.seguros_gobierno.rol_actual() = 'SIU' THEN v ELSE concat(substr(v, 1, 4), repeat('*', 14)) END;

CREATE OR REPLACE FUNCTION demo_catalog.seguros_gobierno.mask_nombre(v STRING)
RETURNS STRING COMMENT 'Nombre: SIU y agente lo ven; actuario/BI solo iniciales'
RETURN CASE WHEN demo_catalog.seguros_gobierno.rol_actual() IN ('SIU', 'AGENTE_REGIONAL') THEN v
  ELSE array_join(transform(split(v, ' '), x -> concat(substr(x, 1, 1), '.')), ' ') END;

CREATE OR REPLACE FUNCTION demo_catalog.seguros_gobierno.mask_email(v STRING)
RETURNS STRING COMMENT 'Email: SIU completo; agente dominio visible; resto oculto'
RETURN CASE demo_catalog.seguros_gobierno.rol_actual()
  WHEN 'SIU' THEN v
  WHEN 'AGENTE_REGIONAL' THEN concat(substr(v, 1, 1), '***@', substring_index(v, '@', -1))
  ELSE '***@***' END;

CREATE OR REPLACE FUNCTION demo_catalog.seguros_gobierno.mask_telefono(v STRING)
RETURNS STRING COMMENT 'Teléfono: SIU completo; agente últimos 4; resto oculto'
RETURN CASE demo_catalog.seguros_gobierno.rol_actual()
  WHEN 'SIU' THEN v
  WHEN 'AGENTE_REGIONAL' THEN concat('******', substr(v, -4))
  ELSE '**********' END;

CREATE OR REPLACE FUNCTION demo_catalog.seguros_gobierno.mask_vin_placas(v STRING)
RETURNS STRING COMMENT 'VIN/placas: SIU completo; resto últimos 3'
RETURN CASE WHEN demo_catalog.seguros_gobierno.rol_actual() = 'SIU' THEN v ELSE concat('*****', substr(v, -3)) END;

-- ---------------------------------------------------------------- filtro de filas por región
CREATE OR REPLACE FUNCTION demo_catalog.seguros_gobierno.filtro_region(region STRING)
RETURNS BOOLEAN COMMENT 'Agente regional solo ve su región; SIU/actuario/BI ven todo'
RETURN demo_catalog.seguros_gobierno.rol_actual() <> 'AGENTE_REGIONAL'
    OR region = demo_catalog.seguros_gobierno.region_actual();
