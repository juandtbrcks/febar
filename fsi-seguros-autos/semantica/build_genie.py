"""Crea (o actualiza, si existe genie_space_id.txt) el Genie space ejecutivo de Aseguradora FSI · Autos sobre las 4 metric views
+ la bandeja de scoring de fraude + la siniestralidad actuarial por periodo.
Run: python3 build_genie.py
"""
import json, subprocess, sys, uuid

sys.path.insert(0, "~/.vibe/marketplace/plugins/fe-internal-tools/skills/genie-rooms/resources")
from genie_space_builder import GenieSpaceBuilder

PROFILE = "DEFAULT"; WID = "<WAREHOUSE_ID>"
PARENT = "/Workspace/Users/<tu_usuario>/seguros_demo"
S = "demo_catalog.seguros_demo"
SCORING = "demo_catalog.seguros_ml.scoring_fraude_siniestros"
EXP = "demo_catalog.seguros_siu_expediente"

space = GenieSpaceBuilder(
    title="Aseguradora FSI · Autos — Genie Ejecutivo",
    description="Pregunta en lenguaje natural por la cartera, rentabilidad, siniestros, fraude y canales comerciales y reservas actuariales de "
                "Seguros Autos FSI. Responde sobre la capa semántica gobernada (una sola fuente, sin extractos).",
    warehouse_id=WID,
)

