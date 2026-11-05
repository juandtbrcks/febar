"""Construye y publica el dashboard ejecutivo de Aseguradora FSI · Autos sobre las 4 metric views (+ tablas actuariales act_*).
Publicado SIN credenciales embebidas: cada usuario ve los datos con sus propios permisos (filtros por región / masking).
Run: python3 build_dashboard.py
"""
import json, subprocess

PROFILE = "DEFAULT"; WID = "<WAREHOUSE_ID>"; S = "demo_catalog.seguros_demo"
PARENT = "/Workspace/Users/<tu_usuario>/seguros_demo"
DBX_COLORS = ["#FF3621", "#1B3139", "#00A972", "#FFAB00", "#8BCAE7", "#AB4057", "#99DDB4", "#919191"]
RISK_MAP = [{"value": "Alto", "color": "#FF3621"}, {"value": "Medio", "color": "#FFAB00"}, {"value": "Bajo", "color": "#00A972"}]
CR, SF, CC = f"{S}.mv_cartera_rentabilidad", f"{S}.mv_siniestros_fraude", f"{S}.mv_comercial_canales"
RA = f"{S}.mv_reservas_actuariales"
EDADES = [12, 24, 36, 48, 60, 72]

DS = {
 # ---- Cartera y rentabilidad
 "ds_kpi_cartera": f"SELECT ROUND(MEASURE(`Prima Emitida`),0) prima_emitida, ROUND(MEASURE(`Prima Devengada`),0) prima_devengada, MEASURE(`Pólizas Vigentes`) vigentes, ROUND(MEASURE(`Siniestralidad %`)*100,1) siniestralidad, ROUND(MEASURE(`Frecuencia`)*100,1) frecuencia, ROUND(MEASURE(`Severidad`),0) severidad FROM {CR}",
 "ds_anio": f"SELECT `Año Suscripción` anio, ROUND(MEASURE(`Prima Emitida`),0) prima, ROUND(MEASURE(`Costo Incurrido`),0) incurrido, ROUND(MEASURE(`Siniestralidad %`)*100,1) siniestralidad FROM {CR} GROUP BY 1 ORDER BY 1",
 "ds_paquete": f"SELECT `Paquete` paquete, ROUND(MEASURE(`Prima Emitida`),0) prima, ROUND(MEASURE(`Siniestralidad %`)*100,1) siniestralidad FROM {CR} GROUP BY 1 ORDER BY prima DESC",
 "ds_region": f"SELECT `Región` region, ROUND(MEASURE(`Prima Emitida`),0) prima, ROUND(MEASURE(`Siniestralidad %`)*100,1) siniestralidad FROM {CR} GROUP BY 1 ORDER BY prima DESC",
 "ds_canal_venta": f"SELECT `Canal de Venta` canal, ROUND(MEASURE(`Prima Emitida`),0) prima FROM {CR} GROUP BY 1 ORDER BY prima DESC",
 "ds_uso": f"SELECT `Uso Vehículo` uso, ROUND(MEASURE(`Frecuencia`)*100,1) frecuencia, ROUND(MEASURE(`Siniestralidad %`)*100,1) siniestralidad FROM {CR} GROUP BY 1 ORDER BY frecuencia DESC",
 "ds_credito": f"SELECT `Cliente con Crédito del Grupo` credito, MEASURE(`Clientes Únicos`) clientes FROM {CR} GROUP BY 1",
 # ---- Siniestros y fraude
 "ds_kpi_sin": f"SELECT MEASURE(`Siniestros`) siniestros, ROUND(MEASURE(`Costo Incurrido`),0) incurrido, ROUND(MEASURE(`Reserva Pendiente`),0) reserva, ROUND(MEASURE(`Tasa de Fraude`)*100,1) tasa_fraude, ROUND(MEASURE(`Monto Fraude Detectado`),0) fraude_detectado, ROUND(MEASURE(`Monto en Riesgo de Fraude`),0) monto_riesgo FROM {SF}",
 "ds_sin_mes": f"SELECT to_date(concat(`Año-Mes Ocurrencia`,'-01')) fecha, MEASURE(`Siniestros`) siniestros, ROUND(MEASURE(`Costo Incurrido`),0) incurrido FROM {SF} GROUP BY 1 ORDER BY 1",
 "ds_cobertura": f"SELECT `Cobertura` cobertura, ROUND(MEASURE(`Costo Incurrido`),0) incurrido, ROUND(MEASURE(`Tasa de Fraude`)*100,1) tasa_fraude FROM {SF} GROUP BY 1 ORDER BY incurrido DESC",
 "ds_taller": f"SELECT `Tipo de Taller` taller, ROUND(MEASURE(`Tasa de Fraude`)*100,1) tasa_fraude, ROUND(MEASURE(`Presupuesto Taller vs Autorizado`),2) ratio FROM {SF} WHERE `Tipo de Taller` <> 'Sin taller' GROUP BY 1 ORDER BY tasa_fraude DESC",
 "ds_nivel": f"SELECT `Nivel Riesgo Fraude` nivel, MEASURE(`Siniestros`) siniestros, ROUND(MEASURE(`Monto en Riesgo de Fraude`),0) monto_riesgo FROM {SF} WHERE `Nivel Riesgo Fraude` IN ('Alto','Medio','Bajo') GROUP BY 1",
 "ds_top_riesgo": "SELECT num_siniestro, cobertura, region, estado_ocurrencia, ROUND(monto_reclamado,0) monto_reclamado, ROUND(prob_fraude*100,1) prob_pct, razon_1, razon_2, razon_3 FROM demo_catalog.seguros_ml.scoring_fraude_siniestros WHERE nivel_riesgo = 'Alto' ORDER BY prob_fraude DESC, monto_reclamado DESC LIMIT 50",
 # ---- Documentos de siniestros (IA: ai_parse_document + ai_query)
 "ds_docs_kpi": f"SELECT COUNT(1) docs, COUNT_IF(num_inconsistencias > 0) con_inc, ROUND(AVG(CASE WHEN num_inconsistencias > 0 THEN 100.0 ELSE 0 END),1) pct_inc, ROUND(SUM(CASE WHEN total_no_coincide THEN total_documento - total_capturado ELSE 0 END),0) sobreprecio FROM {S}.docs_validacion_presupuestos",
 "ds_docs_nivel": f"SELECT nivel_riesgo_modelo nivel, ROUND(AVG(CASE WHEN num_inconsistencias > 0 THEN 100.0 ELSE 0 END),1) pct_inc FROM {S}.docs_validacion_presupuestos WHERE nivel_riesgo_modelo IN ('Alto','Medio','Bajo') GROUP BY 1",
 "ds_docs_motivo": f"SELECT m motivo, COUNT(1) documentos FROM {S}.docs_validacion_presupuestos LATERAL VIEW explode(motivos) t AS m GROUP BY 1 ORDER BY 2 DESC",
 "ds_docs_bandeja": f"SELECT num_siniestro, region, nivel_riesgo_modelo nivel, nombre_taller, ROUND(total_documento,0) total_documento, ROUND(total_capturado,0) total_capturado, ROUND(dif_total_pct*100,1) dif_pct, array_join(motivos, ' · ') motivos FROM {S}.docs_validacion_presupuestos WHERE num_inconsistencias > 0 AND nivel_riesgo_modelo <> 'Cerrado' ORDER BY num_inconsistencias DESC, prob_fraude DESC NULLS LAST",
 # ---- Comercial y canales
 "ds_kpi_com": f"SELECT MEASURE(`Cotizaciones`) cotizaciones, ROUND(MEASURE(`Tasa de Conversión`)*100,1) conversion, ROUND(MEASURE(`Prima Emitida (convertidas)`),0) prima, ROUND(MEASURE(`Prima Cotizada Promedio`),0) prima_prom FROM {CC}",
 "ds_canal": f"SELECT `Canal` canal, MEASURE(`Cotizaciones`) cotizaciones, ROUND(MEASURE(`Tasa de Conversión`)*100,1) conversion, ROUND(MEASURE(`Prima Emitida (convertidas)`),0) prima, ROUND(MEASURE(`Brecha de Precio No Convertidas`)*100,1) brecha FROM {CC} GROUP BY 1 ORDER BY cotizaciones DESC",
 "ds_cot_mes": f"SELECT to_date(concat(`Año-Mes`,'-01')) fecha, MEASURE(`Cotizaciones`) cotizaciones, MEASURE(`Cotizaciones Convertidas`) convertidas FROM {CC} GROUP BY 1 ORDER BY 1",
 "ds_edad": f"SELECT `Rango Edad Conductor` edad, ROUND(MEASURE(`Tasa de Conversión`)*100,1) conversion FROM {CC} GROUP BY 1 ORDER BY 1",
 # ---- Reservas (actuarial, valuación 2026-09-30)
 "ds_kpi_res": f"SELECT ROUND(MEASURE(`Pagado`),0) pagado, ROUND(MEASURE(`Reserva de Caso`),0) caso, ROUND(MEASURE(`Reserva Requerida`),0) requerida, ROUND(MEASURE(`Suficiencia de Reserva`),0) suficiencia, ROUND(MEASURE(`Suficiencia %`)*100,1) suficiencia_pct FROM {RA}",
 "ds_res_alto": f"SELECT ROUND(SUM(f.reserva_pendiente),0) reserva_alto FROM {S}.fact_siniestros f JOIN demo_catalog.seguros_ml.scoring_fraude_siniestros s ON f.id_siniestro = s.id_siniestro WHERE s.nivel_riesgo = 'Alto'",
 "ds_res_cob": f"SELECT cobertura, tipo, monto FROM (SELECT `Cobertura` cobertura, ROUND(MEASURE(`Reserva de Caso`),0) caso, ROUND(MEASURE(`Reserva Requerida`),0) req FROM {RA} GROUP BY 1) UNPIVOT (monto FOR tipo IN (caso AS `Reserva de caso constituida`, req AS `Reserva requerida (chain-ladder)`)) ORDER BY cobertura",
 "ds_triangulo": "SELECT periodo_etiqueta periodo, " + ", ".join(
     f"MAX(CASE WHEN edad_meses = {e} THEN concat(format_number(pagado / 1e6, 1), CASE WHEN tipo_celda = 'Proyectado' THEN ' ▸' ELSE '' END) END) m{e}" for e in EDADES)
     + f" FROM (SELECT periodo_ocurrencia, periodo_etiqueta, edad_meses, tipo_celda, SUM(pagado_acumulado) pagado FROM {S}.act_triangulo GROUP BY ALL) GROUP BY periodo_ocurrencia, periodo_etiqueta ORDER BY periodo_ocurrencia",
 "ds_patron": f"SELECT cobertura, edad_meses, ROUND(pct_desarrollado*100,1) pct FROM {S}.act_factores_desarrollo ORDER BY cobertura, edad_meses",
 "ds_factores": "SELECT cobertura, " + ", ".join(
     f"MAX(CASE WHEN edad_meses = {e} THEN factor_edad_a_edad END) f{e}_{e+12}" for e in EDADES[:-1])
     + f", MAX(CASE WHEN edad_meses = 12 THEN factor_a_ultimo END) cdf12 FROM {S}.act_factores_desarrollo GROUP BY 1 ORDER BY cdf12 DESC",
 "ds_sin_periodo": f"SELECT periodo, tipo, valor FROM (SELECT periodo_etiqueta periodo, ROUND(siniestralidad_reportada*100,1) rep, ROUND(siniestralidad_ultima*100,1) ult FROM {S}.act_siniestralidad_periodo) UNPIVOT (valor FOR tipo IN (rep AS `Reportada (incurrido)`, ult AS `Última estimada (chain-ladder)`)) ORDER BY periodo",
 "ds_res_det": f"SELECT cobertura, periodo_etiqueta periodo, edad_meses, ROUND(pagado,0) pagado, ROUND(reserva_caso,0) caso, ROUND(ultimo_estimado,0) ultimo, ROUND(reserva_requerida,0) requerida, ROUND(suficiencia_reserva,0) suficiencia FROM {S}.act_reservas WHERE reserva_caso > 0 OR reserva_requerida > 0 ORDER BY reserva_caso DESC",
}


