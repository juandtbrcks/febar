"""Ejecuta sentencias SQL (separadas por ';' al final de línea) en el warehouse vía Statement Execution API.
Run: python3 run_sql.py archivo.sql   |   python3 run_sql.py -e "SELECT 1"
"""
import json, subprocess, sys, time

WH = "<WAREHOUSE_ID>"  # seguros-demo-wh


def api(method, path, body=None):
    cmd = ["databricks", "-p", "DEFAULT", "api", method, path]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(out.stderr)
    return json.loads(out.stdout)


def run(stmt):
    r = api("post", "/api/2.0/sql/statements", {"warehouse_id": WH, "statement": stmt, "wait_timeout": "50s"})
    while r["status"]["state"] in ("PENDING", "RUNNING"):
        time.sleep(3)
        r = api("get", f"/api/2.0/sql/statements/{r['statement_id']}")
    if r["status"]["state"] != "SUCCEEDED":
        raise RuntimeError(f"{r['status']}\n--- {stmt[:300]}")
    cols = [c["name"] for c in r.get("manifest", {}).get("schema", {}).get("columns", [])]
    rows = r.get("result", {}).get("data_array", []) or []
    return cols, rows


if __name__ == "__main__":
    text = sys.argv[2] if sys.argv[1] == "-e" else open(sys.argv[1]).read()
    stmts = [s.strip() for s in text.split(";\n") if s.strip() and not all(l.strip().startswith("--") or not l.strip() for l in s.splitlines())]
    for s in stmts:
        cols, rows = run(s.rstrip(";"))
        print(f"OK: {s.splitlines()[0][:90]}")
        if rows:
            print("  " + " | ".join(cols))
            for row in rows[:40]:
                print("  " + " | ".join("" if v is None else str(v) for v in row))
