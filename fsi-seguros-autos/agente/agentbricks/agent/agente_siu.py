"""Agente Investigador SIU — Aseguradora FSI · Autos (LangGraph + model service de Unity Catalog) sobre Agent Bricks.

- LLM: model service `demo_catalog.seguros_ml.model_service_demo_agente` vía AI Gateway (API compatible con OpenAI),
  con la identidad de la app (service principal).
- Herramientas: funciones de Unity Catalog ejecutadas con la identidad del USUARIO que invoca → aplican las políticas ABAC.
- Aprobación humana: el runtime no permite pausar el grafo (`interrupt`) en invocaciones con identidad de usuario, así que
  `abrir_caso_investigacion` solo deja una PROPUESTA en el estado de la sesión. El caso se registra únicamente cuando una
  invocación posterior de la MISMA sesión trae `decision_caso = {"aprobado": true}`; ese paso es determinista (sin LLM)
  y escribe con el token del investigador que aprueba.
- Los mensajes del modelo se guardan tal cual (dicts) para conservar campos extra como la thought signature de Gemini.
"""
import json, uuid
from typing import Annotated, Any, Callable, Optional, TypedDict

import mlflow
from langgraph.graph import StateGraph, START, END

MODEL_SERVICE = "demo_catalog.seguros_ml.model_service_demo_agente"
FN = "demo_catalog.seguros_ml"