def q(sql):
    p = {"warehouse_id": WID, "statement": sql, "wait_timeout": "50s"}
    r = subprocess.run(["databricks", "api", "post", "/api/2.0/sql/statements", "--profile", PROFILE, "--json", json.dumps(p)],
                       capture_output=True, text=True)
    return json.loads(r.stdout).get("status", {})


print("Validando datasets...")
for k, sql in DS.items():
    st = q(sql)
    assert st.get("state") == "SUCCEEDED", f"{k}: {st.get('error', {}).get('message')}"
print("  todos OK")
datasets = [{"name": k, "displayName": k, "queryLines": [v]} for k, v in DS.items()]

# ---------------- widget helpers ----------------
def text(name,md,x,y,w,h):
    return {"widget":{"name":name,"multilineTextboxSpec":{"lines":[md]}},"position":{"x":x,"y":y,"width":w,"height":h}}

def counter(name,ds,field,title,x,y,w,h,fmt=None):
    val={"fieldName":field,"displayName":title}
    if fmt: val["format"]={"type":"number-plain","abbreviation":"compact","decimalPlaces":{"type":"max","places":fmt}}
    return {"widget":{"name":name,"queries":[{"name":"main_query","query":{"datasetName":ds,"fields":[{"name":field,"expression":f"`{field}`"}],"disaggregated":True}}],
        "spec":{"version":2,"widgetType":"counter","encodings":{"value":val},"frame":{"showTitle":True,"title":title}}},
        "position":{"x":x,"y":y,"width":w,"height":h}}

