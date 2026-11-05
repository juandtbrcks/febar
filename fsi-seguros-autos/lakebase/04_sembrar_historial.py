"""Siembra ~3 semanas de trabajo SINTÉTICO del SIU en Lakebase (siu.casos / siu.notas / siu.historial_estatus).
Veredicto ~ Bernoulli(prob. del modelo + ruido) → etiquetas humanas para el ciclo de reentrenamiento (pieza 4).
Deja libres los siniestros del guion (S202600000146) y la mayoría de los Alto para la demo en vivo.
Idempotente: borra lo sembrado antes (origen = 'Histórico (sintético)').
Run:  python3 04_sembrar_historial.py | ./pg.sh -f -
"""
import csv, io, random, subprocess, datetime as dt

R = random.Random(7)
HOY = dt.datetime(2026, 11, 4, 18, 0, tzinfo=dt.timezone(dt.timedelta(hours=-6)))
RESERVADOS = {"S202600000146"}
INVESTIGADORES = ["laura.mendoza@siu.seguros-demo.mx", "carlos.ibarra@siu.seguros-demo.mx",
                  "sofia.ramirez@siu.seguros-demo.mx", "diego.salinas@siu.seguros-demo.mx"]
ORIGEN = "Histórico (sintético)"

out = subprocess.run(["./pg.sh", "-A", "--csv", "-c",
                      "SELECT num_siniestro, region, cobertura, prob_fraude, nivel_riesgo, monto_en_riesgo, monto_reclamado, "
                      "coalesce(razones_modelo,''), coalesce(inconsistencias_documentales,''), modelo_version "
                      "FROM serving.bandeja_siu ORDER BY prob_fraude DESC LIMIT 400"], capture_output=True, text=True, check=True).stdout
filas = [r for r in csv.reader(io.StringIO(out))][1:]
filas = [r for r in filas if r[0] not in RESERVADOS]
# 60 % de los casos de entre los Alto (dejamos ~65 Alto libres para la demo), el resto Medio/Bajo-alto
alto = [r for r in filas if r[4] == "Alto"]
otros = [r for r in filas if r[4] != "Alto"]
R.shuffle(alto); R.shuffle(otros)
elegidos = alto[:95] + otros[:65]
R.shuffle(elegidos)


def q(s):
    return "NULL" if s is None else "'" + str(s).replace("'", "''") + "'"


def ts(d):
    return q(d.isoformat())


sql = ["BEGIN;",
       "ALTER TABLE siu.casos DISABLE TRIGGER USER;",
       f"DELETE FROM siu.notas WHERE id_caso IN (SELECT id_caso FROM siu.casos WHERE origen = {q(ORIGEN)});",
       f"DELETE FROM siu.historial_estatus WHERE id_caso IN (SELECT id_caso FROM siu.casos WHERE origen = {q(ORIGEN)});",
       f"DELETE FROM siu.casos WHERE origen = {q(ORIGEN)};"]

for i, (num, region, cob, prob, nivel, mer, mrec, razones, incons, mv) in enumerate(elegidos):
    prob = float(prob)
    id_caso = f"SIU-H{1000 + i}"
    creado = HOY - dt.timedelta(days=R.uniform(2, 24), hours=R.uniform(0, 8))
    inv = R.choice(INVESTIGADORES)
    prio = "Alta" if nivel == "Alto" else ("Media" if prob > 0.25 else "Baja")
    destino = R.choices(["cerrado", "investigacion", "abierto"], [0.5, 0.32, 0.18])[0]
    hist = [(None, "Abierto", creado, inv)]
    notas = []
    # notas de trabajo
    t = creado + dt.timedelta(hours=R.uniform(2, 30))
    if incons:
        notas.append(("nota", f"El presupuesto del taller presenta inconsistencias ({incons}). Se solicitó factura original y fotos previas a la reparación.", t))
    elif "tercer" in razones.lower():
        notas.append(("nota", "El tercero involucrado aparece en otros siniestros recientes; se cruzó contra la base de terceros recurrentes.", t))
    else:
        notas.append(("nota", "Se contactó al asegurado; se agenda entrevista y revisión de evidencia fotográfica.", t))
    estatus, veredicto, cierre = "Abierto", None, None
    if destino in ("investigacion", "cerrado"):
        t2 = creado + dt.timedelta(days=R.uniform(0.5, 3))
        hist.append(("Abierto", "En investigación", t2, inv))
        estatus = "En investigación"
        notas.append(("nota", R.choice(["Inspección física del vehículo programada con ajustador.",
                                       "Se pidió al ajustador peritaje independiente del daño.",
                                       "Entrevista con el asegurado: hay contradicciones menores en el horario del evento.",
                                       "Se revisó la ubicación GPS del reporte en app contra el lugar declarado."]), t2 + dt.timedelta(hours=3)))
    if destino == "cerrado":
        es_fraude = R.random() < min(0.95, max(0.03, 0.85 * prob + R.gauss(0.05, 0.08)))
        t3 = creado + dt.timedelta(days=R.uniform(3, 14))
        if t3 > HOY - dt.timedelta(hours=6):
            t3 = HOY - dt.timedelta(hours=R.uniform(6, 30))
        estatus = "Cerrado - Fraude confirmado" if es_fraude else "Cerrado - Procedente"
        veredicto, cierre = ("fraude" if es_fraude else "legitimo"), t3
        hist.append(("En investigación", estatus, t3, inv))
        notas.append(("cambio_estatus", ("Cierre: se confirma fraude (daño preexistente / presupuesto inflado). Se rechaza el pago y se turna a Jurídico."
                                         if es_fraude else "Cierre: siniestro procedente, daños compatibles con el evento. Se libera el pago."), t3))
    act = max(h[2] for h in hist)
    sql.append(f"""INSERT INTO siu.casos (id_caso, num_siniestro, region, prioridad, resumen, recomendacion, monto_en_riesgo, prob_fraude_apertura,
  nivel_riesgo_apertura, modelo_version, estatus, veredicto, asignado_a, creado_por, aprobado_por, origen, fecha_creacion, fecha_actualizacion, fecha_cierre)
VALUES ({q(id_caso)}, {q(num)}, {q(region)}, {q(prio)}, {q(f'{cob}: {razones}')}, {q('Investigar antes de pagar')}, {mer or 0}, {prob}, {q(nivel)},
  {mv or 'NULL'}, {q(estatus)}, {q(veredicto)}, {q(inv)}, {q(inv)}, {q(inv)}, {q(ORIGEN)}, {ts(creado)}, {ts(act)}, {ts(cierre) if cierre else 'NULL'});""")
    for ant, nuevo, f, u in hist:
        sql.append(f"INSERT INTO siu.historial_estatus (id_caso, region, estatus_anterior, estatus_nuevo, usuario, fecha) "
                   f"VALUES ({q(id_caso)}, {q(region)}, {q(ant)}, {q(nuevo)}, {q(u)}, {ts(f)});")
    for tipo, txt, f in notas:
        sql.append(f"INSERT INTO siu.notas (num_siniestro, id_caso, region, autor, tipo, texto, fecha) "
                   f"VALUES ({q(num)}, {q(id_caso)}, {q(region)}, {q(inv)}, {q(tipo)}, {q(txt)}, {ts(f)});")

sql += ["ALTER TABLE siu.casos ENABLE TRIGGER USER;", "COMMIT;"]
print("\n".join(sql))
