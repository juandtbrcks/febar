"""Diagrama de arquitectura del demo Aseguradora FSI · Autos (draw.io).
Run: python3 build_diagrama.py   → arquitectura.drawio (+ .png si está draw.io desktop)
"""
import sys

sys.path.insert(0, "~/.vibe/marketplace/plugins/fe-specialized-agents/skills/drawio-diagram/scripts")
from generate_drawio import DrawioBuilder, load_icons, export_to_png

OUT = "./diagrama/arquitectura.drawio"
ICONOS = load_icons()
# Iconos propios (mismo estilo que los oficiales) en ./iconos
import urllib.parse as _u
import glob as _g, os as _os
for _k, _f in [("cuarentena_propio", "capa_cuarentena.svg"), ("agente_propio", "agente_investigador_siu.svg")] + \
        [(_os.path.basename(p)[:-4], _os.path.basename(p)) for p in sorted(_g.glob("./diagrama/iconos/gob_*.svg"))]:
    ICONOS[_k] = "data:image/svg+xml," + _u.quote(open(f"./diagrama/iconos/{_f}").read().replace("\n", ""), safe="")
b = DrawioBuilder(width=1720, height=1570, icons_cache=ICONOS)

b.add_title(30, 15, 1604, "Aseguradora FSI · Autos — Una sola fuente de verdad gobernada en Databricks (Azure)",
            subtitle="Federación sin duplicar · Medallion con calidad · Modelo estrella + reservas actuariales · "
                     "Fraude con MLflow · Capa semántica · Gobierno anti-extractos con Unity Catalog")
b.add_banner(30, 75, 1604, "FLUJO DE DATOS  →")

COL_W, GAP, Y0, H = 200, 34, 110, 830
xs = [30 + i * (COL_W + GAP) for i in range(7)]
NW, NH = 170, 84


def col(i, label, layer):
    return b.add_container(xs[i], Y0, COL_W, H, label, layer)


def node(c, row, label, color, icon, shape="rounded"):
    return b.add_node(15, 45 + row * 112, NW, NH, label, color, icon_name=icon, parent=c, shape=shape)


# 1. Fuentes (se quedan donde están)
c1 = col(0, "Fuentes (simuladas)", "sources")
oracle = node(c1, 0, "DWH de Seguros\nOracle on-prem\n(simulado en PostgreSQL)", "purple", "postgresql")
creditos = node(c1, 1, "Créditos personales\nAWS\n(simulado en PostgreSQL)", "purple", "postgresql")
datalake = node(c1, 2, "App de Autos\nviajes y reportes de siniestro\n(data lake de Ciencia de Datos)", "purple", "cloud_storage")
legacy = node(c1, 3, "Tabla de clientes de 2011\ncolumnas duplicadas\ne inconsistentes", "red", "postgresql")
pdfs = node(c1, 4, "Presupuestos de taller\n(documentos PDF)", "purple", "cloud_storage")
b.add_pain_badge(15, 730, "~55K columnas, duplicadas", parent=c1, w=170)
b.add_pain_badge(15, 754, "Extractos a apps externas", parent=c1, w=170)
b.add_pain_badge(15, 778, "Actuarial ~10 h", parent=c1, w=170)

# 2. Acceso sin copias
c2 = col(1, "Acceso sin copias", "ingestion")
fed = node(c2, 0, "Consulta directa a las fuentes\nsin copiar ni mover datos", "blue", "partner_connect")
fed2 = node(c2, 1, "Catálogo unificado\nDWH y Créditos\nen un solo lugar", "blue", "catalog_store")
autoloader = node(c2, 2, "Ingesta automática\nde archivos nuevos de la app", "blue", "structured_streaming_ui")
b.add_win_badge(15, 730, "Sin réplicas ni ETL externo", parent=c2, w=170)
b.add_win_badge(15, 754, "Cruce seguro ⇄ crédito por RFC", parent=c2, w=170)