def bar(name,ds,xf,yf,xlabel,ylabel,title,x,y,w,h,colorf=None,color_map=None,sort="y-reversed",colors=None,group=False,color_label=None):
    fields=[{"name":xf,"expression":f"`{xf}`"},{"name":yf,"expression":f"`{yf}`"}]
    xscale={"type":"categorical"}
    if sort: xscale["sort"]={"by":sort}
    enc={"x":{"fieldName":xf,"scale":xscale,"displayName":xlabel},
         "y":{"fieldName":yf,"scale":{"type":"quantitative"},"displayName":ylabel},"label":{"show":True}}
    if colorf:
        fields.append({"name":colorf,"expression":f"`{colorf}`"})
        cs={"type":"categorical"}
        if color_map: cs["mappings"]=color_map
        enc["color"]={"fieldName":colorf,"scale":cs,"displayName":color_label or xlabel}
    spec={"version":3,"widgetType":"bar","encodings":enc,"frame":{"showTitle":True,"title":title}}
    if colors: spec["mark"]={"colors":colors}
    if group: spec.setdefault("mark",{})["layout"]="group"
    return {"widget":{"name":name,"queries":[{"name":"main_query","query":{"datasetName":ds,"fields":fields,"disaggregated":True}}],"spec":spec},
        "position":{"x":x,"y":y,"width":w,"height":h}}

