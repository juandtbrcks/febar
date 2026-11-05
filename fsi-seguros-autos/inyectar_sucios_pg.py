"""Inyecta ~100 registros "sucios" en las fuentes PostgreSQL (<PG_SERVIDOR>) para demostrar la cuarentena del pipeline.
Cada registro rompe una regla DROP concreta de plata (o la FK siniestro→póliza de oro). IDs ≥ 9,000,000 para no chocar.
Idempotente: borra primero lo inyectado (por rango de IDs) y lo vuelve a insertar. Ninguno llega a oro.
Run:  PGPASSWORD='<password>' python3 inyectar_sucios_pg.py          (--borrar para solo quitarlos)
"""
import os, sys, random
from datetime import date, datetime, timedelta
import psycopg2

DSN = "host=<PG_HOST> port=5432 dbname={db} user=<PG_USER> sslmode=require"
if not os.environ.get("PGPASSWORD"):
    sys.exit("ERROR: define PGPASSWORD, ej: PGPASSWORD='...' python3 inyectar_sucios_pg.py")
R = random.Random(11)
BASE = 9_000_000          # clientes / siniestros / recibos / créditos (máximos reales: 60K / 27.6K / 458K / 7.03M)
BASE_POL = 90_000_000     # pólizas (las reales van de 10,000,001 a 10,100,000)
RANGO = 1000              # cada DELETE solo toca [base, base + RANGO)
NOMBRES = ["Luis", "Ana", "Jorge", "Sofía", "Pedro", "Lucía", "Raúl", "Elena"]
APELLIDOS = ["Pérez", "García", "López", "Hernández", "Martínez", "Ramírez"]
COBS = ["Daños Materiales", "Robo Total", "Responsabilidad Civil", "Cristales"]


def rfc_ok(i):
    return f"XEXX{80 + i % 20:02d}{1 + i % 12:02d}{1 + i % 28:02d}A{i % 10}{'BCD'[i % 3]}"


def curp_ok(i):
    return f"XEXX{80 + i % 20:02d}{1 + i % 12:02d}{1 + i % 28:02d}HDFRRN0{i % 10}"


def clientes():
    rows = []
    for i in range(20):
        rfc, curp, nac, gen = rfc_ok(i), curp_ok(i), date(1985, 1 + i % 12, 1 + i % 28), "M"
        if i < 8:
            curp = curp[:10] + "X" + curp[11:]           # sexo en CURP inválido → curp_formato
        elif i < 13:
            nac = date(2011 + i % 3, 5, 10)                # menor de edad → edad_valida
        elif i < 17:
            gen = "X"                                      # → genero_valido
        else:
            rfc = rfc[:9]                                  # RFC incompleto → rfc_formato
        rows.append((BASE + i, R.choice(NOMBRES), R.choice(APELLIDOS), R.choice(APELLIDOS), rfc, curp, nac, gen,
                     f"cliente{i}@correo.mx", "5512345678", "Ciudad de México", "Coyoacán", "04000", date(2026, 9, 1), "Masivo"))
    return rows


def polizas(cur):
    cur.execute("SELECT id_cliente FROM seguros_dwh.tb_clientes WHERE id_cliente < %s ORDER BY id_cliente LIMIT 25", (BASE,))
    cli = [r[0] for r in cur.fetchall()]
    rows = []
    for i in range(25):
        ini, fin, prima, suma, est, fp, emi = date(2026, 3, 1), date(2027, 3, 1), 9500.0, 350000.0, "Vigente", "Anual", date(2026, 2, 25)
        if i < 8:
            fin = ini - timedelta(days=30)                 # → vigencia_coherente
        elif i < 14:
            prima = -abs(prima) if i % 2 else 0            # → prima_positiva
        elif i < 19:
            est = "Suspendida"                             # → estatus_valido
        elif i < 22:
            fp = "Quincenal"                               # → forma_pago_valida
        else:
            emi = date(2027, 1, 15)                        # → emision_no_futura
        rows.append((BASE_POL + i, f"AUT-SUC-{i:04d}", cli[i], 1, 1, emi, ini, fin, suma, prima, fp, est, None, False))
    return rows


