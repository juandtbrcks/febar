"""Migra metric_views.sql (YAML v0.1) a v1.1 agregando formato y sinónimos a cada dimensión/medida.
Los nombres no cambian (el dashboard y Genie los referencian). Run: python3 migrar_v1_1.py"""
import re

MXN = "currency_code: MXN"  # marcador
F = {  # formatos reutilizables (YAML, indentado bajo el campo)
    "entero": "type: number\n  decimal_places:\n    type: exact\n    places: 0",
    "anio": "type: number\n  decimal_places:\n    type: exact\n    places: 0\n  hide_group_separator: true",
    "dec1": "type: number\n  decimal_places:\n    type: exact\n    places: 1",
    "mxn": "type: currency\n  currency_code: MXN\n  decimal_places:\n    type: exact\n    places: 0\n  abbreviation: compact",
    "mxn_det": "type: currency\n  currency_code: MXN\n  decimal_places:\n    type: exact\n    places: 0",
    "pct": "type: percentage\n  decimal_places:\n    type: exact\n    places: 1",
}

# nombre -> (formato o None, [sinónimos]) ; la misma etiqueta en vistas distintas comparte metadatos
META = {
    # ---- dimensiones de tiempo
    "Año Suscripción": ("anio", ["año de emisión", "año póliza", "underwriting year"]),
    "Año Ocurrencia": ("anio", ["año del siniestro", "accident year"]),
    "Año": ("anio", ["año de cotización", "year"]),
    "Año Cierre Periodo": ("anio", ["año de origen", "accident year", "periodo actuarial"]),
    "Trimestre Emisión": (None, ["trimestre", "quarter"]),
    "Trimestre Ocurrencia": (None, ["trimestre", "quarter"]),
    "Trimestre": (None, ["quarter"]),
    "Mes Emisión": (None, ["mes", "month"]),
    "Mes Ocurrencia": (None, ["mes", "month"]),
    "Mes": (None, ["month"]),
    "Año-Mes Emisión": (None, ["periodo", "mes de emisión"]),
    "Año-Mes Ocurrencia": (None, ["periodo", "mes del siniestro"]),
    "Año-Mes": (None, ["periodo", "mes de cotización"]),
    "Periodo de Ocurrencia": (None, ["periodo", "año de ocurrencia", "accident period", "origen"]),
    "Edad (meses)": ("entero", ["desarrollo", "development age", "antigüedad del periodo"]),
    # ---- producto / canal / geografía
    "Paquete": (None, ["producto", "plan", "cobertura contratada", "Amplia", "Limitada", "RC"]),
    "Canal de Venta": (None, ["canal", "canal comercial", "sales channel"]),
    "Canal": (None, ["canal de venta", "canal comercial", "sales channel"]),
    "Sistema Origen": (None, ["sistema", "fuente", "plataforma de cotización"]),
    "Región": (None, ["zona", "region"]),
    "Estado": (None, ["entidad federativa", "estado de la república"]),
    "Estado Ocurrencia": (None, ["estado del siniestro", "lugar del siniestro", "entidad"]),
    # ---- cliente
    "Segmento Cliente": (None, ["segmento", "tipo de cliente"]),
    "Rango Edad Cliente": (None, ["edad del cliente", "grupo de edad"]),
    "Cliente con Crédito del Grupo": (None, ["tiene crédito", "acreditado", "venta cruzada", "cross-sell", "cliente del banco"]),
    "Estatus Crédito": (None, ["situación del crédito", "morosidad", "crédito vencido", "credit status"]),
    # ---- vehículo / póliza
    "Uso Vehículo": (None, ["uso", "tipo de uso", "particular", "comercial"]),
    "Marca": (None, ["armadora", "fabricante", "brand"]),
    "Segmento Marca": (None, ["gama", "segmento del vehículo"]),
    "Antigüedad Vehículo": (None, ["edad del auto", "modelo", "antigüedad del coche"]),
    "App Conectada": (None, ["telemetría", "app FSI", "conectado"]),
    "Conductor Joven (<25)": (None, ["conductor joven", "menor de 25", "young driver"]),
    "Forma de Pago": (None, ["frecuencia de pago", "mensual", "anual"]),
    "Estatus Póliza": (None, ["estatus", "vigente", "cancelada"]),
    "Renovación": (None, ["nueva o renovación", "renewal", "tipo de venta"]),
    "Rango Edad Conductor": (None, ["edad del conductor", "grupo de edad"]),
    # ---- siniestro
    "Cobertura": (None, ["ramo", "tipo de cobertura", "coverage"]),
    "Causa": (None, ["tipo de siniestro", "motivo", "choque", "robo"]),
    "Canal de Reporte": (None, ["medio de reporte", "cómo se reportó", "FNOL"]),
    "Estatus Siniestro": (None, ["estatus", "abierto", "cerrado", "en investigación"]),
    "Tipo de Taller": (None, ["agencia o independiente", "tipo de proveedor"]),
    "Taller": (None, ["proveedor", "nombre del taller", "body shop"]),
    "Dictamen Fraude": (None, ["fraude", "resultado SIU", "dictamen"]),
    "Nivel Riesgo Fraude": (None, ["riesgo", "score de fraude", "prioridad SIU", "semáforo"]),
    # ---- medidas: cartera
    "Pólizas": ("entero", ["número de pólizas", "policies", "contratos"]),
    "Pólizas Vigentes": ("entero", ["cartera vigente", "pólizas activas", "in force"]),
    "Clientes Únicos": ("entero", ["asegurados", "número de clientes", "customers"]),
    "Prima Emitida": ("mxn", ["prima", "ventas", "primas emitidas", "written premium", "GWP"]),
    "Prima Devengada": ("mxn", ["prima ganada", "earned premium"]),
    "Prima Cobrada": ("mxn", ["cobranza", "prima recaudada", "collected premium"]),
    "Prima Promedio": ("mxn_det", ["ticket promedio", "prima media", "average premium"]),
    "Suma Asegurada": ("mxn", ["valor asegurado", "sum insured"]),
    "Exposición (años-vehículo)": ("entero", ["exposición", "años vehículo", "earned exposure"]),
    "Siniestros": ("entero", ["número de siniestros", "reclamaciones", "claims"]),
    "Costo Incurrido": ("mxn", ["incurrido", "costo de siniestros", "incurred losses"]),
    "Siniestralidad %": ("pct", ["siniestralidad", "loss ratio", "índice de siniestralidad", "rentabilidad técnica"]),
    "Frecuencia": ("pct", ["frecuencia de siniestros", "claim frequency"]),
    "Severidad": ("mxn_det", ["costo promedio por siniestro", "severity"]),
    "Tasa de Cancelación": ("pct", ["cancelación", "churn", "pólizas canceladas"]),
    "Recibos Vencidos": ("entero", ["recibos pendientes", "morosidad de primas", "adeudos"]),
    # ---- medidas: siniestros / fraude
    "Siniestros Abiertos": ("entero", ["pendientes", "en trámite", "open claims"]),
    "Monto Reclamado": ("mxn", ["reclamado", "monto del reclamo", "claimed amount"]),
    "Pagado": ("mxn", ["pagos", "monto pagado", "paid losses"]),
    "Reserva Pendiente": ("mxn", ["reserva", "reserva de caso", "case reserve", "OSLR"]),
    "Recuperaciones": ("mxn", ["salvamentos", "recobros", "recoveries"]),
    "Severidad Promedio": ("mxn_det", ["severidad", "costo promedio por siniestro", "severity"]),
    "Horas Promedio a Reporte": ("dec1", ["tiempo de reporte", "demora en reportar", "reporting lag"]),
    "% Reportados por App": ("pct", ["adopción app", "reportes digitales", "FNOL digital"]),
    "Fraudes Confirmados": ("entero", ["casos de fraude", "fraudes", "confirmed fraud"]),
    "Tasa de Fraude": ("pct", ["% fraude", "fraude", "fraud rate"]),
    "Monto Fraude Detectado": ("mxn", ["fraude evitado", "ahorro por fraude", "monto de fraude"]),
    "Siniestros Alto Riesgo": ("entero", ["casos alto riesgo", "bandeja SIU", "sospechosos"]),
    "Monto en Riesgo de Fraude": ("mxn", ["exposición a fraude", "monto en riesgo", "dinero en riesgo"]),
    "Probabilidad Fraude Promedio": ("pct", ["score promedio", "probabilidad de fraude", "fraud score"]),
    "Presupuesto Taller vs Autorizado": ("pct", ["inflado de presupuestos", "sobrecosto de taller", "presupuesto vs autorizado"]),
    # ---- medidas: comercial
    "Cotizaciones": ("entero", ["quotes", "número de cotizaciones", "solicitudes"]),
    "Cotizaciones Convertidas": ("entero", ["ventas", "pólizas vendidas", "conversiones"]),
    "Tasa de Conversión": ("pct", ["conversión", "conversion rate", "efectividad", "cierre"]),
    "Prima Cotizada Promedio": ("mxn_det", ["precio cotizado", "cotización promedio"]),
    "Prima Emitida (convertidas)": ("mxn", ["prima vendida", "prima de cotizaciones convertidas"]),
    "Brecha de Precio No Convertidas": ("pct", ["diferencia de precio", "precio vs competencia", "price gap"]),
    # ---- medidas: reservas actuariales
    "Siniestros Reportados": ("entero", ["siniestros", "número de siniestros", "reported claims"]),
    "Reserva de Caso": ("mxn", ["reserva constituida", "case reserve", "reserva pendiente"]),
    "Incurrido Reportado": ("mxn", ["incurrido", "reported incurred"]),
    "Último Estimado": ("mxn", ["ultimate", "costo final estimado", "proyección"]),
    "Reserva Requerida": ("mxn", ["reserva necesaria", "required reserve"]),
    "IBNR": ("mxn", ["ocurridos no reportados", "SONR", "incurred but not reported"]),
    "Suficiencia de Reserva": ("mxn", ["excedente de reserva", "capital inmovilizado", "redundancia", "reserve adequacy"]),
    "Suficiencia %": ("pct", ["% suficiencia", "suficiencia de reservas", "adequacy ratio"]),
    "% Desarrollado": ("pct", ["madurez", "% pagado del último", "development %"]),
}

