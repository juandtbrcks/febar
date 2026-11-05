import sys, json
sys.path.insert(0, "/Workspace/Users/<tu_usuario>/seguros_demo/agente/app")
import mlflow
from databricks.sdk import WorkspaceClient
from agente_siu import AgenteSIU, texto
from sql_uc import crear_sql

mlflow.set_experiment("/Users/<tu_usuario>/seguros_agente_siu")
w = WorkspaceClient()
token = lambda: w.config.authenticate()["Authorization"].split(" ", 1)[1]
ag = AgenteSIU(w.config.host, token, crear_sql(w, "<WAREHOUSE_ID>"), usuario=w.current_user.me().user_name, origen="prueba")
msgs, pend = ag.preguntar("r1", "Investiga el siniestro S202600000146")
print("HERRAMIENTAS:", [t["function"]["name"] for m in msgs if m.get("tool_calls") for t in m["tool_calls"]])
print("RESPUESTA:", texto(msgs[-1])[:1200])
msgs, pend = ag.preguntar("r1", "Sí, abre un caso de investigación para este siniestro.")
print("PENDIENTE DE APROBACIÓN:", json.dumps(pend, ensure_ascii=False)[:400] if pend else None)
assert pend, "se esperaba la tarjeta de aprobación"
print("PRUEBA OK (no se aprobó: nada se escribió)")
