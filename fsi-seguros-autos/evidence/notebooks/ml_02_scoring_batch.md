# ML 02 · Batch scoring of open claims

_Executed notebook exported from Databricks job task run `635786447384282` with its real outputs._

# Aseguradora FSI · Autos — Modelo de Fraude en Siniestros
## 2. Scoring batch de siniestros abiertos con el modelo `@champion`
- `fe.score_batch`: solo se envía `id_siniestro`; las features se buscan en la feature table (mismo código que en entrenamiento).
- Razones por siniestro (SHAP) para que el SIU sepa **por qué** se marcó.
- Resultado: `demo_catalog.seguros_ml.scoring_fraude_siniestros` (tabla oficial, sujeta a los filtros por región).

```python
import mlflow
import numpy as np
import pandas as pd
from mlflow.tracking import MlflowClient
from databricks.feature_engineering import FeatureEngineeringClient
from pyspark.sql import functions as F

CAT, SRC, ML = "demo_catalog", "seguros_demo", "seguros_ml"
FEATURE_TABLE = f"{CAT}.{ML}.features_fraude_siniestro"
MODEL_NAME = f"{CAT}.{ML}.modelo_fraude_siniestros"
SCORING_TABLE = f"{CAT}.{ML}.scoring_fraude_siniestros"

mlflow.set_registry_uri("databricks-uc")
fe = FeatureEngineeringClient()
client = MlflowClient()

spark.conf.set("spark.databricks.remoteFiltering.blockSelfJoins", "false")  # ver nota en 01_features_entrenamiento

rol = spark.sql("SELECT demo_catalog.seguros_gobierno.rol_actual()").first()[0]
assert rol == "SIU", f"El scoring requiere rol SIU (rol actual: {rol})"

champ = client.get_model_version_by_alias(MODEL_NAME, "champion")
umbral_alto, umbral_medio = float(champ.tags["umbral_alto"]), float(champ.tags["umbral_medio"])
print(f"Champion v{champ.version} | umbral Alto {umbral_alto:.3f} · Medio {umbral_medio:.3f}")
```

Output:
```text
Champion v2 | umbral Alto 0.054 · Medio 0.003
```

## Probabilidad de fraude con Feature Engineering (`score_batch`)

```python
abiertos = spark.sql(f"SELECT id_siniestro FROM {CAT}.{SRC}.fact_siniestros WHERE fraude_confirmado IS NULL")
scored = fe.score_batch(model_uri=f"models:/{MODEL_NAME}@champion", df=abiertos, result_type="double") \
           .select("id_siniestro", F.col("prediction").alias("prob_fraude"))
print(scored.count(), "siniestros abiertos calificados")
```

Output:
```text
2026/11/05 00:33:52 WARNING mlflow.pyfunc: Calling `spark_udf()` with `env_manager="local"` does not recreate the same environment that was used during training, which may lead to errors or inaccurate predictions. We recommend specifying `env_manager="conda"`, which automatically recreates the environment that was used to train the model and performs inference in the recreated environment.
```

Output:
```text
2026/11/05 00:33:52 INFO mlflow.models.flavor_backend_registry: Selected backend for flavor 'python_function'
```

Output:
```text
3722 siniestros abiertos calificados
```

## Razones por siniestro (SHAP)

