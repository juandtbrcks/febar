"""Agente Investigador SIU — Aseguradora FSI · Autos (Databricks App · Streamlit).
- Las herramientas (funciones de UC) corren con el token del USUARIO (on-behalf-of) → ABAC por rol/región.
- El LLM se invoca con el service principal de la app a través del model service de Unity Catalog.
- Lakebase (seguros-siu): bandeja sincronizada desde el lakehouse (reverse ETL), expediente del SIU (casos, notas,
  estatus con RLS) y memoria persistente del agente (checkpointer de LangGraph + sesiones por usuario).
"""
import json, os, re, uuid

import mlflow
from mlflow.entities import AssessmentSource
import pandas as pd
import streamlit as st
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

from agente_siu import AgenteSIU, texto
from lakebase import ESTATUS, Contexto, Lakebase, SinPermiso
from sql_uc import crear_sql

WAREHOUSE_ID = os.environ["WAREHOUSE_ID"]
EXPERIMENTO = os.environ.get("MLFLOW_EXPERIMENT", "/Users/<tu_usuario>/seguros_agente_siu")
NOMBRES = {"bandeja_siu": "Bandeja SIU", "detalle_siniestro": "Detalle del siniestro", "evidencia_documental": "Evidencia documental (IA)",
           "historial_cliente": "Historial del asegurado", "perfil_taller": "Perfil del taller", "expediente_siu": "Expediente SIU (Lakebase)",
           "abrir_caso_investigacion": "Abrir caso"}
ICONO_TIPO = {"nota": "📝", "dictamen_agente": "🛡️", "cambio_estatus": "🔁"}

st.set_page_config(page_title="FSI · Agente Investigador SIU", page_icon="🛡️", layout="wide")
st.markdown("""<style>
.block-container {padding-top: 1.2rem;}
.badge {display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.8rem;margin-right:6px;background:#E8EEF2;color:#1B3139}
.nota {border-left:3px solid #C9D3DA;padding:4px 10px;margin:6px 0;font-size:0.9rem}
</style>""", unsafe_allow_html=True)

# ---------------- identidades ----------------
cfg = Config()
app_ws = WorkspaceClient()  # service principal de la app (LLM, tracing, Lakebase)
hdr = st.context.headers
user_token = hdr.get("x-forwarded-access-token")
user_email = hdr.get("x-forwarded-email") or "local"
user_ws = WorkspaceClient(host=cfg.host, token=user_token, auth_type="pat") if user_token else app_ws
sql_usuario = crear_sql(user_ws, WAREHOUSE_ID)


def token_app():
    return app_ws.config.authenticate()["Authorization"].split(" ", 1)[1]


@st.cache_resource
def _mlflow():
    try:
        mlflow.set_tracking_uri("databricks")
        mlflow.set_experiment(EXPERIMENTO)
        return True
    except Exception as e:  # el tracing es opcional: la app funciona sin él
        print("MLflow tracing no disponible:", e)
        return False


@st.cache_resource(show_spinner="Conectando a Lakebase…")
def _lakebase():
    lb = Lakebase(app_ws)
    return lb, lb.checkpointer()


_mlflow()
lb, checkpointer = _lakebase()


@st.cache_data(ttl=60, show_spinner=False)
def perfil(_email):
    try:
        r = sql_usuario("SELECT demo_catalog.seguros_gobierno.rol_actual() rol, demo_catalog.seguros_gobierno.region_actual() region")
        return r[0] if r else {}
    except Exception:
        return {}


p = perfil(user_email)
# Sin perfil de UC → contexto que Postgres niega (región inexistente), nunca "todas"
ctx = Contexto(usuario=user_email, rol=p.get("rol") or "", region=(p.get("region") or None) if p else "—sin acceso—")
es_siu = ctx.rol == "SIU"

if "agente" not in st.session_state:
    st.session_state.agente = AgenteSIU(cfg.host, token_app, sql_usuario, usuario=user_email, lakebase=lb, ctx=ctx, checkpointer=checkpointer)
    st.session_state.hilo = uuid.uuid4().hex
    st.session_state.mensajes, st.session_state.pendiente = [], None
ag: AgenteSIU = st.session_state.agente
ag.ctx = ctx  # el rol/región puede cambiar durante la demo (UPDATE usuarios_rol) → siempre el vigente


def siniestro_en_conversacion(msgs):
    for m in reversed(msgs):
        for t in m.get("tool_calls") or []:
            n = json.loads(t["function"].get("arguments") or "{}").get("num_siniestro")
            if n:
                return n
        if m.get("role") == "user" and (x := re.search(r"S\d{12}", m.get("content") or "")):
            return x.group(0)
    return None


