# Aseguradora FSI Autos — Demo script and roleplay prep

> Format: **tell → show → tell**, ~15 minutes plus Q&A. Two AI personas will probe: a **business stakeholder** (CFO / Head of SIU) and a **technical stakeholder** (Enterprise Architect / CDO).
> Rule of thumb: every "show" beat starts with the business question it answers and ends with the number it moves.

## Before you start (5 min checklist)

- [ ] Start the SQL warehouse `seguros-demo-wh` (first query wakes it; avoid a cold start on camera).
- [ ] Your role in `usuarios_rol` = **SIU** (`gobierno/03_demo_personas.sql`, last cell).
- [ ] Tabs open, in order: deck (slide 2) · pipeline graph `seguros_medallion` · Catalog Explorer `dim_cliente` (tags) · app `seguros-agente-siu` · MLflow experiment `seguros_fraude_siniestros` · Genie space · dashboard.
- [ ] Pick a high-risk claim without an open case for the live investigation (e.g. `S202600000146`).
- [ ] Say once, early: **"All data is synthetic, calibrated to the Mexican auto market. Figures are indicative."**

---

## 1. TELL — the outcome (2 min)

> "Aseguradora FSI Autos has the data to fight fraud and manage reserves, but it lives in 6–7 systems, an Oracle DWH from 2011 with ~55,000 columns, and a separate AWS lake. Every area computes its own loss ratio, PII leaves in extracts, and about 1 in 4 fraudulent claims is still paid.
> What we built shows a conservative **MXN 25–35M in year one** on the auto book alone: **0.5–1 point of loss ratio** from catching more fraud, **~MXN 15M of reserve capital** freed, and the actuarial close going from **~10 hours to under 1**. Let me show you the data journey that produces those numbers, end to end."

## 2. SHOW — the integrated journey (10 min)

| # | Business question | What you click | What you say | Number it moves |
|---|---|---|---|---|
| 1 | *Can we use Oracle and AWS without another migration?* | Pipeline graph `seguros_medallion` → bronze tables from the two foreign catalogs + Auto Loader streaming tables | "Lakeflow reads the sources in place through federation and lands app telemetry with Auto Loader. Nothing is copied by hand." | 0 extracts to start |
| 2 | *Can we trust the data?* | Silver expectations panel → `cuarentena_registros` | "Bad records are not dropped silently: they go to quarantine with the rule that failed. Nothing gets lost." | 748 records quarantined, 0 lost |
| 3 | *Who sees what?* | Run the same `dim_cliente` query as SIU → switch role to AGENTE_REGIONAL Norte → rerun | "Same query, same table, different answer. Unity Catalog ABAC masks PII and filters by region, and that follows the data to BI, Genie, ML and the agent." | 60K rows full PII → 10.6K rows masked |
| 4 | *Can AI find fraud?* | MLflow experiment → champion vs challenger, SHAP drivers | "XGBoost on governed features. The top 10% of claims holds ~80% of fraud. A new model only replaces the champion if it beats it on the same hold-out." | ~8× vs random review |
| 5 | *Can investigators act on it?* | App → SIU queue ("read from Lakebase in X ms") → investigate the claim → agent calls tools → "open a case" → approval card | "The queue is served from Lakebase, synced from the lakehouse. The agent uses governed UC functions with *my* identity, and a human approves every case." | +30% SIU capacity target |
| 6 | *What if I leave?* | Close the tab with an approval pending → reopen → "My investigations" → approve | "Agent memory lives in Lakebase. The approval survives." | — |
| 7 | *Does the human verdict improve the model?* | Cases tab → close as *Fraud confirmed* → Catalog `seguros_siu_expediente.casos` shows it seconds later | "Lakebase CDF writes the change back to Delta. The MLOps job retrains with these verdicts as labels." | 89 human labels in the last run |
| 8 | *Can executives just ask?* | Genie: "¿Qué tanto confirma el SIU los siniestros que el modelo marca como riesgo alto?" then dashboard page *Reservas* | "Genie and the dashboard read the same certified metric views: one definition of loss ratio and IBNR." | Reserve redundancy MXN 45M |

