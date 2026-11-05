"""Pruebas offline: LLM y SQL falsos, checkpointer en memoria. No llaman a Databricks."""
import json
from types import SimpleNamespace

import pytest
from langgraph.checkpoint.memory import InMemorySaver

import agent.agent as agent_mod
import runtime.adapter as adapter
from agent.agente_siu import AgenteSIU


def _msg(content="", tool_calls=None, extra=None):
    d = {"role": "assistant", "content": content}
    if tool_calls:
        d["tool_calls"] = [{"id": f"call_{i}", "type": "function",
                            "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(tool_calls)]
    d.update(extra or {})
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(model_dump=lambda exclude_none=True: dict(d)))])


class LLMFalso:
    def __init__(self, respuestas):
        self.respuestas, self.recibidos = list(respuestas), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages, tools, max_tokens):
        self.recibidos.append(messages)
        return self.respuestas.pop(0)


class SQLFalso:
    def __init__(self):
        self.llamadas = []

    def __call__(self, statement, params=None):
        self.llamadas.append((statement, params))
        if "INSERT" in statement:
            return []
        return [{"num_siniestro": (params or {}).get("num_siniestro", "S1"), "dato": "x"}]


class Contexto:
    def __init__(self, session_id, invocation_id="inv-1"):
        self.session_id, self.invocation_id, self.request_auth, self.eventos = session_id, invocation_id, None, []

    async def emit(self, event):
        self.eventos.append(event)


@pytest.fixture
def entorno(monkeypatch):
    saver = InMemorySaver()
    sql = SQLFalso()
    estado = {"llm": None}
    monkeypatch.setattr(agent_mod, "crear_agente",
                        lambda workspace_client_for=None, **k: AgenteSIU(estado["llm"], sql, saver))
    return estado, sql


async def _invocar(ctx, value):
    return await adapter.invoke(value, ctx)


async def test_investigacion_usa_herramientas_y_conserva_thought_signature(entorno):
    estado, sql = entorno
    firma = {"thoughtSignature": "abc"}
    estado["llm"] = LLMFalso([_msg(tool_calls=[("detalle_siniestro", {"num_siniestro": "S1"}),
                                               ("perfil_taller", {"num_siniestro": "S1"})], extra=firma),
                              _msg("Dictamen preliminar…")])
    r = await _invocar(Contexto("s1"), {"messages": [{"role": "user", "content": "Investiga S1"}]})
    assert r["status"] == "completed" and r["respuesta"] == "Dictamen preliminar…"
    assert [s for s, _ in sql.llamadas] == [
        "SELECT * FROM demo_catalog.seguros_ml.agente_detalle_siniestro(:num_siniestro)",
        "SELECT * FROM demo_catalog.seguros_ml.agente_perfil_taller(:num_siniestro)"]
    # el 2º llamado al modelo recibe el mensaje del asistente con la firma intacta
    assert estado["llm"].recibidos[1][2]["thoughtSignature"] == "abc"


async def test_propuesta_queda_pendiente_y_no_escribe(entorno):
    estado, sql = entorno
    prop = {"num_siniestro": "S1", "prioridad": "Alta", "resumen": "r", "recomendacion": "abrir", "monto_en_riesgo": 1000}
    estado["llm"] = LLMFalso([_msg(tool_calls=[("abrir_caso_investigacion", prop)]), _msg("¿Apruebas abrir el caso?")])
    ctx = Contexto("s2")
    r = await _invocar(ctx, [{"role": "user", "content": "Sí, abre un caso"}])
    assert r["status"] == "pendiente_aprobacion" and r["propuesta_pendiente"] == prop
    assert {"type": "aprobacion_pendiente", "propuesta": prop} in ctx.eventos
    assert not any("INSERT" in s for s, _ in sql.llamadas)


async def test_aprobar_registra_una_vez_sin_llm(entorno):
    estado, sql = entorno
    prop = {"num_siniestro": "S1", "prioridad": "Alta", "resumen": "r", "recomendacion": "abrir"}
    estado["llm"] = LLMFalso([_msg(tool_calls=[("abrir_caso_investigacion", prop)]), _msg("¿Apruebas?")])
    await _invocar(Contexto("s3"), [{"role": "user", "content": "abre caso"}])
    estado["llm"] = LLMFalso([])  # si la decisión llamara al LLM, fallaría
    r = await _invocar(Contexto("s3", "inv-2"), {"decision_caso": {"aprobado": True}})
    inserts = [p for s, p in sql.llamadas if "INSERT" in s]
    assert len(inserts) == 1 and inserts[0]["num"] == "S1" and inserts[0]["monto"] == 0.0
    assert r["status"] == "completed" and r["propuesta_pendiente"] is None and "registrado" in r["respuesta"]
    # una segunda aprobación ya no encuentra propuesta
    r2 = await _invocar(Contexto("s3", "inv-3"), {"decision_caso": {"aprobado": True}})
    assert len([1 for s, _ in sql.llamadas if "INSERT" in s]) == 1 and "No hay" in r2["respuesta"]


async def test_rechazar_no_escribe(entorno):
    estado, sql = entorno
    estado["llm"] = LLMFalso([_msg(tool_calls=[("abrir_caso_investigacion", {"num_siniestro": "S9", "prioridad": "Baja",
                                                                          "resumen": "r", "recomendacion": "x"})]), _msg("¿?")])
    await _invocar(Contexto("s4"), [{"role": "user", "content": "abre caso"}])
    r = await _invocar(Contexto("s4", "inv-2"), {"decision_caso": {"aprobado": False}})
    assert not any("INSERT" in s for s, _ in sql.llamadas) and "NO se abrió" in r["respuesta"]


async def test_decision_en_otra_sesion_no_ve_la_propuesta(entorno):
    estado, sql = entorno
    estado["llm"] = LLMFalso([_msg(tool_calls=[("abrir_caso_investigacion", {"num_siniestro": "S1", "prioridad": "Alta",
                                                                          "resumen": "r", "recomendacion": "x"})]), _msg("¿?")])
    await _invocar(Contexto("sesion-a"), [{"role": "user", "content": "abre caso"}])
    r = await _invocar(Contexto("sesion-b"), {"decision_caso": {"aprobado": True}})
    assert not any("INSERT" in s for s, _ in sql.llamadas) and "No hay" in r["respuesta"]


@pytest.mark.parametrize("valor", [{"decision_caso": {"aprobado": "si"}}, {"messages": []}, "texto"])
async def test_entradas_invalidas(entorno, valor):
    with pytest.raises(ValueError):
        await _invocar(Contexto("s5"), valor)
