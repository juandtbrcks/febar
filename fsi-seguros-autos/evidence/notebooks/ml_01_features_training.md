# ML 01 · Feature table + training + champion/challenger

_Executed notebook exported from Databricks job task run `472877672356572` with its real outputs._

# Aseguradora FSI · Autos — Modelo de Fraude en Siniestros
## 1. Feature table en UC + entrenamiento con MLflow + registro en Unity Catalog

| Paso | Capacidad |
|---|---|
| Features por siniestro (DWH + telemetría app + agregados taller/agente) | **Feature Engineering in Unity Catalog** |
| Selección de modelo (baseline vs. RF vs. búsqueda XGBoost) | **MLflow Tracking** — runs anidados, `log_input` |
| Evaluación hold-out temporal | **`mlflow.evaluate`** + SHAP + curva de captura |
| Registro y promoción | **UC Model Registry** — aliases `champion` / `challenger` con compuerta de calidad |

Etiqueta: `fraude_confirmado` (dictamen SIU, solo siniestros cerrados/rechazados) **+ veredictos frescos del SIU**
capturados en la app (Lakebase `seguros-siu` → CDF → `demo_catalog.seguros_siu_expediente.etiquetas_siu`).
Los veredictos del SIU entran SOLO a entrenamiento; el test se queda en el hold-out histórico (compuerta justa).
Se excluyen variables que delatan la etiqueta (estatus, pagado, fecha de cierre).

```python
import mlflow
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from mlflow.tracking import MlflowClient
from databricks.feature_engineering import FeatureEngineeringClient, FeatureLookup
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

CAT, SRC, ML = "demo_catalog", "seguros_demo", "seguros_ml"
FEATURE_TABLE = f"{CAT}.{ML}.features_fraude_siniestro"
MODEL_NAME = f"{CAT}.{ML}.modelo_fraude_siniestros"
EXPERIMENT = "/Users/<tu_usuario>/seguros_fraude_siniestros"
FECHA_VALID, FECHA_TEST = "2024-10-01", "2025-04-01"   # split temporal
SEED = 42

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(EXPERIMENT)
fe = FeatureEngineeringClient()
client = MlflowClient()
print("MLflow", mlflow.__version__)

# Guardia de gobierno: entrenar con la vista completa (rol SIU). Con otro rol, el row filter
# por región recortaría los datos de entrenamiento.
rol = spark.sql("SELECT demo_catalog.seguros_gobierno.rol_actual()").first()[0]
assert rol == "SIU", f"El entrenamiento requiere rol SIU (rol actual: {rol})"

# Las tablas oficiales tienen políticas ABAC: en cómputo dedicado se filtran remotamente y Spark bloquea por omisión
# los self-joins sobre ellas (la feature SQL lee fact_siniestros/fact_polizas varias veces).
spark.conf.set("spark.databricks.remoteFiltering.blockSelfJoins", "false")

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CAT}.{ML} COMMENT 'FSI — ML gobernado: feature tables, modelos y scoring'")
```

Output:
```text
MLflow 2.21.3
```

Output:
```text
DataFrame[]
```

## Feature table (grano = siniestro)

