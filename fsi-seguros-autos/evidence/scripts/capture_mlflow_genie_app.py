"""Captures MLflow (model registry, runs, agent evaluation, traces), Genie Q&A and Databricks App evidence as Markdown.
Usage: python3 capture_mlflow_genie_app.py <mlflow|genie|app> <output.md>"""
import datetime, json, subprocess, sys

P = ["-p", "DEFAULT"]
MODEL = "demo_catalog.seguros_ml.modelo_fraude_siniestros"
EXP_ML, EXP_AGENT = "<ID>", "<ID>"
GENIE = "<ID>"
APP = "seguros-agente-siu"


def api(method, path, body=None):
    cmd = ["databricks", "api", method, path] + P + (["--json", json.dumps(body)] if body is not None else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(r.stdout) if r.stdout.strip() else {"_error": r.stderr[:300]}


def ts(ms):
    return datetime.datetime.fromtimestamp(int(ms) / 1000).astimezone().strftime("%Y-%m-%d %H:%M") if ms else ""


def table(cols, rows):
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(str(c).replace("|", "/").replace("\n", " ")[:180] for c in r) + " |" for r in rows]
    return "\n".join(out)


def header(title, intro):
    now = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    return [f"# {title}\n", f"_Captured {now} from the live workspace (REST APIs). Values are the real API output._\n", intro + "\n"]


def mlflow_section():
    o = header("Evidence · MLflow model registry, training runs and agent evaluation",
               "Fraud model versions in Unity Catalog, the champion/challenger gate, training metrics, and the SIU agent's evaluation and traces.")
    vers = api("get", f"/api/2.1/unity-catalog/models/{MODEL}/versions?max_results=50").get("model_versions", [])
    aliases = {a: api("get", f"/api/2.1/unity-catalog/models/{MODEL}/aliases/{a}").get("version") for a in ("champion", "challenger")}
    rows = []
    for v in sorted(vers, key=lambda x: int(x["version"])):
        run = api("get", f"/api/2.0/mlflow/runs/get?run_id={v.get('run_id')}").get("run", {}) if v.get("run_id") else {}
        m = {x["key"]: x["value"] for x in run.get("data", {}).get("metrics", [])}
        p = {x["key"]: x["value"] for x in run.get("data", {}).get("params", [])}
        al = [a for a, n in aliases.items() if str(n) == str(v["version"])]
        rows.append([v["version"], ",".join(al), ts(v.get("created_at")), v.get("status"),
                     round(m["test_pr_auc"], 3) if "test_pr_auc" in m else "", round(m["test_roc_auc"], 3) if "test_roc_auc" in m else "",
                     p.get("familia", ""), p.get("etiquetas_siu_lakebase", "")])
    o += ["## Registered model versions (Unity Catalog)\n", f"Model `{MODEL}` · aliases: champion = v{aliases['champion']}, challenger = v{aliases['challenger']}\n",
          table(["version", "alias", "created", "status", "test PR-AUC", "test ROC-AUC", "family", "SIU labels used"], rows), ""]
    runs = api("post", "/api/2.0/mlflow/runs/search", {"experiment_ids": [EXP_ML], "order_by": ["attributes.start_time DESC"], "max_results": 1,
                                                       "filter": "attributes.run_name = 'seleccion_modelo_fraude'"}).get("runs", [])
    if runs:
        parent = runs[0]["info"]["run_id"]
        kids = api("post", "/api/2.0/mlflow/runs/search", {"experiment_ids": [EXP_ML], "max_results": 50,
                                                           "filter": f"tags.mlflow.parentRunId = '{parent}'"}).get("runs", [])
        kr = []
        for k in kids:
            m = {x["key"]: x["value"] for x in k["data"].get("metrics", [])}
            pr = {x["key"]: x["value"] for x in k["data"].get("params", [])}
            kr.append([k["info"].get("run_name"), pr.get("familia", ""), round(m.get("valid_pr_auc", 0), 3), round(m.get("valid_roc_auc", 0), 3),
                       f"{m.get('valid_captura_fraude_top10', m.get('valid_captura_top10', 0)) * 100:.1f}%" if m else ""])
        kr.sort(key=lambda r: -r[2])
        o += ["## Model selection (nested MLflow runs, latest training)\n", f"Parent run `seleccion_modelo_fraude` started {ts(runs[0]['info']['start_time'])} · {len(kids)} candidate models\n",
              table(["run", "family", "valid PR-AUC", "valid ROC-AUC", "fraud captured @10%"], kr[:12]), ""]
    ev = api("post", "/api/2.0/mlflow/runs/search", {"experiment_ids": [EXP_AGENT], "order_by": ["attributes.start_time DESC"], "max_results": 5}).get("runs", [])
    er = []
    for r in ev:
        m = {x["key"]: x["value"] for x in r["data"].get("metrics", [])}
        keep = {k: round(v, 3) for k, v in m.items() if "/mean" in k or k.endswith("_mean") or "value" in k}
        if keep:
            er.append([r["info"].get("run_name"), ts(r["info"]["start_time"]), json.dumps(keep, ensure_ascii=False)[:400]])
    o += ["## SIU agent evaluation runs (mlflow.genai.evaluate)\n", table(["run", "started", "aggregate metrics"], er) if er else "_no metric runs found_", ""]
    tr = api("post", "/api/3.0/mlflow/traces/search", {"locations": [{"type": "MLFLOW_EXPERIMENT", "mlflow_experiment": {"experiment_id": EXP_AGENT}}],
                                                        "max_results": 8, "order_by": ["timestamp_ms DESC"]})
    traces = tr.get("traces", [])
    o.append("## Latest SIU agent traces (MLflow Tracing): request, response preview and assessments\n")
    for t in traces[:6]:
        info = t.get("info", t)
        tags = info.get("tags", {}) or {}
        meta = info.get("trace_metadata", {}) or {}
        assess = info.get("assessments", []) or []
        a_txt = "; ".join(f"{a.get('assessment_name') or a.get('name')}={json.dumps((a.get('feedback') or {}).get('value'), ensure_ascii=False)}" for a in assess)[:500]
        req = str(info.get("request_preview") or info.get("request", ""))[:220]
        resp = str(info.get("response_preview") or info.get("response", ""))[:500]
        o.append(f"- **{info.get('request_time') or ts(info.get('timestamp_ms'))}** · origin=`{tags.get('origen', '')}` · state={info.get('state', '')} · "
                 f"duration={info.get('execution_duration') or info.get('execution_time_ms', '')}\n  - request: `{req}`\n  - response: {resp}\n  - assessments: {a_txt or '(none)'}")
    o.append("")
    return o


