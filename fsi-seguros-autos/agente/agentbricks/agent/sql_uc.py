"""Ejecuta SQL en el warehouse con una identidad dada (en la app: la del usuario → aplican las políticas ABAC de Unity Catalog)."""
import time
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem, StatementState


def crear_sql(w: WorkspaceClient, warehouse_id: str):
    def sql(statement: str, params: dict = None) -> list:
        items = [StatementParameterListItem(name=k, value=None if v is None else str(v),
                                            type="INT" if isinstance(v, int) and not isinstance(v, bool)
                                            else "DOUBLE" if isinstance(v, float) else "STRING")
                 for k, v in (params or {}).items()]
        r = w.statement_execution.execute_statement(warehouse_id=warehouse_id, statement=statement, parameters=items, wait_timeout="50s")
        while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
            time.sleep(1)
            r = w.statement_execution.get_statement(r.statement_id)
        if r.status.state != StatementState.SUCCEEDED:
            raise RuntimeError(r.status.error.message if r.status.error else str(r.status.state))
        if not r.manifest or not r.manifest.schema or not r.manifest.schema.columns:
            return []
        cols = [c.name for c in r.manifest.schema.columns]
        return [dict(zip(cols, row)) for row in (r.result.data_array or [])] if r.result else []
    return sql