def line(name,ds,xf,yfields,xlabel,title,x,y,w,h,xtype="temporal",colorf=None):
    fields=[{"name":xf,"expression":f"`{xf}`"}]+[{"name":f,"expression":f"`{f}`"} for f,_ in yfields]
    yenc={"scale":{"type":"quantitative"},"fields":[{"fieldName":f,"displayName":lbl} for f,lbl in yfields]} if len(yfields)>1 else {"fieldName":yfields[0][0],"scale":{"type":"quantitative"},"displayName":yfields[0][1]}
    enc={"x":{"fieldName":xf,"scale":{"type":xtype},"displayName":xlabel},"y":yenc}
    if colorf:
        fields.append({"name":colorf,"expression":f"`{colorf}`"})
        enc["color"]={"fieldName":colorf,"scale":{"type":"categorical"},"displayName":colorf}
    return {"widget":{"name":name,"queries":[{"name":"main_query","query":{"datasetName":ds,"fields":fields,"disaggregated":True}}],
        "spec":{"version":3,"widgetType":"line","encodings":enc,"frame":{"showTitle":True,"title":title},"mark":{"colors":DBX_COLORS}}},
        "position":{"x":x,"y":y,"width":w,"height":h}}

def pie(name,ds,anglef,colorf,title,x,y,w,h,colors=None):
    spec={"version":3,"widgetType":"pie","encodings":{"angle":{"fieldName":anglef,"scale":{"type":"quantitative"},"displayName":anglef},
        "color":{"fieldName":colorf,"scale":{"type":"categorical"},"displayName":colorf}},"frame":{"showTitle":True,"title":title}}
    if colors: spec["mark"]={"colors":colors}
    return {"widget":{"name":name,"queries":[{"name":"main_query","query":{"datasetName":ds,"fields":[{"name":anglef,"expression":f"`{anglef}`"},{"name":colorf,"expression":f"`{colorf}`"}],"disaggregated":True}}],"spec":spec},
        "position":{"x":x,"y":y,"width":w,"height":h}}

