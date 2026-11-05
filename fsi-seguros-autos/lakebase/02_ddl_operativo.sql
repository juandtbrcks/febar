-- =====================================================================================
-- Lakebase seguros-siu · base siu — capa OPERATIVA del SIU
--   serving.*  → synced tables desde el lakehouse (reverse ETL, solo lectura; las crea el sync)
--   siu.*      → expediente del investigador: casos, notas, historial (OLTP; se replica a Delta vía CDF → pieza 4)
--   app.*      → funciones y vistas de acceso (RLS / región)
--   agente.*   → memoria del agente LangGraph (checkpointer) + sesiones por usuario
-- Gobierno: la identidad y la región vienen de Unity Catalog (rol_actual()/region_actual() vía OBO); la app las
-- propaga a la sesión de Postgres (SET LOCAL app_ctx.*) y Postgres las hace cumplir con Row-Level Security.
-- Ejecutar como owner (<tu_usuario>):  ./pg.sh -f 02_ddl_operativo.sql
-- =====================================================================================
CREATE SCHEMA IF NOT EXISTS siu;
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS agente;

-- ---------------- contexto de seguridad ----------------
CREATE OR REPLACE FUNCTION app.region_ok(r text) RETURNS boolean LANGUAGE sql STABLE AS $$
  SELECT coalesce(current_setting('app_ctx.region', true), '') = '*' OR r = current_setting('app_ctx.region', true)
$$;
CREATE OR REPLACE FUNCTION app.es_siu() RETURNS boolean LANGUAGE sql STABLE AS $$
  SELECT coalesce(current_setting('app_ctx.rol', true), '') = 'SIU'
$$;
CREATE OR REPLACE FUNCTION app.usuario() RETURNS text LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app_ctx.usuario', true), '')
$$;

