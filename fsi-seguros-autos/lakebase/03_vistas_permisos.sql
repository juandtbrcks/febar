-- =====================================================================================
-- Vistas de acceso + permisos mínimos para el service principal de la app (seguros-agente-siu)
-- La synced table serving.bandeja_siu no admite RLS propia (la administra el sync) → vista security_barrier
-- filtrada por región; el SP solo tiene SELECT sobre la vista, NO sobre la tabla sincronizada.
-- =====================================================================================
CREATE OR REPLACE VIEW app.bandeja WITH (security_barrier) AS
  SELECT b.*, c.id_caso, c.estatus AS estatus_caso,
         (SELECT count(*) FROM siu.notas n WHERE n.num_siniestro = b.num_siniestro AND app.region_ok(n.region)) AS num_notas
  FROM serving.bandeja_siu b
  LEFT JOIN siu.casos c ON c.num_siniestro = b.num_siniestro AND c.estatus NOT LIKE 'Cerrado%' AND app.region_ok(c.region)
  WHERE app.region_ok(b.region);

-- Región de un siniestro para sellar notas/casos (la app no confía en la región que mande el LLM)
CREATE OR REPLACE FUNCTION app.region_siniestro(p_num text) RETURNS text LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = serving, pg_temp AS $$
  SELECT region FROM serving.bandeja_siu WHERE num_siniestro = p_num
$$;

-- ---------------- permisos del SP de la app ----------------
GRANT CONNECT ON DATABASE siu TO "<UUID>";
GRANT USAGE ON SCHEMA app, siu TO "<UUID>";
GRANT SELECT ON app.bandeja TO "<UUID>";
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app TO "<UUID>";
GRANT SELECT, INSERT, UPDATE ON siu.casos TO "<UUID>";
GRANT SELECT, INSERT ON siu.notas TO "<UUID>";
GRANT SELECT ON siu.historial_estatus TO "<UUID>";
-- memoria del agente: el SP crea las tablas del checkpointer de LangGraph (setup()) dentro de agente
GRANT USAGE, CREATE ON SCHEMA agente TO "<UUID>";
GRANT SELECT, INSERT, UPDATE, DELETE ON agente.sesiones TO "<UUID>";
