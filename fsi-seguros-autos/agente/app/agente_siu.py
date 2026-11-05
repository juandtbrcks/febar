"""Agente Investigador SIU — Aseguradora FSI · Autos (LangGraph + model service de Unity Catalog).

- LLM: model service `demo_catalog.seguros_ml.model_service_demo_agente` vía AI Gateway (API compatible con OpenAI).
- Herramientas: funciones de Unity Catalog ejecutadas con la identidad del usuario → aplican las políticas ABAC.
- `abrir_caso_investigacion` interrumpe el grafo (human-in-the-loop) y solo escribe si el investigador aprueba.
- Los mensajes del modelo se guardan tal cual (dicts) para conservar campos extra como la thought signature de Gemini.
- Lakebase (opcional): memoria persistente del grafo (checkpointer Postgres), expediente del SIU (casos/notas) y
  registro de casos con RLS. Sin Lakebase (eval/pruebas) usa MemorySaver y la tabla Delta casos_investigacion.
"""
import json, uuid
from typing import Annotated, TypedDict

import mlflow
from openai import OpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.errors import GraphBubbleUp
from langgraph.checkpoint.memory import MemorySaver

MODEL_SERVICE = "demo_catalog.seguros_ml.model_service_demo_agente"
FN = "demo_catalog.seguros_ml"

SYSTEM = """Eres el Agente Investigador del SIU (Unidad Especial de Investigación de fraude) de Aseguradora FSI, ramo Autos (México).
Ayudas a los investigadores a priorizar y analizar siniestros sospechosos. Responde SIEMPRE en español, claro y profesional.

Reglas:
- Usa SOLO datos que obtengas con tus herramientas; nunca inventes cifras, nombres ni siniestros. Si una herramienta no devuelve datos,
  dilo (puede ser que el usuario no tenga acceso a esa región: las políticas de Unity Catalog filtran lo que cada rol ve).
- Para investigar un siniestro consulta: detalle_siniestro, evidencia_documental, historial_cliente, perfil_taller y
  expediente_siu (notas de los investigadores y si ya hay un caso abierto). Si hay notas, intégralas en el dictamen y cítalas
  como "nota del investigador"; si ya existe un caso abierto, NO propongas abrir otro.
- Al investigar entrega un DICTAMEN PRELIMINAR con: 1) Resumen, 2) Señales de alerta (con cifras), 3) Señales atenuantes,
  4) Recomendación (abrir caso / revisar documentación / pagar) y nivel de prioridad (Alta/Media/Baja).
- NO llames abrir_caso_investigacion por iniciativa propia: entrega primero el dictamen y PREGUNTA si desea abrir un caso.
  Solo llámala cuando el investigador lo pida explícitamente; él deberá aprobarlo antes de que se registre.
- Montos en MXN con separador de miles. La PII puede venir enmascarada según el rol: no intentes reconstruirla.
- Aclara que es un dictamen preliminar de apoyo; la decisión final es del investigador."""

TOOLS = [
    {"type": "function", "function": {"name": "bandeja_siu",
        "description": "Lista priorizada de siniestros ABIERTOS por probabilidad de fraude del modelo, con razones e inconsistencias documentales.",
        "parameters": {"type": "object", "properties": {
            "region": {"type": "string", "description": "Región opcional (Centro, Norte, Occidente, Noroeste, Sureste, Bajío). Omitir para todas."},
            "top_n": {"type": "integer", "description": "Cuántos siniestros devolver (default 10, máximo 50)."}}}}},
    {"type": "function", "function": {"name": "detalle_siniestro",
        "description": "Ficha de un siniestro: evento, señales operativas de fraude y calificación/razones del modelo.",
        "parameters": {"type": "object", "properties": {"num_siniestro": {"type": "string"}}, "required": ["num_siniestro"]}}},
    {"type": "function", "function": {"name": "evidencia_documental",
        "description": "Resultado de la lectura con IA del presupuesto del taller (PDF) validado contra los sistemas: total, VIN, placas, fecha.",
        "parameters": {"type": "object", "properties": {"num_siniestro": {"type": "string"}}, "required": ["num_siniestro"]}}},
    {"type": "function", "function": {"name": "historial_cliente",
        "description": "Perfil del asegurado: antigüedad, crédito en el grupo, pólizas, historial de siniestros y fraudes previos.",
        "parameters": {"type": "object", "properties": {"num_siniestro": {"type": "string"}}, "required": ["num_siniestro"]}}},
    {"type": "function", "function": {"name": "perfil_taller",
        "description": "Perfil del taller del siniestro vs la red: tasa de fraude, presupuesto vs autorizado, % de presupuestos inflados.",
        "parameters": {"type": "object", "properties": {"num_siniestro": {"type": "string"}}, "required": ["num_siniestro"]}}},
    {"type": "function", "function": {"name": "expediente_siu",
        "description": "Expediente operativo del SIU para un siniestro: caso abierto (estatus, asignado) y notas de los investigadores.",
        "parameters": {"type": "object", "properties": {"num_siniestro": {"type": "string"}}, "required": ["num_siniestro"]}}},
    {"type": "function", "function": {"name": "abrir_caso_investigacion",
        "description": "Propone abrir un caso formal de investigación SIU. Requiere aprobación del investigador antes de registrarse.",
        "parameters": {"type": "object", "properties": {
            "num_siniestro": {"type": "string"},
            "prioridad": {"type": "string", "enum": ["Alta", "Media", "Baja"]},
            "resumen": {"type": "string", "description": "Resumen de los hallazgos (2-4 frases)."},
            "recomendacion": {"type": "string"},
            "monto_en_riesgo": {"type": "number", "description": "Monto en riesgo estimado en MXN."}},
            "required": ["num_siniestro", "prioridad", "resumen", "recomendacion"]}}},
]

