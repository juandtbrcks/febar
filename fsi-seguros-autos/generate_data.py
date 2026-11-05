"""
Aseguradora FSI · Autos — generador sintético (stdlib puro, seed=42).

Genera CSVs para las fuentes legacy (seguros_dwh / seguros_creditos) y JSON lines
de telemetría de la app de autos (data lake de ciencia de datos).

Salida: ./data/csv/*.csv  y  ./data/telemetria/{trip_summary,fnol}/*.json
Run:    python3 generate_data.py
"""
import csv, json, math, os, random
from datetime import date, datetime, timedelta

R = random.Random(42)
BASE = os.path.dirname(os.path.abspath(__file__))
OUT_CSV = os.path.join(BASE, "data", "csv")
OUT_TEL = os.path.join(BASE, "data", "telemetria")
CUTOFF = date(2026, 10, 13)
START = date(2021, 1, 1)
LAST_EMISION = date(2026, 9, 30)

N_CLIENTES, N_POLIZAS, N_AGENTES = 60_000, 100_000, 600
N_AJUSTADORES, N_TALLERES, N_CREDITOS = 250, 400, 25_000


# ----------------------------------------------------------------- helpers
def add_months(d, m):
    y, mo = divmod(d.month - 1 + m, 12)
    y += d.year
    mo += 1
    dim = [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1]
    return date(y, mo, min(d.day, dim))


def rand_date(a, b):
    return a + timedelta(days=R.randint(0, (b - a).days))


def wpick(items, weights):
    return R.choices(items, weights=weights, k=1)[0]


