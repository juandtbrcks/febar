"""Punto de entrada nativo del agente: no depende de tipos del runtime de Agent Bricks (se puede llamar desde un notebook o tests)."""
import os
from collections.abc import AsyncGenerator, Callable
from typing import Any

import mlflow
from databricks.sdk import WorkspaceClient
from openai import OpenAI

from agent.agente_siu import MODEL_SERVICE, AgenteSIU
from agent.sql_uc import crear_sql
from databricks_agentkit import workspace_client
from databricks_agentkit.langgraph import checkpointer, configure_tracing, start_trace, thread_config
from databricks_agentkit.langgraph.session_store import invocation_id_from_metadata, invocation_metadata
from databricks_agentkit.runtime.tool_manifest import resolve_model_service

# `agentbricks experimental models bind` puede reapuntar el modelo sin cambiar código (AGENT_MODEL_SERVICE_AGENT).
MODEL = resolve_model_service() or MODEL_SERVICE
WAREHOUSE_ID = os.getenv("WAREHOUSE_ID", "<WAREHOUSE_ID>")
ORIGEN = os.getenv("AGENTE_ORIGEN", "agentbricks")


def configure() -> None:
    """Llamar una vez al arrancar el servidor."""
    workspace_client()  # falla rápido si no hay autenticación de Databricks
    configure_tracing()


def _llm_app() -> OpenAI:
    """Cliente del AI Gateway con la identidad de la app (el SP necesita EXECUTE en el model service)."""
    w = workspace_client()
    token = w.config.authenticate()["Authorization"].split(" ", 1)[1]
    return OpenAI(api_key=token, base_url=f"{w.config.host.rstrip('/')}/ai-gateway/mlflow/v1")


def crear_agente(workspace_client_for: Callable[[str], WorkspaceClient] | None = None, *, llm=None, sql=None) -> AgenteSIU:
    """`workspace_client_for("user")` da el cliente del usuario que invoca; en local (`agentbricks dev`) es el perfil."""
    if sql is None:
        w_usuario = workspace_client_for("user") if workspace_client_for else workspace_client()
        sql = crear_sql(w_usuario, WAREHOUSE_ID)
    return AgenteSIU(llm or _llm_app(), sql, checkpointer(), modelo=MODEL)


async def recovery_input(agent_input: Any, *, session_id: str, actor: str, invocation_id: str) -> Any:
    """Tras perder el worker: continuar el checkpoint de ESTA invocación (None) o repetir la entrada original."""
    cp = await checkpointer().aget_tuple(thread_config(session_id, actor))
    return None if cp and invocation_id_from_metadata(cp.metadata) == invocation_id else agent_input


async def run_agent(agent_input: Any, *, session_id: str, actor: str | None = None, invocation_id: str | None = None,
                    workspace_client_for: Callable[[str], WorkspaceClient] | None = None,
                    agente: AgenteSIU | None = None) -> AsyncGenerator[dict, None]:
    """Corre el grafo y emite las actualizaciones nativas de LangGraph ({nodo: cambios})."""
    agente = agente or crear_agente(workspace_client_for)
    config = thread_config(session_id, actor or session_id)
    if invocation_id:
        config["metadata"] = invocation_metadata(invocation_id)
    with start_trace(name="agente_investigador_siu", inputs=agent_input, session_id=session_id) as span:
        if span is not None:
            mlflow.update_current_trace(tags={"app": "agent-bricks-seguros-siu", "origen": ORIGEN})
        ultimo = None
        async for update in agente.grafo.astream(input=agent_input, config=config, stream_mode="updates", durability="sync"):
            ultimo = update
            yield update
        if span is not None and ultimo is not None:
            span.set_outputs(ultimo)
