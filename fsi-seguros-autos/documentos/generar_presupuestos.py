"""Genera PDFs sintéticos de "Presupuesto de reparación" (emitidos por talleres) para una muestra de siniestros.
Una parte trae inconsistencias inyectadas (total alterado, VIN distinto, fecha previa al siniestro) — más probables en
casos de riesgo (riesgo Alto del modelo, fraude confirmado o presupuesto >140 % del autorizado).
PDF escrito a mano (stdlib, sin dependencias). Verdad de lo inyectado en data/presupuestos/_verdad.csv (solo local).
Run: python3 generar_presupuestos.py   →  luego subir con `databricks fs cp -r` (ver README).
"""
import csv, os, random, sys
from datetime import date, timedelta

sys.path.insert(0, os.path.expanduser("."))
from run_sql import run

R = random.Random(7)
OUT = os.path.expanduser("./data/presupuestos")
S = "demo_catalog.seguros_demo"

SQL = f"""
WITH base AS (
  SELECT s.id_siniestro, s.num_siniestro, to_date(s.fecha_ocurrencia) fecha_ocurrencia, s.cobertura, s.estatus,
         s.fraude_confirmado, sc.nivel_riesgo, v.monto_presupuesto_taller, v.monto_autorizado, v.num_piezas,
         v.horas_mano_obra, v.fecha_valuacion, v.ratio_presupuesto_autorizado, t.id_taller, t.nombre_taller, t.tipo tipo_taller,
         t.estado estado_taller, t.municipio, ve.marca, ve.submarca, ve.anio_modelo, ve.placas, ve.num_serie_vin
  FROM {S}.silver_valuaciones v
  JOIN {S}.silver_siniestros s ON v.id_siniestro = s.id_siniestro
  JOIN {S}.silver_talleres t ON v.id_taller = t.id_taller
  JOIN {S}.silver_vehiculos ve ON s.id_poliza = ve.id_poliza
  LEFT JOIN demo_catalog.seguros_ml.scoring_fraude_siniestros sc ON s.id_siniestro = sc.id_siniestro
), muestra AS (
  SELECT *, row_number() OVER (PARTITION BY grupo ORDER BY hash(id_siniestro, 7)) rn FROM (
    SELECT *, CASE WHEN nivel_riesgo IS NOT NULL THEN concat('abierto_', nivel_riesgo)
                   WHEN fraude_confirmado THEN 'cerrado_fraude' ELSE 'cerrado_ok' END grupo FROM base)
)
SELECT * FROM muestra
WHERE (grupo = 'abierto_Alto' AND rn <= 70) OR (grupo = 'abierto_Medio' AND rn <= 50) OR (grupo = 'abierto_Bajo' AND rn <= 60)
   OR (grupo = 'cerrado_fraude' AND rn <= 30) OR (grupo = 'cerrado_ok' AND rn <= 30)
"""

PIEZAS = ["Defensa delantera", "Defensa trasera", "Faro delantero izq.", "Faro delantero der.", "Cofre", "Salpicadera izq.",
          "Salpicadera der.", "Puerta delantera izq.", "Puerta trasera der.", "Parrilla", "Radiador", "Espejo lateral",
          "Calavera trasera", "Tapa de cajuela", "Soporte de defensa", "Parabrisas", "Medallón", "Rin 16\"", "Llanta",
          "Bolsa de aire conductor", "Condensador A/C", "Moldura lateral"]
MANO_OBRA_HORA = 480.0


# ---------------- PDF mínimo (Helvetica, WinAnsi) ----------------
def _esc(t):
    return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class Pdf:
    def __init__(self):
        self.ops = []

    def text(self, x, y, s, size=10, bold=False):
        self.ops.append(f"BT /{'F2' if bold else 'F1'} {size} Tf {x:.1f} {y:.1f} Td ({_esc(s)}) Tj ET")

    def rtext(self, xr, y, s, size=10, bold=False):  # alineado a la derecha (aprox. por ancho medio de Helvetica)
        self.text(xr - len(s) * size * 0.5, y, s, size, bold)

    def line(self, x1, y1, x2, y2, w=0.6):
        self.ops.append(f"{w} w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S")

    def rect(self, x, y, w, h, gray=0.92):
        self.ops.append(f"{gray} g {x:.1f} {y:.1f} {w:.1f} {h:.1f} re f 0 g")

    def save(self, path):
        stream = "\n".join(self.ops).encode("cp1252", errors="replace")
        objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
                b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
                b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
                b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
                b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"]
        out, offs = bytearray(b"%PDF-1.4\n"), []
        for i, o in enumerate(objs, 1):
            offs.append(len(out))
            out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        out += b"".join(b"%010d 00000 n \n" % o for o in offs)
        out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
        open(path, "wb").write(out)


def money(v):
    return f"${v:,.2f}"


def rfc_taller(nombre, id_taller):
    letras = "".join(c for c in nombre.upper() if c.isalpha())[:3].ljust(3, "X")
    return f"{letras}{(10 + id_taller % 13):02d}{(1 + id_taller % 12):02d}{(1 + id_taller % 27):02d}{'ABCDEFGH'[id_taller % 8]}{id_taller % 10}{'KLMNPQ'[id_taller % 6]}"


def alterar_vin(vin):
    v = list(vin)
    for i in R.sample(range(len(v)), 3):
        v[i] = R.choice("ABCDEFGHJKLMNPRSTUVWXYZ0123456789")
    return "".join(v)