## 3. TELL — the value and the ask (2 min)

> "So: raw data in, governed once, served operationally, made intelligent, queryable in Spanish, and surfaced in an app the SIU actually uses, with the investigator's decision flowing back to make the model better.
> That is worth a conservative MXN 25–35M in year one. The ask is a **90-day pilot**: foundation in 30 days, fraud and SIU in 60, actuarial and scale in 90, with success metrics we agree today: fraud capture, time per case, close time and extracts retired."

---

## Objection handling

### Business stakeholder (CFO / Head of SIU)

| Objection | Answer |
|---|---|
| "Are these numbers real?" | "They come from a working demo on synthetic data calibrated to the Mexican auto market, and I kept them conservative: I count only a third of the reserve redundancy and half a point of loss ratio at the low end. The pilot's first deliverable is to recompute them on your closed claims." |
| "What does it cost?" | "Consumption-based. The pilot runs on serverless compute and a small Lakebase (0.5–2 CU, scales to zero). We size it with your volumes in week 1; the fraud lever alone is MXN 10–20M a year, so the payback question is about weeks, not years." |
| "We already have Denodo." | "Keep it. Denodo can consume Databricks with each user's identity, so it inherits the same governance. What it doesn't give you is quality rules, lineage, ML and agents on top; that's what we add." |
| "Will investigators trust an AI?" | "The agent never decides. It ranks, gathers evidence and drafts; the investigator approves every case, and each answer is traced and scored by LLM judges. Their verdicts retrain the model, so it learns from them." |
| "What about PII and the regulator?" | "PII is masked by policy, not by copies. The operational layer gets no PII at all. Every access is audited, and the same query returns different answers per role, which is what an auditor wants to see." |
| "How fast do we see value?" | "Governed gold layer in 30 days, fraud model in shadow mode with your SIU in 60, actuarial and executive Genie in 90." |
| "Why not a point fraud vendor?" | "A vendor scores claims; it doesn't fix the five versions of the loss ratio or the extracts. Here fraud, reserves and reporting run on the same governed data, and the model is yours." |

### Technical stakeholder (Enterprise Architect / CDO)

| Objection | Answer |
|---|---|
| "Federation won't perform at scale." | "Federation is the on-ramp, not the end state. Bronze materializes what we use, with query pushdown, so we don't hit Oracle for every dashboard. Hot tables can move to managed ingestion later without changing the gold layer." |
| "Why Lakebase and not our own Postgres?" | "Synced tables from Delta with no ETL code, OAuth with Databricks identities, scale to zero, branching, and CDF back to Delta. Your own Postgres would need a pipeline in each direction." |
| "Isn't RLS in Postgres a second governance model?" | "It's enforcement, not a second source of truth. Role and region come from Unity Catalog through the user's identity; Postgres applies them. And the operational table carries no PII by design." |
| "Model risk: drift, bias, explainability?" | "Every model is registered in UC with lineage to its feature table, SHAP drivers per claim, a champion/challenger gate, and SIU verdicts as ongoing labels. Drift monitoring and fairness checks are part of the pilot scope." |
| "LLM lock-in?" | "The agent calls a UC model service through AI Gateway. Swapping the model is a routing change in Unity Catalog, not a code change, and every call lands in an inference table." |
| "Some pieces are Beta (Lakebase CDF)." | "Correct, and it's flagged. The fallback is a scheduled snapshot of the Lakebase tables via the UC catalog; the business flow doesn't change." |
| "How does this compare with Snowflake?" | "Focus on what we showed: ingestion with quality, governance, ML, agents with evaluation, an operational database and the app on one platform and one permission model, on open formats. Happy to do a side-by-side on your criteria." |

---

## Rehearsal notes

- Keep each show beat under 75 seconds. If something is slow, narrate the business point and move on.
- If the agent's answer is long, read only the verdict line.
- Backup if the app misbehaves: show the same flow in the dashboard (page *Siniestros y Fraude*) and the MLflow traces.
- End on the ask, not on the architecture slide.