def lognorm(median, sigma):
    return median * math.exp(R.gauss(0, sigma))


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def write_csv(name, header, rows):
    os.makedirs(OUT_CSV, exist_ok=True)
    with open(os.path.join(OUT_CSV, f"{name}.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(["" if v is None else ("t" if v is True else "f" if v is False else v) for v in r])
    print(f"  {name}: {len(rows):,}")


# ----------------------------------------------------------------- catálogos
NOMBRES_H = ["José", "Juan", "Luis", "Carlos", "Jorge", "Miguel", "Alejandro", "Francisco", "Ricardo", "Fernando",
             "Eduardo", "Roberto", "Javier", "Daniel", "Sergio", "Arturo", "Raúl", "Héctor", "Manuel", "Óscar",
             "Diego", "Andrés", "Pablo", "Emilio", "Rodrigo", "Gerardo", "Alberto", "Enrique", "Mario", "Hugo"]
NOMBRES_M = ["María", "Guadalupe", "Ana", "Laura", "Patricia", "Gabriela", "Verónica", "Claudia", "Adriana", "Mónica",
             "Alejandra", "Sofía", "Fernanda", "Daniela", "Mariana", "Valeria", "Leticia", "Rosa", "Elena", "Lucía",
             "Paola", "Andrea", "Carmen", "Silvia", "Teresa", "Beatriz", "Diana", "Karla", "Ximena", "Regina"]
APELLIDOS = ["Hernández", "García", "Martínez", "López", "González", "Pérez", "Rodríguez", "Sánchez", "Ramírez",
             "Cruz", "Flores", "Gómez", "Morales", "Vázquez", "Reyes", "Jiménez", "Torres", "Díaz", "Gutiérrez",
             "Ruiz", "Mendoza", "Aguilar", "Ortiz", "Moreno", "Castillo", "Romero", "Álvarez", "Méndez", "Chávez",
             "Rivera", "Juárez", "Ramos", "Domínguez", "Herrera", "Medina", "Castro", "Vargas", "Guzmán", "Velázquez",
             "Salazar", "Rojas", "Contreras", "Luna", "Ortega", "Delgado", "Soto", "Espinoza", "Navarro", "Cervantes"]

# estado: (peso, region, cve CURP, cve num, lat, lon, municipios)
ESTADOS = {
    "Ciudad de México": (18, "Centro", "DF", "09", 19.43, -99.13, ["Benito Juárez", "Coyoacán", "Miguel Hidalgo", "Tlalpan", "Iztapalapa", "Álvaro Obregón", "Cuauhtémoc", "Gustavo A. Madero"]),
    "Estado de México": (14, "Centro", "MC", "15", 19.35, -99.63, ["Naucalpan", "Tlalnepantla", "Ecatepec", "Toluca", "Huixquilucan", "Atizapán", "Nezahualcóyotl"]),
    "Jalisco": (8, "Occidente", "JC", "14", 20.67, -103.35, ["Guadalajara", "Zapopan", "Tlaquepaque", "Tonalá", "Puerto Vallarta"]),
    "Nuevo León": (8, "Norte", "NL", "19", 25.69, -100.32, ["Monterrey", "San Pedro Garza García", "San Nicolás", "Guadalupe", "Apodaca"]),
    "Puebla": (5, "Centro", "PL", "21", 19.04, -98.21, ["Puebla", "San Andrés Cholula", "Tehuacán"]),
    "Guanajuato": (5, "Bajío", "GT", "11", 21.12, -101.68, ["León", "Irapuato", "Celaya", "Guanajuato"]),
    "Querétaro": (4, "Bajío", "QT", "22", 20.59, -100.39, ["Querétaro", "El Marqués", "Corregidora"]),
    "Veracruz": (5, "Sureste", "VZ", "30", 19.18, -96.14, ["Veracruz", "Xalapa", "Boca del Río", "Coatzacoalcos"]),
    "Yucatán": (3, "Sureste", "YN", "31", 20.97, -89.62, ["Mérida", "Progreso", "Valladolid"]),
    "Quintana Roo": (3, "Sureste", "QR", "23", 21.16, -86.85, ["Cancún", "Playa del Carmen", "Chetumal"]),
    "Chihuahua": (4, "Norte", "CH", "08", 28.63, -106.07, ["Chihuahua", "Ciudad Juárez", "Delicias"]),
    "Baja California": (4, "Noroeste", "BC", "02", 32.51, -117.04, ["Tijuana", "Mexicali", "Ensenada"]),
    "Sonora": (3, "Noroeste", "SR", "26", 29.07, -110.96, ["Hermosillo", "Cajeme", "Nogales"]),
    "Coahuila": (3, "Norte", "CL", "05", 25.42, -101.00, ["Saltillo", "Torreón", "Monclova"]),
    "Tamaulipas": (3, "Norte", "TS", "28", 22.25, -97.86, ["Tampico", "Reynosa", "Matamoros", "Ciudad Victoria"]),
    "Michoacán": (3, "Occidente", "MN", "16", 19.70, -101.19, ["Morelia", "Uruapan", "Zamora"]),
    "Sinaloa": (3, "Noroeste", "SL", "25", 24.80, -107.39, ["Culiacán", "Mazatlán", "Los Mochis"]),
    "San Luis Potosí": (2, "Bajío", "SP", "24", 22.15, -100.98, ["San Luis Potosí", "Soledad"]),
    "Aguascalientes": (2, "Bajío", "AS", "01", 21.88, -102.29, ["Aguascalientes", "Jesús María"]),
    "Morelos": (2, "Centro", "MS", "17", 18.92, -99.23, ["Cuernavaca", "Jiutepec", "Cuautla"]),
}
EST_NAMES = list(ESTADOS)
EST_W = [ESTADOS[e][0] for e in EST_NAMES]

PRODUCTOS = [  # id, cve, nombre, ramo, subramo, peso, tasa_sobre_valor
    (1, "AUT-AMP", "Autos Amplia", "Autos", "Individual", 45, 0.045),
    (2, "AUT-LIM", "Autos Limitada", "Autos", "Individual", 22, 0.022),
    (3, "AUT-RC", "Autos Responsabilidad Civil", "Autos", "Individual", 12, 0.0045),
    (4, "AUT-PLT", "Autos Plataformas Digitales", "Autos", "Plataforma", 11, 0.075),
    (5, "AUT-FLT", "Autos Flotilla PyME", "Autos", "Flotilla", 6, 0.050),
    (6, "AUT-PLS", "Autos Amplia Plus", "Autos", "Premium", 4, 0.058),
]
PROD_BY_ID = {p[0]: p for p in PRODUCTOS}

MARCAS = {  # marca: (peso, [submarcas], valor base)
    "Nissan": (18, ["Versa", "Sentra", "March", "Kicks", "NP300"], 330_000),
    "Chevrolet": (12, ["Aveo", "Onix", "Tracker", "Captiva", "Silverado"], 360_000),
    "Volkswagen": (11, ["Jetta", "Vento", "Virtus", "Tiguan", "Taos"], 420_000),
    "Toyota": (10, ["Corolla", "Yaris", "RAV4", "Hilux", "Camry"], 480_000),
    "Kia": (8, ["Rio", "Forte", "Seltos", "Sportage"], 380_000),
    "Mazda": (7, ["Mazda 2", "Mazda 3", "CX-3", "CX-5"], 430_000),
    "Honda": (7, ["City", "Civic", "HR-V", "CR-V"], 470_000),
    "Hyundai": (5, ["Grand i10", "Accent", "Creta", "Tucson"], 350_000),
    "Ford": (5, ["Figo", "Territory", "Escape", "Lobo"], 460_000),
    "MG": (4, ["MG5", "ZS", "HS"], 340_000),
    "BMW": (2, ["Serie 3", "X1", "X3"], 950_000),
    "Mercedes-Benz": (2, ["Clase A", "Clase C", "GLA"], 980_000),
}
MARCA_N = list(MARCAS)
MARCA_W = [MARCAS[m][0] for m in MARCA_N]


# ----------------------------------------------------------------- RFC / CURP
VOC = "AEIOU"
CONS = "BCDFGHJKLMNPQRSTVWXYZ"
ALNUM = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789"


def strip_acc(s):
    return s.translate(str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun")).upper()


def first_vowel(s):
    for ch in s[1:]:
        if ch in VOC:
            return ch
    return "X"


def first_cons(s):
    for ch in s[1:]:
        if ch in CONS:
            return ch
    return "X"


def mk_rfc_curp(nom, ap, am, fn, gen, cve_edo):
    n, p, m = strip_acc(nom), strip_acc(ap), strip_acc(am)
    base = p[0] + first_vowel(p) + m[0] + n[0]
    ymd = fn.strftime("%y%m%d")
    rfc = base + ymd + "".join(R.choice(ALNUM) for _ in range(3))
    curp = (base + ymd + ("H" if gen == "M" else "M") + cve_edo + first_cons(p) + first_cons(m) + first_cons(n)
            + R.choice("0123456789A") + R.choice("0123456789"))
    return rfc, curp


# ================================================================= 1. productos
print("Generando…")
productos = [(p[0], p[1], p[2], p[3], p[4]) for p in PRODUCTOS]

# ================================================================= 2. agentes
CANALES = ["Agente", "Banca Seguros", "Tienda Aliada", "Digital", "Broker"]
agentes, agent_ring = [], set()
ring_ids = set(R.sample(range(1, N_AGENTES + 1), 15))  # agentes coludidos
for i in range(1, N_AGENTES + 1):
    est = wpick(EST_NAMES, EST_W)
    canal = wpick(CANALES, [60, 18, 8, 6, 8])
    gen = R.random() < 0.5
    nom = f"{R.choice(NOMBRES_H if gen else NOMBRES_M)} {R.choice(APELLIDOS)} {R.choice(APELLIDOS)}"
    if canal in ("Banca Seguros", "Tienda Aliada", "Digital"):
        nom = {"Banca Seguros": "Sucursal del Banco del Grupo", "Tienda Aliada": "Módulo Tienda Aliada",
               "Digital": "Canal Digital FSI"}[canal] + f" {i:04d}"
    agentes.append((i, f"AG{i:05d}", nom, canal, f"Oficina {ESTADOS[est][6][0]}", ESTADOS[est][1],
                    rand_date(date(2005, 1, 1), date(2024, 12, 31)), R.random() > 0.07))
    if i in ring_ids and canal == "Agente":
        agent_ring.add(i)
agent_region = {a[0]: a[5] for a in agentes}
agents_by_region = {}
for a in agentes:
    agents_by_region.setdefault(a[5], []).append(a[0])

# ================================================================= 3. clientes
clientes = []
cli_info = {}
for i in range(1, N_CLIENTES + 1):
    gen = "M" if R.random() < 0.52 else "F"
    nom = R.choice(NOMBRES_H if gen == "M" else NOMBRES_M)
    ap, am = R.choice(APELLIDOS), R.choice(APELLIDOS)
    fn = rand_date(date(1950, 1, 1), date(2004, 12, 31))
    est = wpick(EST_NAMES, EST_W)
    e = ESTADOS[est]
    rfc, curp = mk_rfc_curp(nom, ap, am, fn, gen, e[2])
    seg = wpick(["Masivo", "Preferente", "Patrimonial", "PyME"], [62, 24, 6, 8])
    email = f"{strip_acc(nom).lower()}.{strip_acc(ap).lower()}{R.randint(1, 999)}@{R.choice(['gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com.mx', 'prodigy.net.mx'])}"
    tel = f"{R.choice(['55', '33', '81', '222', '442', '477', '999', '998', '664'])}{R.randint(10_000_000, 99_999_999)}"[:10]
    cp = f"{R.randint(1000, 99999):05d}"
    alta = rand_date(date(2008, 1, 1), date(2026, 6, 30))
    clientes.append((i, nom, ap, am, rfc, curp, fn, gen, email, tel, est, R.choice(e[6]), cp, alta, seg))
    cli_info[i] = dict(nom=nom, ap=ap, am=am, rfc=rfc, curp=curp, fn=fn, est=est, seg=seg, email=email,
                       tel=tel, cp=cp, alta=alta, region=e[1])

# ================================================================= 4. pólizas + vehículos + recibos
COBERTURAS = {  # id: (cve, nombre, tipo, peso_prima, suma_asegurada, deducible_pct)
    1: ("DM", "Daños Materiales", "Básica", 38, None, 5.0),
    2: ("RT", "Robo Total", "Básica", 24, None, 10.0),
    3: ("RCB", "Responsabilidad Civil Bienes", "Básica", 12, 3_000_000, 0.0),
    4: ("RCP", "Responsabilidad Civil Personas", "Básica", 9, 3_000_000, 0.0),
    5: ("GMO", "Gastos Médicos Ocupantes", "Básica", 6, 200_000, 0.0),
    6: ("AV", "Asistencia Vial", "Servicio", 2, None, 0.0),
    7: ("CR", "Cristales", "Adicional", 3, None, 20.0),
    8: ("DL", "Defensa Legal", "Servicio", 2, None, 0.0),
    9: ("ERC", "Extensión de RC", "Adicional", 2, 1_000_000, 0.0),
    10: ("AS", "Auto Sustituto", "Adicional", 1, None, 0.0),
    11: ("RCU", "RC en EUA y Canadá", "Adicional", 1, 1_500_000, 0.0),
}
PAQUETES = {1: [1, 2, 3, 4, 5, 6, 7, 8], 2: [2, 3, 4, 5, 6, 8], 3: [3, 4, 6, 8],
            4: [1, 2, 3, 4, 5, 6, 7, 8, 9], 5: [1, 2, 3, 4, 5, 6, 8], 6: list(range(1, 12))}
polizas, vehiculos, recibos, conductores, poliza_coberturas = [], [], [], [], []
id_cond = 1
pol_info = {}
prod_ids = [p[0] for p in PRODUCTOS]
prod_w = [p[5] for p in PRODUCTOS]
FP = {"Anual": 1, "Semestral": 2, "Trimestral": 4, "Mensual": 12}
RECARGO = {"Anual": 0.0, "Semestral": 0.03, "Trimestral": 0.05, "Mensual": 0.08}
id_rec = 1
for pid in range(1, N_POLIZAS + 1):
    id_pol = 10_000_000 + pid
    cid = R.randint(1, N_CLIENTES)
    ci = cli_info[cid]
    prod = PROD_BY_ID[wpick(prod_ids, prod_w)]
    ramo = prod[3]
    # agente: 80% de la región del cliente
    if R.random() < 0.8 and agents_by_region.get(ci["region"]):
        ag = R.choice(agents_by_region[ci["region"]])
    else:
        ag = R.randint(1, N_AGENTES)
    emision = rand_date(START, LAST_EMISION)
    ini = emision + timedelta(days=R.randint(0, 10))
    fin = add_months(ini, 12)
    # conductor habitual (titular 85%; plataforma/flotilla con más conductores)
    edad_tit = (CUTOFF - ci["fn"]).days // 365
    n_cond = R.randint(1, 3) if prod[0] == 5 else (R.randint(1, 2) if prod[0] == 4 else 1)
    conds = []
    for j in range(n_cond):
        titular = j == 0 and R.random() < 0.85
        edad = edad_tit if titular else R.randint(19, 65)
        conds.append((titular, edad))
    edad_cond = min(c[1] for c in conds)
    f_edad = 1.35 if edad_cond < 25 else 1.12 if edad_cond < 30 else 1.06 if edad_cond > 70 else 1.0
    marca = wpick(MARCA_N, MARCA_W)
    mb = MARCAS[marca]
    anio = R.randint(2012, 2026)
    valor = round(mb[2] * (0.92 ** (2026 - anio)) * R.uniform(0.85, 1.25), -2)
    uso = "Plataforma" if prod[0] == 4 else ("Carga ligera" if prod[0] == 5 and R.random() < 0.6 else "Particular")
    suma = valor
    prima = round(max(2_800, valor * prod[6] * 1.65 * f_edad * R.uniform(0.8, 1.3) * (1.15 if ci["region"] == "Centro" else 1.0)), 2)
    app = R.random() < (0.55 if uso == "Plataforma" else 0.32)
    vin = "".join(R.choice("ABCDEFGHJKLMNPRSTUVWXYZ0123456789") for _ in range(17))
    placas = f"{''.join(R.choice('ABCDEFGHJKLMNPRSTUVWXYZ') for _ in range(3))}{R.randint(100, 999)}{R.choice('ABCDEFGHJKLMNPRSTUVWXYZ')}"
    veh = dict(marca=marca, sub=R.choice(mb[1]), valor=valor, uso=uso, anio=anio, app=app)
    vehiculos.append((5_000_000 + pid, id_pol, marca, veh["sub"], anio, uso, valor, vin, placas, app))
    for j, (titular, edad) in enumerate(conds):
        conductores.append((id_cond, id_pol, cid if titular else None, titular, edad,
                            "M" if R.random() < 0.6 else "F", max(0, min(edad - 18, int(R.uniform(0.3, 1.0) * (edad - 17)))),
                            "Chofer" if uso in ("Plataforma", "Carga ligera") else "Automovilista",
                            ci["cp"] if titular else f"{R.randint(1000, 99999):05d}"))
        id_cond += 1
    # coberturas del paquete (prima repartida por peso)
    paquete = PAQUETES[prod[0]]
    wsum = sum(COBERTURAS[c][3] for c in paquete)
    for c in paquete:
        cv = COBERTURAS[c]
        sa = (valor if c in (1, 2) else round(valor * 0.05, -2) if c == 7 else cv[4])
        poliza_coberturas.append((id_pol, c, sa, cv[5], round(prima * cv[3] / wsum, 2)))
    fpago = wpick(list(FP), [45, 15, 10, 30] if prod[0] != 5 else [70, 15, 10, 5])
    # cancelación (más en mensual = falta de pago)
    p_canc = 0.06 + (0.06 if fpago == "Mensual" else 0)
    canc = None
    if R.random() < p_canc:
        c = ini + timedelta(days=R.randint(30, 330))
        if c <= CUTOFF:
            canc = c
    est_pol = "Cancelada" if canc else ("Vigente" if fin > CUTOFF and ini <= CUTOFF else "Vencida")
    polizas.append((id_pol, f"{prod[1][:3]}-{ini.year}-{pid:07d}", cid, prod[0], ag, emision, ini, fin,
                    suma, prima, fpago, est_pol, canc, R.random() < 0.55))
    pol_info[id_pol] = dict(cid=cid, prod=prod, ramo=ramo, ag=ag, ini=ini, fin=fin, canc=canc, suma=suma,
                            prima=prima, veh=veh, est=ci["est"], emision=emision,
                            freq_mult=1.45 if edad_cond < 25 else 1.15 if edad_cond < 30 else 1.0)
    n = FP[fpago]
    imp = round(prima * (1 + RECARGO[fpago]) / n, 2)
    for k in range(n):
        venc = add_months(ini, k * 12 // n)
        if canc and venc > canc:
            st, fp_ = "Cancelado", None
        elif venc > CUTOFF:
            st, fp_ = "Pendiente", None
        elif R.random() < 0.95:
            st, fp_ = "Pagado", min(CUTOFF, venc + timedelta(days=int(abs(R.gauss(3, 8)))))
        else:
            st, fp_ = "Pendiente", None
        recibos.append((id_rec, id_pol, k + 1, venc, fp_, imp, st))
        id_rec += 1

# ================================================================= 5. ajustadores / talleres
ajustadores = []
for i in range(1, N_AJUSTADORES + 1):
    gen = R.random() < 0.7
    ajustadores.append((i, f"{R.choice(NOMBRES_H if gen else NOMBRES_M)} {R.choice(APELLIDOS)} {R.choice(APELLIDOS)}",
                        wpick(sorted({v[1] for v in ESTADOS.values()}), [1] * 6), wpick(["Interno", "Despacho"], [65, 35])))
aj_by_region = {}
for a in ajustadores:
    aj_by_region.setdefault(a[2], []).append(a[0])

talleres = []
TALLER_PREF = ["Taller", "Servicio Automotriz", "Hojalatería y Pintura", "Autocentro", "Carrocerías"]
for i in range(1, N_TALLERES + 1):
    est = wpick(EST_NAMES, EST_W)
    tipo = wpick(["Agencia", "Multimarca", "Independiente"], [35, 40, 25])
    nom = (f"Agencia {R.choice(MARCA_N)} {R.choice(ESTADOS[est][6])}" if tipo == "Agencia"
           else f"{R.choice(TALLER_PREF)} {R.choice(APELLIDOS)} {R.choice(['', 'Hnos.', 'e Hijos', 'Express', 'del Valle'])}".strip())
    talleres.append((i, nom, tipo, est, R.choice(ESTADOS[est][6])))
talleres_by_est = {}
for t in talleres:
    talleres_by_est.setdefault(t[3], []).append(t[0])
# red de talleres sospechosos: independientes en CDMX/Edomex/Jalisco/NL
ring_talleres = [t[0] for t in talleres if t[2] == "Independiente" and t[3] in
                 ("Ciudad de México", "Estado de México", "Jalisco", "Nuevo León")][:18]

# ================================================================= 6. siniestros + movimientos + FNOL
FREQ = {"Autos": 0.32, "GMM": 0.35, "Vida": 0.006, "Hogar": 0.05, "Daños": 0.08}
COB = {
    "Autos": [("Daños Materiales", 55, 32_000, 0.7), ("Responsabilidad Civil", 20, 24_000, 0.8),
              ("Robo Total", 7, None, 0), ("Cristales", 13, 6_500, 0.4), ("Gastos Médicos Ocupantes", 5, 38_000, 0.8)],
    "GMM": [("Hospitalización", 45, 120_000, 1.0), ("Cirugía", 30, 180_000, 0.9), ("Maternidad", 10, 70_000, 0.5),
            ("Padecimiento Crónico", 15, 90_000, 1.1)],
    "Vida": [("Fallecimiento", 85, None, 0), ("Invalidez", 15, None, 0)],
    "Hogar": [("Robo con Violencia", 30, 45_000, 0.8), ("Daños por Agua", 35, 28_000, 0.7),
              ("Incendio", 10, 220_000, 1.0), ("Fenómenos Hidrometeorológicos", 25, 85_000, 0.9)],
    "Daños": [("Incendio", 25, 650_000, 1.2), ("Robo", 25, 180_000, 1.0), ("Responsabilidad Civil", 25, 250_000, 1.0),
              ("Daño a Mercancía", 25, 140_000, 1.0)],
}
COB_IDS = {"Daños Materiales": [1], "Robo Total": [2], "Responsabilidad Civil": [3, 4], "Cristales": [7],
           "Gastos Médicos Ocupantes": [5]}
CAUSAS = {
    "Daños Materiales": ["Colisión con vehículo", "Alcance", "Volcadura", "Colisión con objeto fijo", "Inundación"],
    "Responsabilidad Civil": ["Daño a tercero en colisión", "Atropellamiento", "Daño a propiedad ajena"],
    "Robo Total": ["Robo con violencia", "Robo estacionado"],
    "Cristales": ["Rotura de parabrisas", "Rotura de cristal lateral"],
    "Gastos Médicos Ocupantes": ["Lesiones en colisión"],
}
# desarrollo de pagos por cobertura: (n_pagos min, moda, max, meses máx entre primer y último pago, días máx a 1er pago)
TAIL = {"Daños Materiales": (1, 2, 4, 8, 25), "Cristales": (1, 1, 1, 0, 15), "Robo Total": (1, 1, 2, 10, 90),
        "Responsabilidad Civil": (1, 3, 8, 30, 120), "Gastos Médicos Ocupantes": (1, 3, 8, 24, 60)}

siniestros, movtos, fnol_events, valuaciones, terceros_sin = [], [], [], [], []
RING_TERCEROS = [(f"{R.choice(NOMBRES_H + NOMBRES_M)} {R.choice(APELLIDOS)} {R.choice(APELLIDOS)}",
                  f"55{R.randint(10_000_000, 99_999_999)}") for _ in range(70)]
id_val, id_ter = 1, 1
id_sin, id_mov = 1, 1
cli_claims = {}
for id_pol, p in pol_info.items():
    end = min(p["fin"], p["canc"] or p["fin"], CUTOFF)
    expo = (end - p["ini"]).days / 365.0
    if expo <= 0:
        continue
    # solo coberturas que el paquete ampara; la frecuencia escala con el peso de esas coberturas
    cubre = set(PAQUETES[p["prod"][0]])
    cobs = [c for c in COB["Autos"] if any(i in cubre for i in COB_IDS[c[0]])]
    lam = FREQ[p["ramo"]] * expo * p["freq_mult"] * sum(c[1] for c in cobs) / sum(c[1] for c in COB["Autos"])
    n_claims = 0
    while R.random() < lam / (n_claims + 1) and n_claims < 4:  # ~Poisson truncada
        n_claims += 1
    if p["ramo"] == "Autos" and p["veh"]["uso"] == "Plataforma":
        n_claims += 1 if R.random() < 0.15 else 0
    for _ in range(n_claims):
        ramo = p["ramo"]
        cob = wpick(cobs, [c[1] for c in cobs])
        veh = p["veh"]
        # ---------- fraude latente (solo Autos)
        fraude = False
        if ramo == "Autos":
            lg = (-3.4 + 1.9 * (p["ag"] in agent_ring) + 0.7 * (veh["uso"] == "Plataforma")
                  + 1.1 * (cob[0] == "Robo Total") + 0.5 * (cob[0] == "Daños Materiales")
                  + 0.6 * (cli_claims.get(p["cid"], 0) >= 1) + 0.4 * (veh["anio"] < 2016) + R.gauss(0, 0.4))
            fraude = R.random() < sigmoid(lg)
        # ---------- fecha ocurrencia (fraude: pegada al inicio de vigencia)
        span = (end - p["ini"]).days
        if fraude and R.random() < 0.45:
            d_occ = p["ini"] + timedelta(days=R.randint(0, min(30, span)))
        else:
            d_occ = p["ini"] + timedelta(days=R.randint(0, span))
        hour = (R.choice([22, 23, 0, 1, 2, 3, 4]) if (fraude and R.random() < 0.5)
                else int(R.triangular(6, 23, 15)) if R.random() < 0.85 else R.choice([22, 23, 0, 1, 2, 3, 4]))
        f_occ = datetime(d_occ.year, d_occ.month, d_occ.day, hour % 24, R.randint(0, 59))
        lag_h = (abs(R.gauss(60, 40)) if fraude and R.random() < 0.6 else abs(R.gauss(4, 6)))
        if ramo in ("GMM", "Vida", "Daños"):
            lag_h = abs(R.gauss(24 * 8, 24 * 10))
        if cob[0] in ("Responsabilidad Civil", "Gastos Médicos Ocupantes") and R.random() < 0.12:
            lag_h += 24 * R.randint(30, 240)  # tercero reclama meses después (IBNR)
        f_rep = f_occ + timedelta(hours=lag_h)
        if f_rep.date() > CUTOFF:
            continue
        # ---------- monto
        if cob[0] == "Robo Total":
            monto = veh["valor"] * R.uniform(0.9, 1.0)
        elif cob[0] in ("Fallecimiento", "Invalidez"):
            monto = p["suma"] * (1.0 if cob[0] == "Fallecimiento" else 0.5)
        else:
            monto = lognorm(cob[2], cob[3])
            if ramo == "Autos":
                monto = min(monto, veh["valor"] * 0.8)
                if fraude and cob[0] != "Cristales":
                    monto *= R.uniform(1.3, 2.2)  # inflado
                    monto = min(monto, veh["valor"] * 0.95)
            monto = min(monto, p["suma"])
        monto = round(monto, 2)
        deducible = round(monto * (0.05 if cob[0] == "Daños Materiales" else 0.10 if cob[0] == "Robo Total" else 0)
                          if ramo == "Autos" else (25_000 if ramo == "GMM" else 0), 2)
        # ---------- atributos operativos
        est_occ = p["est"] if R.random() < 0.9 else wpick(EST_NAMES, EST_W)
        aj = R.choice(aj_by_region.get(ESTADOS[est_occ][1], [1]))
        taller = None
        if ramo == "Autos" and cob[0] in ("Daños Materiales", "Cristales", "Responsabilidad Civil"):
            if fraude and R.random() < 0.5 and ring_talleres:
                taller = R.choice(ring_talleres)
            elif R.random() < 0.03:
                taller = R.choice(ring_talleres)
            else:
                taller = R.choice(talleres_by_est.get(est_occ) or [t[0] for t in talleres])
        if ramo == "Autos":
            canal = ("App" if veh["app"] and R.random() < 0.7 else
                     wpick(["Call Center", "Agente", "Sucursal"], [70, 22, 8]))
            autoridad = R.random() < (0.35 if fraude else 0.75) if cob[0] != "Cristales" else False
            terceros = 0 if cob[0] in ("Robo Total", "Cristales") else wpick([0, 1, 2, 3], [40, 45, 12, 3])
            if fraude and cob[0] in ("Daños Materiales", "Responsabilidad Civil"):
                terceros = wpick([0, 1, 2, 3], [20, 35, 30, 15])
        else:
            canal = wpick(["Call Center", "Agente", "Sucursal"], [45, 40, 15])
            autoridad = cob[0] in ("Robo con Violencia", "Robo", "Fallecimiento")
            terceros = 0
        # ---------- desarrollo del siniestro (pagos)
        reserva = round(monto * R.uniform(0.9, 1.25), 2)
        detected = fraude and R.random() < 0.75
        k_min, k_mode, k_max, span_max, pay_max = TAIL[cob[0]]
        n_pay = max(1, int(round(R.triangular(k_min, k_max, k_mode))))
        first_pay = f_rep.date() + timedelta(days=R.randint(5, pay_max))
        settle = monto - deducible if not (ramo == "Autos" and cob[0] == "Robo Total" and R.random() < 0.25) else 0
        settle *= R.uniform(0.75, 1.0)
        rejected = detected or (R.random() < 0.04)
        num = f"S{f_rep.year}{id_sin:08d}"
        movtos.append((id_mov, id_sin, f_rep.date(), "Ajuste Reserva", reserva)); id_mov += 1
        pagado, last_d, all_done = 0.0, None, True
        if rejected:
            d_rej = f_rep.date() + timedelta(days=R.randint(20, 120))
            if d_rej <= CUTOFF:
                movtos.append((id_mov, id_sin, d_rej, "Ajuste Reserva", -reserva)); id_mov += 1
                last_d = d_rej
            else:
                all_done = False
        else:
            span_m = R.randint(span_max // 3, span_max) if span_max else 0
            for j in range(n_pay):
                d_pay = first_pay + timedelta(days=int(30 * span_m * j / max(1, n_pay - 1))) if n_pay > 1 else first_pay
                if d_pay > CUTOFF:
                    all_done = False
                    break
                amt = round(settle / n_pay, 2)
                movtos.append((id_mov, id_sin, d_pay, "Pago", amt)); id_mov += 1
                pagado += amt
                last_d = d_pay
            if all_done and last_d:
                movtos.append((id_mov, id_sin, last_d, "Ajuste Reserva", round(-(reserva - pagado), 2))); id_mov += 1
                if ramo == "Autos" and cob[0] in ("Robo Total", "Responsabilidad Civil") and R.random() < 0.2:
                    rd = last_d + timedelta(days=R.randint(30, 200))
                    if rd <= CUTOFF:
                        movtos.append((id_mov, id_sin, rd, "Recuperación", -round(pagado * R.uniform(0.2, 0.6), 2)))
                        id_mov += 1
        if all_done:
            estatus = "Rechazado" if rejected else "Cerrado"
            f_cierre = last_d
            label = True if detected else False  # fraudes no detectados quedan como False (ruido realista)
        else:
            estatus = "En investigación" if (ramo == "Autos" and (fraude and R.random() < 0.35 or R.random() < 0.03)) else "Abierto"
            f_cierre, label = None, None
        if ramo != "Autos":
            label = False if all_done else None
        causa = R.choice(CAUSAS.get(cob[0], [cob[0]]))
        siniestros.append((id_sin, num, id_pol, aj, taller, f_occ, f_rep, cob[0], causa, est_occ, canal, monto,
                           reserva, deducible, autoridad, terceros, estatus, f_cierre, label))
        cli_claims[p["cid"]] = cli_claims.get(p["cid"], 0) + 1
        # ---------- FNOL de la app (telemetría)
        if canal == "App":
            e = ESTADOS[est_occ]
            dist = (abs(R.gauss(18, 15)) if fraude and R.random() < 0.6 else abs(R.gauss(0.4, 0.6)))
            fnol_events.append(dict(
                event_type="fnol", event_ts=f_rep.isoformat(), device_id=f"DEV-{id_pol}", id_poliza=id_pol,
                num_siniestro=num, gps_lat=round(e[4] + R.gauss(0, 0.08), 5), gps_lon=round(e[5] + R.gauss(0, 0.08), 5),
                distancia_km_ubicacion_declarada=round(dist, 2),
                fotos_adjuntas=(R.randint(0, 2) if fraude and R.random() < 0.6 else R.randint(3, 9)),
                video_adjunto=R.random() < (0.15 if fraude else 0.45),
                velocidad_previa_kmh=round(abs(R.gauss(45, 20)), 1),
                impacto_detectado_g=(round(abs(R.gauss(0.3, 0.3)), 2) if fraude and R.random() < 0.5
                                     else round(abs(R.gauss(2.8, 1.2)), 2)),
                app_version=R.choice(["4.2.1", "4.3.0", "4.3.2", "5.0.0"])))
        # ---------- valuación en taller (presupuesto vs autorizado)
        if taller:
            inflado = R.uniform(1.4, 2.1) if taller in ring_talleres else R.uniform(1.02, 1.22)
            autorizado = round(monto * R.uniform(0.85, 1.0), 2)
            n_piezas = max(1, int(abs(R.gauss(6 if cob[0] == "Daños Materiales" else 1, 3))))
            valuaciones.append((id_val, id_sin, taller, (f_rep + timedelta(days=R.randint(1, 6))).date(),
                                round(autorizado * inflado, 2), autorizado, n_piezas,
                                round(min(1.0, max(0.0, R.gauss(0.45 if taller in ring_talleres else 0.8, 0.15))), 2),
                                round(abs(R.gauss(4 * n_piezas, 4)), 1), max(1, int(abs(R.gauss(12, 6))))))
            id_val += 1
        # ---------- terceros involucrados (fraude: reaparecen los mismos)
        for _t in range(terceros):
            if fraude and R.random() < 0.6:
                nom_t, tel_t = R.choice(RING_TERCEROS)
            else:
                nom_t = f"{R.choice(NOMBRES_H + NOMBRES_M)} {R.choice(APELLIDOS)} {R.choice(APELLIDOS)}"
                tel_t = f"{R.choice(['55', '33', '81', '222', '442'])}{R.randint(10_000_000, 99_999_999)}"[:10]
            tipo_t = wpick(["Vehículo", "Peatón", "Propiedad"], [80, 8, 12]) if cob[0] != "Gastos Médicos Ocupantes" else "Vehículo"
            terceros_sin.append((id_ter, id_sin, tipo_t, nom_t, tel_t,
                                 f"{''.join(R.choice('ABCDEFGHJKLMNPRSTUVWXYZ') for _ in range(3))}{R.randint(100, 999)}" if tipo_t == "Vehículo" else None,
                                 wpick(["Sin seguro", "Otra aseguradora", "FSI"], [45, 45, 10]) if tipo_t == "Vehículo" else None,
                                 round(lognorm(22_000 if tipo_t != "Peatón" else 60_000, 0.7) * (1.6 if fraude else 1.0), 2)))
            id_ter += 1
        id_sin += 1

# ================================================================= 6b. cotizaciones (app/web/comparadores externos)
CANAL_COT = [("App Autos FSI", "APP_AUTOS", 22, 0.30), ("Portal Web", "PORTAL_WEB", 20, 0.22),
             ("Comparador Externo", "API_COMPARADOR", 28, 0.09), ("Agente", "SISE", 22, 0.55),
             ("Módulo Tienda Aliada", "SISE", 8, 0.35)]
cotizaciones = []
id_cot = 1
pol_list = list(pol_info.items())
for id_pol, p in pol_list:  # cotizaciones que convirtieron
    if R.random() < 0.5:
        ch = wpick(CANAL_COT, [c[2] * c[3] for c in CANAL_COT])
        v, ci = p["veh"], cli_info[p["cid"]]
        cotizaciones.append((id_cot, p["emision"] - timedelta(days=R.randint(0, 20)), ch[0], ch[1], ci["cp"], ci["est"],
                             v["marca"], v["sub"], v["anio"], (p["emision"] - ci["fn"]).days // 365, p["prod"][0],
                             round(p["prima"] * R.uniform(0.97, 1.03), 2), True, id_pol))
        id_cot += 1
for _ in range(230_000):  # cotizaciones no convertidas (más caras / más comparador)
    ch = wpick(CANAL_COT, [c[2] * (1 - c[3]) for c in CANAL_COT])
    _, src_p = R.choice(pol_list)
    v = src_p["veh"]
    est = wpick(EST_NAMES, EST_W)
    cotizaciones.append((id_cot, rand_date(START, CUTOFF), ch[0], ch[1], f"{R.randint(1000, 99999):05d}", est,
                         v["marca"], v["sub"], v["anio"], R.randint(19, 75), src_p["prod"][0],
                         round(src_p["prima"] * R.uniform(1.0, 1.35), 2), False, None))
    id_cot += 1
cotizaciones.sort(key=lambda c: c[1])

# ================================================================= 6c. asistencias viales
TIPOS_AS = [("Grúa", 40, 1_900), ("Paso de corriente", 20, 450), ("Cambio de llanta", 18, 400),
            ("Cerrajería", 8, 650), ("Envío de gasolina", 8, 380), ("Traslado/Taxi", 6, 520)]
PROVEEDORES = [f"Asistencia {n}" for n in ("Express Norte", "Centro 24/7", "Bajío Vial", "Sureste Grúas",
                                          "Occidente Auxilio", "Pacífico Rescate", "Metro Grúas", "Ruta Segura")]
asistencias = []
id_as = 1
for id_pol, p in pol_list:
    end = min(p["fin"], p["canc"] or p["fin"], CUTOFF)
    span = (end - p["ini"]).days
    if span <= 0:
        continue
    n = 0
    while R.random() < 0.35 * span / 365 / (n + 1) and n < 3:
        n += 1
    for _ in range(n):
        t = wpick(TIPOS_AS, [x[1] for x in TIPOS_AS])
        canal = "App" if p["veh"]["app"] and R.random() < 0.75 else "Call Center"
        arribo = max(8, int(R.gauss(38 if canal == "App" else 52, 18) * (1.3 if ESTADOS[p["est"]][1] in ("Sureste", "Noroeste") else 1)))
        concl = R.random() > 0.06
        cal = (min(5, max(1, int(round(5.6 - arribo / 25 + R.gauss(0, 0.6))))) if concl else None)
        ts = datetime.combine(p["ini"] + timedelta(days=R.randint(0, span)), datetime.min.time()) + timedelta(minutes=R.randint(0, 1439))
        asistencias.append((id_as, id_pol, ts, t[0], canal, p["est"], R.choice(PROVEEDORES), arribo if concl else None,
                            round(t[2] * R.uniform(0.8, 1.6), 2) if concl else 0, cal, "Concluida" if concl else "Cancelada"))
        id_as += 1

# ================================================================= 7. telemetría trip_summary (2025-01..2026-09)
trips = []
TEL_START = date(2025, 1, 1)
for (id_veh, id_pol, marca, sub, anio, uso, valor, vin, pl, app) in vehiculos:
    if not app:
        continue
    p = pol_info[id_pol]
    end = min(p["fin"], p["canc"] or p["fin"], date(2026, 9, 30))
    m = date(max(p["ini"], TEL_START).year, max(p["ini"], TEL_START).month, 1)
    style = R.gauss(0, 1)  # perfil de manejo
    while m <= end:
        km = abs(R.gauss(2600 if uso == "Plataforma" else 900, 400 if uso == "Plataforma" else 300))
        trips.append(dict(
            event_type="trip_summary", device_id=f"DEV-{id_pol}", id_poliza=id_pol, mes=m.strftime("%Y-%m"),
            km_recorridos=round(km, 1), num_viajes=max(1, int(km / R.uniform(9, 16))),
            frenados_bruscos=max(0, int(km / 100 * max(0.1, 0.8 + 0.5 * style + R.gauss(0, 0.3)))),
            excesos_velocidad=max(0, int(km / 150 * max(0.05, 0.6 + 0.5 * style + R.gauss(0, 0.3)))),
            pct_manejo_nocturno=round(min(0.9, max(0, 0.12 + 0.06 * style + (0.15 if uso == "Plataforma" else 0) + R.gauss(0, 0.04))), 3),
            uso_celular_min=round(max(0, 20 + 15 * style + R.gauss(0, 8)), 1),
            score_manejo=int(min(100, max(20, 78 - 9 * style + R.gauss(0, 4))))))
        m = add_months(m, 1)

# ================================================================= 8. tabla consolidada legacy (duplicación)
pol_by_cli = {}
for id_pol, p in pol_info.items():
    pol_by_cli.setdefault(p["cid"], []).append(p)
EST_CVE = {e: v[3] for e, v in ESTADOS.items()}
legacy = []
for c in clientes:
    cid = c[0]
    ci = cli_info[cid]
    full = f"{ci['nom']} {ci['ap']} {ci['am']}"
    ps = pol_by_cli.get(cid, [])
    vig = sum(1 for p in ps if p["fin"] > CUTOFF and not p["canc"])
    prima_tot = round(sum(p["prima"] for p in ps), 2)
    copies = 2 if R.random() < 0.04 else 1
    for k in range(copies):
        stale = R.random() < 0.15
        legacy.append((
            cid, strip_acc(full), strip_acc(full)[:20], full,
            ci["rfc"], ci["rfc"] if R.random() > 0.03 else ci["rfc"][:10], ci["rfc"][:10] + "000" if R.random() < 0.3 else None,
            ci["curp"], ci["curp"] if R.random() > 0.05 else None,
            ci["fn"].strftime("%d/%m/%Y"), ci["fn"], ci["fn"].strftime("%Y%m%d"),
            ci["email"], ci["email"] if not stale else ci["email"].replace("@", "_old@"), ci["email"].upper() if R.random() < 0.5 else None,
            ci["tel"], ci["tel"] if R.random() > 0.2 else None, ("52" + ci["tel"]) if R.random() < 0.4 else ci["tel"],
            ci["est"], strip_acc(ci["est"]), EST_CVE[ci["est"]],
            ci["cp"], ci["cp"] if R.random() > 0.02 else None,
            ci["seg"], ci["seg"].upper()[:3],
            vig, len(ps) + (R.randint(1, 2) if stale else 0), prima_tot, round(prima_tot * (R.uniform(0.7, 1.2) if stale else 1.0), 2),
            rand_date(date(2011, 3, 1), date(2026, 9, 30)).strftime("%d/%m/%Y"),
            R.choice(["ETL_NOCT", "ETL_SEG", "USR_ACT01", "USR_MIG2014", "ODI_JOB"]),
            "SISE" if k == 0 else R.choice(["CRM_SIEBEL", "CARGA_MANUAL", "SAP_FI"])))

# ================================================================= 9. créditos personales (AWS)
creditos = []
for i in range(1, N_CREDITOS + 1):
    if R.random() < 0.6:
        cid = R.randint(1, N_CLIENTES)
        rfc = cli_info[cid]["rfc"]
        if R.random() < 0.06:
            rfc = rfc.lower()  # calidad cross-source
    else:
        cid = 900_000 + i
        rfc = "".join(R.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(4)) + f"{R.randint(500101, 991231)}" + "".join(R.choice(ALNUM) for _ in range(3))
    prod = wpick(["Personal", "Nómina", "Auto", "PyME"], [45, 30, 15, 10])
    orig = rand_date(date(2020, 1, 1), date(2026, 9, 30))
    term = R.choice([12, 18, 24, 36, 48, 60])
    amt = round(lognorm({"Personal": 60_000, "Nómina": 45_000, "Auto": 280_000, "PyME": 450_000}[prod], 0.5), -2)
    rate = round(R.uniform(16, 42) if prod in ("Personal", "Nómina") else R.uniform(11, 22), 2)
    months = (CUTOFF.year - orig.year) * 12 + CUTOFF.month - orig.month
    st = wpick(["current", "delinquent", "default"], [86, 9, 5])
    if months >= term and st == "current":
        st, bal = "paid_off", 0.0
    else:
        bal = round(amt * max(0.0, 1 - months / term) * (1.1 if st != "current" else 1.0), 2)
    dpd = 0 if st in ("current", "paid_off") else (R.randint(1, 89) if st == "delinquent" else R.randint(90, 360))
    creditos.append((7_000_000 + i, cid, rfc, prod, orig, term, amt, rate, bal, dpd, st))

# ================================================================= escritura
print("Escribiendo CSVs…")
write_csv("tb_productos", ["id_producto", "cve_producto", "nombre_producto", "ramo", "subramo"], productos)
write_csv("tb_agentes", ["id_agente", "cve_agente", "nombre_agente", "canal", "oficina", "region", "fecha_alta", "activo"], agentes)
write_csv("tb_clientes", ["id_cliente", "nombre", "apellido_paterno", "apellido_materno", "rfc", "curp", "fecha_nacimiento",
                          "genero", "email", "telefono", "estado", "municipio", "codigo_postal", "fecha_alta", "segmento"], clientes)
write_csv("tb_polizas", ["id_poliza", "num_poliza", "id_cliente", "id_producto", "id_agente", "fecha_emision", "inicio_vigencia",
                         "fin_vigencia", "suma_asegurada", "prima_neta_anual", "forma_pago", "estatus", "fecha_cancelacion",
                         "es_renovacion"], polizas)
write_csv("tb_vehiculos", ["id_vehiculo", "id_poliza", "marca", "submarca", "anio_modelo", "uso", "valor_comercial",
                           "num_serie_vin", "placas", "app_conectada"], vehiculos)
write_csv("tb_coberturas", ["id_cobertura", "cve_cobertura", "nombre_cobertura", "tipo", "deducible_pct_default"],
          [(k, v[0], v[1], v[2], v[5]) for k, v in COBERTURAS.items()])
write_csv("tb_poliza_coberturas", ["id_poliza", "id_cobertura", "suma_asegurada", "deducible_pct", "prima_cobertura"], poliza_coberturas)
write_csv("tb_conductores", ["id_conductor", "id_poliza", "id_cliente", "es_titular", "edad", "genero", "anios_licencia",
                             "tipo_licencia", "codigo_postal"], conductores)
write_csv("tb_cotizaciones", ["id_cotizacion", "fecha_cotizacion", "canal", "sistema_origen", "codigo_postal", "estado", "marca",
                              "submarca", "anio_modelo", "edad_conductor", "id_producto", "prima_cotizada", "convertida",
                              "id_poliza"], cotizaciones)
write_csv("tb_asistencias", ["id_asistencia", "id_poliza", "fecha_solicitud", "tipo_servicio", "canal_solicitud", "estado",
                             "proveedor", "tiempo_arribo_min", "costo", "calificacion", "estatus"], asistencias)
write_csv("tb_valuaciones", ["id_valuacion", "id_siniestro", "id_taller", "fecha_valuacion", "monto_presupuesto_taller",
                             "monto_autorizado", "num_piezas", "pct_piezas_originales", "horas_mano_obra", "dias_reparacion"], valuaciones)
write_csv("tb_terceros_siniestro", ["id_tercero", "id_siniestro", "tipo_tercero", "nombre_tercero", "telefono_tercero",
                                    "placas_tercero", "aseguradora_tercero", "monto_reclamado_tercero"], terceros_sin)
write_csv("tb_recibos", ["id_recibo", "id_poliza", "num_recibo", "fecha_vencimiento", "fecha_pago", "importe", "estatus"], recibos)
write_csv("tb_ajustadores", ["id_ajustador", "nombre_ajustador", "region", "tipo"], ajustadores)
write_csv("tb_talleres", ["id_taller", "nombre_taller", "tipo", "estado", "municipio"], talleres)
write_csv("tb_siniestros", ["id_siniestro", "num_siniestro", "id_poliza", "id_ajustador", "id_taller", "fecha_ocurrencia",
                            "fecha_reporte", "cobertura", "causa", "estado_ocurrencia", "canal_reporte", "monto_reclamado",
                            "reserva_inicial", "deducible", "reporte_autoridad", "num_terceros", "estatus", "fecha_cierre",
                            "fraude_confirmado"], siniestros)
write_csv("tb_movtos_siniestro", ["id_movimiento", "id_siniestro", "fecha_movimiento", "tipo_movimiento", "importe"], movtos)
write_csv("tb_cliente_consolidado_2011", [
    "id_cliente", "nombre_cliente", "nom_cte", "nombre_completo", "rfc", "rfc_cliente", "rfc_cte_ant", "curp", "curp_cte",
    "fec_nac", "fecha_nacimiento", "fch_nacimiento_cte", "email", "correo_e", "mail_contacto", "tel", "telefono_casa",
    "tel_contacto_1", "edo", "estado_residencia", "cve_edo", "cp", "cod_postal", "segmento", "seg_cte", "num_polizas_vig",
    "tot_polizas", "prima_total", "prima_tot_anual", "fec_ult_act", "usr_ult_act", "origen_carga"], legacy)
write_csv("creditos_personales", ["credito_id", "customer_id", "customer_rfc", "product", "origination_date", "term_months",
                                  "amount", "rate_pct", "balance", "days_past_due", "status"], creditos)

print("Escribiendo telemetría JSON…")
for kind, evs, key in (("trip_summary", trips, "mes"), ("fnol", fnol_events, "event_ts")):
    d = os.path.join(OUT_TEL, kind)
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))
    by_m = {}
    for e in evs:
        by_m.setdefault(e[key][:7], []).append(e)
    for m, es in sorted(by_m.items()):
        with open(os.path.join(d, f"{kind}_{m}.json"), "w") as f:
            for e in es:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"  {kind}: {len(evs):,} eventos en {len(by_m)} archivos")

# ================================================================= stats
aut = [s for s in siniestros if PROD_BY_ID[pol_info[s[2]]["prod"][0]][3] == "Autos"]
lab = [s for s in aut if s[18] is not None]
print(f"\nSiniestros: {len(siniestros):,} (Autos {len(aut):,}); con etiqueta {len(lab):,}, "
      f"fraude confirmado {sum(1 for s in lab if s[18]) / max(1, len(lab)):.1%}")
print(f"Abiertos/En investigación Autos: {sum(1 for s in aut if s[18] is None):,}")
prima = sum(p[9] for p in polizas)
print(f"Prima emitida total: ${prima / 1e9:.2f}B MXN")