space.set_instructions("""CONTEXTO DE NEGOCIO
Aseguradora FSI — ramo AUTOS (México). Paquetes: Amplia, Limitada, RC (Responsabilidad Civil), Plataformas (vehículos de plataformas digitales), Flotilla (PyME) y Amplia Plus. Canales de venta: Agente, Banca Seguros, Tienda Aliada, Digital y Broker. Montos en pesos mexicanos (MXN). Fecha de corte de los datos: 13 de octubre de 2026.

FUENTES (METRIC VIEWS — CAPA SEMÁNTICA) + 3 TABLAS
- demo_catalog.seguros_demo.mv_cartera_rentabilidad: una fila por póliza. Prima emitida/devengada/cobrada, pólizas, exposición y rentabilidad técnica (Siniestralidad %, Frecuencia, Severidad, Tasa de Cancelación) por año de suscripción, paquete, canal de venta, región, estado, segmento, vehículo y conductor.
- demo_catalog.seguros_demo.mv_siniestros_fraude: una fila por siniestro. Costo (Monto Reclamado, Costo Incurrido, Pagado, Reserva Pendiente, Recuperaciones), oportunidad de reporte y fraude (Tasa de Fraude, Monto Fraude Detectado, Siniestros Alto Riesgo, Monto en Riesgo de Fraude) por cobertura, canal de reporte, estatus, región, taller y tiempo.
- demo_catalog.seguros_demo.mv_comercial_canales: una fila por cotización. Cotizaciones, Tasa de Conversión, Prima Emitida (convertidas) y Brecha de Precio por canal (App Autos FSI, Portal Web, Comparador Externo, Agente, Módulo Tienda Aliada).
- demo_catalog.seguros_ml.scoring_fraude_siniestros (tabla normal, NO metric view): siniestros ABIERTOS calificados por el modelo de fraude, con prob_fraude, nivel_riesgo (Alto/Medio/Bajo), monto_en_riesgo y tres razones (razon_1..razon_3). Úsala para listar casos concretos ("¿qué siniestros debe revisar el SIU?").
- demo_catalog.seguros_demo.mv_reservas_actuariales: una fila por cobertura × periodo de ocurrencia, valuación al 30-sep-2026 (método chain-ladder sobre pagos). Medidas: Pagado, Reserva de Caso, Incurrido Reportado, Último Estimado, Reserva Requerida, IBNR, Suficiencia de Reserva, Suficiencia %, % Desarrollado, Siniestros Reportados. Dimensiones: Cobertura, Periodo de Ocurrencia (ej. 'oct-2025 a sep-2026'), Año Cierre Periodo, Edad (meses).
- demo_catalog.seguros_demo.act_siniestralidad_periodo (tabla normal): una fila por periodo de ocurrencia con prima_devengada, incurrido_reportado, ultimo_estimado, reserva_caso, reserva_requerida, suficiencia_reserva, siniestralidad_reportada y siniestralidad_ultima (fracciones 0–1). Úsala para "siniestralidad última" o "a cuánto llegará la siniestralidad".
- demo_catalog.seguros_demo.docs_validacion_presupuestos (tabla normal): un renglón por presupuesto de taller en PDF leído con IA (ai_parse_document + ai_query) y validado contra los sistemas. Columnas clave: num_siniestro, region, estatus, nombre_taller, total_documento, total_capturado, dif_total_pct, flags (total_no_coincide, vin_no_coincide, placas_no_coincide, fecha_previa_siniestro, taller_no_coincide, aritmetica_incorrecta), motivos (array de textos), num_inconsistencias, nivel_riesgo_modelo (Alto/Medio/Bajo/Cerrado), prob_fraude. Úsala para "documentos inconsistentes", "presupuestos alterados", "VIN que no coincide".

- demo_catalog.seguros_siu_expediente.casos (vista normal): casos de investigación del SIU operados en la app (Lakebase seguros-siu, replicados a Delta por CDF casi en tiempo real). Columnas: id_caso, num_siniestro, region, prioridad, estatus ('Abierto','En investigación','Cerrado - Fraude confirmado','Cerrado - Procedente'), veredicto ('fraude'/'legitimo', solo cerrados), asignado_a, monto_en_riesgo, prob_fraude_apertura (score del modelo al abrir, 0–1), fecha_creacion, fecha_cierre.
- demo_catalog.seguros_siu_expediente.etiquetas_siu (vista normal): un renglón por caso CERRADO con veredicto del investigador, fraude (1/0), prob_fraude_apertura y nivel_riesgo_apertura. Úsala para "¿qué tan bien acierta el modelo frente al SIU?", "tasa de confirmación", "monto evitado". Estas etiquetas alimentan el reentrenamiento del modelo.

REGLAS CRÍTICAS DE CONSULTA
1. En las METRIC VIEWS consulta SIEMPRE las medidas con MEASURE(`Nombre de la Medida`) y agrupa por dimensiones. NUNCA uses SUM()/AVG()/COUNT() directo sobre columnas de una metric view y NUNCA hagas JOIN entre metric views.
   Ejemplo: SELECT `Paquete`, MEASURE(`Prima Emitida`), MEASURE(`Siniestralidad %`) FROM demo_catalog.seguros_demo.mv_cartera_rentabilidad GROUP BY 1.
2. Usa los nombres exactos de medidas y dimensiones (con acentos y espacios, entre backticks).
3. Suficiencia %, % Desarrollado, Siniestralidad %, Tasa de Fraude, Tasa de Cancelación, Tasa de Conversión, % Reportados por App y Brecha de Precio vienen como fracción 0–1: preséntalas como porcentaje.
4. "Frecuencia" = siniestros por año-vehículo expuesto (multiplica por 100 para "por cada 100 autos").

DEFINICIONES DE NEGOCIO
- Siniestralidad = Costo Incurrido / Prima Devengada. Incurrido = pagado + reserva pendiente − recuperaciones. Los años de suscripción recientes (2025–2026) aún están en desarrollo: su siniestralidad es mayor porque incluye reservas abiertas.
- Prima devengada = parte de la prima ya "ganada" según el tiempo transcurrido de la vigencia.
- Fraude confirmado = dictamen del SIU (solo siniestros cerrados/rechazados). "En proceso" = sin dictamen todavía.
- Nivel Riesgo Fraude: Alto = top 10 % de riesgo según el modelo, Medio = top 25 %. Monto en Riesgo de Fraude = probabilidad × monto reclamado.
- RESERVAS (actuarial): periodos de ocurrencia de 12 meses que cierran el 30 de septiembre (el periodo 2026 = oct-2025 a sep-2026). Reserva de Caso = lo que los ajustadores tienen reservado en siniestros abiertos. Último Estimado = costo final proyectado con chain-ladder. Reserva Requerida = Último − Pagado. IBNR = Último − Incurrido (aquí sale NEGATIVO: las reservas de caso son conservadoras). Suficiencia de Reserva = Reserva de Caso − Reserva Requerida (>0 = reserva sobrada / capital inmovilizado). Cobertura de cola larga: Responsabilidad Civil y Gastos Médicos Ocupantes.
- Brecha de Precio No Convertidas = cuánto más caras fueron, en promedio, las cotizaciones que NO se convirtieron (sensibilidad a precio).

ESTILO DE RESPUESTA
Responde en español, con el hallazgo clave primero; indica filtros aplicados; montos en MXN con separador de miles (usa millones cuando sean grandes).""")

