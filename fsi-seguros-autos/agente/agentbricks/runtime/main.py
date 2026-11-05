"""Servidor del Agente Investigador SIU sobre DurableAgentServer (Agent Bricks)."""
import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from agent.agent import configure
from databricks_agentkit import DurableAgentServer
from runtime.adapter import invoke, recover

# override=False: las variables DATABRICKS_* que inyecta `agentbricks dev`/el deploy ganan sobre un .env local.
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)
configure()

app = DurableAgentServer()
app.invoke(invoke)
app.recover(recover)


def main() -> None:
    uvicorn.run("runtime.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
