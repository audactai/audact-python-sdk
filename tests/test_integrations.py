"""
Tests for the ``client.integrations`` sub-client: Cal.com
connection CRUD, live health-check (``test_connection``), event-type
listing, and the OAuth connect flow (``calcom_oauth_start`` /
``calcom_oauth_callback``) — agent-worker (8089).

Uses ``respx`` to mock the agent-worker transport (``http://localhost:8089``)
so no real network calls are made.
"""

from __future__ import annotations

import json as _json
from uuid import uuid4

import httpx
import pytest
import respx

from audact import AudactClient
from audact.client import IntegrationsClient
from audact.exceptions import AudactAPIError, AudactNotFoundError
from audact.models import (
    CalcomEventType,
    Connection,
    CreateConnectionRequest,
    DeleteConnectionResponse,
    OAuthStartResponse,
    TestConnectionResponse,
)

BASE = "http://localhost:8089"

CONNECTION_ID = uuid4()
TENANT_ID = uuid4()


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _error_response(status: int, code: str, message: str) -> httpx.Response:
    """The server's real nested error envelope."""
    return httpx.Response(status, json={"error": {"code": code, "message": message}})


@pytest.fixture()
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_test123")


def _connection_payload(**overrides) -> dict:
    payload = {
        "connection_id": str(CONNECTION_ID),
        "tenant_id": str(TENANT_ID),
        "provider": "cal_com",
        "name": "My Cal.com Account",
        "auth_method": "api_key",
        "cal_username": "jane-doe",
        "has_api_key": True,
        "has_oauth_token": False,
        "status": "active",
        "health": "connected",
        "last_checked_at": "2026-03-18T15:17:00Z",
        "created_at": "2026-03-18T15:17:00Z",
        "updated_at": "2026-03-18T15:17:00Z",
    }
    payload.update(overrides)
    return payload


def test_integrations_is_integrations_client(client: AudactClient) -> None:
    assert isinstance(client.integrations, IntegrationsClient)


# ─────────────────────────────────────────────────────────────────────────────
# list_connections — GET /v1/integrations
# ─────────────────────────────────────────────────────────────────────────────

