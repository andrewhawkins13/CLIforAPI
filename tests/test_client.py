"""Tests for HTTP client."""

from __future__ import annotations

import pytest
import httpx
import respx

from cliforapi.auth import ResolvedAuth
from cliforapi.client import ApiResponse, NetworkError, execute
from cliforapi.resolver import ResolvedRequest


class TestExecute:
    @respx.mock
    def test_simple_get(self):
        respx.get("https://api.test.com/pets").mock(
            return_value=httpx.Response(
                200,
                json=[{"id": 1, "name": "Fido"}],
                headers={"content-type": "application/json"},
            )
        )

        request = ResolvedRequest(method="GET", path="/pets")
        response = execute(request, "https://api.test.com")

        assert response.status == 200
        assert response.body == [{"id": 1, "name": "Fido"}]
        assert response.elapsed_ms >= 0

    @respx.mock
    def test_post_with_body(self):
        respx.post("https://api.test.com/pets").mock(
            return_value=httpx.Response(
                201,
                json={"id": 2, "name": "Rex"},
                headers={"content-type": "application/json"},
            )
        )

        request = ResolvedRequest(method="POST", path="/pets", body={"name": "Rex"})
        response = execute(request, "https://api.test.com")

        assert response.status == 201
        assert response.body["name"] == "Rex"

    @respx.mock
    def test_auth_headers_applied(self):
        route = respx.get("https://api.test.com/pets").mock(
            return_value=httpx.Response(200, json=[])
        )

        auth = ResolvedAuth(headers={"Authorization": "Bearer tok123"})
        request = ResolvedRequest(method="GET", path="/pets")
        execute(request, "https://api.test.com", auth=auth)

        assert route.calls[0].request.headers["authorization"] == "Bearer tok123"

    @respx.mock
    def test_query_params(self):
        route = respx.get("https://api.test.com/pets").mock(
            return_value=httpx.Response(200, json=[])
        )

        request = ResolvedRequest(method="GET", path="/pets", query_params={"status": "available"})
        execute(request, "https://api.test.com")

        assert "status=available" in str(route.calls[0].request.url)

    @respx.mock
    def test_network_error(self):
        respx.get("https://api.test.com/pets").mock(side_effect=httpx.ConnectError("fail"))
        request = ResolvedRequest(method="GET", path="/pets")

        with pytest.raises(NetworkError, match="Connection failed"):
            execute(request, "https://api.test.com")

    @respx.mock
    def test_timeout_error(self):
        respx.get("https://api.test.com/pets").mock(side_effect=httpx.ReadTimeout("timeout"))
        request = ResolvedRequest(method="GET", path="/pets")

        with pytest.raises(NetworkError, match="timed out"):
            execute(request, "https://api.test.com")