```python
features_sql = f"""
WITH tal AS (   -- comportamiento histórico del taller (sin usar la etiqueta)
  SELECT id_taller, COUNT(*) taller_num_siniestros,
         AVG(ratio_presupuesto_autorizado) taller_ratio_presupuesto_prom,
         AVG(CAST(primeros_30_dias AS INT)) taller_pct_primeros_30d
  FROM {CAT}.{SRC}.fact_siniestros WHERE id_taller IS NOT NULL GROUP BY id_taller
), ag AS (      -- comportamiento del agente que vendió la póliza
  SELECT p.id_agente, COUNT(s.id_siniestro) / COUNT(DISTINCT p.id_poliza) agente_siniestros_por_poliza,
         AVG(CAST(s.primeros_30_dias AS INT)) agente_pct_primeros_30d,
         AVG(s.terceros_recurrentes) agente_terceros_recurrentes_prom
  FROM {CAT}.{SRC}.fact_polizas p LEFT JOIN {CAT}.{SRC}.fact_siniestros s ON p.id_poliza = s.id_poliza
  GROUP BY p.id_agente
), tel AS (     -- manejo en los 3 meses previos al siniestro (data lake app)
  SELECT s.id_siniestro, AVG(t.score_manejo) tel_score_manejo_3m, AVG(t.frenados_por_100km) tel_frenados_100km_3m,
         AVG(t.pct_manejo_nocturno) tel_pct_nocturno_3m, AVG(t.km_recorridos) tel_km_mes_3m
  FROM {CAT}.{SRC}.fact_siniestros s
  JOIN {CAT}.{SRC}.fact_telemetria_mensual t
    ON s.id_poliza = t.id_poliza
   AND t.mes BETWEEN add_months(trunc(s.fecha_ocurrencia, 'MM'), -3) AND add_months(trunc(s.fecha_ocurrencia, 'MM'), -1)
  GROUP BY s.id_siniestro
)
SELECT
  s.id_siniestro,
  -- siniestro
  s.cobertura, s.canal_reporte, CAST(s.monto_reclamado AS DOUBLE) monto_reclamado, CAST(s.deducible AS DOUBLE) deducible,
  s.dias_desde_inicio_vigencia, CAST(s.primeros_30_dias AS INT) primeros_30_dias, CAST(s.horas_a_reporte AS DOUBLE) horas_a_reporte,
  CAST(s.ocurrencia_nocturna AS INT) ocurrencia_nocturna, CAST(s.reporte_autoridad AS INT) reporte_autoridad,
  s.num_terceros, s.terceros_recurrentes, CAST(s.monto_reclamado_terceros AS DOUBLE) monto_reclamado_terceros,
  s.siniestros_previos_cliente, CAST(s.ratio_monto_valor_vehiculo AS DOUBLE) ratio_monto_valor_vehiculo,
  CAST(s.ratio_presupuesto_autorizado AS DOUBLE) ratio_presupuesto_autorizado, s.pct_piezas_originales,
  -- app (FNOL)
  s.distancia_km_ubicacion_declarada, s.fotos_adjuntas, CAST(s.video_adjunto AS INT) video_adjunto, s.impacto_detectado_g,
  -- póliza / vehículo / cliente
  pr.paquete, p.forma_pago, CAST(p.es_renovacion AS INT) es_renovacion, p.num_conductores, p.edad_conductor_min,
  v.uso uso_vehiculo, v.antiguedad_anios antiguedad_vehiculo, CAST(v.valor_comercial AS DOUBLE) valor_comercial,
  v.segmento_marca, CAST(v.app_conectada AS INT) app_conectada,
  c.edad edad_cliente, c.segmento segmento_cliente, c.antiguedad_anios antiguedad_cliente,
  CAST(c.tiene_credito_grupo AS INT) tiene_credito_grupo, c.estatus_credito, s.region,
  -- agregados
  tal.taller_num_siniestros, tal.taller_ratio_presupuesto_prom, tal.taller_pct_primeros_30d,
  ag.agente_siniestros_por_poliza, ag.agente_pct_primeros_30d, ag.agente_terceros_recurrentes_prom,
  tel.tel_score_manejo_3m, tel.tel_frenados_100km_3m, tel.tel_pct_nocturno_3m, tel.tel_km_mes_3m
FROM {CAT}.{SRC}.fact_siniestros s
JOIN {CAT}.{SRC}.fact_polizas p ON s.id_poliza = p.id_poliza
LEFT JOIN {CAT}.{SRC}.dim_producto pr ON s.id_producto = pr.id_producto
LEFT JOIN {CAT}.{SRC}.dim_vehiculo v ON s.id_vehiculo = v.id_vehiculo
LEFT JOIN {CAT}.{SRC}.dim_cliente c ON s.id_cliente = c.id_cliente
LEFT JOIN tal ON s.id_taller = tal.id_taller
LEFT JOIN ag ON s.id_agente = ag.id_agente
LEFT JOIN tel ON s.id_siniestro = tel.id_siniestro
"""
features_df = spark.sql(features_sql)

if spark.catalog.tableExists(FEATURE_TABLE):
    fe.write_table(name=FEATURE_TABLE, df=features_df, mode="merge")
else:
    fe.create_table(
        name=FEATURE_TABLE, primary_keys=["id_siniestro"], df=features_df,
        description="Features por siniestro para detección de fraude: atributos del siniestro, reporte en app (FNOL), "
                    "póliza/vehículo/cliente, comportamiento histórico de taller y agente, y manejo previo (telemetría).")
spark.sql(f"ALTER TABLE {FEATURE_TABLE} SET TAGS ('seguros_certificacion' = 'oficial')")
print(FEATURE_TABLE, spark.table(FEATURE_TABLE).count(), "filas")
```

Output:
```text
demo_catalog.seguros_ml.features_fraude_siniestro 36726 filas
```

## Training sets con split temporal (train → valid → test)

