"""Traduce invocaciones de Agent Bricks (`/api/invocations`) al grafo nativo del agente SIU.

Entrada (`input`):
  - Pregunta:  {"messages": [{"role": "user", "content": "Investiga S202600000146"}]}   (o la lista de mensajes directa)
  - Decisión:  {"decision_caso": {"aprobado": true}}   → registra (o descarta) la propuesta pendiente de la sesión.
`session_id` (top-level) identifica la conversación; el runtime lo separa por usuario autenticado.

Salida: {"output": [mensajes nuevos], "respuesta": texto final, "propuesta_pendiente": {...} | null,
         "status": "pendiente_aprobacion" | "completed"}
Eventos emitidos: {"type": "message", "message": {...}} y {"type": "aprobacion_pendiente", "propuesta": {...}}.
"""
from typing import Any

from agent.agent import recovery_input, run_agent
from agent.agente_siu import texto
from databricks_agentkit import InvocationContext
from databricks_agentkit.runtime.auth import AuthError


def _payload(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        return {"messages": value}
    if not isinstance(value, dict):
        raise ValueError("input debe ser una lista de mensajes o un objeto")
    return value


def _session_id(context: InvocationContext) -> str:
    value = context.session_id
    if not isinstance(value, str) or not value:
        raise ValueError("session_id debe venir como campo top-level de la invocación")
    return value


def _agent_input(payload: dict[str, Any]) -> dict:
    if (decision := payload.get("decision_caso")) is not None:
        if not isinstance(decision, dict) or not isinstance(decision.get("aprobado"), bool):
            raise ValueError('decision_caso debe ser {"aprobado": true|false}')
        return {"decision_caso": {"aprobado": decision["aprobado"]}}
    messages = payload.get("messages") or []
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages debe ser una lista no vacía")
    return {"messages": messages}


async def invoke(value: Any, context: InvocationContext) -> dict:
    return await _invoke_agent(_agent_input(_payload(value)), context)


async def recover(value: Any, context: InvocationContext) -> dict:
    if getattr(context, "request_auth", None) is not None:
        raise AuthError("MCP_USER_AUTH_BACKGROUND_UNSUPPORTED",
                        "Request-user invocations cannot be recovered in the background.", 400)
    session_id = _session_id(context)
    agent_input = await recovery_input(_agent_input(_payload(value)), session_id=session_id, actor=session_id,
                                       invocation_id=context.invocation_id)
    return await _invoke_agent(agent_input, context)


async def _invoke_agent(agent_input: Any, context: InvocationContext) -> dict:
    session_id = _session_id(context)
    auth = getattr(context, "request_auth", None)
    kwargs = {"workspace_client_for": auth.client_for} if auth is not None else {}
    mensajes, propuesta = [], None
    async for update in run_agent(agent_input, session_id=session_id, actor=session_id,
                                  invocation_id=context.invocation_id, **kwargs):
        for cambios in update.values():
            if not isinstance(cambios, dict):
                continue
            for msg in cambios.get("messages") or []:
                await context.emit({"type": "message", "message": msg})
                mensajes.append(msg)
            if cambios.get("propuesta_pendiente"):
                propuesta = cambios["propuesta_pendiente"]
            elif "propuesta_pendiente" in cambios:  # la decisión la resolvió
                propuesta = None
    if propuesta:
        await context.emit({"type": "aprobacion_pendiente", "propuesta": propuesta})
    final = next((m for m in reversed(mensajes) if m.get("role") == "assistant" and texto(m)), None)
    return {"output": mensajes, "respuesta": texto(final) if final else "", "propuesta_pendiente": propuesta,
            "status": "pendiente_aprobacion" if propuesta else "completed"}
