import sys, json, os
sys.path.insert(0, "/Workspace/Users/<tu_usuario>/seguros_demo/agente/app")
import mlflow
from databricks.sdk import WorkspaceClient
from agente_siu import AgenteSIU, texto
from sql_uc import crear_sql

mlflow.set_experiment("/Users/<tu_usuario>/seguros_agente_siu")
w = WorkspaceClient()
token = w.config.authenticate()["Authorization"].split(" ", 1)[1]
ag = AgenteSIU(w.config.host, token, crear_sql(w, "<WAREHOUSE_ID>"), usuario=w.current_user.me().user_name)

def show(msgs, pend):
    for m in msgs[-6:]:
        if m["role"] == "assistant" and m.get("tool_calls"):
            print("  → herramientas:", [(t["function"]["name"], t["function"]["arguments"]) for t in m["tool_calls"]],
                  "| thoughtSignature:", any("thoughtSignature" in t for t in m["tool_calls"]))
        elif m["role"] == "assistant":
            print("  RESPUESTA:\n", texto(m)[:1800])
    print("  PENDIENTE:", json.dumps(pend, ensure_ascii=False)[:600] if pend else None)

print("=== 1. Investigación"); show(*ag.preguntar("t1", "Investiga el siniestro S202600000146 y dame tu dictamen."))
print("=== 2. Pedir caso (interrupt)"); msgs, pend = ag.preguntar("t1", "Sí, abre un caso de investigación para este siniestro."); show(msgs, pend)
assert pend, "se esperaba interrupción para aprobación"
print("=== 3. Aprobación → reanudar"); show(*ag.preguntar("t1", reanudar={"aprobado": True}))
print("=== 4. Rechazo"); msgs, pend = ag.preguntar("t3", "Abre un caso de prioridad Baja para el siniestro S202600005219 por reporte tardío."); show(msgs, pend)
if pend: show(*ag.preguntar("t3", reanudar={"aprobado": False}))
print("=== 5. Casos registrados"); print(ag.sql("SELECT id_caso, num_siniestro, prioridad, creado_por, aprobado_por, estatus FROM demo_catalog.seguros_ml.casos_investigacion ORDER BY fecha_creacion DESC LIMIT 5"))
