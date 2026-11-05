"""Capa operativa del SIU en Lakebase (Postgres) — proyecto `seguros-siu`, base `siu`.

- La app se conecta como su service principal (OAuth de Lakebase, token renovado antes de expirar).
- Cada operación corre en una transacción con el CONTEXTO DEL USUARIO (`SET LOCAL app_ctx.usuario/rol/region`),
  tomado de Unity Catalog (rol_actual()/region_actual() vía OBO). Postgres lo hace cumplir con Row-Level Security:
  región para ver, rol SIU para abrir/cerrar casos, nadie firma notas por otro.
- `checkpointer()` → memoria persistente del agente LangGraph en el schema `agente`.
"""
import os, threading, time
from contextlib import contextmanager
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

ENDPOINT = os.environ.get("LAKEBASE_ENDPOINT", "projects/seguros-siu/branches/production/endpoints/primary")
ESTATUS = ["Abierto", "En investigación", "Cerrado - Fraude confirmado", "Cerrado - Procedente"]


@dataclass
class Contexto:
    usuario: str
    rol: str
    region: str | None  # None = todas (SIU / actuario)

    @property
    def region_pg(self):
        return self.region or "*"


class SinPermiso(Exception):
    """La política RLS de Lakebase rechazó la operación."""


class Lakebase:
    def __init__(self, ws):
        self.ws = ws
        self._tok, self._exp, self._lock = None, 0.0, threading.Lock()
        self.host = os.environ.get("PGHOST") or ws.postgres.get_endpoint(ENDPOINT).status.hosts.host
        self.db = os.environ.get("PGDATABASE", "siu")
        self.user = os.environ.get("PGUSER") or ws.config.client_id or ws.current_user.me().user_name
        lb = self

        class _Conn(psycopg.Connection):  # cada conexión nueva toma un token OAuth vigente
            @classmethod
            def connect(cls, conninfo="", **kw):
                kw["password"] = lb.token()
                return super().connect(conninfo, **kw)

        base = dict(host=self.host, port=5432, dbname=self.db, user=self.user, sslmode="require")
        common = dict(connection_class=_Conn, min_size=1, max_size=8, max_lifetime=45 * 60, open=True)
        self.pool = ConnectionPool(kwargs={**base, "autocommit": True, "row_factory": dict_row}, **common)
        self.pool_agente = ConnectionPool(kwargs={**base, "autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
                                          configure=lambda c: c.execute("SET search_path TO agente"), **common)

    def token(self):
        with self._lock:
            if not self._tok or time.time() > self._exp:
                self._tok = self.ws.postgres.generate_database_credential(endpoint=ENDPOINT).token
                self._exp = time.time() + 40 * 60
            return self._tok

    # ---------------- transacción con contexto de usuario ----------------
    @contextmanager
    def tx(self, ctx: Contexto):
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT set_config('app_ctx.usuario', %s, true), set_config('app_ctx.rol', %s, true), "
                        "set_config('app_ctx.region', %s, true)", (ctx.usuario, ctx.rol or "", ctx.region_pg))
            try:
                yield cur
            except psycopg.errors.InsufficientPrivilege as e:
                raise SinPermiso(str(e).split("\n")[0]) from e

    def q(self, ctx, sql, params=None):
        with self.tx(ctx) as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else []

    # ---------------- bandeja (synced table, reverse ETL) ----------------
    def bandeja(self, ctx, limite=60):
        t = time.perf_counter()
        filas = self.q(ctx, """SELECT num_siniestro, region, cobertura, prob_fraude, nivel_riesgo, monto_reclamado, monto_en_riesgo,
                                      razones_modelo, inconsistencias_documentales, id_caso, estatus_caso, num_notas, fecha_scoring
                               FROM app.bandeja ORDER BY prob_fraude DESC, monto_reclamado DESC LIMIT %s""", (limite,))
        return filas, (time.perf_counter() - t) * 1000

    def siniestro(self, ctx, num):
        r = self.q(ctx, "SELECT * FROM app.bandeja WHERE num_siniestro = %s", (num,))
        return r[0] if r else None

    # ---------------- notas ----------------
    def notas(self, ctx, num):
        return self.q(ctx, "SELECT id_nota, id_caso, autor, tipo, texto, fecha FROM siu.notas WHERE num_siniestro = %s ORDER BY fecha DESC", (num,))

    def agregar_nota(self, ctx, num, texto, tipo="nota"):
        with self.tx(ctx) as cur:
            cur.execute("SELECT app.region_siniestro(%s) r", (num,))
            region = cur.fetchone()["r"]
            if region is None:
                raise ValueError(f"{num} no está en la bandeja (solo siniestros abiertos calificados por el modelo).")
            cur.execute("SELECT id_caso FROM siu.casos WHERE num_siniestro = %s AND estatus NOT LIKE 'Cerrado%%'", (num,))
            caso = cur.fetchone()
            cur.execute("INSERT INTO siu.notas (num_siniestro, id_caso, region, autor, tipo, texto) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id_nota",
                        (num, caso["id_caso"] if caso else None, region, ctx.usuario, tipo, texto.strip()))
            return cur.fetchone()["id_nota"]

    # ---------------- casos ----------------
    def casos(self, ctx, estatus=None, limite=200):
        sql = ("SELECT id_caso, num_siniestro, region, prioridad, estatus, veredicto, asignado_a, monto_en_riesgo, prob_fraude_apertura, "
               "aprobado_por, origen, fecha_creacion, fecha_actualizacion FROM siu.casos")
        params = []
        if estatus:
            sql += " WHERE estatus = ANY(%s)"
            params.append(list(estatus))
        return self.q(ctx, sql + " ORDER BY fecha_actualizacion DESC LIMIT %s", params + [limite])

    def caso(self, ctx, id_caso):
        r = self.q(ctx, "SELECT * FROM siu.casos WHERE id_caso = %s", (id_caso,))
        return r[0] if r else None

    def historial(self, ctx, id_caso):
        return self.q(ctx, "SELECT estatus_anterior, estatus_nuevo, usuario, fecha FROM siu.historial_estatus WHERE id_caso = %s ORDER BY fecha", (id_caso,))

    def caso_abierto(self, ctx, num):
        r = self.q(ctx, "SELECT id_caso, estatus FROM siu.casos WHERE num_siniestro = %s AND estatus NOT LIKE 'Cerrado%%'", (num,))
        return r[0] if r else None

    def abrir_caso(self, ctx, args: dict, id_caso: str, aprobado_por: str):
        num = args["num_siniestro"]
        with self.tx(ctx) as cur:
            cur.execute("SELECT app.region_siniestro(%s) region", (num,))  # la región la sella Postgres, no el LLM
            region = cur.fetchone()["region"]
            cur.execute("SELECT prob_fraude, nivel_riesgo, modelo_version FROM app.bandeja WHERE num_siniestro = %s", (num,))
            s = cur.fetchone() or {}  # score del modelo al momento de abrir → luego se compara con el veredicto
            try:
                cur.execute("""INSERT INTO siu.casos (id_caso, num_siniestro, region, prioridad, resumen, recomendacion, monto_en_riesgo,
                                 prob_fraude_apertura, nivel_riesgo_apertura, modelo_version, asignado_a, creado_por, aprobado_por)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (id_caso, num, region, args.get("prioridad", "Media"), args.get("resumen", ""), args.get("recomendacion", ""),
                             float(args.get("monto_en_riesgo") or 0), s.get("prob_fraude"), s.get("nivel_riesgo"), s.get("modelo_version"),
                             ctx.usuario, ctx.usuario, aprobado_por))
            except psycopg.errors.UniqueViolation:
                raise ValueError(f"Ya existe un caso abierto para {num}.")
            cur.execute("INSERT INTO siu.notas (num_siniestro, id_caso, region, autor, tipo, texto) VALUES (%s,%s,%s,%s,'dictamen_agente',%s)",
                        (num, id_caso, region, ctx.usuario,
                         f"Caso abierto desde el Agente Investigador (aprobado por {aprobado_por}).\nResumen: {args.get('resumen', '')}\n"
                         f"Recomendación: {args.get('recomendacion', '')}"))
        return id_caso

    def cambiar_estatus(self, ctx, id_caso, estatus, comentario="", asignado_a=None):
        with self.tx(ctx) as cur:
            cur.execute("UPDATE siu.casos SET estatus = %s, asignado_a = coalesce(%s, asignado_a) WHERE id_caso = %s RETURNING num_siniestro, region",
                        (estatus, asignado_a or None, id_caso))
            r = cur.fetchone()
            if not r:
                raise SinPermiso("El caso no existe o no tienes acceso.")
            cur.execute("INSERT INTO siu.notas (num_siniestro, id_caso, region, autor, tipo, texto) VALUES (%s,%s,%s,%s,'cambio_estatus',%s)",
                        (r["num_siniestro"], id_caso, r["region"], ctx.usuario, f"Estatus → {estatus}." + (f" {comentario.strip()}" if comentario.strip() else "")))

    def metricas(self, ctx):
        r = self.q(ctx, """SELECT count(*) FILTER (WHERE estatus NOT LIKE 'Cerrado%%') abiertos,
                                  count(*) FILTER (WHERE veredicto = 'fraude') fraudes,
                                  count(*) FILTER (WHERE veredicto = 'legitimo') procedentes,
                                  coalesce(sum(monto_en_riesgo) FILTER (WHERE veredicto = 'fraude'), 0) monto_evitado
                           FROM siu.casos""")
        return r[0]

    # ---------------- sesiones del agente ----------------
    def sesiones(self, ctx, limite=15):
        return self.q(ctx, "SELECT hilo, titulo, num_siniestro, actualizada, aprobacion_pendiente FROM agente.sesiones "
                           "ORDER BY actualizada DESC LIMIT %s", (limite,))

    def guardar_sesion(self, ctx, hilo, titulo, num_siniestro, pendiente):
        self.q(ctx, """INSERT INTO agente.sesiones (hilo, usuario, titulo, num_siniestro, aprobacion_pendiente) VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT (hilo) DO UPDATE SET actualizada = now(), aprobacion_pendiente = EXCLUDED.aprobacion_pendiente,
                         num_siniestro = coalesce(EXCLUDED.num_siniestro, agente.sesiones.num_siniestro)""",
               (hilo, ctx.usuario, (titulo or "Conversación")[:120], num_siniestro, bool(pendiente)))

    # ---------------- memoria del agente (LangGraph) ----------------
    def checkpointer(self):
        from langgraph.checkpoint.postgres import PostgresSaver
        saver = PostgresSaver(self.pool_agente)
        saver.setup()  # idempotente: crea/migra checkpoints, checkpoint_blobs, checkpoint_writes en el schema agente
        return saver
