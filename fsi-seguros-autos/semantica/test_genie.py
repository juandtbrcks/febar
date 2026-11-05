"""Hace preguntas al Genie space y muestra el SQL generado + primeras filas. Run: python3 test_genie.py "pregunta" ..."""
import json, subprocess, sys, time
SID = open("genie_space_id.txt").read().strip()
api = lambda m, p, b=None: json.loads(subprocess.run(["databricks", "api", m, p, "-p", "DEFAULT"] + (["--json", json.dumps(b)] if b else []), capture_output=True, text=True).stdout or "{}")
for q in sys.argv[1:]:
    r = api("post", f"/api/2.0/genie/spaces/{SID}/start-conversation", {"content": q})
    cid, mid = r["conversation_id"], r["message_id"]
    for _ in range(60):
        time.sleep(4)
        m = api("get", f"/api/2.0/genie/spaces/{SID}/conversations/{cid}/messages/{mid}")
        if m.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
            break
    print(f"\n### {q}\nstatus: {m.get('status')}")
    for a in m.get("attachments", []):
        if a.get("text"):
            print("texto:", a["text"].get("content", "")[:500])
        if a.get("query"):
            print("SQL:", a["query"].get("query", "").replace("\n", " ")[:600])
            res = api("get", f"/api/2.0/genie/spaces/{SID}/conversations/{cid}/messages/{mid}/attachments/{a['attachment_id']}/query-result")
            rows = (res.get("statement_response", {}).get("result", {}) or {}).get("data_array", [])
            for row in rows[:6]:
                print("  ", row)
