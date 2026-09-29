"""ApiTool: REST API client wrapper for testing testbed endpoints.
Validates requests against allowlisted endpoints and returns structured ToolResult.
"""
import re
import time
import httpx
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from agent.config import config
from agent.tools.base import BaseTool, ToolResult


class ApiToolInput(BaseModel):
    method: str = Field(..., description="HTTP Method (GET, POST, PUT, DELETE).")
    path: str = Field(..., description="API Path (e.g. /api/products, /api/checkout).")
    body: Optional[Dict[str, Any]] = Field(default=None, description="JSON body payload for POST/PUT requests.")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Query string parameters.")


class ApiTool(BaseTool):
    name = "api_client"
    description = (
        "Execute HTTP requests against the Agentic QA Lab testbed REST API. "
        "Allows standard testbed endpoints: /api/health, /api/products, /api/products/{id}, "
        "POST /api/voucher/apply, POST /api/checkout, /api/orders/{order_number}, "
        "/api/admin/fault-injection, /api/admin/reset-db."
    )
    input_schema = ApiToolInput

    # Allowed endpoint path patterns (regex)
    ALLOWED_PATHS = [
        r"^/api/health/?$",
        r"^/api/products/?$",
        r"^/api/products/\d+/?$",
        r"^/api/voucher/apply/?$",
        r"^/api/checkout/?$",
        r"^/api/orders/[A-Za-z0-9_-]+/?$",
        r"^/api/admin/fault-injection/?$",
        r"^/api/admin/reset-db/?$",
    ]

    ALLOWED_METHODS = {"GET", "POST", "PUT", "DELETE"}

    def __init__(self, base_url: Optional[str] = None, client: Optional[Any] = None):
        self.base_url = (base_url or config.base_url).rstrip("/")
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        return httpx.Client(base_url=self.base_url, timeout=10.0)

    def _is_allowed_path(self, path: str) -> bool:
        # Normalize leading slash
        clean_path = path if path.startswith("/") else f"/{path}"
        # Strip query params from path check
        path_without_query = clean_path.split("?")[0]
        return any(re.match(pattern, path_without_query) for pattern in self.ALLOWED_PATHS)

    def run(self, **kwargs) -> ToolResult:
        start_time = time.time()

        try:
            args = ApiToolInput(**kwargs)
            method = args.method.strip().upper()
            path = args.path.strip()
            body = args.body
            query_params = args.params
        except Exception as e:
            return self._error(f"Invalid input parameters: {str(e)}", int((time.time() - start_time) * 1000))

        # Enforce method allowlist
        if method not in self.ALLOWED_METHODS:
            return self._error(
                f"Safety violation: Method '{method}' is not allowed ({', '.join(sorted(self.ALLOWED_METHODS))}).",
                int((time.time() - start_time) * 1000)
            )

        # Enforce path allowlist
        if not self._is_allowed_path(path):
            return self._error(
                f"Safety violation: Path '{path}' is not in the allowlisted API endpoints.",
                int((time.time() - start_time) * 1000)
            )

        # Normalize path
        normalized_path = path if path.startswith("/") else f"/{path}"

        # Execute HTTP Request
        owns_client = self._client is None
        client = self._get_client()
        try:
            resp = client.request(
                method=method,
                url=normalized_path,
                json=body,
                params=query_params,
            )

            # Try parsing JSON body, fallback to text
            try:
                resp_data = resp.json()
            except Exception:
                resp_data = resp.text

            latency = int((time.time() - start_time) * 1000)

            return self._success(
                {
                    "status_code": resp.status_code,
                    "body": resp_data,
                    "headers": dict(resp.headers),
                    "url": str(resp.url),
                },
                latency=latency,
            )
        except httpx.RequestError as e:
            return self._error(f"HTTP connection error: {str(e)}", int((time.time() - start_time) * 1000))
        except Exception as e:
            return self._error(f"Unexpected API execution error: {str(e)}", int((time.time() - start_time) * 1000))
        finally:
            if owns_client:
                client.close()