```python
labels = spark.sql(f"""
  SELECT id_siniestro, CAST(fraude_confirmado AS INT) fraude, fecha_ocurrencia
  FROM {CAT}.{SRC}.fact_siniestros WHERE fraude_confirmado IS NOT NULL
""")
lookups = [FeatureLookup(table_name=FEATURE_TABLE, lookup_key="id_siniestro")]

# Ciclo SIU → modelo: veredictos humanos registrados en la app (Lakebase) que el DWH aún no tiene como etiqueta
ETIQUETAS_SIU = "demo_catalog.seguros_siu_expediente.etiquetas_siu"
try:
    labels_siu = (spark.table(ETIQUETAS_SIU).select("id_siniestro", "fraude")
                  .join(labels.select("id_siniestro"), "id_siniestro", "left_anti").dropDuplicates(["id_siniestro"]))
    N_SIU = labels_siu.count()
except Exception as e:  # sin expediente SIU el entrenamiento sigue igual
    print("Sin etiquetas del SIU:", str(e)[:200])
    labels_siu, N_SIU = None, 0
print(f"Etiquetas frescas del SIU (Lakebase → CDF): {N_SIU}")


def training_set(cond, con_siu=False):
    df = labels.where(cond).select("id_siniestro", "fraude")
    if con_siu and labels_siu is not None:
        df = df.unionByName(labels_siu)
    return fe.create_training_set(df=df, feature_lookups=lookups, label="fraude", exclude_columns=["id_siniestro"])


ts_train = training_set(f"fecha_ocurrencia < '{FECHA_VALID}'", con_siu=True)
ts_valid = training_set(f"fecha_ocurrencia >= '{FECHA_VALID}' AND fecha_ocurrencia < '{FECHA_TEST}'")
ts_test = training_set(f"fecha_ocurrencia >= '{FECHA_TEST}'")
ts_trainval = training_set(f"fecha_ocurrencia < '{FECHA_TEST}'", con_siu=True)

train, valid, test = (t.load_df().toPandas() for t in (ts_train, ts_valid, ts_test))
trainval = pd.concat([train, valid], ignore_index=True)
X = lambda d: d.drop(columns=["fraude"])
y = lambda d: d["fraude"].astype(int)
for n, d in (("train", train), ("valid", valid), ("test", test)):
    print(f"{n:6} {len(d):6,} siniestros | fraude {y(d).mean():.1%}")

CATEGORICAS = ["cobertura", "canal_reporte", "paquete", "forma_pago", "uso_vehiculo", "segmento_marca",
               "segmento_cliente", "estatus_credito", "region"]
NUMERICAS = [c for c in X(train).columns if c not in CATEGORICAS]
for c in NUMERICAS:
    for d in (train, valid, test, trainval):
        d[c] = pd.to_numeric(d[c], errors="coerce").astype(float)
```

Output:
```text
Etiquetas frescas del SIU (Lakebase → CDF): 89
```

Output:
```text
/databricks/spark/python/pyspark/sql/pandas/utils.py:149: UserWarning: The conversion of DecimalType columns is inefficient and may take a long time. Column names: [taller_ratio_presupuesto_prom] If those columns are not necessary, you may consider dropping them or converting to primitive types before the conversion.
  warnings.warn(
/databricks/spark/python/pyspark/sql/pandas/utils.py:149: UserWarning: The conversion of DecimalType columns is inefficient and may take a long time. Column names: [taller_ratio_presupuesto_prom] If those columns are not necessary, you may consider dropping them or converting to primitive types before the conversion.
  warnings.warn(
/databricks/spark/python/pyspark/sql/pandas/utils.py:149: UserWarning: The conversion of DecimalType columns is inefficient and may take a long time. Column names: [taller_ratio_presupuesto_prom] If those columns are not necessary, you may consider dropping them or converting to primitive types before the conversion.
  warnings.warn(
```

Output:
```text
train  17,079 siniestros | fraude 6.7%
valid   2,341 siniestros | fraude 7.2%
test    4,591 siniestros | fraude 8.2%
```

## Métricas de negocio para el SIU

```python
def metricas(y_true, p, monto, prefix):
    """AUC/PR-AUC + métricas operativas: el SIU solo puede revisar un % de los siniestros."""
    y_true, p, monto = np.asarray(y_true), np.asarray(p), np.asarray(monto)
    orden = np.argsort(-p)
    out = {f"{prefix}_roc_auc": roc_auc_score(y_true, p), f"{prefix}_pr_auc": average_precision_score(y_true, p)}
    for pct in (5, 10, 20):
        k = max(1, int(len(p) * pct / 100))
        top = orden[:k]
        out[f"{prefix}_precision_top{pct}"] = y_true[top].mean()
        out[f"{prefix}_captura_top{pct}"] = y_true[top].sum() / max(1, y_true.sum())
        out[f"{prefix}_monto_fraude_capturado_top{pct}_pct"] = (monto[top] * y_true[top]).sum() / max(1, (monto * y_true).sum())
    return out


def preprocesador(escalar):
    num = [("imp", SimpleImputer(strategy="median", add_indicator=True))] + ([("esc", StandardScaler())] if escalar else [])
    return ColumnTransformer([
        ("num", Pipeline(num), NUMERICAS),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="NA")),
                          ("oh", OneHotEncoder(handle_unknown="ignore", min_frequency=20))]), CATEGORICAS)])


pos_weight = float((y(train) == 0).sum() / (y(train) == 1).sum())
```

