"""
Aseguradora FSI · Autos — recrea las dos fuentes "legacy" en Azure PostgreSQL (<PG_SERVIDOR>), cada una en su
propia base de datos para que cada foreign catalog de Databricks vea solo su sistema:
  dwh_seguros   / seguros_dwh       -> proxy del DWH Oracle on-prem
  creditos_aws  / seguros_creditos  -> proxy de la BD de créditos personales en AWS
Carga los CSV generados por generate_data.py vía COPY.

Run:  PGPASSWORD='<password>' python3 load_pg.py
"""
import os, sys, psycopg2

BASE = os.path.dirname(os.path.abspath(__file__))
CSV_DIR = os.path.join(BASE, "data", "csv")
DSN = ("host=<PG_HOST> port=5432 dbname={db} "
       "user=<PG_USER> sslmode=require")

if not os.environ.get("PGPASSWORD"):
    sys.exit("ERROR: define PGPASSWORD, ej: PGPASSWORD='...' python3 load_pg.py")

SOURCES = [  # (base de datos, ddl, schema, tablas en orden de carga)
    ("dwh_seguros", "ddl_dwh.sql", "seguros_dwh", [
        "tb_productos", "tb_agentes", "tb_clientes", "tb_polizas", "tb_vehiculos", "tb_coberturas",
        "tb_poliza_coberturas", "tb_conductores", "tb_cotizaciones", "tb_asistencias", "tb_recibos",
        "tb_ajustadores", "tb_talleres", "tb_siniestros", "tb_movtos_siniestro", "tb_valuaciones",
        "tb_terceros_siniestro", "tb_cliente_consolidado_2011"]),
    ("creditos_aws", "ddl_creditos.sql", "seguros_creditos", ["creditos_personales"]),
]

admin = psycopg2.connect(DSN.format(db="postgres"))
admin.autocommit = True
acur = admin.cursor()
for db, *_ in SOURCES:
    acur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db,))
    if not acur.fetchone():
        acur.execute(f"CREATE DATABASE {db}")
        print(f"CREATE DATABASE {db}")
admin.close()

for db, ddl, sch, tables in SOURCES:
    print(f"== {db} ==")
    conn = psycopg2.connect(DSN.format(db=db))
    cur = conn.cursor()
    cur.execute(open(os.path.join(BASE, ddl)).read())
    conn.commit()
    for t in tables:
        with open(os.path.join(CSV_DIR, f"{t}.csv")) as f:
            cur.copy_expert(f"COPY {sch}.{t} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')", f)
        conn.commit()
        cur.execute(f"SELECT COUNT(*) FROM {sch}.{t}")
        print(f"  {sch}.{t}: {cur.fetchone()[0]:,}")
    cur.execute("ANALYZE")
    conn.commit()
    conn.close()
print("CARGA COMPLETA.")