SQL_TOOLS = {
    "bandeja_siu": f"SELECT * FROM {FN}.agente_bandeja_siu(region_filtro => :region, top_n => :top_n)",
    "detalle_siniestro": f"SELECT * FROM {FN}.agente_detalle_siniestro(:num_siniestro)",
    "evidencia_documental": f"SELECT * FROM {FN}.agente_evidencia_documental(:num_siniestro)",
    "historial_cliente": f"SELECT * FROM {FN}.agente_historial_cliente(:num_siniestro)",
    "perfil_taller": f"SELECT * FROM {FN}.agente_perfil_taller(:num_siniestro)",
}


def texto(msg: dict) -> str:
    """Texto visible de un mensaje (Gemini puede devolver `content` como lista de partes con thoughtSignature)."""
    c = msg.get("content")
    if isinstance(c, list):
        return "".join(p.get("text", "") for p in c if isinstance(p, dict))
    return c or ""


def _add(a: list, b: list) -> list:
    return a + b


class Estado(TypedDict):
    messages: Annotated[list, _add]


class AgenteSIU:
    """`sql(statement, params) -> list[dict]` ejecuta SQL con la identidad del usuario (ABAC aplica)."""

    def __init__(self, host: str, token_llm, sql, usuario: str = "", max_pasos: int = 12, origen: str = "app",
                 lakebase=None, ctx=None, checkpointer=None):
        # token_llm: str o función que devuelve un token vigente (OAuth del service principal de la app se renueva)
        self.token_fn = token_llm if callable(token_llm) else (lambda: token_llm)
        self.llm = OpenAI(api_key=self.token_fn(), base_url=f"{host.rstrip('/')}/ai-gateway/mlflow/v1")
        self.sql, self.usuario, self.max_pasos, self.origen = sql, usuario, max_pasos, origen
        self.lb, self.ctx = lakebase, ctx
        g = StateGraph(Estado)
        g.add_node("modelo", self.nodo_modelo)
        g.add_node("herramientas", self.nodo_herramientas)
        g.add_edge(START, "modelo")
        g.add_conditional_edges("modelo", self.ruta, {"herramientas": "herramientas", END: END})
        g.add_edge("herramientas", "modelo")
        self.grafo = g.compile(checkpointer=checkpointer or MemorySaver())

    # ---------------- nodos ----------------
    @mlflow.trace(name="modelo", span_type="LLM")
    def nodo_modelo(self, estado: Estado):
        self.llm.api_key = self.token_fn()
        r = self.llm.chat.completions.create(model=MODEL_SERVICE, messages=[{"role": "system", "content": SYSTEM}] + estado["messages"],
                                             tools=TOOLS, max_tokens=1800)
        msg = r.choices[0].message.model_dump(exclude_none=True)  # conserva campos extra (p. ej. thoughtSignature)
        msg.setdefault("content", "")
        return {"messages": [msg]}

    def ruta(self, estado: Estado):
        ult = estado["messages"][-1]
        pasos = sum(1 for m in estado["messages"] if m.get("role") == "assistant")
        return "herramientas" if ult.get("tool_calls") and pasos <= self.max_pasos else END

    def nodo_herramientas(self, estado: Estado):
        salida = []
        for tc in estado["messages"][-1]["tool_calls"]:
            nombre, args = tc["function"]["name"], json.loads(tc["function"].get("arguments") or "{}")
            salida.append({"role": "tool", "tool_call_id": tc["id"], "content": self.ejecutar(nombre, args)})
        return {"messages": salida}

    # ---------------- herramientas ----------------
    def ejecutar(self, nombre: str, args: dict) -> str:
        with mlflow.start_span(name=nombre, span_type="TOOL") as span:  # un span por herramienta (nombre visible en el trace)
            span.set_inputs(args)
            salida = self._ejecutar(nombre, args)
            span.set_outputs(salida)
            return salida

    def _ejecutar(self, nombre: str, args: dict) -> str:
        try:
            if nombre == "abrir_caso_investigacion":
                return self.abrir_caso(args)
            if nombre == "expediente_siu":
                return self.expediente(args["num_siniestro"])
            params = dict(args)
            if nombre == "bandeja_siu":
                params = {"region": args.get("region") or None, "top_n": min(int(args.get("top_n") or 10), 50)}
            filas = self.sql(SQL_TOOLS[nombre], params)
            if not filas:
                return json.dumps({"resultado": "Sin datos (no existe o no tienes acceso por tu rol/región)."}, ensure_ascii=False)
            return json.dumps(filas, ensure_ascii=False, default=str)
        except GraphBubbleUp:  # interrupt() de human-in-the-loop: dejar que LangGraph lo maneje
            raise
        except Exception as e:  # el modelo recibe el error y puede corregir
            return json.dumps({"error": str(e)[:500]}, ensure_ascii=False)

    def abrir_caso(self, args: dict) -> str:
        if self.lb is not None and (ya := self.lb.caso_abierto(self.ctx, args.get("num_siniestro", ""))):
            return json.dumps({"resultado": f"Ya existe el caso {ya['id_caso']} ({ya['estatus']}) para este siniestro; no se abre otro."},
                              ensure_ascii=False)
        decision = interrupt({"tipo": "aprobacion_caso", "propuesta": args})  # la app muestra Aprobar / Rechazar
        if not decision or not decision.get("aprobado"):
            return json.dumps({"resultado": "El investigador RECHAZÓ abrir el caso. No se registró nada."}, ensure_ascii=False)
        id_caso = f"SIU-{uuid.uuid4().hex[:8].upper()}"
        if self.lb is not None:  # Lakebase: RLS decide si el rol puede abrir casos en esa región
            from lakebase import SinPermiso
            try:
                self.lb.abrir_caso(self.ctx, args, id_caso, aprobado_por=self.usuario)
            except SinPermiso:
                return json.dumps({"resultado": "Lakebase rechazó el registro: tu rol no puede abrir casos SIU (política RLS)."}, ensure_ascii=False)
            except ValueError as e:
                return json.dumps({"resultado": str(e)}, ensure_ascii=False)
            return json.dumps({"resultado": f"Caso {id_caso} registrado en el expediente SIU (Lakebase), aprobado por el investigador."},
                              ensure_ascii=False)
        self.sql(f"""INSERT INTO {FN}.casos_investigacion VALUES (:id, :num, :prio, :resumen, :reco, :monto, current_user(), :aprobador,
                     current_timestamp(), 'Abierto', 'Agente Investigador SIU')""",
                 {"id": id_caso, "num": args["num_siniestro"], "prio": args.get("prioridad", "Media"), "resumen": args.get("resumen", ""),
                  "reco": args.get("recomendacion", ""), "monto": float(args.get("monto_en_riesgo") or 0), "aprobador": self.usuario})
        return json.dumps({"resultado": f"Caso {id_caso} registrado en casos_investigacion (aprobado por el investigador)."}, ensure_ascii=False)

    def expediente(self, num: str) -> str:
        if self.lb is None:
            return json.dumps({"resultado": "Expediente SIU no disponible en este entorno."}, ensure_ascii=False)
        caso = self.lb.caso_abierto(self.ctx, num)
        notas = self.lb.notas(self.ctx, num)[:10]
        return json.dumps({"caso_abierto": caso, "notas": notas or "Sin notas de investigadores."}, ensure_ascii=False, default=str)

    def estado(self, hilo: str):
        """(mensajes, aprobación_pendiente) guardados de un hilo → retomar una investigación (memoria en Lakebase)."""
        st = self.grafo.get_state({"configurable": {"thread_id": hilo}})
        if not st or not st.values:
            return [], None
        pendiente = next((i.value for t in st.tasks for i in (t.interrupts or [])), None)
        return st.values.get("messages", []), pendiente

    # ---------------- API para la app ----------------
    def preguntar(self, hilo: str, texto_usuario: str = None, reanudar: dict = None):
        """Devuelve (mensajes, aprobación_pendiente). Cada llamada es un trace de MLflow con usuario y sesión."""
        cfg = {"configurable": {"thread_id": hilo}}
        entrada = Command(resume=reanudar) if reanudar is not None else {"messages": [{"role": "user", "content": texto_usuario}]}
        pregunta = texto_usuario if reanudar is None else ("[Investigador APRUEBA abrir el caso]" if reanudar.get("aprobado")
                                                           else "[Investigador RECHAZA abrir el caso]")
        with mlflow.start_span(name="agente_investigador_siu", span_type="AGENT") as span:
            span.set_inputs({"pregunta": pregunta})
            try:
                mlflow.update_current_trace(metadata={"mlflow.trace.user": self.usuario, "mlflow.trace.session": hilo},
                                            tags={"app": "seguros-agente-siu", "origen": self.origen})
            except Exception:
                pass
            self.grafo.invoke(entrada, cfg)
            st = self.grafo.get_state(cfg)
            pendiente = next((i.value for t in st.tasks for i in (t.interrupts or [])), None)
            msgs = st.values["messages"]
            respuesta = texto(msgs[-1]) if msgs and msgs[-1].get("role") == "assistant" else ""
            if pendiente:
                respuesta = (respuesta + f"\n\n[PENDIENTE DE APROBACIÓN DEL INVESTIGADOR: abrir caso {json.dumps(pendiente['propuesta'], ensure_ascii=False)}]").strip()
            span.set_outputs(respuesta)
        self.ultimo_trace_id = mlflow.get_last_active_trace_id()
        return msgs, pendiente
