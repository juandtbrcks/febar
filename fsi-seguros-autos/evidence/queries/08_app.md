# Evidence · Databricks App (business surface)

_Captured 2026-11-05 13:54 CST from the live workspace (REST APIs). Values are the real API output._

App `seguros-agente-siu`: Streamlit + LangGraph SIU agent, Lakebase case file and the 'Pregunta a Genie' tab.

## App status

```json
{
 "name": "seguros-agente-siu",
 "app_status": {
  "message": "App has status: App is running",
  "state": "RUNNING"
 },
 "compute_status": {
  "message": "App compute is running.",
  "state": "ACTIVE"
 },
 "user_api_scopes": [
  "dashboards.genie",
  "sql"
 ],
 "effective_user_api_scopes": [
  "dashboards.genie",
  "iam.access-control:read",
  "iam.current-user:read",
  "sql"
 ]
}
```

## Resources bound to the app

```json
[
 {
  "name": "sql-warehouse",
  "sql_warehouse": {
   "id": "<WAREHOUSE_ID>",
   "permission": "CAN_USE"
  }
 },
 {
  "name": "lakebase",
  "postgres": {
   "branch": "projects/seguros-siu/branches/production",
   "database": "projects/seguros-siu/branches/production/databases/siu",
   "permission": "CAN_CONNECT_AND_CREATE"
  }
 }
]
```

## Recent deployments

| deployment | created | state | message |
|---|---|---|---|
| <ID> | 2026-11-05T19:33:40Z | SUCCEEDED | App started successfully |
| <ID> | 2026-11-05T19:32:01Z | FAILED | App deployment failed unexpectedly. |
| <ID> | 2026-11-05T19:30:18Z | FAILED | App deployment failed unexpectedly. |
| <ID> | 2026-11-05T00:21:44Z | SUCCEEDED | App started successfully |
| <ID> | 2026-11-05T00:01:58Z | SUCCEEDED | App started successfully |

## App log tail (`databricks apps logs`)

```text
2026-11-05T19:32:36Z [BUILD] [INFO] Starting app with command: [streamlit run app.py --server.headless true]
2026-11-05T19:32:37Z [APP] 
  You can now view your Streamlit app in your browser.
2026-11-05T19:32:37Z [APP] 
  URL: http://0.0.0.0:8000
2026-11-05T19:32:38Z [BUILD] [INFO] Deployment <ID> ended in 4.613317597s
2026-11-05T19:32:38Z [BUILD] [INFO] Deployment successful
2026-11-05T19:33:44Z [BUILD] [INFO] Starting deployment <ID>...
2026-11-05T19:33:44Z [APP]   Stopping...
2026-11-05T19:33:44Z [BUILD] [INFO] Downloading source code from /Workspace/Users/<UUID>/src/<ID>
2026-11-05T19:33:44Z [BUILD] [INFO] Updated file: python/source_code/lakebase.py
2026-11-05T19:33:45Z [BUILD] [INFO] Updated file: python/source_code/app.py
2026-11-05T19:33:45Z [BUILD] [INFO] Updated file: python/source_code/app.yaml
2026-11-05T19:33:45Z [BUILD] [INFO] Updated file: python/source_code/agente_siu.py
2026-11-05T19:33:45Z [BUILD] [INFO] Updated file: python/source_code/sql_uc.py
2026-11-05T19:33:45Z [BUILD] [INFO] Updated file: python/source_code/requirements.txt
2026-11-05T19:33:45Z [BUILD] [INFO] Updated file: python/source_code/genie_uc.py
2026-11-05T19:33:45Z [BUILD] [INFO] Updated file: python/source_code/__pycache__/agente_siu.cpython-312.pyc
2026-11-05T19:33:45Z [BUILD] [INFO] Updated file: python/source_code/__pycache__/app.cpython-312.pyc
2026-11-05T19:33:45Z [BUILD] [INFO] Updated file: python/source_code/__pycache__/lakebase.cpython-312.pyc
2026-11-05T19:33:46Z [BUILD] [INFO] Requirements have not changed. Skipping installation.
2026-11-05T19:33:46Z [BUILD] [INFO] Starting app with command: [streamlit run app.py --server.headless true]
2026-11-05T19:33:47Z [APP] 
  You can now view your Streamlit app in your browser.
2026-11-05T19:33:47Z [APP] 
  URL: http://0.0.0.0:8000
2026-11-05T19:33:48Z [BUILD] [INFO] Deployment <ID> ended in 4.360464605s
2026-11-05T19:33:48Z [BUILD] [INFO] Deployment successful
2026-11-05T19:34:26Z [HTTP] 75.125.239.194 - 143268355149365@<WORKSPACE_ID> [05/Nov/2026:19:34:25 +0000] "GET /_stcore/health HTTP/1.1" 304 0 "https://<APP_URL>/" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
2026-11-05T19:34:26Z [HTTP] 75.125.239.194 - 143268355149365@<WORKSPACE_ID> [05/Nov/2026:19:34:25 +0000] "GET /_stcore/host-config HTTP/1.1" 304 0 "https://<APP_URL>/" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
```