# 3. Medallion completo (un solo bloque: Bronce → Plata → Oro)
c3 = b.add_container(xs[2], Y0, 2 * COL_W + GAP, H, "Medallion · Bronce → Plata → Oro", "medallion")
GX = 15 + COL_W + GAP  # sub-columna Oro
bronce = node(c3, 0, "Bronce · Datos tal como llegan\nCopia fiel de cada sistema\nsin cambios · auditable", "bronze", "unstructured_bronze")
plata = node(c3, 1, "Plata · Datos confiables\nLimpios, validados y en un\nsolo formato para todos", "silver", "semi_structured_silver")
calidad = node(c3, 2, "Alertas de calidad\nPresupuestos inflados, GPS\nlejano, RFC mal capturado", "silver", "data_quality_2")
estrella = b.add_node(GX, 45, NW, NH, "Oro · Listo para el negocio\nIndicadores certificados\npara BI, IA y actuaría", "gold", icon_name="delta_table", parent=c3)
cuarentena = node(c3, 3, "Cuarentena · Nada se pierde\nErrores apartados y explicados\npara corregir en el origen", "red", "cuarentena_propio")
b.add_text(15, 470, 170, 30, "Proceso automático: la calidad se mide en cada carga", font_size=9, font_color="#546E7A", parent=c3)
b.add_win_badge(GX, 754, "Reservas en minutos", parent=c3, w=170)

# 5. IA / ML
c5 = col(4, "IA · Fraude y agente", "aiml")
fs = node(c5, 0, "Señales de fraude\n36 indicadores por siniestro", "orange", "feature_store")
mlflow = node(c5, 1, "Modelo de fraude\nentrenado, versionado\ny aprobado", "orange", "mlflow")
scoring = node(c5, 2, "Calificación de riesgo\nAlto / Medio / Bajo\ncon razones explicables", "orange", "predict")
docs = node(c5, 4, "IA sobre documentos\nlee presupuestos y detecta\ninconsistencias", "orange", "ai")
agente = node(c5, 5, "Agente Investigador SIU\nanaliza siniestros y propone\ncasos · respeta permisos", "orange", "agente_propio")
b.add_win_badge(15, 754, "Top 10% → 90% del fraude", parent=c5, w=170)

# 6. Capa semántica
c6 = col(5, "Capa semántica", "compute")
mv1 = node(c6, 0, "mv_cartera_rentabilidad", "compute_green", "data_warehouse_heavy")
mv2 = node(c6, 2, "mv_siniestros_fraude", "compute_green", "data_warehouse_heavy")
mv3 = node(c6, 1, "mv_comercial_canales", "compute_green", "data_warehouse_heavy")
mv4 = node(c6, 3, "mv_reservas_actuariales", "compute_green", "data_warehouse_heavy")
b.add_text(15, 715, 170, 50, "UC Metric Views · SQL Warehouse serverless\nUna sola capa semántica para\nDashboard, Genie y herramientas externas", font_size=9, font_color="#546E7A", parent=c6)

# 7. Consumo
c7 = col(6, "Consumo", "consumption")
dash = node(c7, 0, "AI/BI Dashboard\n4 páginas (sin credenciales\nembebidas)", "green", "output")
genie = node(c7, 1, "Genie Ejecutivo\npreguntas en español", "green", "ai")
app_siu = node(c7, 5, "App Agente SIU\nDatabricks App · chat +\naprobación humana", "green", "apps_services")
denodo = b.add_aspirational_card(15, 45 + 3 * 112, NW, NH, "Denodo / apps externas",
                                 sub="consumen vía SQL (OAuth)", parent=c7)

# Flujos
H_ = dict(exit_x=1, exit_y=0.5, entry_x=0, entry_y=0.5)
b.add_edge(oracle, fed, "", **H_)
b.add_edge(creditos, fed, "", exit_x=1, exit_y=0.5, entry_x=0, entry_y=0.8)
b.add_edge(datalake, autoloader, "", **H_)
b.add_edge(fed, bronce, "", stroke_width=2.5, **H_)
b.add_edge(autoloader, bronce, "", exit_x=1, exit_y=0.5, entry_x=0, entry_y=0.8)
b.add_edge(bronce, plata, "", exit_x=0.5, exit_y=1, entry_x=0.5, entry_y=0)
b.add_edge(plata, calidad, "", exit_x=0.5, exit_y=1, entry_x=0.5, entry_y=0, dashed=True)
b.add_edge(calidad, cuarentena, "", exit_x=0.5, exit_y=1, entry_x=0.5, entry_y=0, dashed=True)
b.add_edge(plata, estrella, "", stroke_width=2.5, exit_x=1, exit_y=0.5, entry_x=0, entry_y=0.5)
b.add_edge(estrella, fs, "", **H_)
b.add_edge(fs, mlflow, "", exit_x=0.5, exit_y=1, entry_x=0.5, entry_y=0)
b.add_edge(mlflow, scoring, "", exit_x=0.5, exit_y=1, entry_x=0.5, entry_y=0)
b.add_edge(estrella, mv1, "", stroke_width=2.5, exit_x=0.5, exit_y=0, entry_x=0.5, entry_y=0)
b.add_edge(scoring, mv2, "", **H_)
# La capa semántica completa (las 4 metric views) alimenta a cada consumidor
for destino, fila_dest in [(dash, 0), (genie, 1), (denodo, 3)]:
    b.add_edge(c6, destino, "", stroke_width=2.5, exit_x=1, exit_y=round((45 + fila_dest * 112 + NH / 2) / H, 4), entry_x=0, entry_y=0.5)
