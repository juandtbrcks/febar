"""Genera pipeline3_cuarentena.sql a partir de las expectations ON VIOLATION DROP ROW de pipeline1_bronze_silver.sql.
Así las reglas viven en UN solo lugar (las expectations de plata) y la cuarentena se regenera si cambian.
Semántica igual a las expectations: una condición que da NULL cuenta como FALLA (por eso COALESCE(cond, FALSE)).
Para cada tabla de plata: re-evalúa sus reglas DROP sobre la misma proyección (mismos casts) que usa plata y manda a
`cuarentena_registros` los registros que fallan alguna, con las reglas fallidas y el registro completo en JSON.
En producción se recomienda además una conciliación por tabla (origen = destino + cuarentena) como control de auditoría;
se quitó del demo para mantener simple el grafo del pipeline.
Run: python3 gen_cuarentena.py   (y volver a subir el notebook pipeline3_cuarentena)
"""
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))
SRC, OUT = os.path.join(BASE, "pipeline1_bronze_silver.sql"), os.path.join(BASE, "pipeline3_cuarentena.sql")
S = "demo_catalog.seguros_demo"


def silver_blocks(sql):
    for blk in re.split(r"(?=CREATE OR REFRESH)", sql)[1:]:
        m = re.match(r"CREATE OR REFRESH (?:MATERIALIZED VIEW|STREAMING TABLE) (silver_\w+)", blk)
        if not m:
            continue
        name = m.group(1)
        drops, pk = [], None
        for line in blk.splitlines():
            c = re.match(r"\s*CONSTRAINT\s+(\w+)\s+EXPECT\s*\((.*)\)\s*ON VIOLATION (DROP ROW|FAIL UPDATE)", line)
            if not c:
                continue
            if c.group(3) == "DROP ROW":
                drops.append((c.group(1), c.group(2)))
            elif pk is None and c.group(1).startswith("pk_"):
                pk = re.sub(r"\s+IS NOT NULL", "", c.group(2)).replace(" AND ", ", ")
        proj = re.search(r"\nAS (SELECT\s.*?);\s*(?:\n|$)", blk, re.S).group(1)
        src = re.search(r"FROM (?:STREAM\()?(bronze_\w+)\)?(?:\s+\w+)?\s*$", proj.strip(), re.S)
        assert src and " WHERE " not in proj.upper().split("FROM")[-1], f"{name}: proyección con filtros, revisar"
        proj = re.sub(r"STREAM\((bronze_\w+)\)", r"\1", proj)
        yield name, src.group(1), pk, drops, proj


def main():
    blocks = list(silver_blocks(open(SRC).read()))
    parts = []
    for name, bronze, pk, drops, proj in blocks:
        if not drops:
            continue
        llave = f"concat_ws('|', {pk})" if pk else "CAST(NULL AS STRING)"
        if name == "silver_app_fnol":
            llave = "coalesce(num_siniestro, device_id)"
        reglas = ",\n         ".join(f"IF(NOT COALESCE({cond}, FALSE), '{rule}', NULL)" for rule, cond in drops)
        where = "\n     OR ".join(f"NOT COALESCE({cond}, FALSE)" for _, cond in drops)
        parts.append(f"""  SELECT '{name}' tabla_destino, 'Plata' capa, '{bronze}' tabla_origen, CAST({llave} AS STRING) llave,
         filter(array({reglas}), r -> r IS NOT NULL) reglas_fallidas,
         to_json(struct(*)) registro
  FROM ({proj}) x
  WHERE {where}""")
    # Oro: siniestros cuya póliza no existe (fk_poliza_existe en fact_siniestros)
    parts.append(f"""  SELECT 'fact_siniestros' tabla_destino, 'Oro' capa, 'silver_siniestros' tabla_origen, CAST(s.id_siniestro AS STRING) llave,
         array('fk_poliza_existe') reglas_fallidas, to_json(struct(s.*)) registro
  FROM {S}.silver_siniestros s LEFT ANTI JOIN {S}.silver_polizas p ON s.id_poliza = p.id_poliza""")

    head = """-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Aseguradora FSI · Autos — Pipeline Medallion · Cuarentena de calidad
-- MAGIC **Archivo GENERADO por `gen_cuarentena.py`** a partir de las expectations `ON VIOLATION DROP ROW` de plata (no editar a mano).
-- MAGIC - `cuarentena_registros`: cada registro que una regla DROP descartó, con las reglas que falló y el registro completo (JSON)
-- MAGIC   para que el equipo de datos lo corrija en la fuente. Nada se pierde en silencio.

-- COMMAND ----------
CREATE OR REFRESH MATERIALIZED VIEW cuarentena_registros
COMMENT 'Cuarentena: registros descartados por las expectations DROP (plata y oro), con reglas fallidas y registro en JSON. Contiene PII en `registro`: acceso solo para el equipo de calidad de datos'
AS SELECT *, size(reglas_fallidas) num_reglas_fallidas, current_timestamp() fecha_deteccion FROM (
"""
    sql = head + "\n  UNION ALL\n".join(parts) + "\n);\n"
    open(OUT, "w").write(sql)
    print(f"{OUT}: {len(parts)} fuentes de cuarentena")


if __name__ == "__main__":
    main()