## Selección de modelo — runs anidados

```python
rng = np.random.default_rng(SEED)
candidatos = [("logistic_regression", {"C": 0.5}), ("random_forest", {"n_estimators": 300, "max_depth": 10, "min_samples_leaf": 5})]
for _ in range(10):  # búsqueda aleatoria de hiperparámetros XGBoost
    candidatos.append(("xgboost", {
        "n_estimators": int(rng.choice([200, 300, 500])), "max_depth": int(rng.choice([3, 4, 5, 6])),
        "learning_rate": float(rng.choice([0.03, 0.05, 0.1])), "subsample": float(rng.choice([0.7, 0.85, 1.0])),
        "colsample_bytree": float(rng.choice([0.6, 0.8, 1.0])), "min_child_weight": int(rng.choice([1, 5, 10]))}))


def construir(familia, params):
    if familia == "logistic_regression":
        est = LogisticRegression(class_weight="balanced", max_iter=2000, **params)
    elif familia == "random_forest":
        est = RandomForestClassifier(class_weight="balanced_subsample", n_jobs=-1, random_state=SEED, **params)
    else:
        est = XGBClassifier(scale_pos_weight=pos_weight, eval_metric="aucpr", n_jobs=-1, random_state=SEED, **params)
    return Pipeline([("prep", preprocesador(familia == "logistic_regression")), ("modelo", est)])


feature_ds = mlflow.data.load_delta(table_name=FEATURE_TABLE)
resultados = []
with mlflow.start_run(run_name="seleccion_modelo_fraude") as parent:
    mlflow.log_input(feature_ds, context="features")
    mlflow.log_param("etiquetas_siu_lakebase", N_SIU)
    mlflow.log_params({"split_valid": FECHA_VALID, "split_test": FECHA_TEST, "n_train": len(train),
                       "n_valid": len(valid), "tasa_fraude_train": round(y(train).mean(), 4)})
    for i, (familia, params) in enumerate(candidatos):
        with mlflow.start_run(run_name=f"{familia}_{i:02d}", nested=True):
            pipe = construir(familia, params).fit(X(train), y(train))
            p = pipe.predict_proba(X(valid))[:, 1]
            m = metricas(y(valid), p, valid["monto_reclamado"], "valid")
            mlflow.log_param("familia", familia)
            mlflow.log_params(params)
            mlflow.log_metrics(m)
            resultados.append({"familia": familia, "params": params, **m})
            print(f"{familia:20} PR-AUC {m['valid_pr_auc']:.3f}  AUC {m['valid_roc_auc']:.3f}  captura@10% {m['valid_captura_top10']:.1%}")
    ranking = pd.DataFrame(resultados).sort_values("valid_pr_auc", ascending=False)
    mejor = ranking.iloc[0]
    mlflow.log_table(ranking.assign(params=ranking["params"].astype(str)), "ranking_candidatos.json")
    mlflow.set_tag("mejor_familia", mejor["familia"])

print("Mejor:", mejor["familia"], mejor["params"])
```

Output:
```text
2026/11/05 00:32:11 WARNING mlflow.data.spark_dataset: Failed to infer schema for Spark dataset. Exception: Expected mlflow.types.schema.Datatype, mlflow.types.schema.Array, mlflow.types.schema.Object, mlflow.types.schema.Map, mlflow.types.schema.AnyType or str for the 'type' argument, but got None
```

Output:
```text
logistic_regression  PR-AUC 0.612  AUC 0.949  captura@10% 75.1%
random_forest        PR-AUC 0.710  AUC 0.974  captura@10% 87.6%
xgboost              PR-AUC 0.729  AUC 0.974  captura@10% 89.3%
xgboost              PR-AUC 0.724  AUC 0.974  captura@10% 89.9%
xgboost              PR-AUC 0.740  AUC 0.971  captura@10% 85.8%
xgboost              PR-AUC 0.740  AUC 0.973  captura@10% 88.8%
xgboost              PR-AUC 0.737  AUC 0.970  captura@10% 88.8%
xgboost              PR-AUC 0.703  AUC 0.975  captura@10% 89.3%
xgboost              PR-AUC 0.739  AUC 0.973  captura@10% 88.8%
xgboost              PR-AUC 0.722  AUC 0.973  captura@10% 89.3%
xgboost              PR-AUC 0.735  AUC 0.970  captura@10% 88.8%
xgboost              PR-AUC 0.708  AUC 0.973  captura@10% 89.3%
Mejor: xgboost {'n_estimators': 500, 'max_depth': 4, 'learning_rate': 0.05, 'subsample': 0.85, 'colsample_bytree': 0.6, 'min_child_weight': 10}
```