for v in ["mv_cartera_rentabilidad", "mv_siniestros_fraude", "mv_comercial_canales", "mv_reservas_actuariales"]:
    space.add_metric_view(f"{S}.{v}")
space.add_table(SCORING)
space.add_table(f"{S}.act_siniestralidad_periodo")
space.add_table(f"{S}.docs_validacion_presupuestos")
space.add_table(f"{EXP}.casos")
space.add_table(f"{EXP}.etiquetas_siu")

EJEMPLOS = [
    ("Siniestralidad por paquete",
     f"SELECT `Paquete`, MEASURE(`Prima Emitida`) AS prima_emitida, MEASURE(`Siniestralidad %`) AS siniestralidad "
     f"FROM {S}.mv_cartera_rentabilidad GROUP BY `Paquete` ORDER BY prima_emitida DESC",
     "Rentabilidad técnica por paquete con MEASURE() + GROUP BY."),
    ("Evolución anual de prima y siniestralidad",
     f"SELECT `Año Suscripción`, MEASURE(`Prima Emitida`) AS prima, MEASURE(`Costo Incurrido`) AS incurrido, "
     f"MEASURE(`Siniestralidad %`) AS siniestralidad FROM {S}.mv_cartera_rentabilidad GROUP BY 1 ORDER BY 1",
     "Serie anual por año de suscripción."),
    ("Fraude por tipo de taller",
     f"SELECT `Tipo de Taller`, MEASURE(`Siniestros`) AS siniestros, MEASURE(`Tasa de Fraude`) AS tasa_fraude, "
     f"MEASURE(`Presupuesto Taller vs Autorizado`) AS ratio_presupuesto FROM {S}.mv_siniestros_fraude "
     f"GROUP BY 1 ORDER BY tasa_fraude DESC",
     "Dónde se concentra el fraude en la red de talleres."),
    ("Conversión por canal",
     f"SELECT `Canal`, MEASURE(`Cotizaciones`) AS cotizaciones, MEASURE(`Tasa de Conversión`) AS conversion, "
     f"MEASURE(`Prima Emitida (convertidas)`) AS prima FROM {S}.mv_comercial_canales GROUP BY 1 ORDER BY cotizaciones DESC",
     "Embudo comercial por canal, incluido el comparador externo."),
    ("Siniestros abiertos de alto riesgo para el SIU",
     f"SELECT num_siniestro, cobertura, region, monto_reclamado, prob_fraude, razon_1, razon_2, razon_3 "
     f"FROM {SCORING} WHERE nivel_riesgo = 'Alto' ORDER BY prob_fraude DESC, monto_reclamado DESC LIMIT 20",
     "Bandeja priorizada de casos a investigar (tabla de scoring, no metric view)."),
    ("Suficiencia de reservas por cobertura",
     f"SELECT `Cobertura`, MEASURE(`Reserva de Caso`) AS reserva_caso, MEASURE(`Reserva Requerida`) AS reserva_requerida, "
     f"MEASURE(`Suficiencia de Reserva`) AS suficiencia, MEASURE(`% Desarrollado`) AS pct_desarrollado "
     f"FROM {S}.mv_reservas_actuariales GROUP BY 1 ORDER BY reserva_caso DESC",
     "Reserva constituida vs requerida (chain-ladder) por cobertura."),
    ("Siniestralidad reportada vs última por periodo",
     f"SELECT periodo_etiqueta, prima_devengada, siniestralidad_reportada, siniestralidad_ultima, reserva_requerida "
     f"FROM {S}.act_siniestralidad_periodo ORDER BY periodo_ocurrencia",
     "Cuánto costará al final cada periodo de ocurrencia vs lo que se ve hoy."),
    ("Siniestros abiertos con presupuestos inconsistentes",
     f"SELECT num_siniestro, region, nivel_riesgo_modelo, nombre_taller, total_documento, total_capturado, dif_total_pct, "
     f"array_join(motivos, ' · ') AS motivos FROM {S}.docs_validacion_presupuestos "
     f"WHERE num_inconsistencias > 0 AND nivel_riesgo_modelo <> 'Cerrado' ORDER BY num_inconsistencias DESC, prob_fraude DESC",
     "Documentos de taller cuya información no coincide con los sistemas (IA sobre PDFs)."),
    ("Modelo vs veredicto del SIU",
     f"SELECT nivel_riesgo_apertura, count(*) AS casos_cerrados, sum(fraude) AS fraudes_confirmados, avg(fraude) AS tasa_confirmacion, "
     f"avg(prob_fraude_apertura) AS prob_media_modelo, sum(CASE WHEN fraude = 1 THEN monto_en_riesgo END) AS monto_evitado "
     f"FROM {EXP}.etiquetas_siu GROUP BY 1 ORDER BY tasa_confirmacion DESC",
     "Qué tanto confirma el SIU lo que el modelo marcó (etiquetas humanas desde Lakebase)."),
    ("Carga de trabajo del SIU",
     f"SELECT region, estatus, count(*) AS casos, sum(monto_en_riesgo) AS monto_en_riesgo FROM {EXP}.casos GROUP BY 1, 2 ORDER BY 1, 2",
     "Casos SIU por región y estatus (operados en la app, replicados por CDF)."),
]
for title, sql, desc in EJEMPLOS:
    space.add_example_sql(title=title, sql=sql, description=desc)