def correr(texto_usuario=None, reanudar=None):
    with st.spinner("El agente está investigando…"):
        try:
            msgs, pend = ag.preguntar(st.session_state.hilo, texto_usuario, reanudar)
            st.session_state.mensajes, st.session_state.pendiente = msgs, pend
            st.session_state.trace_id, st.session_state.voto = getattr(ag, "ultimo_trace_id", None), None
            st.session_state.error = None
            primera = next((m["content"] for m in msgs if m.get("role") == "user"), texto_usuario)
            lb.guardar_sesion(ctx, st.session_state.hilo, primera, siniestro_en_conversacion(msgs), pend)
        except Exception as e:  # se guarda para mostrarlo después del st.rerun() (si no, el rerun lo borra)
            st.session_state.error = str(e)[:600]


def retomar(hilo):
    st.session_state.hilo = hilo
    st.session_state.mensajes, st.session_state.pendiente = ag.estado(hilo)
    st.session_state.trace_id, st.session_state.error = None, None


def mostrar_notas(num):
    notas = lb.notas(ctx, num)
    if not notas:
        st.caption("Sin notas todavía.")
    for n in notas:
        st.markdown(f"<div class='nota'>{ICONO_TIPO.get(n['tipo'], '📝')} <b>{n['autor'].split('@')[0]}</b> · "
                    f"{n['fecha']:%d/%m %H:%M}<br>{n['texto'].replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)


# ---------------- barra lateral: memoria del agente ----------------
with st.sidebar:
    st.markdown("### 🧠 Mis investigaciones")
    st.caption("Conversaciones guardadas en Lakebase (checkpointer de LangGraph): cierra la app y retómalas después, "
               "incluso con una aprobación pendiente.")
    if st.button("➕ Nueva investigación", use_container_width=True):
        st.session_state.hilo, st.session_state.mensajes, st.session_state.pendiente = uuid.uuid4().hex, [], None
        st.session_state.trace_id = st.session_state.error = None
        st.rerun()
    try:
        for s in lb.sesiones(ctx):
            activo = s["hilo"] == st.session_state.hilo
            etiqueta = ("✋ " if s["aprobacion_pendiente"] else "") + (s["titulo"] or "Conversación")[:48]
            if st.button(etiqueta, key=f"ses-{s['hilo']}", use_container_width=True, type="primary" if activo else "secondary",
                         help=f"{s['num_siniestro'] or ''} · {s['actualizada']:%d/%m %H:%M}"):
                retomar(s["hilo"])
                st.rerun()
    except Exception as e:
        st.warning(f"No se pudieron leer las sesiones: {e}")

# ---------------- encabezado ----------------
c1, c2 = st.columns([3, 2])
with c1:
    st.markdown("## 🛡️ Agente Investigador SIU")
    st.caption("Aseguradora FSI · Autos — LangGraph + model service de Unity Catalog · herramientas gobernadas por ABAC · expediente en Lakebase")
with c2:
    st.markdown(f"<div style='text-align:right;padding-top:18px'><span class='badge'>👤 {user_email}</span>"
                f"<span class='badge'>Rol: {p.get('rol', '—')}</span><span class='badge'>Región: {p.get('region') or 'Todas'}</span></div>",
                unsafe_allow_html=True)

izq, der = st.columns([1.15, 1.35], gap="large")

# ---------------- bandeja / casos / ciclo ----------------
with izq:
    t1, t2, t3 = st.tabs(["📥 Bandeja SIU", "📁 Casos", "🔁 Ciclo SIU → modelo"])
    with t1:
        try:
            filas, ms = lb.bandeja(ctx)
            b = pd.DataFrame(filas)
            if b.empty:
                st.info("Sin siniestros visibles para tu rol/región.")
            else:
                st.caption(f"⚡ Leída de **Lakebase** (synced table desde el lakehouse) en **{ms:.0f} ms** · "
                           f"scoring del {pd.to_datetime(b['fecha_scoring'].max()):%d/%m/%Y}")
                v = pd.DataFrame({
                    "Siniestro": b["num_siniestro"], "Región": b["region"], "Cobertura": b["cobertura"],
                    "Prob. %": (b["prob_fraude"].astype(float) * 100).round(1), "Riesgo": b["nivel_riesgo"],
                    "Monto": b["monto_reclamado"].astype(float).map("${:,.0f}".format),
                    "📄": b["inconsistencias_documentales"].fillna("").map(lambda x: "⚠️" if x else ""),
                    "Caso": b["estatus_caso"].fillna(""), "📝": b["num_notas"].astype(int).map(lambda n: n or "")})
                st.dataframe(v, hide_index=True, use_container_width=True, height=330)
                sel = st.selectbox("Siniestro", b["num_siniestro"].tolist(), index=None, placeholder="Elige uno de la bandeja…")
                if sel:
                    if st.button(f"🔎 Investigar {sel} con el agente", disabled=bool(st.session_state.pendiente), use_container_width=True):
                        st.session_state.hilo, st.session_state.mensajes, st.session_state.pendiente = uuid.uuid4().hex, [], None
                        correr(f"Investiga el siniestro {sel} y dame tu dictamen preliminar.")
                        st.rerun()
                    with st.expander(f"🗂️ Expediente de {sel}", expanded=True):
                        with st.form(f"nota-{sel}", clear_on_submit=True):
                            nueva = st.text_area("Nueva nota", placeholder="Hallazgo, llamada, documento solicitado…", height=80)
                            if st.form_submit_button("📝 Agregar nota") and nueva.strip():
                                try:
                                    lb.agregar_nota(ctx, sel, nueva)
                                    st.toast("Nota guardada en Lakebase")
                                except SinPermiso as e:
                                    st.error(f"Lakebase (RLS) rechazó la nota: {e}")
                        mostrar_notas(sel)
        except Exception as e:
            st.error(f"No se pudo leer la bandeja: {e}")

    with t2:
        try:
            filtro = st.multiselect("Estatus", ESTATUS, default=["Abierto", "En investigación"])
            cs = pd.DataFrame(lb.casos(ctx, filtro or None))
            if cs.empty:
                st.info("No hay casos con ese filtro.")
            else:
                st.dataframe(cs[["id_caso", "num_siniestro", "region", "prioridad", "estatus", "asignado_a", "monto_en_riesgo",
                                 "fecha_actualizacion"]].assign(asignado_a=lambda d: d["asignado_a"].fillna("").str.split("@").str[0]),
                             hide_index=True, use_container_width=True, height=250)
                idc = st.selectbox("Caso", cs["id_caso"].tolist(), index=None, placeholder="Elige un caso…")
                if idc:
                    c = lb.caso(ctx, idc)
                    st.markdown(f"**{c['id_caso']}** · {c['num_siniestro']} · {c['region']} · prioridad **{c['prioridad']}** · "
                                f"score al abrir {float(c['prob_fraude_apertura'] or 0) * 100:.0f}% · {c['estatus']}")
                    st.caption(c["resumen"] or "")
                    with st.form(f"estatus-{idc}"):
                        e1, e2 = st.columns(2)
                        nuevo = e1.selectbox("Estatus", ESTATUS, index=ESTATUS.index(c["estatus"]))
                        asig = e2.text_input("Asignado a", value=c["asignado_a"] or "")
                        com = st.text_input("Comentario", placeholder="Motivo del cambio / dictamen final")
                        if st.form_submit_button("Guardar", disabled=not es_siu):
                            try:
                                lb.cambiar_estatus(ctx, idc, nuevo, com, asig)
                                st.toast(f"{idc} → {nuevo}")
                                st.rerun()
                            except SinPermiso as e:
                                st.error(f"Lakebase (RLS) rechazó el cambio: {e}")
                        if not es_siu:
                            st.caption("🔒 Solo el rol SIU puede cambiar estatus (política RLS en Lakebase).")
                    with st.expander("Bitácora de estatus"):
                        st.dataframe(pd.DataFrame(lb.historial(ctx, idc)), hide_index=True, use_container_width=True)
                    mostrar_notas(c["num_siniestro"])
        except Exception as e:
            st.error(f"No se pudieron leer los casos: {e}")

    with t3:
        try:
            m = lb.metricas(ctx)
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Casos activos", f"{m['abiertos']:,}")
            k2.metric("Fraude confirmado", f"{m['fraudes']:,}")
            k3.metric("Procedentes", f"{m['procedentes']:,}")
            k4.metric("Monto evitado", f"${float(m['monto_evitado']) / 1e6:,.1f} M")
            st.markdown(
                "**Cómo se cierra el ciclo**\n"
                "1. El modelo califica los siniestros en el lakehouse → `bandeja_siu_serving` (Delta, CDF).\n"
                "2. **Reverse ETL**: la synced table la lleva a Lakebase → esta bandeja en milisegundos.\n"
                "3. El investigador trabaja el caso aquí (notas, estatus, veredicto) → transacciones en Postgres con RLS.\n"
                "4. **CDF de Lakebase → Delta**: `demo_catalog.seguros_siu_expediente.*` se actualiza solo, sin ETL.\n"
                "5. Los veredictos del SIU entran como **etiquetas** al reentrenamiento del modelo (job MLOps) y a Genie.")
        except Exception as e:
            st.error(f"No se pudieron leer las métricas: {e}")

# ---------------- chat ----------------
with der:
    caja = st.container(height=560)
    with caja:
        if not st.session_state.mensajes:
            st.markdown("**Prueba con:**\n- ¿Qué 5 siniestros debo revisar primero en la región Centro?\n"
                        "- Investiga el siniestro S202600000146\n- ¿Qué tan confiable es el taller de ese siniestro frente a la red?")
        for m in st.session_state.mensajes:
            if m["role"] == "user":
                st.chat_message("user").markdown(m["content"])
            elif m["role"] == "assistant":
                if m.get("tool_calls"):
                    usadas = " · ".join(NOMBRES.get(t["function"]["name"], t["function"]["name"]) for t in m["tool_calls"])
                    with st.chat_message("assistant", avatar="🔧"):
                        with st.expander(f"Consultó: {usadas}"):
                            for t in m["tool_calls"]:
                                st.code(f"{t['function']['name']}({t['function'].get('arguments', '')})", language="json")
                if texto(m).strip():
                    st.chat_message("assistant", avatar="🛡️").markdown(texto(m))

    msgs = st.session_state.mensajes
    ultimo = texto(msgs[-1]) if msgs and msgs[-1].get("role") == "assistant" else ""
    num_ctx = siniestro_en_conversacion(msgs) if msgs else None
    tid = st.session_state.get("trace_id")
    if msgs and not st.session_state.pendiente:
        f1, f2, f3 = st.columns([1, 1, 3])
        if tid:
            if st.session_state.get("voto"):
                f1.caption(f"Evaluación: {st.session_state.voto} ✓")
            else:
                for col, util, etiqueta in [(f1, True, "👍 Útil"), (f2, False, "👎 No útil")]:
                    if col.button(etiqueta, key=f"voto-{tid}-{util}"):
                        try:
                            mlflow.log_feedback(trace_id=tid, name="satisfaccion_investigador", value=util,
                                                source=AssessmentSource(source_type="HUMAN", source_id=user_email))
                            st.session_state.voto = "útil" if util else "no útil"
                        except Exception as e:
                            st.warning(f"No se pudo registrar la evaluación: {e}")
                        st.rerun()
        if ultimo.strip() and num_ctx and f3.button(f"🗂️ Guardar dictamen en el expediente de {num_ctx}", use_container_width=True):
            try:
                lb.agregar_nota(ctx, num_ctx, f"Dictamen preliminar del agente:\n{ultimo}", tipo="dictamen_agente")
                st.toast("Dictamen guardado en Lakebase")
            except (SinPermiso, ValueError) as e:
                st.error(f"No se pudo guardar: {e}")

    if st.session_state.get("error"):
        st.error(f"El agente no pudo responder: {st.session_state.error}")

    pend = st.session_state.pendiente
    if pend:
        prop = pend.get("propuesta", {})
        with st.container(border=True):
            st.markdown(f"#### ✋ Aprobación requerida — abrir caso SIU para **{prop.get('num_siniestro')}**")
            st.markdown(f"**Prioridad:** {prop.get('prioridad')} · **Monto en riesgo:** ${float(prop.get('monto_en_riesgo') or 0):,.0f} MXN")
            st.markdown(f"**Resumen:** {prop.get('resumen', '')}")
            st.markdown(f"**Recomendación:** {prop.get('recomendacion', '')}")
            st.caption("La aprobación pendiente está guardada en Lakebase: puedes cerrar la app y retomarla desde *Mis investigaciones*.")
            a, r = st.columns(2)
            if a.button("✅ Aprobar y registrar", type="primary", use_container_width=True):
                correr(reanudar={"aprobado": True}); st.rerun()
            if r.button("❌ Rechazar", use_container_width=True):
                correr(reanudar={"aprobado": False}); st.rerun()

    pregunta = st.chat_input("Pregunta al agente…", disabled=bool(pend))
    if pregunta:
        correr(pregunta)
        st.rerun()
    st.caption("Dictamen preliminar de apoyo: la decisión final es del investigador. Cada paso queda trazado en MLflow y cada llamada al "
               "modelo en la inference table del model service.")
