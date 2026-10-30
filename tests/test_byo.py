"""
Tests for the bring-your-own (BYO) telephony surface.

Covers the BYO connection CRUD/verify endpoints, ``GET /v1/byo/config``, and
the origin-aware ``create_number``/``list_numbers`` DID pool methods. BYO is
pure JSON — no multipart involved.

Uses ``respx`` to mock the voice-gateway transport so no real network calls
are made.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
import respx

from audact import AudactClient
from audact.exceptions import AudactAPIError
from audact.models import (
    ByoConfig,
    BYOConnection,
    CreateBYOConnectionRequest,
    CreateNumberRequest,
    PhoneNumber,
    UpdateBYOConnectionRequest,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures & helpers
# ─────────────────────────────────────────────────────────────────────────────

BASE = "http://localhost:8088"

CONN_ID = uuid4()
NUMBER_ID = uuid4()
NOW = datetime.now(tz=UTC).isoformat()


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _error_response(
    status: int, code: str, message: str, details: dict | None = None
) -> httpx.Response:
    body = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return httpx.Response(status, json=body)


def _connection_payload(conn_id: UUID = CONN_ID, **overrides) -> dict:
    payload = {
        "id": str(conn_id),
        "name": "Acme HQ Twilio Trunk",
        "provider": "twilio",
        "sip_host": "acme.pstn.twilio.com",
        "sip_transport": "auto",
        "has_credentials": True,
        "inbound_allowed_ips": [],
        "connection_health": "healthy",
        "health_detail": "outbound call connected successfully",
        "last_error_code": None,
        "last_error_at": None,
        "last_verified_at": NOW,
        "created_at": NOW,
        "updated_at": NOW,
    }
    payload.update(overrides)
    return payload


def _number_payload(number_id: UUID = NUMBER_ID, **overrides) -> dict:
    payload = {
        "id": str(number_id),
        "did": "+442045136446",
        "country_code": "GB",
        "trunk_provider": "",
        "trunk_id": None,
        "assigned_agent_id": None,
        "status": "available",
        "origin": "audact",
        "byo_connection_id": None,
        "provider": None,
        "connection_health": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_test123")


# ─────────────────────────────────────────────────────────────────────────────
# BYO connections — list / get
# ─────────────────────────────────────────────────────────────────────────────

class TestBYOConnectionsReadOnly:
    @pytest.mark.asyncio
    @respx.mock
    async def test_list_byo_connections(self):
        respx.get(f"{BASE}/v1/byo/connections").mock(
            return_value=_json_response({"connections": [_connection_payload()]})
        )
        async with AudactClient(api_key="key") as c:
            result = await c.list_byo_connections()
        assert result.connections == [BYOConnection.model_validate(_connection_payload())]
        assert isinstance(result.connections[0], BYOConnection)
        assert result.connections[0].connection_health == "healthy"

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_byo_connections_empty(self):
        respx.get(f"{BASE}/v1/byo/connections").mock(
            return_value=_json_response({"connections": []})
        )
        async with AudactClient(api_key="key") as c:
            result = await c.list_byo_connections()
        assert result.connections == []
        assert result.next_cursor is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_byo_connections_pagination_params(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response({"connections": [], "next_cursor": "opaque-cursor"})

        respx.get(f"{BASE}/v1/byo/connections").mock(side_effect=_handler)

        async with AudactClient(api_key="key") as c:
            result = await c.list_byo_connections(limit=10, cursor="prev-cursor")

        assert dict(captured[0].url.params) == {"limit": "10", "cursor": "prev-cursor"}
        assert result.next_cursor == "opaque-cursor"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_byo_connection(self):
        respx.get(f"{BASE}/v1/byo/connections/{CONN_ID}").mock(
            return_value=_json_response(_connection_payload())
        )
        async with AudactClient(api_key="key") as c:
            conn = await c.get_byo_connection(CONN_ID)
        assert isinstance(conn, BYOConnection)
        assert conn.id == CONN_ID
        assert conn.provider == "twilio"
        assert conn.has_credentials is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_byo_connection_not_found(self):
        respx.get(f"{BASE}/v1/byo/connections/{CONN_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "byo connection not found")
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.get_byo_connection(CONN_ID)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# BYO connections — create
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateBYOConnection:
    @pytest.mark.asyncio
    @respx.mock
    async def test_create_byo_connection(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_connection_payload(), status=201)

        respx.post(f"{BASE}/v1/byo/connections").mock(side_effect=_handler)

        req = CreateBYOConnectionRequest(
            name="Acme HQ Twilio Trunk",
            provider="twilio",
            sip_host="acme.pstn.twilio.com",
            sip_username="acme-trunk-user",
            sip_password="correct-horse-battery-staple",
        )

        async with AudactClient(api_key="key") as c:
            conn = await c.create_byo_connection(req)

        assert isinstance(conn, BYOConnection)
        assert conn.id == CONN_ID
        assert conn.connection_health == "healthy"

        sent = captured[0]
        assert sent.headers["content-type"] == "application/json"
        body = json.loads(sent.content)
        assert body["name"] == "Acme HQ Twilio Trunk"
        assert body["provider"] == "twilio"
        assert body["sip_host"] == "acme.pstn.twilio.com"
        assert body["sip_username"] == "acme-trunk-user"
        assert body["sip_password"] == "correct-horse-battery-staple"
        assert "inbound_allowed_ips" not in body  # exclude_none — omitted, not null

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_byo_connection_idempotency_key_header(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_connection_payload(), status=201)

        respx.post(f"{BASE}/v1/byo/connections").mock(side_effect=_handler)

        req = CreateBYOConnectionRequest(
            name="Acme HQ Twilio Trunk",
            provider="twilio",
            sip_host="acme.pstn.twilio.com",
            inbound_allowed_ips=["203.0.113.0/24"],
        )
        async with AudactClient(api_key="key") as c:
            await c.create_byo_connection(req, idempotency_key="idem-byo-1")

        assert captured[0].headers["idempotency-key"] == "idem-byo-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_byo_connection_missing_connection_material_422(self):
        """Neither creds nor an allowlist supplied surfaces 422 with details."""
        respx.post(f"{BASE}/v1/byo/connections").mock(
            return_value=_error_response(
                422,
                "missing_connection_material",
                "connection has neither SIP credentials nor an inbound IP allowlist",
                details={"field": "inbound_allowed_ips"},
            )
        )
        req = CreateBYOConnectionRequest(
            name="No Auth Trunk",
            provider="generic_sip",
            sip_host="sip.example.com",
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.create_byo_connection(req)

        assert exc_info.value.status_code == 422
        assert exc_info.value.code == "missing_connection_material"
        assert exc_info.value.details["field"] == "inbound_allowed_ips"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_byo_connection_allowlist_too_broad_422(self):
        respx.post(f"{BASE}/v1/byo/connections").mock(
            return_value=_error_response(
                422,
                "inbound_allowlist_too_broad",
                'inbound_allowed_ips entry "0.0.0.0/0" is too broad',
                details={"field": "inbound_allowed_ips"},
            )
        )
        req = CreateBYOConnectionRequest(
            name="Accept Any Trunk",
            provider="generic_sip",
            sip_host="sip.example.com",
            inbound_allowed_ips=["0.0.0.0/0"],
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.create_byo_connection(req)

        assert exc_info.value.status_code == 422
        assert exc_info.value.code == "inbound_allowlist_too_broad"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_byo_connection_name_conflict_409(self):
        respx.post(f"{BASE}/v1/byo/connections").mock(
            return_value=_error_response(
                409,
                "CONFLICT",
                "a connection with this name already exists for your tenant",
                details={"field": "name"},
            )
        )
        req = CreateBYOConnectionRequest(
            name="Acme HQ Twilio Trunk",
            provider="twilio",
            sip_host="acme.pstn.twilio.com",
            inbound_allowed_ips=["203.0.113.0/24"],
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.create_byo_connection(req)

        assert exc_info.value.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# BYO connections — update / verify / delete
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdateVerifyDeleteBYOConnection:
    @pytest.mark.asyncio
    @respx.mock
    async def test_update_byo_connection(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_connection_payload(sip_host="new.pstn.twilio.com"))

        respx.put(f"{BASE}/v1/byo/connections/{CONN_ID}").mock(side_effect=_handler)

        req = UpdateBYOConnectionRequest(sip_host="new.pstn.twilio.com")
        async with AudactClient(api_key="key") as c:
            conn = await c.update_byo_connection(CONN_ID, req)

        assert conn.sip_host == "new.pstn.twilio.com"
        body = json.loads(captured[0].content)
        assert body == {"sip_host": "new.pstn.twilio.com"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_update_byo_connection_clear_allowlist_sends_empty_list(self):
        """An explicit empty list must round-trip as [] on the wire, not be omitted."""
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_connection_payload(inbound_allowed_ips=[]))

        respx.put(f"{BASE}/v1/byo/connections/{CONN_ID}").mock(side_effect=_handler)

        req = UpdateBYOConnectionRequest(inbound_allowed_ips=[])
        async with AudactClient(api_key="key") as c:
            await c.update_byo_connection(CONN_ID, req)

        body = json.loads(captured[0].content)
        assert body["inbound_allowed_ips"] == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_update_byo_connection_not_found(self):
        respx.put(f"{BASE}/v1/byo/connections/{CONN_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "byo connection not found")
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.update_byo_connection(CONN_ID, UpdateBYOConnectionRequest(name="x"))
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @respx.mock
    async def test_verify_byo_connection(self):
        respx.post(f"{BASE}/v1/byo/connections/{CONN_ID}/verify").mock(
            return_value=_json_response(_connection_payload(connection_health="unreachable"))
        )
        async with AudactClient(api_key="key") as c:
            conn = await c.verify_byo_connection(CONN_ID)
        assert conn.connection_health == "unreachable"

    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_byo_connection(self):
        respx.delete(f"{BASE}/v1/byo/connections/{CONN_ID}").mock(
            return_value=httpx.Response(204)
        )
        async with AudactClient(api_key="key") as c:
            result = await c.delete_byo_connection(CONN_ID)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_byo_connection_numbers_attached_409(self):
        """Deleting a connection with attached numbers surfaces 409."""
        respx.delete(f"{BASE}/v1/byo/connections/{CONN_ID}").mock(
            return_value=_error_response(
                409,
                "CONFLICT",
                "2 phone number(s) are still attached to this connection",
                details={"attached_numbers": 2},
            )
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.delete_byo_connection(CONN_ID)

        assert exc_info.value.status_code == 409
        assert exc_info.value.details["attached_numbers"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# GET /v1/byo/config
# ─────────────────────────────────────────────────────────────────────────────

class TestGetByoConfig:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_byo_config(self):
        respx.get(f"{BASE}/v1/byo/config").mock(
            return_value=_json_response(
                {
                    "sip_ingress_host": "sip.us.audact.ai",
                    "signaling_ips": ["203.0.113.10/32"],
                }
            )
        )
        async with AudactClient(api_key="key") as c:
            config = await c.get_byo_config()
        assert isinstance(config, ByoConfig)
        assert config.sip_ingress_host == "sip.us.audact.ai"
        assert config.signaling_ips == ["203.0.113.10/32"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_byo_config_no_signaling_ips(self):
        respx.get(f"{BASE}/v1/byo/config").mock(
            return_value=_json_response({"sip_ingress_host": "sip.us.audact.ai"})
        )
        async with AudactClient(api_key="key") as c:
            config = await c.get_byo_config()
        assert config.signaling_ips == []


# ─────────────────────────────────────────────────────────────────────────────
# Origin-aware create_number / list_numbers
# ─────────────────────────────────────────────────────────────────────────────

class TestOriginAwareCreateNumber:
    @pytest.mark.asyncio
    @respx.mock
    async def test_create_number_default_origin_omits_origin_field(self):
        """Historical Audact-only flow: origin left unset, never sent as null."""
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_number_payload(), status=201)

        respx.post(f"{BASE}/v1/numbers").mock(side_effect=_handler)

        req = CreateNumberRequest(did="+442045136446", country_code="GB")
        async with AudactClient(api_key="key") as c:
            number = await c.create_number(req)

        assert isinstance(number, PhoneNumber)
        assert number.origin == "audact"

        body = json.loads(captured[0].content)
        assert body == {"did": "+442045136446", "country_code": "GB"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_number_byo_with_existing_connection_id(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                _number_payload(
                    origin="byo",
                    byo_connection_id=str(CONN_ID),
                    provider="twilio",
                    connection_health="healthy",
                ),
                status=201,
            )

        respx.post(f"{BASE}/v1/numbers").mock(side_effect=_handler)

        req = CreateNumberRequest(
            did="+12125551234",
            country_code="US",
            origin="byo",
            byo_connection_id=CONN_ID,
        )
        async with AudactClient(api_key="key") as c:
            number = await c.create_number(req)

        assert number.origin == "byo"
        assert number.byo_connection_id == CONN_ID
        assert number.provider == "twilio"
        assert number.connection_health == "healthy"

        body = json.loads(captured[0].content)
        assert body["origin"] == "byo"
        assert body["byo_connection_id"] == str(CONN_ID)
        assert "connection" not in body

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_number_byo_with_inline_connection(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                _number_payload(
                    origin="byo",
                    byo_connection_id=str(CONN_ID),
                    provider="telnyx",
                    connection_health="unverified",
                ),
                status=201,
            )

        respx.post(f"{BASE}/v1/numbers").mock(side_effect=_handler)

        req = CreateNumberRequest(
            did="+31201234567",
            country_code="NL",
            origin="byo",
            connection=CreateBYOConnectionRequest(
                provider="telnyx",
                sip_host="acme.sip.telnyx.com",
                sip_username="acme-user",
                sip_password="acme-pass",
            ),
        )
        async with AudactClient(api_key="key") as c:
            number = await c.create_number(req)

        assert number.origin == "byo"
        assert number.connection_health == "unverified"

        body = json.loads(captured[0].content)
        assert body["origin"] == "byo"
        assert "byo_connection_id" not in body
        assert body["connection"]["provider"] == "telnyx"
        assert body["connection"]["sip_host"] == "acme.sip.telnyx.com"
        assert body["connection"]["sip_username"] == "acme-user"
        assert "name" not in body["connection"]  # server synthesizes one when omitted

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_number_idempotency_key_header(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_number_payload(), status=201)

        respx.post(f"{BASE}/v1/numbers").mock(side_effect=_handler)

        req = CreateNumberRequest(did="+442045136446", country_code="GB")
        async with AudactClient(api_key="key") as c:
            await c.create_number(req, idempotency_key="idem-number-1")

        assert captured[0].headers["idempotency-key"] == "idem-number-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_number_did_already_exists_409(self):
        respx.post(f"{BASE}/v1/numbers").mock(
            return_value=_error_response(
                409, "CONFLICT", "phone number already exists"
            )
        )
        req = CreateNumberRequest(did="+442045136446", country_code="GB")
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.create_number(req)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_numbers_includes_byo_fields(self):
        respx.get(f"{BASE}/v1/numbers").mock(
            return_value=_json_response(
                {
                    "numbers": [
                        _number_payload(),
                        _number_payload(
                            id=str(uuid4()),
                            did="+12125551234",
                            country_code="US",
                            origin="byo",
                            byo_connection_id=str(CONN_ID),
                            provider="twilio",
                            connection_health="healthy",
                        ),
                    ],
                    "total_count": 2,
                }
            )
        )
        async with AudactClient(api_key="key") as c:
            result = await c.list_numbers()

        assert len(result.numbers) == 2
        assert result.total_count == 2
        assert result.numbers[0].origin == "audact"
        assert result.numbers[1].origin == "byo"
        assert result.numbers[1].provider == "twilio"
        assert result.numbers[1].connection_health == "healthy"

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_numbers_query_params(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response({"numbers": []})

        respx.get(f"{BASE}/v1/numbers").mock(side_effect=_handler)

        async with AudactClient(api_key="key") as c:
            await c.list_numbers(country="NL", status="available", limit=25, cursor="abc")

        assert dict(captured[0].url.params) == {
            "country": "NL",
            "status": "available",
            "limit": "25",
            "cursor": "abc",
        }
