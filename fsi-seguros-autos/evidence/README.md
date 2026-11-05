# Execution evidence (text, not screenshots)

Everything in this folder is **real output captured from the running build** in an Azure Databricks workspace:
executed notebooks with their cell outputs, job-run logs, query results, MLflow registry and trace data, Genie answers
and app/deployment status. Identifiers were sanitized the same way as the rest of the repo; values were not edited.

Capture date: 2026-11-04/05 (ML job run, pipeline update and queries) and 2026-10-18/19 (agent evaluation and tests).
The capture scripts are in [`scripts/`](scripts/) so the evidence can be regenerated.

## Map: requirement → evidence

| Stage | Evidence file | What it proves (from the actual output) |
|---|---|---|
| **Raw data → Lakeflow** | [`queries/01_lakeflow_pipeline.md`](queries/01_lakeflow_pipeline.md) | Pipeline event log: update `COMPLETED` on 2026-11-05; rows written per table (e.g. `bronze_siniestros` 27,674, `bronze_polizas` 100,025, Auto Loader app tables); expectations with passed/failed records; quarantine by rule; federated sources read in place, incl. a cross-system join |
| **Unity Catalog** | [`queries/02_governance.md`](queries/02_governance.md) | 7 ABAC policies; governed tags on columns; **the same query as 3 roles**: SIU → 60,000 clients with full PII · ACTUARIO → 60,000 with masked name/RFC · AGENTE_REGIONAL Norte → 10,655 rows, 1 region; sandbox copy stays masked |
| **ML** | [`notebooks/ml_01_features_training.ipynb`](notebooks/ml_01_features_training.ipynb) (+ `.md`) | Executed training notebook: feature table 36,726 rows; 89 SIU labels from Lakebase; train/valid/test sizes; 12 candidate models with PR-AUC/AUC; gate result `version=5 alias=challenger test_pr_auc=0.737` |
| | [`notebooks/ml_02_scoring_batch.ipynb`](notebooks/ml_02_scoring_batch.ipynb) (+ `.md`) | Executed scoring notebook: champion v2 thresholds; `3722 siniestros abiertos calificados` |
| | [`queries/06_mlflow.md`](queries/06_mlflow.md) | UC model versions 1–5 with aliases (champion v2, challenger v5), test metrics, nested model-selection runs |
| | [`queries/03_ml_scoring.md`](queries/03_ml_scoring.md) | Scoring by risk tier (167 high-risk claims, MXN 14.35M claimed), top claims with SHAP reasons, model vs SIU verdicts |
| **Gen AI** | [`queries/04_genai.md`](queries/04_genai.md) | `ai_parse_document` + `ai_query` over 240 PDFs (83 with inconsistencies) with sample extracted fields; agent tool (UC function) output; model-service inference table with calls per day/model |
| | [`run_logs/agent_end_to_end_test.log`](run_logs/agent_end_to_end_test.log) | Job-run stdout: the agent investigates a claim (tool calls + full assessment), proposes a case (human-in-the-loop interrupt), approval writes the case, rejection writes nothing, regional ABAC holds |
| | [`notebooks/agent_01_evaluation.ipynb`](notebooks/agent_01_evaluation.ipynb) · [`agent_02_production_monitoring.ipynb`](notebooks/agent_02_production_monitoring.ipynb) | Executed `mlflow.genai.evaluate` with custom LLM judges and the production-monitoring setup; aggregate metrics also in `queries/06_mlflow.md` |
| **Lakebase** | [`queries/05_lakebase.md`](queries/05_lakebase.md) | Synced table `SYNCED_TABLE_ONLINE`, Delta vs Lakebase row counts; case file contents; agent checkpoint tables created by the app's service principal; **RLS tests** (3 inserts rejected with `violates row-level security policy`, default-deny = 0 rows); CDF `STREAMING` and Postgres = Delta counts (160 cases / 384 notes) |
| **Genie** | [`queries/07_genie.md`](queries/07_genie.md) | 6 natural-language questions (one follow-up) with Genie's answer text, generated SQL and result tables |
| **Databricks App** | [`queries/08_app.md`](queries/08_app.md) | App `RUNNING`, bound resources (SQL warehouse + Lakebase), user scopes (`sql`, `dashboards.genie`), deployments, log tail |
| | [`queries/06_mlflow.md`](queries/06_mlflow.md) (traces) · [`queries/05_lakebase.md`](queries/05_lakebase.md) | Traces with `origin=app` from real use of the app (question + agent answer), and the note and session the app wrote to Lakebase |
| **Dashboard** | [`queries/09_dashboard.md`](queries/09_dashboard.md) | Dashboard dataset SQL executed: premium MXN 1,995M, loss ratio 55.7%, fraud 6.9% (MXN 145.6M), reserve sufficiency MXN 44.7M (62%); published with `embed_credentials=false` |

## How the figures tie together

The business-case numbers in the deck and README come from these outputs: loss ratio 55.7% and fraud 6.9% (`09_dashboard.md`),
~80–90% of fraud captured in the top 10% (`ml_01_features_training`), MXN 45M reserve redundancy (`09_dashboard.md`), 89 SIU labels
flowing back through Lakebase CDF (`05_lakebase.md`, `ml_01_features_training`).

> Data is synthetic (fixed-seed generator calibrated to the Mexican auto-insurance market); model metrics are optimistic versus real data.