## Modelo final: re-entrena con train+valid, evalúa en test (hold-out temporal) y registra en UC

```python
class ProbabilidadFraude(mlflow.pyfunc.PythonModel):
    """Devuelve P(fraude) en lugar de la clase, para que fe.score_batch entregue probabilidades."""

    def __init__(self, pipe, numericas):
        self.pipe = pipe
        self.numericas = numericas

    def predict(self, context, model_input):
        df = model_input.copy()
        for c in self.numericas:
            if c in df:
                df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
        return self.pipe.predict_proba(df)[:, 1]


final = construir(mejor["familia"], mejor["params"]).fit(X(trainval), y(trainval))
p_test = final.predict_proba(X(test))[:, 1]
m_test = metricas(y(test), p_test, test["monto_reclamado"], "test")

# Umbrales operativos (desde train+valid): Alto = top 10 %, Medio = top 25 %
p_tv = final.predict_proba(X(trainval))[:, 1]
umbral_alto, umbral_medio = float(np.quantile(p_tv, 0.90)), float(np.quantile(p_tv, 0.75))

with mlflow.start_run(run_name="modelo_final_fraude") as run:
    mlflow.log_input(feature_ds, context="features")
    mlflow.log_param("familia", mejor["familia"])
    mlflow.log_params({"etiquetas_siu_lakebase": N_SIU, "fuente_etiquetas_siu": ETIQUETAS_SIU})
    mlflow.log_params(mejor["params"])
    mlflow.log_params({"umbral_alto": round(umbral_alto, 4), "umbral_medio": round(umbral_medio, 4),
                       "n_trainval": len(trainval), "n_test": len(test)})
    mlflow.log_metrics(m_test)

    # Modelo sklearn (para mlflow.evaluate y explicabilidad SHAP en el scoring)
    test_eval = test.copy()
    sig = mlflow.models.infer_signature(X(trainval).head(100), final.predict_proba(X(trainval).head(100))[:, 1])
    mlflow.sklearn.log_model(final, "modelo_sklearn", signature=sig, input_example=X(trainval).head(3))
    eval_res = mlflow.evaluate(model=f"runs:/{run.info.run_id}/modelo_sklearn", data=test_eval, targets="fraude",
                               model_type="classifier",
                               evaluator_config={"log_model_explainability": False, "pos_label": 1})

    # Curva de captura (lenguaje SIU)
    orden = np.argsort(-p_test)
    yt = y(test).values[orden]
    pct_rev = np.arange(1, len(yt) + 1) / len(yt) * 100
    captura = np.cumsum(yt) / yt.sum() * 100
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(pct_rev, captura, color="#FF3621", lw=2.5, label="Modelo")
    ax.plot([0, 100], [0, 100], "--", color="#8a8a8a", label="Revisión aleatoria")
    for pct in (10, 20):
        ax.axvline(pct, color="#1B3139", lw=0.8, alpha=0.4)
        ax.annotate(f"{m_test[f'test_captura_top{pct}']:.0%} del fraude", (pct, m_test[f"test_captura_top{pct}"] * 100),
                    xytext=(pct + 3, m_test[f"test_captura_top{pct}"] * 100 - 8), fontsize=9)
    ax.set_xlabel("% de siniestros revisados por el SIU (ordenados por riesgo)")
    ax.set_ylabel("% del fraude capturado")
    ax.set_title("Curva de captura — hold-out temporal")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.2)
    mlflow.log_figure(fig, "curva_captura_siu.png")
    plt.close(fig)

    # SHAP — drivers globales del fraude
    if mejor["familia"] in ("xgboost", "random_forest"):
        import shap
        Xt = final.named_steps["prep"].transform(X(test))
        Xt = Xt.toarray() if hasattr(Xt, "toarray") else Xt
        nombres = [n.split("__", 1)[1] for n in final.named_steps["prep"].get_feature_names_out()]
        sv = shap.TreeExplainer(final.named_steps["modelo"]).shap_values(Xt)
        sv = sv[1] if isinstance(sv, list) else (sv[..., 1] if sv.ndim == 3 else sv)
        imp = pd.DataFrame({"feature": nombres, "shap_medio_abs": np.abs(sv).mean(axis=0)}).sort_values("shap_medio_abs", ascending=False)
        mlflow.log_table(imp, "importancia_shap.json")
        fig, ax = plt.subplots(figsize=(7, 6))
        top = imp.head(15).iloc[::-1]
        ax.barh(top["feature"], top["shap_medio_abs"], color="#FF3621")
        ax.set_title("Drivers de fraude (|SHAP| medio)")
        ax.set_xlabel("Impacto medio en la predicción")
        fig.tight_layout()
        mlflow.log_figure(fig, "shap_drivers_fraude.png")
        plt.close(fig)

    # Modelo registrado en UC, empaquetado con Feature Engineering (lookups por id_siniestro)
    fe.log_model(model=ProbabilidadFraude(final, NUMERICAS), artifact_path="modelo", flavor=mlflow.pyfunc,
                 training_set=ts_trainval, registered_model_name=MODEL_NAME)
    run_id = run.info.run_id

print({k: round(v, 3) for k, v in m_test.items()})
```