def siniestros(cur):
    cur.execute("SELECT id_poliza FROM seguros_dwh.tb_polizas WHERE id_poliza < %s ORDER BY id_poliza LIMIT 30", (BASE_POL,))
    pol = [r[0] for r in cur.fetchall()]
    rows = []
    for i in range(30):
        occ = datetime(2026, 8, 1 + i % 28, 14, 30)
        rep, cob, monto, est, id_pol = occ + timedelta(hours=3), R.choice(COBS), 25000.0, "Abierto", pol[i]
        if i < 6:
            cob = "Granizo"                                # → cobertura_valida
        elif i < 11:
            monto = -1500.0                                # → monto_no_negativo
        elif i < 15:
            occ = datetime(2026, 12, 20, 10, 0); rep = occ + timedelta(hours=2)   # → ocurrencia_no_futura
        elif i < 20:
            rep = occ - timedelta(days=2)                  # → reporte_post_ocurr
        elif i < 25:
            est = "Pendiente"                              # → estatus_valido
        else:
            id_pol = BASE_POL * 10 + i                        # válido en plata, sin póliza → oro (fk_poliza_existe)
        rows.append((BASE + i, f"SX2026{BASE + i:08d}", id_pol, 1, None, occ, rep, cob, "Colisión", "Ciudad de México",
                     "Call Center", monto, abs(monto), 0, True, 0, est, None, None))
    return rows


def recibos(cur):
    cur.execute("SELECT id_poliza FROM seguros_dwh.tb_polizas WHERE id_poliza < %s ORDER BY id_poliza LIMIT 10", (BASE_POL,))
    pol = [r[0] for r in cur.fetchall()]
    rows = []
    for i in range(10):
        est, fpago, imp = "Pagado", date(2026, 9, 5), 1200.0
        if i < 4:
            est = "Reembolsado"                            # → estatus_valido
        elif i < 8:
            fpago = None                                   # Pagado sin fecha → pagado_con_fecha
        else:
            imp = 0                                        # → importe_positivo
        rows.append((BASE + i, pol[i], 99, date(2026, 9, 1), fpago, imp, est))
    return rows


def creditos():
    rows = []
    for i in range(10):
        amount, balance, status = 80000.0, 45000.0, "current"
        if i < 4:
            amount = -80000.0                              # → monto_positivo
        elif i < 7:
            balance = -1200.0                              # → saldo_no_neg
        else:
            status = "written_off"                         # estatus no catalogado → estatus_valido
        rows.append((BASE + i, None, rfc_ok(40 + i), "Personal", date(2026, 1, 15), 24, amount, 24.9, balance, 0, status))
    return rows


def run(db, fn):
    con = psycopg2.connect(DSN.format(db=db)); con.autocommit = False
    with con, con.cursor() as cur:
        fn(cur)
    con.close()


def dwh(cur):
    for t, k, b in [("tb_siniestros", "id_siniestro", BASE), ("tb_recibos", "id_recibo", BASE),
                    ("tb_polizas", "id_poliza", BASE_POL), ("tb_clientes", "id_cliente", BASE)]:
        cur.execute(f"DELETE FROM seguros_dwh.{t} WHERE {k} >= %s AND {k} < %s", (b, b + RANGO))
        assert cur.rowcount <= 100, f"{t}: el DELETE tocaría {cur.rowcount} filas — abortando"
    if "--borrar" in sys.argv:
        return
    cur.executemany("INSERT INTO seguros_dwh.tb_clientes VALUES (" + ",".join(["%s"] * 15) + ")", clientes())
    cur.executemany("INSERT INTO seguros_dwh.tb_polizas VALUES (" + ",".join(["%s"] * 14) + ")", polizas(cur))
    cur.executemany("INSERT INTO seguros_dwh.tb_siniestros VALUES (" + ",".join(["%s"] * 19) + ")", siniestros(cur))
    cur.executemany("INSERT INTO seguros_dwh.tb_recibos VALUES (" + ",".join(["%s"] * 7) + ")", recibos(cur))


def cred(cur):
    cur.execute("DELETE FROM seguros_creditos.creditos_personales WHERE credito_id >= %s AND credito_id < %s", (BASE, BASE + RANGO))
    assert cur.rowcount <= 100, "créditos: el DELETE tocaría demasiadas filas — abortando"
    if "--borrar" in sys.argv:
        return
    cur.executemany("INSERT INTO seguros_creditos.creditos_personales VALUES (" + ",".join(["%s"] * 11) + ")", creditos())


run("dwh_seguros", dwh)
run("creditos_aws", cred)
print("Borrados los registros sucios." if "--borrar" in sys.argv else
      "Inyectados: 20 clientes, 25 pólizas, 30 siniestros, 10 recibos (dwh_seguros) + 10 créditos (creditos_aws).")
