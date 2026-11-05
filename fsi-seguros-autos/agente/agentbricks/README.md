# Agente Investigador SIU en Agent Bricks (Agent Runtime)

**Deployment:** `agent-bricks-seguros-siu` → https://<APP_URL>
(SP client id `<UUID>`, user scope `sql`, Session Store `seguros-siu-sessions`).
Aparece en la sección **Agents** del workspace (prefijo `agent-`). La app Streamlit `seguros-agente-siu` (`../app/`) sigue igual.

| Pieza | Detalle |
|---|---|
| Servidor | `DurableAgentServer` (`runtime/main.py`), API `/api/invocations` |
| Grafo | `agent/agente_siu.py` — mismo prompt, herramientas y modelo que la app; mensajes crudos (thoughtSignature de Gemini) |
| Identidad | LLM con el SP de la app (EXECUTE en el model service). SQL con el token del usuario (`[auth.user]` + scope `sql`) → ABAC |
| Estado | Session Store administrado (Lakebase): conversación + propuesta de caso pendiente por sesión (separada por usuario) |
| Tracing | Experimento `/Users/<tu_usuario>/seguros_agente_siu`, `tags.origen = 'agentbricks'` |

## Aprobación de casos (cambio vs la app)
El runtime NO permite `interrupt()` en invocaciones con identidad de usuario (`MCP_USER_AUTH_HITL_UNSUPPORTED`). Por eso:
1. `abrir_caso_investigacion` solo deja `propuesta_pendiente` en el estado → respuesta `status: "pendiente_aprobacion"`.
2. El investigador decide en otra invocación de la MISMA sesión: `input = {"decision_caso": {"aprobado": true|false}}`.
   Nodo determinista (sin LLM) que hace el INSERT con su token (`current_user()` = creador y aprobador).

## Invocar
```bash
agentbricks --profile DEFAULT endpoint invoke agent-bricks-seguros-siu --path /api/invocations \
  --json '{"id":"<uuid>","session_id":"<uuid-sesion>","input":{"messages":[{"role":"user","content":"Investiga S202600000146"}]}}'
# aprobar la propuesta pendiente de esa sesión
agentbricks --profile DEFAULT endpoint invoke agent-bricks-seguros-siu --path /api/invocations \
  --json '{"id":"<uuid-nuevo>","session_id":"<uuid-sesion>","input":{"decision_caso":{"aprobado":true}}}'
```

## Desarrollo
- PyPI está bloqueado en la red local → usar el proxy SOLO para instalar: `UV_INDEX_URL=https://pypi-proxy.cloud.databricks.com/simple`
  (el deploy usa PyPI público y excluye `uv.lock`).
- Pruebas offline: `.venv/bin/python -m pytest -q` (8 pruebas). `agentbricks doctor .` → 7/7.
- Redeploy: `agentbricks --profile DEFAULT deploy` (el nombre quedó registrado).
- Gotchas: con identidad de usuario no hay recuperación en background (`MCP_USER_AUTH_RECOVERY_UNSUPPORTED`); las tools
  `uc_function` declaradas en agent.toml solo corren como el SP → por eso las herramientas siguen en Python con OBO.