b.add_edge(pdfs, docs, "", exit_x=1, exit_y=0.5, entry_x=0, entry_y=0.5, dashed=True)
b.add_edge(docs, agente, "", exit_x=0.5, exit_y=1, entry_x=0.5, entry_y=0)
b.add_edge(agente, app_siu, "", stroke_width=2.5, **H_)

# Gobierno transversal
g = b.add_container(30, Y0 + H + 25, 1604, 270, "Unity Catalog · Gobierno de datos e IA (aplica en TODAS las capas, a cada usuario y a los agentes)",
                    "governance", dashed=True)
gov = [("Etiquetas de negocio\nidentifican datos personales,\nregión y nivel de confianza", "gob_01_etiquetas"),
       ("Datos personales protegidos\ncada rol ve solo lo que debe\n(enmascarado automático)", "gob_02_datos_personales"),
       ("Cada región ve lo suyo\nlos agentes regionales solo\nven a sus clientes", "gob_03_cada_region"),
       ("Sello de confianza\noficial · en pruebas · no usar", "gob_04_sello_confianza"),
       ("Espacio seguro para\nCiencia de Datos\nsin exponer datos personales", "gob_05_espacio_ciencia_datos"),
       ("Auditoría completa\nquién consultó qué y cuándo", "gob_06_auditoria"),
       ("Trazabilidad de punta a punta\nde la fuente al tablero", "gob_07_trazabilidad"),
       ("Catálogo de negocio\nlos datos de Seguros Autos\nen un solo lugar", "gob_08_catalogo_negocio"),
       ("Control de modelos de IA\nqué modelo se usa, quién\nlo usa y cuánto", "gob_09_control_modelos_ia"),
       ("Calidad de la IA\ncada respuesta se evalúa\ny se monitorea", "gob_10_calidad_ia")]
for i, (lbl, ic) in enumerate(gov):
    b.add_node(16 + (i % 5) * 318, 45 + (i // 5) * 110, 300, 96, lbl, "gov", icon_name=ic, parent=g)

b.add_legend(30, Y0 + H + 315, [
    {"color": "#8D6E3F", "label": "Bronce (crudo)", "style": "swatch"},
    {"color": "#546E7A", "label": "Plata (validado)", "style": "swatch"},
    {"color": "#F57F17", "label": "Oro (negocio)", "style": "swatch"},
    {"color": "#E8F5E9", "label": "Consumo", "style": "swatch"},
    {"color": "#FFEBEE", "label": "Gobierno (Unity Catalog)", "style": "swatch"},
    {"color": "#FAFAFA", "label": "Borde punteado = herramienta del cliente", "style": "swatch"},
], title="Leyenda")
b.add_note(330, Y0 + H + 315, 1304, 60,
           "Mensaje: los datos NO se copian de las fuentes — se leen vía Lakehouse Federation; todo (BI, Genie, ML, actuarial) "
           "consume la MISMA capa oro certificada. El gobierno viaja con el dato: cada usuario ve solo su región y la PII "
           "según su rol, incluso desde Denodo o herramientas externas. <b>Para el demo</b>: datos sintéticos; Oracle on-prem y "
           "la BD de AWS se simulan con Azure PostgreSQL (<PG_SERVIDOR>) y el data lake de DS con un Volume de Unity Catalog. "
           "En el escenario real cambia solo la connection de Federation (Oracle / PostgreSQL en AWS / S3).")

# Etiquetas HTML: saltos de línea como <br> y texto libre con ajuste de línea
for cell in b._cells:
    if isinstance(cell.get("value"), str):
        cell["value"] = cell["value"].replace("\n", "<br>")
    if cell.get("style", "").startswith("text;") and "whiteSpace=wrap" not in cell["style"]:
        cell["style"] += "whiteSpace=wrap;"

b.print_validation()
b.save(OUT)
export_to_png(OUT)
print(OUT)