def table(name,ds,cols,title,x,y,w,h):
    fields=[{"name":c,"expression":f"`{c}`"} for c,_ in cols]
    return {"widget":{"name":name,"queries":[{"name":"main_query","query":{"datasetName":ds,"fields":fields,"disaggregated":True}}],
        "spec":{"version":2,"widgetType":"table","encodings":{"columns":[{"fieldName":c,"displayName":l} for c,l in cols]},"frame":{"showTitle":True,"title":title}}},
        "position":{"x":x,"y":y,"width":w,"height":h}}

# ---------------- PÁGINA 1: Cartera y Rentabilidad ----------------
p1 = [
 text("p1-title", "# 🚗 Aseguradora FSI · Autos — Cartera y Rentabilidad", 0, 0, 6, 1),
 text("p1-sub", "Prima, cartera y rentabilidad técnica · Una sola fuente gobernada (sin extractos) · Metric view `mv_cartera_rentabilidad`", 0, 1, 6, 1),
 counter("p1-k1", "ds_kpi_cartera", "prima_emitida", "Prima Emitida (MXN)", 0, 2, 2, 3, fmt=1),
 counter("p1-k2", "ds_kpi_cartera", "prima_devengada", "Prima Devengada (MXN)", 2, 2, 2, 3, fmt=1),
 counter("p1-k3", "ds_kpi_cartera", "vigentes", "Pólizas Vigentes", 4, 2, 2, 3),
 counter("p1-k4", "ds_kpi_cartera", "siniestralidad", "Siniestralidad %", 0, 5, 2, 3),
 counter("p1-k5", "ds_kpi_cartera", "frecuencia", "Frecuencia (siniestros por 100 autos-año)", 2, 5, 2, 3),
 counter("p1-k6", "ds_kpi_cartera", "severidad", "Severidad (MXN por siniestro)", 4, 5, 2, 3),
 text("p1-h1", "### Evolución por año de suscripción", 0, 8, 6, 1),
 bar("p1-prima-anio", "ds_anio", "anio", "prima", "Año", "Prima Emitida", "Prima Emitida por Año", 0, 9, 3, 6, sort="x", colors=DBX_COLORS),
 bar("p1-sin-anio", "ds_anio", "anio", "siniestralidad", "Año", "Siniestralidad %", "Siniestralidad % por Año (años recientes aún en desarrollo)", 3, 9, 3, 6, sort="x", colors=["#1B3139"]),
 text("p1-h2", "### ¿Dónde ganamos y dónde perdemos?", 0, 15, 6, 1),
 bar("p1-paq", "ds_paquete", "paquete", "prima", "Paquete", "Prima Emitida", "Prima Emitida por Paquete", 0, 16, 3, 6, colors=DBX_COLORS),
 bar("p1-reg", "ds_region", "region", "siniestralidad", "Región", "Siniestralidad %", "Siniestralidad % por Región", 3, 16, 3, 6, colors=["#FF3621"]),
 pie("p1-canal", "ds_canal_venta", "prima", "canal", "Prima Emitida por Canal de Venta", 0, 22, 2, 6, colors=DBX_COLORS),
 bar("p1-uso", "ds_uso", "uso", "frecuencia", "Uso del Vehículo", "Frecuencia (por 100 autos-año)", "Frecuencia por Uso del Vehículo", 2, 22, 2, 6, colors=["#1B3139"]),
 pie("p1-cred", "ds_credito", "clientes", "credito", "Asegurados con Crédito del Grupo (cruce DWH ⇄ AWS)", 4, 22, 2, 6, colors=["#00A972", "#919191"]),
]