src = open("metric_views_v0_1_backup.sql").read().replace("version: 0.1", "version: 1.1")
out, usados = [], set()
lines = src.split("\n")
i = 0
while i < len(lines):
    ln = lines[i]
    out.append(ln)
    m = re.match(r"^  - name: (.+)$", ln)
    if m and i + 1 < len(lines) and lines[i + 1].startswith("    expr:"):
        nombre = m.group(1).strip().strip("'")
        out.append(lines[i + 1]); i += 1
        if nombre not in META:
            raise SystemExit(f"Sin metadatos: {nombre}")
        fmt, syn = META[nombre]
        usados.add(nombre)
        out.append("    synonyms: [" + ", ".join("'" + s.replace("'", "''") + "'" for s in syn) + "]")
        if fmt:
            out.append("    format:")
            out += ["      " + l[2:] if j else "      " + l for j, l in enumerate(F[fmt].split("\n"))]
    i += 1

cab = "-- Versión YAML 1.1: cada dimensión/medida lleva formato (MXN, %, enteros) y sinónimos (español/inglés) que usan el dashboard y Genie.\n"
res = "\n".join(out).replace("-- Joins prefijados", cab + "-- Joins prefijados", 1)
open("metric_views.sql", "w").write(res)
print("campos con metadatos:", len(usados), "| sin usar en META:", sorted(set(META) - usados))