```python
import shap

ETIQUETAS = {
    "terceros_recurrentes": "Terceros que aparecen en otros siniestros",
    "ratio_presupuesto_autorizado": "Presupuesto del taller muy arriba de lo autorizado",
    "taller_ratio_presupuesto_prom": "Taller con historial de presupuestos inflados",
    "taller_pct_primeros_30d": "Taller con muchos siniestros al inicio de vigencia",
    "primeros_30_dias": "Siniestro en los primeros 30 días de la póliza",
    "dias_desde_inicio_vigencia": "Poco tiempo desde el inicio de vigencia",
    "horas_a_reporte": "Reporte tardío",
    "ocurrencia_nocturna": "Ocurrió de noche",
    "reporte_autoridad": "Sin reporte a la autoridad",
    "distancia_km_ubicacion_declarada": "GPS de la app lejos de la ubicación declarada",
    "fotos_adjuntas": "Pocas fotos en el reporte de la app",
    "impacto_detectado_g": "La app no detectó impacto",
    "monto_reclamado": "Monto reclamado alto",
    "ratio_monto_valor_vehiculo": "Monto alto vs. valor del vehículo",
    "monto_reclamado_terceros": "Reclamación de terceros alta",
    "num_terceros": "Varios terceros involucrados",
    "siniestros_previos_cliente": "Cliente con siniestros previos",
    "agente_pct_primeros_30d": "Agente con muchos siniestros tempranos",
    "agente_terceros_recurrentes_prom": "Agente con terceros recurrentes",
    "agente_siniestros_por_poliza": "Agente con alta siniestralidad",
    "pct_piezas_originales": "Pocas piezas originales en la reparación",
    "cobertura": "Tipo de cobertura",
    "uso_vehiculo": "Uso del vehículo",
    "antiguedad_vehiculo": "Antigüedad del vehículo",
}


def etiqueta(nombre_transformado):
    base = nombre_transformado.split("__", 1)[1]
    base = base.replace("missingindicator_", "")
    for k in sorted(ETIQUETAS, key=len, reverse=True):
        if base.startswith(k):
            return ETIQUETAS[k]
    return base


sk = mlflow.sklearn.load_model(f"runs:/{champ.run_id}/modelo_sklearn")
prep, modelo = sk.named_steps["prep"], sk.named_steps["modelo"]
feat = spark.table(FEATURE_TABLE).join(abiertos, "id_siniestro").toPandas()
ids = feat.pop("id_siniestro")
num_cols = prep.transformers_[0][2]
for c in num_cols:
    feat[c] = pd.to_numeric(feat[c], errors="coerce").astype(float)
Xt = prep.transform(feat)
Xt = Xt.toarray() if hasattr(Xt, "toarray") else Xt
nombres = [etiqueta(n) for n in prep.get_feature_names_out()]
sv = shap.TreeExplainer(modelo).shap_values(Xt)
sv = sv[1] if isinstance(sv, list) else (sv[..., 1] if sv.ndim == 3 else sv)

razones = []
for fila in sv:
    vistas, top = set(), []
    for j in np.argsort(-fila):
        if fila[j] <= 0 or len(top) == 3:
            break
        if nombres[j] not in vistas:
            vistas.add(nombres[j])
            top.append(nombres[j])
    razones.append(top + [None] * (3 - len(top)))
razones_df = spark.createDataFrame(pd.DataFrame(razones, columns=["razon_1", "razon_2", "razon_3"]).assign(id_siniestro=ids.values))
```

Output:
```text
/databricks/spark/python/pyspark/sql/pandas/utils.py:149: UserWarning: The conversion of DecimalType columns is inefficient and may take a long time. Column names: [taller_ratio_presupuesto_prom] If those columns are not necessary, you may consider dropping them or converting to primitive types before the conversion.
  warnings.warn(
```

## Tabla de scoring (oficial, gobernada)

```python
resultado = (scored.join(razones_df, "id_siniestro")
  .join(spark.table(f"{CAT}.{SRC}.fact_siniestros").select(
        "id_siniestro", "num_siniestro", "fecha_ocurrencia", "fecha_reporte", "cobertura", "canal_reporte", "estatus",
        "region", "estado_ocurrencia", "id_taller", "id_agente", "monto_reclamado"), "id_siniestro")
  .withColumn("nivel_riesgo", F.when(F.col("prob_fraude") >= umbral_alto, "Alto")
                               .when(F.col("prob_fraude") >= umbral_medio, "Medio").otherwise("Bajo"))
  .withColumn("monto_en_riesgo", F.col("prob_fraude") * F.col("monto_reclamado"))
  .withColumn("modelo", F.lit(MODEL_NAME))
  .withColumn("modelo_version", F.lit(int(champ.version)))
  .withColumn("fecha_scoring", F.current_timestamp()))

# La tabla tiene política ABAC (filtro por región): el cómputo dedicado no puede sobrescribirla,
# así que se recrea y se vuelven a aplicar los tags (que reactivan la política).
resultado = resultado.localCheckpoint()
spark.sql(f"DROP TABLE IF EXISTS {SCORING_TABLE}")
resultado.write.mode("overwrite").saveAsTable(SCORING_TABLE)
spark.sql(f"COMMENT ON TABLE {SCORING_TABLE} IS 'Siniestros abiertos calificados por el modelo de fraude @champion: probabilidad, nivel (Alto=top10%, Medio=top25%) y 3 razones SHAP.'")
spark.sql(f"ALTER TABLE {SCORING_TABLE} SET TAGS ('seguros_certificacion' = 'oficial')")
spark.sql(f"ALTER TABLE {SCORING_TABLE} ALTER COLUMN region SET TAGS ('seguros_region' = 'region')")

display(spark.sql(f"""
  SELECT nivel_riesgo, COUNT(*) siniestros, ROUND(AVG(prob_fraude), 3) prob_media,
         ROUND(SUM(monto_reclamado) / 1e6, 2) monto_reclamado_mdp, ROUND(SUM(monto_en_riesgo) / 1e6, 2) monto_en_riesgo_mdp
  FROM {SCORING_TABLE} GROUP BY 1 ORDER BY prob_media DESC"""))

dbutils.notebook.exit(f"scored={resultado.count()} version={champ.version}")
```

Output:
```text
scored=3722 version=2
```