Output:
```text
/databricks/python/lib/python3.12/site-packages/mlflow/pyfunc/utils/data_validation.py:186: UserWarning: Add type hints to the `predict` method to enable data validation and automatic signature inference during model logging. Check https://mlflow.org/docs/latest/model/python_model.html#type-hint-usage-in-pythonmodel for more details.
  color_warning(
```

Output:
```text
2026/11/05 00:32:54 WARNING mlflow.data.spark_dataset: Encountered an unexpected exception while computing Spark dataset profile. Exception: An error occurred while calling o3314.sumApprox.
: org.apache.spark.SparkException: [FAILED_READ_FILE.NO_HINT] Error while reading file abfss:REDACTED_LOCAL_PART@unitydemo.dfs.core.windows.net/<UUID>/tables/<UUID>/part-00000-<UUID>-c000.zstd.parquet.  SQLSTATE: KD001
	at org.apache.spark.sql.errors.QueryExecutionErrors$.cannotReadFilesError(QueryExecutionErrors.scala:1151)
	at org.apache.spark.sql.execution.datasources.FileScanRDD$$anon$1$$anon$2.logErrorFileNameAndThrow(FileScanRDD.scala:885)
	at org.apache.spark.sql.execution.datasources.FileScanRDD$$anon$1$$anon$2.getNext(FileScanRDD.scala:840)
	at org.apache.spark.util.NextIterator.hasNext(NextIterator.scala:73)
	at org.apache.spark.sql.execution.datasources.FileScanRDD$$anon$1.$anonfun$prepareNextFile$1(FileScanRDD.scala:1090)
	at scala.concurrent.Future$.$anonfun$apply$1(Future.scala:659)
	at scala.util.Success.$anonfun$map$1(Try.scala:255)
	at scala.util.Success.map(Try.scala:213)
	at scala.concurrent.Future.$anonfun$map$1(Future.scala:292)
	at scala.concurrent.impl.Promise.liftedTree1$1(Promise.scala:33)
	at scala.concurrent.impl.Promise.$anonfun$transform$1(Promise.scala:33)
	at scala.concurrent.impl.CallbackRunnable.run(Promise.scala:64)
	at org.apache.spark.util.threads.SparkThreadLocalCapturingRunnable.$anonfun$run$1(SparkThreadLocalForwardingThreadPoolExecutor.scala:165)
	at scala.runtime.java8.JFunction0$mcV$sp.apply(JFunction0$mcV$sp.java:23)
	at com.databricks.util.LexicalThreadLocal$Handle.runWith(LexicalThreadLocal.scala:63)
	at org.apache.spark.util.threads.SparkThreadLocalCapturingHelper.$anonfun$runWithCaptured$6(SparkThreadLocalForwardingThreadPoolExecutor.scala:119)
	at com.databricks.sql.transaction.tahoe.mst.MSTThreadHelper$.runWithMstTxnId(MSTThreadHelper.scala:57)
	at org.apache.spark.util.threads.SparkThreadLocalCapturingHelper.$anonfun$runWithCaptured$5(SparkThreadLocalForwardingThreadPoolExecutor.scala:118)
	at com.databricks.spark.util.IdentityClaim$.withClaim(IdentityClaim.scala:48)
	at org.apache.spark.util.threads.SparkThreadLocalCapturingHelper.$anonfun$runWithCaptured$4(SparkThreadLocalForwardingThreadPoolExecutor.scala:117)
	at com.databricks.unity.UCSEphemeralState$Handle.runWith(UCSEphemeralState.scala:51)
	at org.apache.spark.util.threads.SparkThreadLocalCapturingHelper.runWithCaptured(SparkThreadLocalForwardingThreadPoolExecutor.scala:116)
	at org.apache.spark.util.threads.SparkThreadLocalCapturingHelper.runWithCaptured$(SparkThreadLocalForwardingThreadPoolExecutor.scala:93)
	at org.apache.spark.util.threads.SparkThreadLocalCapturingRunnable.runWithCaptured(SparkThreadLocalForwardingThreadPoolExecutor.scala:162)
	at org.apache.spark.util.threads.SparkThreadLocalCapturingRunnable.run(SparkThreadLocalForwardingThreadPoolExecutor.scala:165)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1136)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:635)
	at java.base/java.lang.Thread.run(Thread.java:840)
Caused by: Failure to initialize configuration for storage account unitydemo.dfs.core.windows.net: Invalid configuration value detected for fs.azure.account.keyInvalid configuration value detected for fs.azure.account.key
	at shaded.databricks.azurebfs.org.apache.hadoop.fs.azurebfs.services.SimpleKeyProvider.getStorageAccountKey(SimpleKeyProvider.java:52)
	at shaded.databricks.azurebfs.org.apache.hadoop.fs.azurebfs.AbfsConfiguration.getStorageAccountKey(AbfsConfiguration.java:730)
	at shaded.databricks.azurebfs.org.apache.hadoop.fs.azurebfs.AzureBlobFileSystemStore.initializeClient(AzureBlobFileSystemStore.java:2356)
	at shaded.databricks.azurebfs.org.apache.hadoop.fs.azurebfs.AzureBlobFileSystemStore.<init>(AzureBlobFileSystemStore.java:297)
	at shaded.databricks.azurebfs.org.apache.hadoop.fs.azurebfs.AzureBlobFileSystem.initialize(AzureBlobFileSystem.java:261)
	at com.databricks.common.filesystem.LokiABFS.initialize(LokiABFS.scala:38)
	at com.databricks.sql.io.LokiFileSystem$.$anonfun$getLokiFS$1(LokiFileSystem.scala:109)
	at com.databricks.sql.io.FileSystemCache.getOrCompute(FileSystemCache.scala:60)
	at com.databricks.sql.io.LokiFileSystem$.getLokiFS(LokiFileSystem.scala:105)
	at com.databricks.sql.io.LokiFileSystem.initialize(LokiFileSystem.scala:198)
	at org.apache.hadoop.fs.FileSystem.createFileSystem(FileSystem.java:3611)
	at org.apache.hadoop.fs.FileSystem.get(FileSystem.java:554)
	at org.apache.hadoop.fs.Path.getFileSystem(Path.java:365)
	at com.databricks.unity.SAM.createDelegate(SAM.scala:461)
	at com.databricks.unity.SAM.createDelegate$(SAM.scala:442)
	at com.databricks.unity.ClusterDefaultSAM$.createDelegate(SAM.scala:621)
	at com.databricks.sql.acl.fs.CredentialScopeFileSystem.createDelegate(CredentialScopeFileSystem.scala:74)
	at com.databricks.sql.acl.fs.CredentialScopeFileSystem.$anonfun$setDelegates$1(CredentialScopeFileSystem.scala:127)
	at com.databricks.sql.acl.fs.Lazy.apply(DelegatingFileSystem.scala:310)
	at com.databricks.sql.acl.fs.CredentialScopeFileSystem.getReadDelegate(CredentialScopeFileSystem.scala:87)
	at com.databricks.sql.acl.fs.CredentialScopeFileSystem.openFileWithOptions(CredentialScopeFileSystem.scala:187)
	at org.apache.hadoop.fs.FileSystem$FSDataInputStreamBuilder.build(FileSystem.java:4913)
	at com.databricks.spark.util.DatabricksRangeFetcher.fetchRange(DatabricksRangeFetcher.scala:73)
	at com.databricks.io.RangeFetcher$.fetch(RangeFetcher.scala:104)
	at com.databricks.io.RangeFetcher.fetch(RangeFetcher.scala)
	at com.databricks.sql.io.HDFSStorage$ReadFileImpl.lambda$fetchRange$0(HDFSStorage.java:105)
	at com.databricks.sql.io.Futures.run(Futures.java:74)
	at com.databricks.sql.io.PendingFutures.submit(PendingFutures.java:64)
	at com.databricks.sql.io.Storage$R
```

