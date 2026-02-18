"""HTTP execution via httpx."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from .auth import ResolvedAuth
from .resolver import ResolvedRequest


@dataclass
class ApiResponse:
    status: int
    headers: dict[str, str]
    body: Any
    elapsed_ms: int


class NetworkError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def execute(
    request: ResolvedRequest,
    base_url: str,
    auth: ResolvedAuth | None = None,
    timeout: float = 30.0,
) -> ApiResponse:
    """Execute the resolved request and return a structured response."""
    url = base_url.rstrip("/") + request.path

    headers = dict(request.headers)
    params = dict(request.query_params)

    if auth:
        headers.update(auth.headers)
        params.update(auth.query_params)

    # Build httpx request kwargs
    kwargs: dict[str, Any] = {
        "method": request.method,
        "url": url,
        "headers": headers,
        "params": params,
        "timeout": timeout,
        "follow_redirects": True,
    }

    if request.body is not None:
        if isinstance(request.body, (dict, list)):
            kwargs["json"] = request.body
        else:
            kwargs["content"] = str(request.body)
            headers.setdefault("Content-Type", "text/plain")

    start = time.monotonic()
    try:
        with httpx.Client() as client:
            resp = client.request(**kwargs)
    except httpx.ConnectError as e:
        raise NetworkError(f"Connection failed: {e}") from e
    except httpx.TimeoutException as e:
        raise NetworkError(f"Request timed out after {timeout}s") from e
    except httpx.HTTPError as e:
        raise NetworkError(str(e)) from e

    elapsed_ms = int((time.monotonic() - start) * 1000)

    # Parse response body
    body: Any
    content_type = resp.headers.get("content-type", "")
    if "json" in content_type:
        try:
            body = resp.json()
        except Exception:
            body = resp.text
    else:
        body = resp.text

    resp_headers = dict(resp.headers)

    return ApiResponse(
        status=resp.status_code,
        headers=resp_headers,
        body=body,
        elapsed_ms=elapsed_ms,
    )