SYSTEM = """Eres el Agente Investigador del SIU (Unidad Especial de Investigación de fraude) de Aseguradora FSI, ramo Autos (México).
Ayudas a los investigadores a priorizar y analizar siniestros sospechosos. Responde SIEMPRE en español, claro y profesional.

Reglas:
- Usa SOLO datos que obtengas con tus herramientas; nunca inventes cifras, nombres ni siniestros. Si una herramienta no devuelve datos,
  dilo (puede ser que el usuario no tenga acceso a esa región: las políticas de Unity Catalog filtran lo que cada rol ve).
- Para investigar un siniestro consulta: detalle_siniestro, evidencia_documental, historial_cliente y perfil_taller.
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


def _ultimo(a: Any, b: Any) -> Any:
    return b


class Estado(TypedDict, total=False):
    messages: Annotated[list, _add]
    propuesta_pendiente: Annotated[Optional[dict], _ultimo]  # caso propuesto por el agente, esperando decisión
    decision_caso: Annotated[Optional[dict], _ultimo]  # entrada de la invocación de aprobación: {"aprobado": bool}


class AgenteSIU:
    """Construye el grafo para UNA invocación.

    `llm`: cliente OpenAI apuntando al AI Gateway (identidad de la app).
    `sql(statement, params) -> list[dict]`: SQL con la identidad del usuario que invoca (ABAC aplica).
    `checkpointer`: el de Agent Bricks (Session Store administrado o en memoria), compartido entre invocaciones.
    """

    def __init__(self, llm, sql: Callable, checkpointer, modelo: str = MODEL_SERVICE, max_pasos: int = 12):
        self.llm, self.sql, self.modelo, self.max_pasos = llm, sql, modelo, max_pasos
        g = StateGraph(Estado)
        g.add_node("modelo", self.nodo_modelo)
        g.add_node("herramientas", self.nodo_herramientas)
        g.add_node("decision", self.nodo_decision)
        g.add_conditional_edges(START, self.ruta_inicio, {"decision": "decision", "modelo": "modelo"})
        g.add_conditional_edges("modelo", self.ruta, {"herramientas": "herramientas", END: END})
        g.add_edge("herramientas", "modelo")
        g.add_edge("decision", END)
        self.grafo = g.compile(checkpointer=checkpointer)

    # ---------------- rutas ----------------
    def ruta_inicio(self, estado: Estado):
        return "decision" if estado.get("decision_caso") is not None else "modelo"

    def ruta(self, estado: Estado):
        ult = estado["messages"][-1]
        pasos = sum(1 for m in estado["messages"] if m.get("role") == "assistant")
        return "herramientas" if ult.get("tool_calls") and pasos <= self.max_pasos else END

    # ---------------- nodos ----------------
    @mlflow.trace(name="modelo", span_type="LLM")
    def nodo_modelo(self, estado: Estado):
        r = self.llm.chat.completions.create(model=self.modelo, messages=[{"role": "system", "content": SYSTEM}] + estado["messages"],
                                             tools=TOOLS, max_tokens=1800)
        msg = r.choices[0].message.model_dump(exclude_none=True)  # conserva campos extra (p. ej. thoughtSignature)
        msg.setdefault("content", "")
        return {"messages": [msg]}

    def nodo_herramientas(self, estado: Estado):
        salida, propuesta = [], None
        for tc in estado["messages"][-1]["tool_calls"]:
            nombre, args = tc["function"]["name"], json.loads(tc["function"].get("arguments") or "{}")
            if nombre == "abrir_caso_investigacion":
                propuesta = args
                contenido = json.dumps({"resultado": "Propuesta de caso registrada y PENDIENTE DE APROBACIÓN del investigador. "
                                        "Todavía no se ha registrado nada: indícale que debe aprobarla o rechazarla."}, ensure_ascii=False)
                with mlflow.start_span(name=nombre, span_type="TOOL") as span:
                    span.set_inputs(args)
                    span.set_outputs(contenido)
            else:
                contenido = self.ejecutar(nombre, args)
            salida.append({"role": "tool", "tool_call_id": tc["id"], "content": contenido})
        return {"messages": salida, "propuesta_pendiente": propuesta} if propuesta else {"messages": salida}

    @mlflow.trace(name="decision_caso", span_type="TOOL")
    def nodo_decision(self, estado: Estado):
        """Aplica la decisión del investigador sobre la propuesta pendiente. Determinista: el LLM no participa."""
        aprobado = bool((estado.get("decision_caso") or {}).get("aprobado"))
        propuesta = estado.get("propuesta_pendiente")
        marca = {"role": "user", "content": "[Investigador APRUEBA abrir el caso]" if aprobado else "[Investigador RECHAZA abrir el caso]"}
        if not propuesta:
            resultado = "No hay ninguna propuesta de caso pendiente de aprobación en esta conversación."
        elif not aprobado:
            resultado = f"Entendido: NO se abrió caso para el siniestro {propuesta.get('num_siniestro')}. No se registró nada."
        else:
            try:
                resultado = self.registrar_caso(propuesta)
            except Exception as e:  # se informa y la propuesta sigue pendiente para reintentar
                return {"messages": [marca, {"role": "assistant", "content": f"No se pudo registrar el caso: {str(e)[:300]}"}],
                        "decision_caso": None}
        return {"messages": [marca, {"role": "assistant", "content": resultado}], "propuesta_pendiente": None, "decision_caso": None}

    # ---------------- herramientas ----------------
    def ejecutar(self, nombre: str, args: dict) -> str:
        with mlflow.start_span(name=nombre, span_type="TOOL") as span:  # un span por herramienta (nombre visible en el trace)
            span.set_inputs(args)
            salida = self._ejecutar(nombre, args)
            span.set_outputs(salida)
            return salida

    def _ejecutar(self, nombre: str, args: dict) -> str:
        try:
            if nombre not in SQL_TOOLS:
                return json.dumps({"error": f"Herramienta desconocida: {nombre}"}, ensure_ascii=False)
            params = dict(args)
            if nombre == "bandeja_siu":
                params = {"region": args.get("region") or None, "top_n": min(int(args.get("top_n") or 10), 50)}
            filas = self.sql(SQL_TOOLS[nombre], params)
            if not filas:
                return json.dumps({"resultado": "Sin datos (no existe o no tienes acceso por tu rol/región)."}, ensure_ascii=False)
            return json.dumps(filas, ensure_ascii=False, default=str)
        except Exception as e:  # el modelo recibe el error y puede corregir
            return json.dumps({"error": str(e)[:500]}, ensure_ascii=False)

    def registrar_caso(self, propuesta: dict) -> str:
        """INSERT con el token del investigador que aprueba: current_user() queda como creador y aprobador."""
        id_caso = f"SIU-{uuid.uuid4().hex[:8].upper()}"
        self.sql(f"""INSERT INTO {FN}.casos_investigacion VALUES (:id, :num, :prio, :resumen, :reco, :monto, current_user(), current_user(),
                     current_timestamp(), 'Abierto', 'Agente Investigador SIU')""",
                 {"id": id_caso, "num": propuesta["num_siniestro"], "prio": propuesta.get("prioridad", "Media"),
                  "resumen": propuesta.get("resumen", ""), "reco": propuesta.get("recomendacion", ""),
                  "monto": float(propuesta.get("monto_en_riesgo") or 0)})
        return f"Caso {id_caso} registrado en casos_investigacion para el siniestro {propuesta['num_siniestro']} (aprobado por el investigador)."
