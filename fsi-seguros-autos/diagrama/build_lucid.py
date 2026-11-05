"""Genera el Standard Import JSON (Lucid) del diagrama de arquitectura del demo FSI con íconos oficiales de Databricks.
Íconos: SVG del skill fe-architecture-diagram embebidos como data URL base64.
Run: python3 build_lucid.py > lucid_arquitectura_es.json
"""
import base64, json, re

ICON_DIR = "<DIRECTORIO_ICONOS_DATABRICKS>/"
NAVY, LAVA, OAT, GRIS, TXT2 = "#1B3139", "#FF3621", "#F9F7F4", "#DCE0E2", "#5A6F77"


def icono(n):
    s = re.sub(r"\s+", " ", open(ICON_DIR + n + ".svg").read()).replace("> <", "><").strip()
    return "data:image/svg+xml;base64," + base64.b64encode(s.encode()).decode()


CW, CH = 290, 100                     # tarjeta
COLS = [80, 450, 820, 1190, 1560, 1930, 2300]
ROWS = [330, 480, 630, 780, 930, 1180, 1400]

shapes, lines = [], []


def html(titulo, sub, color=NAVY, sub_color=TXT2):
    return (f"<p style=\"font-size:11px;text-align:left;color:{sub_color}\"><span style=\"font-size:13px;color:{color}\"><b>{titulo}</b></span>"
            f"<br>{sub}</p>")


def tarjeta(cid, c, r, titulo, sub, icon=None, named=None, fill="#FFFFFF", stroke=GRIS, dashed=False):
    x, y = COLS[c], ROWS[r]
    shapes.append({"id": cid, "type": "rectangle", "boundingBox": {"x": x, "y": y, "w": CW, "h": CH},
                   "style": {"fill": {"type": "color", "color": fill}, "stroke": {"color": stroke, "width": 1.5, "style": "dashed" if dashed else "solid"}}})
    if icon:
        shapes.append({"id": cid + "_i", "type": "image", "boundingBox": {"x": x + 14, "y": y + 22, "w": 56, "h": 56},
                       "image": {"type": "image", "url": icono(icon)}, "stroke": {"color": "#FFFFFF00", "width": 0, "style": "solid"}})
    if named:
        shapes.append({"id": cid + "_i", "type": "namedShape", "className": named, "boundingBox": {"x": x + 20, "y": y + 22, "w": 44, "h": 56}})
    tx = x + (80 if (icon or named) else 16)
    shapes.append({"id": cid + "_t", "type": "text", "boundingBox": {"x": tx, "y": y + 8, "w": x + CW - 10 - tx, "h": CH - 16},
                   "text": html(titulo, sub, "#FFFFFF" if fill == NAVY else NAVY, "#DCE0E2" if fill == NAVY else TXT2)})


def contenedor(cid, x, y, w, h, titulo, fill=OAT, stroke=GRIS):
    shapes.append({"id": cid, "type": "roundedRectangleContainer", "boundingBox": {"x": x, "y": y, "w": w, "h": h},
                   "containerTitle": {"text": titulo},
                   "style": {"fill": {"type": "color", "color": fill}, "stroke": {"color": stroke, "width": 1.5, "style": "solid"}}})


def linea(lid, a, b, pa, pb, texto=None, color=NAVY, dashed=False, tipo="straight", pos=0.5, side="top"):
    l = {"id": lid, "lineType": tipo,
         "endpoint1": {"type": "shapeEndpoint", "style": "none", "shapeId": a, "position": {"x": pa[0], "y": pa[1]}},
         "endpoint2": {"type": "shapeEndpoint", "style": "arrow", "shapeId": b, "position": {"x": pb[0], "y": pb[1]}},
         "stroke": {"color": color, "width": 2, "style": "dashed" if dashed else "solid"}}
    if texto:
        l["text"] = [{"text": f"<span style=\"font-size:10px;color:{color}\">{texto}</span>", "position": pos, "side": side}]
    lines.append(l)


R, L_, T, B = (1, .5), (0, .5), (.5, 0), (.5, 1)

# ---------------- contenedores (primero → quedan atrás) ----------------
shapes.append({"id": "titulo", "type": "text", "boundingBox": {"x": 60, "y": 20, "w": 2550, "h": 50},
               "text": "<p style=\"font-size:24px;text-align:left;color:#1B3139\"><b>Aseguradora FSI · Autos</b> — Arquitectura del demo en "
                       "Databricks on Azure: una sola fuente gobernada, sin extractos</p>"})