# ---------------- PÁGINA 2: Siniestros y Fraude ----------------
p2 = [
 text("p2-title", "# 🛡️ Siniestros y Fraude", 0, 0, 6, 1),
 text("p2-sub", "Costo de siniestros, dictámenes SIU y riesgo de fraude del modelo `modelo_fraude_siniestros@champion` · Metric view `mv_siniestros_fraude`", 0, 1, 6, 1),
 counter("p2-k1", "ds_kpi_sin", "siniestros", "Siniestros", 0, 2, 2, 3),
 counter("p2-k2", "ds_kpi_sin", "incurrido", "Costo Incurrido (MXN)", 2, 2, 2, 3, fmt=1),
 counter("p2-k3", "ds_kpi_sin", "reserva", "Reserva Pendiente (MXN)", 4, 2, 2, 3, fmt=1),
 counter("p2-k4", "ds_kpi_sin", "tasa_fraude", "Tasa de Fraude Confirmado %", 0, 5, 2, 3),
 counter("p2-k5", "ds_kpi_sin", "fraude_detectado", "Monto Fraude Detectado (MXN)", 2, 5, 2, 3, fmt=1),
 counter("p2-k6", "ds_kpi_sin", "monto_riesgo", "Monto en Riesgo — abiertos (MXN)", 4, 5, 2, 3, fmt=1),
 text("p2-h1", "### Tendencia y composición del costo", 0, 8, 6, 1),
 line("p2-mes", "ds_sin_mes", "fecha", [("incurrido", "Costo Incurrido")], "Mes de ocurrencia", "Costo Incurrido por Mes", 0, 9, 4, 6),
 bar("p2-cob", "ds_cobertura", "cobertura", "incurrido", "Cobertura", "Costo Incurrido", "Costo por Cobertura", 4, 9, 2, 6, colors=DBX_COLORS),
 text("p2-h2", "### Fraude: ¿dónde está?", 0, 15, 6, 1),
 bar("p2-cobf", "ds_cobertura", "cobertura", "tasa_fraude", "Cobertura", "Tasa de Fraude %", "Tasa de Fraude por Cobertura", 0, 16, 2, 6, colors=["#FF3621"]),
 bar("p2-tal", "ds_taller", "taller", "tasa_fraude", "Tipo de Taller", "Tasa de Fraude %", "Tasa de Fraude por Tipo de Taller", 2, 16, 2, 6, colors=["#AB4057"]),
 bar("p2-niv", "ds_nivel", "nivel", "siniestros", "Nivel de Riesgo", "Siniestros abiertos", "Siniestros Abiertos por Nivel de Riesgo (modelo)", 4, 16, 2, 6, colorf="nivel", color_map=RISK_MAP, sort=None),
 table("p2-top", "ds_top_riesgo", [("num_siniestro", "Siniestro"), ("cobertura", "Cobertura"), ("region", "Región"), ("estado_ocurrencia", "Estado"),
       ("monto_reclamado", "Monto Reclamado"), ("prob_pct", "Prob. Fraude %"), ("razon_1", "Razón 1"), ("razon_2", "Razón 2"), ("razon_3", "Razón 3")],
       "Bandeja SIU — siniestros abiertos de riesgo Alto (con razones del modelo)", 0, 22, 6, 8),
 text("p2-h3", "### 📄 IA sobre documentos: presupuestos de taller (PDF) validados contra los sistemas", 0, 30, 6, 1),
 text("p2-docs-sub", "`ai_parse_document` lee el PDF → `ai_query` extrae los campos en JSON → se cruzan con la valuación capturada, el vehículo asegurado y la fecha del siniestro · Volume `documentos_siniestros` · tabla `docs_validacion_presupuestos`", 0, 31, 6, 1),
 counter("p2-d1", "ds_docs_kpi", "docs", "Presupuestos procesados", 0, 32, 2, 3),
 counter("p2-d2", "ds_docs_kpi", "pct_inc", "% con inconsistencias", 2, 32, 2, 3),
 counter("p2-d3", "ds_docs_kpi", "sobreprecio", "Sobreprecio documentado vs capturado (MXN)", 4, 32, 2, 3, fmt=1),
 bar("p2-dniv", "ds_docs_nivel", "nivel", "pct_inc", "Nivel de riesgo (modelo)", "% con inconsistencias", "% de documentos con inconsistencias por nivel de riesgo del modelo", 0, 35, 3, 6, colorf="nivel", color_map=RISK_MAP, sort=None),
 bar("p2-dmot", "ds_docs_motivo", "motivo", "documentos", "Motivo", "Documentos", "Inconsistencias detectadas por tipo", 3, 35, 3, 6, colors=["#AB4057"]),
 table("p2-dband", "ds_docs_bandeja", [("num_siniestro", "Siniestro"), ("region", "Región"), ("nivel", "Riesgo modelo"), ("nombre_taller", "Taller"),
       ("total_documento", "Total documento"), ("total_capturado", "Total capturado"), ("dif_pct", "Diferencia %"), ("motivos", "Inconsistencias")],
       "Siniestros abiertos con inconsistencias documentales (incluye casos que el modelo calificó Bajo)", 0, 41, 6, 8),
]

