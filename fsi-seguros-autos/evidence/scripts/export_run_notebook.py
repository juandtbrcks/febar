"""Exports a Databricks job-run notebook (with its real cell outputs) as .ipynb + .md, readable as text.
Usage: python3 export_run_notebook.py <task_run_id> <output_basename> [<title>]
Uses `databricks jobs export-run` (profile DEFAULT) and decodes the embedded notebook model."""
import base64, json, re, subprocess, sys, urllib.parse

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\[(?:\d+;)*\d*m")


def clean(t):
    return ANSI.sub("", t or "")


def export(run_id):
    out = subprocess.run(["databricks", "jobs", "export-run", str(run_id), "--views-to-export", "CODE", "-p", "DEFAULT", "-o", "json"],
                         capture_output=True, text=True, check=True).stdout
    html = json.loads(out)["views"][0]["content"]
    raw = re.search(r"__DATABRICKS_NOTEBOOK_MODEL = '([^']+)'", html).group(1)
    return json.loads(urllib.parse.unquote(base64.b64decode(raw).decode()))


def table_text(d):
    schema = [c.get("name") for c in d.get("schema", [])]
    rows = d.get("data", [])[:30]
    lines = [" | ".join(schema), " | ".join("---" for _ in schema)] + [" | ".join(str(v) for v in r) for r in rows]
    if len(d.get("data", [])) > 30:
        lines.append(f"... ({len(d['data'])} rows total, first 30 shown)")
    return "\n".join(lines)


def outputs_of(res):
    outs = []
    if not res:
        return outs
    items = res.get("data", []) if res.get("type") == "listResults" else [res]
    for it in items:
        t, d = it.get("type"), it.get("data")
        if t in ("ansi", "raw", "text"):
            txt = clean(d if isinstance(d, str) else json.dumps(d))
        elif t == "table":
            txt = table_text(it)
        elif t == "mimeBundle" and isinstance(d, dict):
            txt = clean(d.get("text/plain", ""))
            if "Uploading artifacts" in txt or "Downloading artifacts" in txt:
                continue  # progress widgets, no information
        elif t == "image":
            txt = "[image output: chart rendered in the notebook (logged to MLflow as an artifact)]"
        else:
            continue
        if txt.strip():
            outs.append(txt)
    if res.get("type") == "error":
        outs.append("ERROR: " + clean(res.get("data", "")))
    return outs


def main():
    run_id, base = sys.argv[1], sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else base
    nb = export(run_id)
    cells, md = [], [f"# {title}\n", f"_Executed notebook exported from Databricks job task run `{run_id}` with its real outputs._\n"]
    for c in sorted(nb.get("commands", []), key=lambda c: c.get("position", 0)):
        src = c.get("command", "")
        if src.lstrip().startswith("%md"):
            body = re.sub(r"^\s*%md\s?", "", src)
            cells.append({"cell_type": "markdown", "metadata": {}, "source": body})
            md.append(body + "\n")
            continue
        outs = outputs_of(c.get("results"))
        cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "source": src,
                      "outputs": [{"output_type": "stream", "name": "stdout", "text": o + ("\n" if not o.endswith("\n") else "")} for o in outs]})
        md.append("```python\n" + src.strip() + "\n```\n")
        for o in outs:
            md.append("Output:\n```text\n" + o.strip()[:6000] + "\n```\n")
    ipynb = {"nbformat": 4, "nbformat_minor": 5, "metadata": {"databricks_task_run_id": str(run_id), "language_info": {"name": "python"}}, "cells": cells}
    open(base + ".ipynb", "w").write(json.dumps(ipynb, indent=1, ensure_ascii=False))
    open(base + ".md", "w").write("\n".join(md))
    n_out = sum(1 for c in cells if c["cell_type"] == "code" and c["outputs"])
    print(f"{base}: {len(cells)} cells, {n_out} code cells with output")


if __name__ == "__main__":
    main()
