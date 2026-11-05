-- =====================================================================================
-- Lakehouse Federation: las dos fuentes "legacy" se consultan SIN copiarlas.
--   seguros_dwh_onprem   → proxy del DWH Oracle on-prem (BD dwh_seguros en PostgreSQL)
--   seguros_creditos_aws → proxy de la BD de créditos personales en AWS (BD creditos_aws)
-- Dos conexiones a propósito: en un cliente real son sistemas distintos (on-prem vs nube).
-- GOTCHA: en CREATE FOREIGN CATALOG el COMMENT va ANTES de OPTIONS.
-- Recomendado: guardar la contraseña en un secret scope y usar secret('scope','key').
-- =====================================================================================
CREATE CONNECTION IF NOT EXISTS seguros_dwh_onprem TYPE postgresql
OPTIONS (host '<PG_HOST>', port '5432', user '<PG_USER>', password secret('<SECRET_SCOPE>', 'pg_password'))
COMMENT 'DWH de seguros (simula Oracle on-prem)';

CREATE CONNECTION IF NOT EXISTS seguros_creditos_aws TYPE postgresql
OPTIONS (host '<PG_HOST>', port '5432', user '<PG_USER>', password secret('<SECRET_SCOPE>', 'pg_password'))
COMMENT 'BD de créditos personales (simula AWS)';

CREATE FOREIGN CATALOG IF NOT EXISTS seguros_dwh_onprem USING CONNECTION seguros_dwh_onprem
COMMENT 'DWH de seguros vía federación — sin copiar datos'
OPTIONS (database 'dwh_seguros');

CREATE FOREIGN CATALOG IF NOT EXISTS seguros_creditos_aws USING CONNECTION seguros_creditos_aws
COMMENT 'Créditos personales vía federación — sin copiar datos'
OPTIONS (database 'creditos_aws');

-- Prueba: join entre "sistemas" sin mover datos
SELECT count(*) clientes_con_seguro_y_credito
FROM seguros_dwh_onprem.seguros_dwh.tb_clientes c
JOIN seguros_creditos_aws.seguros_creditos.creditos_personales k ON upper(k.customer_rfc) = c.rfc;