# ---------------- PÁGINA 3: Comercial y Canales ----------------
p3 = [
 text("p3-title", "# 📈 Comercial y Canales", 0, 0, 6, 1),
 text("p3-sub", "Embudo de cotización → póliza por canal, incluidas integraciones externas (comparadores) · Metric view `mv_comercial_canales`", 0, 1, 6, 1),
 counter("p3-k1", "ds_kpi_com", "cotizaciones", "Cotizaciones", 0, 2, 2, 3),
 counter("p3-k2", "ds_kpi_com", "conversion", "Tasa de Conversión %", 2, 2, 2, 3),
 counter("p3-k3", "ds_kpi_com", "prima", "Prima Emitida desde Cotización (MXN)", 4, 2, 2, 3, fmt=1),
 text("p3-h1", "### Desempeño por canal", 0, 5, 6, 1),
 bar("p3-cot", "ds_canal", "canal", "cotizaciones", "Canal", "Cotizaciones", "Cotizaciones por Canal", 0, 6, 3, 6, colors=DBX_COLORS),
 bar("p3-conv", "ds_canal", "canal", "conversion", "Canal", "Conversión %", "Tasa de Conversión por Canal", 3, 6, 3, 6, colors=["#00A972"]),
 line("p3-mes", "ds_cot_mes", "fecha", [("cotizaciones", "Cotizaciones"), ("convertidas", "Convertidas")], "Mes", "Cotizaciones vs Convertidas por Mes", 0, 12, 4, 6),
 bar("p3-edad", "ds_edad", "edad", "conversion", "Edad del Conductor", "Conversión %", "Conversión por Edad del Conductor", 4, 12, 2, 6, sort="x", colors=["#1B3139"]),
 table("p3-tbl", "ds_canal", [("canal", "Canal"), ("cotizaciones", "Cotizaciones"), ("conversion", "Conversión %"), ("prima", "Prima Emitida"),
       ("brecha", "Brecha de precio no convertidas %")], "Detalle por Canal — la brecha indica sensibilidad a precio", 0, 18, 6, 5),
]

