"""Genie dentro de la app: preguntas en lenguaje natural al Genie space ejecutivo, con la identidad del USUARIO
(token on-behalf-of, scope `dashboards.genie`). Genie corre el SQL como el usuario → aplican las políticas ABAC."""
from datetime import timedelta

import pandas as pd


def preguntar(ws, space_id: str, pregunta: str, conversation_id: str | None = None) -> dict:
    t = timedelta(seconds=180)
    if conversation_id:
        msg = ws.genie.create_message_and_wait(space_id, conversation_id, pregunta, timeout=t)
    else:
        msg = ws.genie.start_conversation_and_wait(space_id, pregunta, timeout=t)
    out = {"conversation_id": msg.conversation_id, "texto": [], "sql": None, "descripcion": None,
           "df": None, "sugerencias": [], "estado": str(msg.status.value if msg.status else ""),
           "error": (msg.error.error if msg.error else None)}
    for att in msg.attachments or []:
        if att.text and att.text.content:
            out["texto"].append(att.text.content)
        if att.suggested_questions and att.suggested_questions.questions:
            out["sugerencias"] = list(att.suggested_questions.questions)
        if att.query:
            out["sql"], out["descripcion"] = att.query.query, att.query.description
            try:
                r = ws.genie.get_message_attachment_query_result(space_id, msg.conversation_id,
                                                                 msg.message_id or msg.id, att.attachment_id)
                st = r.statement_response
                cols = [c.name for c in st.manifest.schema.columns]
                out["df"] = pd.DataFrame((st.result.data_array or []) if st.result else [], columns=cols)
            except Exception as e:  # el texto de Genie sigue siendo útil aunque falle el resultado
                out["error"] = f"No se pudo leer el resultado: {str(e)[:200]}"
    return out