def build(r):
    riesgo = r["nivel_riesgo"] == "Alto" or r["fraude_confirmado"] == "true" or float(r["ratio_presupuesto_autorizado"]) > 1.4
    total_cap = float(r["monto_presupuesto_taller"])
    f_occ = date.fromisoformat(r["fecha_ocurrencia"][:10])
    f_doc = date.fromisoformat(r["fecha_valuacion"][:10])
    inc = []
    total_doc = total_cap
    if R.random() < (0.40 if riesgo else 0.04):
        total_doc = round(total_cap * R.uniform(1.15, 1.45), 2); inc.append("total_alterado")
    vin_doc = r["num_serie_vin"]
    if R.random() < (0.22 if riesgo else 0.01):
        vin_doc = alterar_vin(vin_doc); inc.append("vin_distinto")
    if R.random() < (0.18 if riesgo else 0.01):
        f_doc = f_occ - timedelta(days=R.randint(3, 25)); inc.append("fecha_previa_siniestro")

    subtotal = round(total_doc / 1.16, 2)
    iva = round(total_doc - subtotal, 2)
    horas = max(float(r["horas_mano_obra"]), 0.5)
    mano = round(min(horas * MANO_OBRA_HORA, subtotal * 0.45), 2)
    n = max(1, min(int(r["num_piezas"]), 9))
    piezas_monto = subtotal - mano
    pesos = [R.uniform(0.5, 2.0) for _ in range(n)]
    lineas = [(p, round(piezas_monto * w / sum(pesos), 2)) for p, w in zip(R.sample(PIEZAS, n), pesos)]
    lineas[-1] = (lineas[-1][0], round(piezas_monto - sum(m for _, m in lineas[:-1]), 2))

    folio = f"PR-{r['id_taller']:>04}-{R.randint(10000, 99999)}"
    pdf = Pdf()
    pdf.rect(40, 712, 532, 50, 0.93)
    pdf.text(52, 742, r["nombre_taller"], 15, True)
    pdf.text(52, 724, f"RFC {rfc_taller(r['nombre_taller'], int(r['id_taller']))}  ·  {r['municipio']}, {r['estado_taller']}  ·  Taller {r['tipo_taller'].lower()}", 9)
    pdf.text(40, 684, "PRESUPUESTO DE REPARACIÓN", 13, True)
    pdf.rtext(572, 684, f"Folio {folio}", 10, True)
    pdf.text(40, 664, f"Fecha de emisión: {f_doc.strftime('%d/%m/%Y')}", 10)
    pdf.text(40, 640, "Aseguradora: Aseguradora FSI, S.A. (grupo financiero)", 10)
    pdf.text(40, 624, f"Número de siniestro: {r['num_siniestro']}", 10, True)
    pdf.text(330, 624, f"Cobertura: {r['cobertura']}", 10)
    pdf.line(40, 610, 572, 610)
    pdf.text(40, 592, "DATOS DEL VEHÍCULO", 10, True)
    pdf.text(40, 576, f"Marca / modelo: {r['marca']} {r['submarca']} {r['anio_modelo']}", 10)
    pdf.text(40, 560, f"Placas: {r['placas']}", 10)
    pdf.text(250, 560, f"No. de serie (VIN): {vin_doc}", 10)
    pdf.line(40, 546, 572, 546)
    pdf.rect(40, 520, 532, 18, 0.88)
    pdf.text(48, 525, "Concepto", 10, True); pdf.text(380, 525, "Cant.", 10, True); pdf.rtext(566, 525, "Importe", 10, True)
    y = 504
    for p, m in lineas:
        pdf.text(48, y, f"Refacción: {p}", 10); pdf.text(388, y, "1", 10); pdf.rtext(566, y, money(m), 10); y -= 16
    pdf.text(48, y, f"Mano de obra hojalatería y pintura ({horas:.1f} h)", 10); pdf.rtext(566, y, money(mano), 10); y -= 22
    pdf.line(330, y + 10, 572, y + 10)
    pdf.text(380, y, "Subtotal", 10); pdf.rtext(566, y, money(subtotal), 10); y -= 16
    pdf.text(380, y, "IVA 16%", 10); pdf.rtext(566, y, money(iva), 10); y -= 18
    pdf.text(380, y, "TOTAL", 12, True); pdf.rtext(566, y, money(total_doc), 12, True); y -= 40
    pdf.text(40, y, f"Tiempo estimado de reparación: {R.randint(3, 21)} días hábiles. Vigencia del presupuesto: 15 días.", 9)
    pdf.text(40, y - 14, "Precios en pesos mexicanos. Sujeto a autorización del ajustador de la aseguradora.", 9)
    pdf.line(60, 110, 250, 110); pdf.text(95, 96, "Firma del responsable del taller", 9)
    pdf.line(360, 110, 550, 110); pdf.text(400, 96, "Vo.Bo. ajustador FSI", 9)
    name = f"presupuesto_{r['num_siniestro']}.pdf"
    pdf.save(os.path.join(OUT, name))
    return {"archivo": name, "num_siniestro": r["num_siniestro"], "grupo": r["grupo"], "riesgo": riesgo,
            "total_capturado": total_cap, "total_documento": total_doc, "inconsistencias": "|".join(inc)}


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    cols, rows = run(SQL)
    data = [dict(zip(cols, row)) for row in rows]
    verdad = [build(r) for r in data]
    with open(os.path.join(OUT, "_verdad.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(verdad[0].keys())); w.writeheader(); w.writerows(verdad)
    con = sum(1 for v in verdad if v["inconsistencias"])
    print(f"{len(verdad)} PDFs en {OUT} · {con} con inconsistencias inyectadas")