def genie_section():
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "agente" / "app"))
    from databricks.sdk import WorkspaceClient
    from genie_uc import preguntar
    w = WorkspaceClient(profile="DEFAULT")
    o = header("Evidence · Genie (natural-language queries over governed metric views)",
               f"Genie space `{GENIE}` queried through the Genie Conversation API with the user's identity (same code path as the app's 'Pregunta a Genie' tab, `agente/app/genie_uc.py`).")
    conv = None
    for q, follow in [("¿Cuál es la siniestralidad por paquete y cuál es el más rentable?", False),
                      ("¿Qué tanto confirma el SIU los siniestros que el modelo marca como riesgo alto?", False),
                      ("¿En qué tipos de taller se concentra el fraude?", False),
                      ("¿Cuántos casos SIU hay por estatus?", False),
                      ("¿Y solo en la región Centro?", True),
                      ("¿Nuestras reservas son suficientes? ¿En qué cobertura sobra o falta?", False)]:
        r = preguntar(w, GENIE, q, conv if follow else None)
        conv = r["conversation_id"]
        o.append(f"## Q: {q}" + (" _(follow-up in the same conversation)_" if follow else "") + "\n")
        o.append(f"Status: `{r['estado']}`" + (f" · error: {r['error']}" if r.get("error") else "") + "\n")
        for t in r["texto"]:
            o.append("> " + t.replace("\n", "\n> ") + "\n")
        if r.get("sql"):
            o.append("Generated SQL:\n```sql\n" + r["sql"].strip() + "\n```\n")
        if r.get("df") is not None and not r["df"].empty:
            df = r["df"].head(15)
            o.append("Result:\n\n" + table(list(df.columns), df.values.tolist()) + "\n")
    return o


def app_section():
    o = header("Evidence · Databricks App (business surface)", f"App `{APP}`: Streamlit + LangGraph SIU agent, Lakebase case file and the 'Pregunta a Genie' tab.")
    a = api("get", f"/api/2.0/apps/{APP}")
    o += ["## App status\n", "```json\n" + json.dumps({k: a.get(k) for k in ("name", "app_status", "compute_status", "user_api_scopes", "effective_user_api_scopes")}, indent=1, ensure_ascii=False)
          + "\n```\n", "## Resources bound to the app\n", "```json\n" + json.dumps(a.get("resources"), indent=1) + "\n```\n"]
    d = api("get", f"/api/2.0/apps/{APP}/deployments").get("app_deployments", [])[:5]
    o += ["## Recent deployments\n", table(["deployment", "created", "state", "message"],
                                         [[x.get("deployment_id"), x.get("create_time"), x["status"].get("state"), x["status"].get("message")] for x in d]), ""]
    logs = subprocess.run(["databricks", "apps", "logs", APP, "--tail-lines", "60"] + P, capture_output=True, text=True, cwd="/tmp").stdout
    keep = [l for l in logs.splitlines() if "Requirement already" not in l and "━" not in l][-30:]
    o += ["## App log tail (`databricks apps logs`)\n", "```text\n" + "\n".join(keep) + "\n```\n"]
    return o


if __name__ == "__main__":
    fn = {"mlflow": mlflow_section, "genie": genie_section, "app": app_section}[sys.argv[1]]
    open(sys.argv[2], "w").write("\n".join(fn()))
    print("wrote", sys.argv[2])