PREGUNTAS = [
    "¿Cuál es la siniestralidad por paquete y cuál es el más rentable?",
    "¿Cómo ha evolucionado la prima emitida y la siniestralidad por año?",
    "¿En qué coberturas y tipos de taller se concentra el fraude?",
    "¿Qué canal convierte mejor las cotizaciones y cuánta prima genera?",
    "¿Qué siniestros abiertos de riesgo alto debe revisar el SIU primero y por qué?",
    "¿Nuestras reservas de siniestros son suficientes? ¿En qué cobertura sobra o falta?",
    "¿Qué siniestros abiertos tienen presupuestos de taller inconsistentes y por qué?",
    "¿Qué tanto confirma el SIU los siniestros que el modelo marca como riesgo alto?",
]
space._space.setdefault("config", {})["sample_questions"] = [{"id": uuid.uuid4().hex, "question": [q]} for q in PREGUNTAS]
space.validate()

d = space.to_dict()
# La API exige listas con id ordenadas por id
for path in [("instructions", "text_instructions"), ("instructions", "example_question_sqls"), ("instructions", "sql_functions"),
             ("instructions", "join_specs"), ("benchmarks", "questions"), ("config", "sample_questions")]:
    cur = d
    for k in path[:-1]:
        cur = cur.get(k, {}) if isinstance(cur, dict) else {}
    if isinstance(cur, dict) and isinstance(cur.get(path[-1]), list):
        cur[path[-1]].sort(key=lambda x: x.get("id", "") if isinstance(x, dict) else "")
ds = d.get("data_sources", {})
for k in ("tables", "metric_views"):
    if isinstance(ds.get(k), list):
        ds[k].sort(key=lambda x: x.get("identifier", ""))

payload = {"title": space.title, "description": space.description, "parent_path": PARENT, "warehouse_id": WID,
           "serialized_space": json.dumps(d)}
open("/tmp/create_genie_seguros.json", "w").write(json.dumps(payload))
try:
    sid_prev = open("genie_space_id.txt").read().strip()
except FileNotFoundError:
    sid_prev = ""
method, path = ("patch", f"/api/2.0/genie/spaces/{sid_prev}") if sid_prev else ("post", "/api/2.0/genie/spaces")
r = subprocess.run(["databricks", "api", method, path, "--profile", PROFILE, "--json",
                    "@/tmp/create_genie_seguros.json"], capture_output=True, text=True)
try:
    out = json.loads(r.stdout)
    sid = out.get("space_id") or out.get("id") or sid_prev
    print("space_id:", sid)
    open("genie_space_id.txt", "w").write(sid or "")
except Exception:
    print("ERR:", r.stdout[:1500], r.stderr[:600])