contenedor("k_uc", 60, 110, 2550, 120, "Unity Catalog · gobierno unificado (catálogo demo_catalog)", fill="#EEF4F7", stroke="#9DB4BE")
contenedor("k_src", 60, 300, 330, 610, "Fuentes · on-prem y multicloud")
contenedor("k_ing", 430, 300, 330, 610, "Ingesta sin duplicar")
contenedor("k_dlt", 800, 300, 330, 610, "Lakeflow Declarative Pipeline · seguros_medallion")
contenedor("k_ai", 1170, 300, 1080, 760, "IA, MLOps y consumo")
contenedor("k_usr", 2280, 300, 330, 760, "Usuarios")
contenedor("k_lb", 1170, 1140, 1080, 180, "Lakebase · proyecto seguros-siu (Postgres 17 autoscaling · RLS)", fill="#FFF1EE", stroke="#FF5F46")

# ---------------- banda UC ----------------
shapes.append({"id": "uc_i", "type": "image", "boundingBox": {"x": 90, "y": 138, "w": 64, "h": 64},
               "image": {"type": "image", "url": icono("unity_catalog")}, "stroke": {"color": "#FFFFFF00", "width": 0, "style": "solid"}})
chips = ["<b>Governed tags</b><br>PII · región · certificación",
         "<b>ABAC</b><br>masking de PII + filtro por región",
         "<b>Lakehouse Federation</b><br>foreign catalogs, sin copiar",
         "<b>Linaje + auditoría</b><br>system tables",
         "<b>Discover</b><br>dominio Seguros / Autos"]
for i, c in enumerate(chips):
    shapes.append({"id": f"chip{i}", "type": "rectangle", "boundingBox": {"x": 200 + i * 482, "y": 140, "w": 420, "h": 60},
                   "text": f"<p style=\"font-size:12px;text-align:center;color:#1B3139\">{c}</p>",
                   "style": {"fill": {"type": "color", "color": "#FFFFFF"}, "stroke": {"color": "#9DB4BE", "width": 1, "style": "solid"}}})

# ---------------- tarjetas ----------------
tarjeta("oracle", 0, 0, "DWH Oracle 2011 (on-prem)", "simulado en Azure PostgreSQL · dwh_seguros · 18 tablas", named="OracleDatabaseAzure2024")
tarjeta("cred", 0, 1, "Créditos personales (AWS)", "simulado en Azure PostgreSQL · creditos_aws", named="AzureDatabasePostgreSQLServerAzure2024")
tarjeta("app_json", 0, 2, "App Autos FSI", "telemetría de manejo + FNOL (JSON) · data lake de DS")
tarjeta("pdfs", 0, 3, "Presupuestos de taller", "240 PDFs en Volume documentos_siniestros")

tarjeta("fed", 1, 0, "Lakehouse Federation", "seguros_dwh_onprem · seguros_creditos_aws (pushdown)", icon="lakeflow_connect")
tarjeta("autoloader", 1, 2, "Auto Loader", "Volume datalake_ds → streaming tables", icon="data_streaming")
tarjeta("aifn", 1, 3, "AI Functions", "ai_parse_document + ai_query (Claude) → validación de PDFs", icon="agent_bricks")

tarjeta("bronce", 2, 0, "Bronce", "18 MVs desde federación + 2 streaming tables", icon="delta_lake")
tarjeta("plata", 2, 1, "Plata + cuarentena", "expectations FAIL/DROP/WARN · RFC normalizado", icon="delta_lake")
tarjeta("oro", 2, 2, "Oro · modelo estrella", "6 dims · 5 facts · región · tags oficial", icon="delta_lake")
tarjeta("act", 2, 3, "Actuarial", "triángulos chain-ladder · reservas IBNR", icon="delta_lake")

tarjeta("mv", 3, 0, "Metric views (4)", "cartera · fraude · comercial · reservas", icon="sql_warehouse")
tarjeta("ml", 3, 2, "Feature Store + MLflow", "fraude XGBoost · SHAP · champion / challenger", icon="mlflow")
tarjeta("job", 3, 3, "Lakeflow Jobs · MLOps", "entrena → scoring → serving → sync", icon="workflows")
tarjeta("serving", 3, 4, "bandeja_siu_serving", "Delta con CDF · sin PII (MERGE)", icon="delta_lake")