class TestListConnections:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/integrations").mock(
            return_value=_json_response({"connections": [_connection_payload()]})
        )

        result = await client.integrations.list_connections()

        assert route.called
        request = route.calls.last.request
        assert request.headers["Authorization"] == "Bearer aud_live_test123"
        assert len(result) == 1
        assert isinstance(result[0], Connection)
        assert result[0].connection_id == CONNECTION_ID
        assert result[0].has_api_key is True
        assert result[0].has_oauth_token is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_provider_filter(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/integrations").mock(
            return_value=_json_response({"connections": []})
        )

        await client.integrations.list_connections(provider="cal_com")

        request = route.calls.last.request
        assert request.url.params["provider"] == "cal_com"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_unauthorized(self, client: AudactClient):
        respx.get(f"{BASE}/v1/integrations").mock(
            return_value=_error_response(401, "UNAUTHORIZED", "missing bearer token")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.integrations.list_connections()
        assert exc_info.value.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# create_connection — POST /v1/integrations
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateConnection:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.post(f"{BASE}/v1/integrations").mock(
            return_value=_json_response(_connection_payload(), status=201)
        )

        result = await client.integrations.create_connection(
            CreateConnectionRequest(
                name="My Cal.com Account",
                api_key="cal_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            )
        )

        assert isinstance(result, Connection)
        assert result.connection_id == CONNECTION_ID
        request = route.calls.last.request
        body = _json.loads(request.content)
        assert body == {
            "name": "My Cal.com Account",
            "api_key": "cal_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        }
        # The raw API key must never be echoed back on the response — the
        # server only ever returns has_api_key/has_oauth_token booleans.
        assert not hasattr(result, "api_key")
        assert not hasattr(result, "raw_api_key")

    @pytest.mark.asyncio
    @respx.mock
    async def test_idempotency_key_header(self, client: AudactClient):
        respx.post(f"{BASE}/v1/integrations").mock(
            return_value=_json_response(_connection_payload(), status=201)
        )

        await client.integrations.create_connection(
            CreateConnectionRequest(name="My Cal.com Account", api_key="cal_live_x"),
            idempotency_key="idem-conn-1",
        )

        request = respx.calls.last.request
        assert request.headers["Idempotency-Key"] == "idem-conn-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_name_conflict(self, client: AudactClient):
        respx.post(f"{BASE}/v1/integrations").mock(
            return_value=_error_response(409, "CONFLICT", "name already exists")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.integrations.create_connection(
                CreateConnectionRequest(name="My Cal.com Account", api_key="cal_live_x")
            )
        assert exc_info.value.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# get_connection — GET /v1/integrations/{connection_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestGetConnection:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/integrations/{CONNECTION_ID}").mock(
            return_value=_json_response(_connection_payload())
        )

        result = await client.integrations.get_connection(CONNECTION_ID)

        assert route.called
        assert isinstance(result, Connection)
        assert result.connection_id == CONNECTION_ID
        assert result.name == "My Cal.com Account"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_not_found(self, client: AudactClient):
        respx.get(f"{BASE}/v1/integrations/{CONNECTION_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "connection not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.integrations.get_connection(CONNECTION_ID)


# ─────────────────────────────────────────────────────────────────────────────
# delete_connection — DELETE /v1/integrations/{connection_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteConnection:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.delete(f"{BASE}/v1/integrations/{CONNECTION_ID}").mock(
            return_value=_json_response({"deleted": True})
        )

        result = await client.integrations.delete_connection(CONNECTION_ID)

        assert route.called
        assert isinstance(result, DeleteConnectionResponse)
        assert result.deleted is True
        assert "force" not in route.calls.last.request.url.params

    @pytest.mark.asyncio
    @respx.mock
    async def test_force_query_param(self, client: AudactClient):
        route = respx.delete(f"{BASE}/v1/integrations/{CONNECTION_ID}").mock(
            return_value=_json_response({"deleted": True})
        )

        await client.integrations.delete_connection(CONNECTION_ID, force=True)

        assert route.calls.last.request.url.params["force"] == "true"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_dependent_tools_conflict(self, client: AudactClient):
        respx.delete(f"{BASE}/v1/integrations/{CONNECTION_ID}").mock(
            return_value=_error_response(409, "CONFLICT", "connection has dependent tools")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.integrations.delete_connection(CONNECTION_ID)
        assert exc_info.value.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# test_connection — POST /v1/integrations/{connection_id}/test
# ─────────────────────────────────────────────────────────────────────────────

class TestTestConnection:
    @pytest.mark.asyncio
    @respx.mock
    async def test_healthy(self, client: AudactClient):
        route = respx.post(f"{BASE}/v1/integrations/{CONNECTION_ID}/test").mock(
            return_value=_json_response(
                {
                    "connection_id": str(CONNECTION_ID),
                    "healthy": True,
                    "health": "connected",
                    "event_type_count": 3,
                }
            )
        )

        result = await client.integrations.test_connection(CONNECTION_ID)

        assert route.called
        assert isinstance(result, TestConnectionResponse)
        assert result.healthy is True
        assert result.event_type_count == 3
        assert result.error is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_unhealthy(self, client: AudactClient):
        respx.post(f"{BASE}/v1/integrations/{CONNECTION_ID}/test").mock(
            return_value=_json_response(
                {
                    "connection_id": str(CONNECTION_ID),
                    "healthy": False,
                    "health": "revoked",
                    "error": "connection_revoked",
                }
            )
        )

        result = await client.integrations.test_connection(CONNECTION_ID)

        assert result.healthy is False
        assert result.error == "connection_revoked"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_not_found(self, client: AudactClient):
        respx.post(f"{BASE}/v1/integrations/{CONNECTION_ID}/test").mock(
            return_value=_error_response(404, "NOT_FOUND", "connection not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.integrations.test_connection(CONNECTION_ID)


# ─────────────────────────────────────────────────────────────────────────────
# list_connection_event_types — GET /v1/integrations/{connection_id}/event-types
# ─────────────────────────────────────────────────────────────────────────────

class TestListConnectionEventTypes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/integrations/{CONNECTION_ID}/event-types").mock(
            return_value=_json_response(
                {
                    "event_types": [
                        {
                            "id": 123,
                            "title": "30 Minute Meeting",
                            "slug": "30min",
                            "lengthInMinutes": 30,
                            "hidden": False,
                        }
                    ]
                }
            )
        )

        result = await client.integrations.list_connection_event_types(CONNECTION_ID)

        assert route.called
        assert len(result) == 1
        assert isinstance(result[0], CalcomEventType)
        assert result[0].id == 123
        assert result[0].slug == "30min"
        assert result[0].length_in_minutes == 30

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_conflict_needs_reauth(self, client: AudactClient):
        respx.get(f"{BASE}/v1/integrations/{CONNECTION_ID}/event-types").mock(
            return_value=_error_response(409, "CONFLICT", "connection needs re-authorization")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.integrations.list_connection_event_types(CONNECTION_ID)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_upstream_unavailable(self, client: AudactClient):
        respx.get(f"{BASE}/v1/integrations/{CONNECTION_ID}/event-types").mock(
            return_value=_error_response(502, "BAD_GATEWAY", "Cal.com is currently unavailable")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.integrations.list_connection_event_types(CONNECTION_ID)
        assert exc_info.value.status_code == 502


# ─────────────────────────────────────────────────────────────────────────────
# calcom_oauth_start — GET /v1/integrations/cal_com/oauth/start
# ─────────────────────────────────────────────────────────────────────────────

class TestCalcomOauthStart:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/integrations/cal_com/oauth/start").mock(
            return_value=_json_response(
                {"authorize_url": "https://app.cal.com/oauth/authorize?client_id=xyz"}
            )
        )

        result = await client.integrations.calcom_oauth_start(
            name="My Cal.com Account", cal_username="jane-doe"
        )

        assert route.called
        request = route.calls.last.request
        assert request.headers["Authorization"] == "Bearer aud_live_test123"
        assert request.url.params["name"] == "My Cal.com Account"
        assert request.url.params["cal_username"] == "jane-doe"
        assert isinstance(result, OAuthStartResponse)
        assert result.authorize_url == "https://app.cal.com/oauth/authorize?client_id=xyz"

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_query_params_when_omitted(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/integrations/cal_com/oauth/start").mock(
            return_value=_json_response({"authorize_url": "https://app.cal.com/oauth/authorize"})
        )

        await client.integrations.calcom_oauth_start()

        assert route.calls.last.request.url.params == httpx.QueryParams()

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_not_configured(self, client: AudactClient):
        respx.get(f"{BASE}/v1/integrations/cal_com/oauth/start").mock(
            return_value=_error_response(500, "INTERNAL", "OAuth not configured")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.integrations.calcom_oauth_start()
        assert exc_info.value.status_code == 500


# ─────────────────────────────────────────────────────────────────────────────
# calcom_oauth_callback — GET /v1/integrations/cal_com/oauth/callback
# ─────────────────────────────────────────────────────────────────────────────

class TestCalcomOauthCallback:
    @pytest.mark.asyncio
    @respx.mock
    async def test_success_redirect_has_no_auth_header(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/integrations/cal_com/oauth/callback").mock(
            return_value=httpx.Response(
                302,
                headers={"Location": "https://dashboard.audact.ai/integrations?connected=1"},
            )
        )

        result = await client.integrations.calcom_oauth_callback(
            state="single-use-state-token", code="auth-code-123"
        )

        assert route.called
        request = route.calls.last.request
        # The server authenticates this endpoint solely by the state token —
        # Cal.com's browser redirect cannot carry an Authorization header, so
        # the SDK must not send the tenant api_key here.
        assert "Authorization" not in request.headers
        assert request.url.params["state"] == "single-use-state-token"
        assert request.url.params["code"] == "auth-code-123"
        assert result == "https://dashboard.audact.ai/integrations?connected=1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_decline_redirect_carries_error_query_param(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/integrations/cal_com/oauth/callback").mock(
            return_value=httpx.Response(
                302,
                headers={
                    "Location": "https://dashboard.audact.ai/integrations?error=access_denied"
                },
            )
        )

        result = await client.integrations.calcom_oauth_callback(
            state="single-use-state-token", error="access_denied"
        )

        assert route.calls.last.request.url.params["error"] == "access_denied"
        assert result == "https://dashboard.audact.ai/integrations?error=access_denied"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_expired_state(self, client: AudactClient):
        respx.get(f"{BASE}/v1/integrations/cal_com/oauth/callback").mock(
            return_value=_error_response(400, "BAD_REQUEST", "unknown or expired state")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.integrations.calcom_oauth_callback(state="expired-token")
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_token_exchange_failure(self, client: AudactClient):
        respx.get(f"{BASE}/v1/integrations/cal_com/oauth/callback").mock(
            return_value=_error_response(502, "BAD_GATEWAY", "Cal.com token exchange failed")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.integrations.calcom_oauth_callback(
                state="single-use-state-token", code="auth-code-123"
            )
        assert exc_info.value.status_code == 502
