"""Agent configuration — centralized environment-driven settings."""
import os
from dataclasses import dataclass


@dataclass
class AgentConfig:
    base_url: str = os.getenv("AQA_BASE_URL", "http://127.0.0.1:8091")
    db_path: str = os.getenv(
        "AQA_DB_PATH",
        "/home/zoeltea/my_work/agentic-qa-lab/app/testbed.sqlite3",
    )
    log_file_path: str = os.getenv(
        "AQA_LOG_PATH",
        "/home/zoeltea/my_work/agentic-qa-lab/server.log",
    )
    browser_headless: bool = os.getenv(
        "AQA_BROWSER_HEADLESS", "true"
    ).lower() == "true"
    browser_timeout_ms: int = int(
        os.getenv("AQA_BROWSER_TIMEOUT_MS", "10000")
    )


config = AgentConfig()