tarjeta("dash", 4, 0, "AI/BI Dashboard", "tablero ejecutivo · 4 páginas", icon="ai_bi")
tarjeta("genie", 4, 1, "Genie", "preguntas en español · veredictos SIU", icon="genie")
tarjeta("gw", 4, 3, "Model service UC · AI Gateway", "Gemini 3.8 Flash · inference table", icon="unity_ai_gateway")
tarjeta("eval", 4, 4, "MLflow Tracing + Evaluación", "jueces LLM (Claude) · monitoreo", icon="mlflow")

tarjeta("bricks", 5, 2, "Agent Bricks", "misma lógica en Agent Runtime", icon="agent_bricks", dashed=True)
tarjeta("app", 5, 3, "App · Agente Investigador SIU", "Streamlit + LangGraph · herramientas UC con OBO", icon="apps")

tarjeta("u_ejec", 6, 0, "Dirección / ejecutivos", "rentabilidad, fraude, canales", fill=NAVY, stroke=NAVY)
tarjeta("u_act", 6, 1, "Actuarios y analistas", "reservas, siniestralidad", fill=NAVY, stroke=NAVY)
tarjeta("u_siu", 6, 3, "Investigadores SIU", "PII completa · todas las regiones", fill=NAVY, stroke=NAVY)
tarjeta("u_reg", 6, 4, "Agente regional", "solo su región · PII enmascarada", fill=NAVY, stroke=NAVY)

tarjeta("lb_sync", 3, 5, "Synced table", "serving.bandeja_siu (reverse ETL)", icon="lakebase")
tarjeta("lb_exp", 4, 5, "Expediente SIU", "casos · notas · bitácora (trigger) · RLS", icon="lakebase")
tarjeta("lb_mem", 5, 5, "Memoria del agente", "checkpointer LangGraph + sesiones", icon="lakebase")
tarjeta("delta_exp", 3, 6, "seguros_siu_expediente", "Delta vía CDF de Lakebase → etiquetas SIU", icon="delta_lake")

# ---------------- líneas ----------------
linea("l1", "oracle", "fed", R, L_)
linea("l2", "cred", "fed", R, (0, .8))
linea("l3", "app_json", "autoloader", R, L_)
linea("l4", "pdfs", "aifn", R, L_)
linea("l6", "fed", "bronce", R, L_)
linea("l7", "autoloader", "bronce", R, (0, .8))
linea("l8", "bronce", "plata", B, T)
linea("l9", "plata", "oro", B, T)
linea("l10", "oro", "act", B, T)
linea("l11", "aifn", "oro", R, (0, .7))
linea("l13", "oro", "mv", (1, .2), (0, .8))
linea("l14", "oro", "ml", R, L_, "features", pos=.5)
linea("l15", "ml", "job", B, T)
linea("l16", "job", "serving", B, T)
linea("l17", "serving", "lb_sync", B, T, "synced table", color=LAVA, pos=.5, side="middle")
linea("l18", "mv", "dash", R, L_)
linea("l19", "mv", "genie", (1, .8), (0, .3))
linea("l20", "dash", "u_ejec", R, L_)
linea("l21", "genie", "u_act", R, L_)
linea("l22", "app", "gw", L_, R, "LLM")
linea("l23", "app", "eval", (0, .9), (1, .3), "traces", pos=.5, side="bottom")
linea("l24", "u_siu", "app", L_, R)
linea("l25", "u_reg", "app", (0, .3), (1, .9))
linea("l26", "bricks", "app", B, T, color=TXT2, dashed=True)
linea("l27", "app", "lb_exp", (.2, 1), (.9, 0), "notas · casos", color=LAVA, pos=.55, side="bottom")
linea("l28", "app", "lb_mem", (.8, 1), (.8, 0), "memoria", color=LAVA, pos=.6, side="top")
linea("l29", "lb_sync", "lb_exp", R, L_, color=LAVA)
linea("l30", "lb_exp", "delta_exp", (.5, 1), (1, .5), "CDF", color=LAVA, tipo="elbow", pos=.6)
linea("l31", "delta_exp", "job", (0, .5), (0, .5), "etiquetas → reentrena", color=LAVA, tipo="elbow", pos=.5)

doc = {"version": 1, "pages": [{"id": "arq", "title": "Arquitectura", "shapes": shapes, "lines": lines}]}
print(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
