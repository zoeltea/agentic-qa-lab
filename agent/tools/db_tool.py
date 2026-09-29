"""DbTool: Read-only SQLite assertion tool with strict safety guardrails.
Enforces SELECT-only execution and allowlists tables to prevent unintentional mutation.
"""
import re
import time
import sqlite3
from typing import Any, List, Optional
from pydantic import BaseModel, Field

from agent.config import config
from agent.tools.base import BaseTool, ToolResult


class DbToolInput(BaseModel):
    sql: str = Field(..., description="SQL SELECT query to execute.")
    params: List[Any] = Field(default_factory=list, description="Query positional parameters.")


class DbTool(BaseTool):
    name = "db_query"
    description = (
        "Execute read-only SQL queries against the testbed SQLite database to assert ground truth. "
        "Strictly enforces SELECT statements on allowed tables: products, vouchers, orders, "
        "order_items, fault_injection_config. Mutating queries (INSERT/UPDATE/DELETE/DROP) are rejected."
    )
    input_schema = DbToolInput

    ALLOWED_TABLES = {
        "products",
        "vouchers",
        "orders",
        "order_items",
        "fault_injection_config",
    }

    FORBIDDEN_KEYWORDS = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
        "REPLACE", "CREATE", "ATTACH", "DETACH", "PRAGMA",
    ]

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _validate_safety(self, sql: str) -> Optional[str]:
        cleaned = sql.strip().upper()

        # 1. Must start with SELECT
        if not re.match(r"^\s*SELECT\b", cleaned):
            return "Safety violation: Only SELECT queries are permitted."

        # 2. Check forbidden mutation keywords (word-boundary matched)
        for kw in self.FORBIDDEN_KEYWORDS:
            if re.search(rf"\b{kw}\b", cleaned):
                return f"Safety violation: Forbidden keyword '{kw}' detected in query."

        # 3. Prevent multiple statements / semicolon chaining
        # Remove trailing semicolon first
        sql_no_trailing = re.sub(r";\s*$", "", sql.strip())
        if ";" in sql_no_trailing:
            return "Safety violation: Multiple statements / semicolon chaining is not permitted."

        # 4. Check that queried tables belong to allowlist
        # Simple extraction of tables after FROM / JOIN
        table_matches = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)", cleaned)
        for table in table_matches:
            if table.lower() not in self.ALLOWED_TABLES:
                return f"Safety violation: Table '{table}' is not in the allowlist ({', '.join(sorted(self.ALLOWED_TABLES))})."

        return None

    def run(self, **kwargs) -> ToolResult:
        start_time = time.time()

        try:
            # Parse / validate input
            args = DbToolInput(**kwargs)
            sql = args.sql
            params = args.params
        except Exception as e:
            return self._error(f"Invalid input parameters: {str(e)}", int((time.time() - start_time) * 1000))

        # Enforce safety guardrails
        safety_error = self._validate_safety(sql)
        if safety_error:
            return self._error(safety_error, int((time.time() - start_time) * 1000))

        # Execute query
        try:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall()
                data = [dict(row) for row in rows]
                latency = int((time.time() - start_time) * 1000)
                return self._success(
                    {
                        "rows": data,
                        "row_count": len(data),
                        "sql": sql,
                    },
                    latency=latency,
                )
            finally:
                conn.close()
        except sqlite3.Error as e:
            return self._error(f"SQLite error: {str(e)}", int((time.time() - start_time) * 1000))
        except Exception as e:
            return self._error(f"Unexpected database execution error: {str(e)}", int((time.time() - start_time) * 1000))