-- ---------------- expediente SIU ----------------
CREATE TABLE IF NOT EXISTS siu.casos (
  id_caso               text PRIMARY KEY,
  num_siniestro         text NOT NULL,
  region                text,
  prioridad             text NOT NULL CHECK (prioridad IN ('Alta','Media','Baja')),
  resumen               text,
  recomendacion         text,
  monto_en_riesgo       numeric(14,2),
  prob_fraude_apertura  numeric(6,4),      -- score del modelo al abrir el caso (para medir el modelo vs el veredicto)
  nivel_riesgo_apertura text,
  modelo_version        int,
  estatus               text NOT NULL DEFAULT 'Abierto'
                        CHECK (estatus IN ('Abierto','En investigación','Cerrado - Fraude confirmado','Cerrado - Procedente')),
  veredicto             text CHECK (veredicto IN ('fraude','legitimo')),
  asignado_a            text,
  creado_por            text NOT NULL,
  aprobado_por          text,
  origen                text NOT NULL DEFAULT 'Agente Investigador SIU',
  fecha_creacion        timestamptz NOT NULL DEFAULT now(),
  fecha_actualizacion   timestamptz NOT NULL DEFAULT now(),
  fecha_cierre          timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS casos_un_abierto_por_siniestro ON siu.casos (num_siniestro) WHERE estatus NOT LIKE 'Cerrado%';
CREATE INDEX IF NOT EXISTS casos_estatus ON siu.casos (estatus, region);

CREATE TABLE IF NOT EXISTS siu.notas (
  id_nota        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  num_siniestro  text NOT NULL,
  id_caso        text REFERENCES siu.casos(id_caso),
  region         text,
  autor          text NOT NULL,
  tipo           text NOT NULL DEFAULT 'nota' CHECK (tipo IN ('nota','dictamen_agente','cambio_estatus')),
  texto          text NOT NULL CHECK (length(texto) BETWEEN 1 AND 8000),
  fecha          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS notas_siniestro ON siu.notas (num_siniestro, fecha DESC);

CREATE TABLE IF NOT EXISTS siu.historial_estatus (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_caso          text NOT NULL REFERENCES siu.casos(id_caso),
  region           text,
  estatus_anterior text,
  estatus_nuevo    text NOT NULL,
  usuario          text,
  fecha            timestamptz NOT NULL DEFAULT now()
);

-- Trigger: mantiene fechas/veredicto y la bitácora de estatus (auditoría transaccional dentro de Postgres)
-- SECURITY DEFINER: la bitácora la escribe el owner; la app NO tiene INSERT directo sobre historial_estatus
CREATE OR REPLACE FUNCTION siu.tg_casos() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = siu, app, pg_temp AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO siu.historial_estatus (id_caso, region, estatus_anterior, estatus_nuevo, usuario)
    VALUES (NEW.id_caso, NEW.region, NULL, NEW.estatus, coalesce(app.usuario(), NEW.creado_por));
    RETURN NEW;
  END IF;
  NEW.fecha_actualizacion := now();
  IF NEW.estatus IS DISTINCT FROM OLD.estatus THEN
    NEW.veredicto := CASE NEW.estatus WHEN 'Cerrado - Fraude confirmado' THEN 'fraude' WHEN 'Cerrado - Procedente' THEN 'legitimo' END;
    NEW.fecha_cierre := CASE WHEN NEW.estatus LIKE 'Cerrado%' THEN now() END;
    INSERT INTO siu.historial_estatus (id_caso, region, estatus_anterior, estatus_nuevo, usuario)
    VALUES (NEW.id_caso, NEW.region, OLD.estatus, NEW.estatus, app.usuario());
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS casos_bitacora_ins ON siu.casos;
DROP TRIGGER IF EXISTS casos_bitacora_upd ON siu.casos;
CREATE TRIGGER casos_bitacora_ins AFTER INSERT ON siu.casos FOR EACH ROW EXECUTE FUNCTION siu.tg_casos();
CREATE TRIGGER casos_bitacora_upd BEFORE UPDATE ON siu.casos FOR EACH ROW EXECUTE FUNCTION siu.tg_casos();

-- ---------------- Row-Level Security ----------------
ALTER TABLE siu.casos ENABLE ROW LEVEL SECURITY;
ALTER TABLE siu.notas ENABLE ROW LEVEL SECURITY;
ALTER TABLE siu.historial_estatus ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS casos_ver ON siu.casos;
DROP POLICY IF EXISTS casos_abrir ON siu.casos;
DROP POLICY IF EXISTS casos_actualizar ON siu.casos;
CREATE POLICY casos_ver ON siu.casos FOR SELECT USING (app.region_ok(region));
CREATE POLICY casos_abrir ON siu.casos FOR INSERT WITH CHECK (app.es_siu() AND app.region_ok(region));        -- solo el SIU abre casos
CREATE POLICY casos_actualizar ON siu.casos FOR UPDATE USING (app.region_ok(region)) WITH CHECK (app.es_siu());  -- solo el SIU cambia estatus

DROP POLICY IF EXISTS notas_ver ON siu.notas;
DROP POLICY IF EXISTS notas_escribir ON siu.notas;
CREATE POLICY notas_ver ON siu.notas FOR SELECT USING (app.region_ok(region));
CREATE POLICY notas_escribir ON siu.notas FOR INSERT WITH CHECK (app.region_ok(region) AND autor = app.usuario());  -- nadie firma por otro

DROP POLICY IF EXISTS hist_ver ON siu.historial_estatus;
CREATE POLICY hist_ver ON siu.historial_estatus FOR SELECT USING (app.region_ok(region));

-- ---------------- memoria del agente ----------------
CREATE TABLE IF NOT EXISTS agente.sesiones (
  hilo            text PRIMARY KEY,
  usuario         text NOT NULL,
  titulo          text,
  num_siniestro   text,
  creada          timestamptz NOT NULL DEFAULT now(),
  actualizada     timestamptz NOT NULL DEFAULT now(),
  aprobacion_pendiente boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS sesiones_usuario ON agente.sesiones (usuario, actualizada DESC);
ALTER TABLE agente.sesiones ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sesiones_propias ON agente.sesiones;
CREATE POLICY sesiones_propias ON agente.sesiones USING (usuario = app.usuario()) WITH CHECK (usuario = app.usuario());

-- ---------------- Pieza 4: CDF Lakebase → Delta (requiere REPLICA IDENTITY FULL) ----------------
ALTER TABLE siu.casos REPLICA IDENTITY FULL;
ALTER TABLE siu.notas REPLICA IDENTITY FULL;
ALTER TABLE siu.historial_estatus REPLICA IDENTITY FULL;
