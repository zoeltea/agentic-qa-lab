"""LogTool: Inspects server logs and fault injection state.
Helps the Agent verify cross-layer anomalies and detect simulated failures.
"""
import os
import time
import sqlite3
from typing import Optional
from pydantic import BaseModel, Field

from agent.config import config
from agent.tools.base import BaseTool, ToolResult


class LogToolInput(BaseModel):
    last_n_lines: int = Field(default=50, ge=1, le=500, description="Number of tail lines to retrieve from server log.")
    check_fault_config: bool = Field(default=True, description="Whether to query current fault_injection_config state.")


class LogTool(BaseTool):
    name = "log_inspector"
    description = (
        "Inspect recent server log output and query current fault_injection_config state. "
        "Used to diagnose runtime crashes, tracebacks, or verify whether artificial backend "
        "failures (silent DB drop, artificial delay, stock corruption) are active."
    )
    input_schema = LogToolInput

    def __init__(self, log_file_path: Optional[str] = None, db_path: Optional[str] = None):
        self.log_file_path = log_file_path or config.log_file_path
        self.db_path = db_path or config.db_path

    def run(self, **kwargs) -> ToolResult:
        start_time = time.time()

        try:
            args = LogToolInput(**kwargs)
            last_n = args.last_n_lines
            check_fault = args.check_fault_config
        except Exception as e:
            return self._error(f"Invalid input parameters: {str(e)}", int((time.time() - start_time) * 1000))

        fault_config = None
        logs = []

        # 1. Check fault_injection_config in DB if requested
        if check_fault:
            if os.path.exists(self.db_path):
                try:
                    conn = sqlite3.connect(self.db_path)
                    conn.row_factory = sqlite3.Row
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT * FROM fault_injection_config WHERE id = 1")
                        row = cur.fetchone()
                        if row:
                            fault_config = dict(row)
                    finally:
                        conn.close()
                except Exception as e:
                    fault_config = {"error": f"Failed to read fault config: {str(e)}"}
            else:
                fault_config = {"warning": f"Database file not found at {self.db_path}"}

        # 2. Read tail of log file
        if os.path.exists(self.log_file_path):
            try:
                with open(self.log_file_path, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()
                    logs = [line.rstrip("\r\n") for line in all_lines[-last_n:]]
            except Exception as e:
                logs = [f"[ERROR reading log file]: {str(e)}"]
        else:
            logs = [f"[INFO] Log file not found at {self.log_file_path} (server running without file log redirection)."]

        latency = int((time.time() - start_time) * 1000)

        return self._success(
            {
                "fault_config": fault_config,
                "log_lines_count": len(logs),
                "logs": logs,
            },
            latency=latency,
        )