Output:
```text
/databricks/python/lib/python3.12/site-packages/mlflow/types/utils.py:452: UserWarning: Hint: Inferred schema contains integer column(s). Integer columns in Python cannot represent missing values. If your input data contains missing values at inference time, it will be encoded as floats and will cause a schema enforcement error. The best way to avoid this problem is to infer the model schema based on a realistic data sample (training dataset) that includes missing values. Alternatively, you can declare integer columns as doubles (float64) whenever these columns may have missing values. See `Handling Integers With Missing Values <https://www.mlflow.org/docs/latest/models.html#handling-integers-with-missing-values>`_ for more details.
  warnings.warn(
2026/11/05 00:33:04 INFO mlflow.models.evaluation.utils.trace: Auto tracing is temporarily enabled during the model evaluation for computing some metrics and debugging. To disable tracing, call `mlflow.autolog(disable=True)`.
2026/11/05 00:33:04 WARNING mlflow.models.evaluation.evaluators.classifier: According to the evaluation dataset label values, the model type looks like None, but you specified model type 'classifier'. Please verify that you set the `model_type` and `dataset` arguments correctly.
2026/11/05 00:33:04 INFO mlflow.models.evaluation.evaluators.classifier: The evaluation dataset is inferred as binary dataset, positive label is 1, negative label is 0.
2026/11/05 00:33:04 INFO mlflow.models.evaluation.default_evaluator: Testing metrics on first row...
2026/11/05 00:33:15 WARNING databricks.ml_features.utils.signature_utils: The following features will not be included in the input schema because their data types are not supported by MLflow model signatures: taller_ratio_presupuesto_prom (decimal(22,7)). These features cannot be overridden during model serving.
/databricks/python/lib/python3.12/site-packages/mlflow/pyfunc/__init__.py:3212: UserWarning: An input example was not provided when logging the model. To ensure the model signature functions correctly, specify the `input_example` parameter. See https://mlflow.org/docs/latest/model/signatures.html#model-input-example for more details about the benefits of using input_example.
  color_warning(
```

Output:
```text
Registered model 'demo_catalog.seguros_ml.modelo_fraude_siniestros' already exists. Creating a new version of this model...
```

Output:
```text
{'test_roc_auc': 0.968, 'test_pr_auc': 0.737, 'test_precision_top5': 0.808, 'test_captura_top5': 0.492, 'test_monto_fraude_capturado_top5_pct': 0.503, 'test_precision_top10': 0.715, 'test_captura_top10': 0.872, 'test_monto_fraude_capturado_top10_pct': 0.866, 'test_precision_top20': 0.383, 'test_captura_top20': 0.936, 'test_monto_fraude_capturado_top20_pct': 0.954}
```

Output:
```text
Created version '5' of model 'demo_catalog.seguros_ml.modelo_fraude_siniestros'.
```

Output:
```text
<Figure size 1050x700 with 0 Axes>
```

## Compuerta de calidad: champion / challenger

```python
version = str(max(int(v.version) for v in client.search_model_versions(f"name = '{MODEL_NAME}'") if v.run_id == run_id))
nuevo_pr = m_test["test_pr_auc"]
# El champion actual se re-evalúa sobre el MISMO test de hoy: comparación justa aunque los datos hayan cambiado.
try:
    champ = client.get_model_version_by_alias(MODEL_NAME, "champion")
    champ_sk = mlflow.sklearn.load_model(f"runs:/{champ.run_id}/modelo_sklearn")
    champ_pr = average_precision_score(y(test), champ_sk.predict_proba(X(test))[:, 1])
except Exception as e:
    print("Sin champion comparable:", e)
    champ, champ_pr = None, -1.0

alias = "champion" if nuevo_pr >= champ_pr else "challenger"
client.set_registered_model_alias(MODEL_NAME, alias, version)
print(f"Versión {version}: PR-AUC test {nuevo_pr:.3f} vs champion re-evaluado {champ_pr:.3f} → alias '{alias}'")
if alias == "champion":
    client.set_model_version_tag(MODEL_NAME, version, "champion_anterior_pr_auc_mismo_test", f"{champ_pr:.4f}")

client.update_registered_model(MODEL_NAME, description=(
    "Detección de fraude en siniestros de autos (aseguradora FSI). Entrada: id_siniestro (las features se buscan en "
    f"{FEATURE_TABLE}). Salida: probabilidad de fraude. Niveles: Alto = top 10 % de riesgo, Medio = top 25 %. "
    "Entrenado con dictámenes SIU; split temporal."))
client.update_model_version(MODEL_NAME, version, description=(
    f"{mejor['familia']} {mejor['params']} | test PR-AUC {nuevo_pr:.3f}, ROC-AUC {m_test['test_roc_auc']:.3f}, "
    f"captura top 10 % = {m_test['test_captura_top10']:.0%}, top 20 % = {m_test['test_captura_top20']:.0%}"))
for k, v in {"familia": mejor["familia"], "umbral_alto": f"{umbral_alto:.4f}", "umbral_medio": f"{umbral_medio:.4f}",
             "test_pr_auc": f"{nuevo_pr:.4f}", "test_captura_top10": f"{m_test['test_captura_top10']:.4f}",
             "caso_uso": "fraude_siniestros_autos", "dueno": "SIU / Ciencia de Datos"}.items():
    client.set_model_version_tag(MODEL_NAME, version, k, v)

dbutils.jobs.taskValues.set(key="model_version", value=version)
dbutils.notebook.exit(f"version={version} alias={alias} test_pr_auc={nuevo_pr:.3f}")
```

Output:
```text
version=5 alias=challenger test_pr_auc=0.737
```