# ---------------- PÁGINA 4: Reservas (Actuarial) ----------------
p4 = [
 text("p4-title", "# 📐 Reservas de Siniestros — Chain-Ladder", 0, 0, 6, 1),
 text("p4-sub", "Valuación al **30-sep-2026** · Triángulos de desarrollo sobre la misma tabla gobernada `fact_movtos_siniestro` (sin extractos) · Metric view `mv_reservas_actuariales` · Periodos de ocurrencia oct–sep", 0, 1, 6, 1),
 counter("p4-k1", "ds_kpi_res", "caso", "Reserva de Caso Constituida (MXN)", 0, 2, 2, 3, fmt=1),
 counter("p4-k2", "ds_kpi_res", "requerida", "Reserva Requerida — chain-ladder (MXN)", 2, 2, 2, 3, fmt=1),
 counter("p4-k3", "ds_kpi_res", "suficiencia", "Suficiencia: reserva sobrada (MXN)", 4, 2, 2, 3, fmt=1),
 counter("p4-k4", "ds_kpi_res", "suficiencia_pct", "Suficiencia % sobre lo requerido", 0, 5, 2, 3),
 counter("p4-k5", "ds_kpi_res", "pagado", "Pagado acumulado (MXN)", 2, 5, 2, 3, fmt=1),
 counter("p4-k6", "ds_res_alto", "reserva_alto", "Reserva de caso en siniestros con riesgo ALTO de fraude (MXN)", 4, 5, 2, 3, fmt=1),
 text("p4-h1", "### ¿Dónde está la reserva y cuánto se necesita realmente?", 0, 8, 6, 1),
 bar("p4-cob", "ds_res_cob", "cobertura", "monto", "Cobertura", "MXN", "Reserva de caso vs requerida por cobertura", 0, 9, 3, 7,
     colorf="tipo", color_label="Reserva", sort=None, group=True, colors=["#1B3139", "#FF3621"]),
 line("p4-patron", "ds_patron", "edad_meses", [("pct", "% desarrollado")], "Edad (meses)", "Patrón de pago: % del costo final pagado por edad", 3, 9, 3, 7, xtype="quantitative", colorf="cobertura"),
 text("p4-h2", "### Triángulo de pagos acumulados (MXN millones, todas las coberturas) · ▸ = proyección chain-ladder", 0, 16, 6, 1),
 table("p4-tri", "ds_triangulo", [("periodo", "Periodo de ocurrencia")] + [(f"m{e}", f"{e} meses") for e in EDADES],
       "Cada fila es un periodo de ocurrencia; cada columna, la edad de evaluación. Arriba-izquierda = historia; abajo-derecha = futuro estimado", 0, 17, 6, 6),
 table("p4-fac", "ds_factores", [("cobertura", "Cobertura")] + [(f"f{e}_{e+12}", f"{e}→{e+12}") for e in EDADES[:-1]] + [("cdf12", "Factor a último desde 12m")],
       "Factores de desarrollo edad-a-edad (ponderados por volumen)", 0, 23, 6, 5),
 text("p4-h3", "### Siniestralidad: lo que se ve hoy vs lo que costará al final", 0, 28, 6, 1),
 bar("p4-sin", "ds_sin_periodo", "periodo", "valor", "Periodo de ocurrencia", "Siniestralidad %", "Siniestralidad reportada vs última estimada por periodo", 0, 29, 6, 6,
     colorf="tipo", color_label="Medición", sort="x", group=True, colors=["#919191", "#00A972"]),
 table("p4-det", "ds_res_det", [("cobertura", "Cobertura"), ("periodo", "Periodo"), ("edad_meses", "Edad (m)"), ("pagado", "Pagado"), ("caso", "Reserva de caso"),
       ("ultimo", "Último estimado"), ("requerida", "Reserva requerida"), ("suficiencia", "Suficiencia")],
       "Detalle de reservas por cobertura y periodo", 0, 35, 6, 7),
]

pages = [
 {"name": "page_cartera", "displayName": "Cartera y Rentabilidad", "pageType": "PAGE_TYPE_CANVAS", "layout": p1},
 {"name": "page_siniestros", "displayName": "Siniestros y Fraude", "pageType": "PAGE_TYPE_CANVAS", "layout": p2},
 {"name": "page_comercial", "displayName": "Comercial y Canales", "pageType": "PAGE_TYPE_CANVAS", "layout": p3},
 {"name": "page_reservas", "displayName": "Reservas (Actuarial)", "pageType": "PAGE_TYPE_CANVAS", "layout": p4},
]
dashboard = {"datasets": datasets, "pages": pages, "uiSettings": {"theme": {"widgetHeaderAlignment": "ALIGNMENT_UNSPECIFIED"}}}


def api(method, path, body):
    r = subprocess.run(["databricks", "api", method, path, "--profile", PROFILE, "--json", json.dumps(body)], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[:800])
    return json.loads(r.stdout or "{}")


payload = {"display_name": "Aseguradora FSI · Autos — Tablero Ejecutivo", "warehouse_id": WID, "parent_path": PARENT,
           "serialized_dashboard": json.dumps(dashboard)}
try:
    did = open("dashboard_id.txt").read().strip()
    d = api("patch", f"/api/2.0/lakeview/dashboards/{did}", payload)
except (FileNotFoundError, RuntimeError):
    d = api("post", "/api/2.0/lakeview/dashboards", payload)
    did = d["dashboard_id"]
    open("dashboard_id.txt", "w").write(did)
# embed_credentials=False → cada usuario consulta con su identidad: aplican filtros por región y masking
api("post", f"/api/2.0/lakeview/dashboards/{did}/published", {"embed_credentials": False, "warehouse_id": WID})
print("dashboard_id:", did)
print(f"https://<WORKSPACE_HOST>/dashboardsv3/{did}/published")
