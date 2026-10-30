"""
Tests for the ``client.calls`` sub-client: outbound/
inbound/browser SIP calls, hangup, status, warm handover, and SIP REFER
transfers — voice-gateway (8088).

Part 2 appends below: SIP trunks (inbound/outbound/list),
dispatch rules (routes) list/create, the pre-connect admission-url hook,
and WebSocket tickets.

Uses ``respx`` to mock the voice-gateway transport (``http://localhost:8088``)
so no real network calls are made.
"""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest
import respx

from audact import AudactClient
from audact.client import CallsClient
from audact.exceptions import AudactAPIError, AudactForbiddenError, AudactNotFoundError
from audact.models import (
    AdmissionURLResponse,
    BrowserCallRequest,
    BrowserCallResponse,
    CallStatusResponse,
    CreateDispatchRuleRequest,
    CreateDispatchRuleResponse,
    CreateInboundTrunkRequest,
    CreateInboundTrunkResponse,
    CreateOutboundTrunkRequest,
    CreateOutboundTrunkResponse,
    HandoverRequest,
    HandoverResponse,
    HandoverStateResponse,
    HangupResponse,
    InboundCallRequest,
    InboundCallResponse,
    ListRoutesResponse,
    ListTrunksResponse,
    OutboundCallRequest,
    OutboundCallResponse,
    SetAdmissionURLRequest,
    TransferRequest,
    TransferResponse,
    TransferSessionResponse,
    TransferStateResponse,
    WsTicketResponse,
)

BASE = "http://localhost:8088"

CALL_ID = uuid4()
AGENT_ID = uuid4()
HANDOVER_ID = uuid4()
TRANSFER_ID = uuid4()


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _error_response(status: int, code: str, message: str) -> httpx.Response:
    """The server's real nested error envelope."""
    return httpx.Response(status, json={"error": {"code": code, "message": message}})


@pytest.fixture()
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_test123")


def test_calls_is_calls_client(client: AudactClient) -> None:
    assert isinstance(client.calls, CallsClient)


# ─────────────────────────────────────────────────────────────────────────────
# initiate_outbound_call — POST /v1/sip/calls/outbound
# ─────────────────────────────────────────────────────────────────────────────

class TestInitiateOutboundCall:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/calls/outbound").mock(
            return_value=_json_response(
                {
                    "call_id": str(CALL_ID),
                    "room_name": f"call-{CALL_ID}",
                    "participant_id": f"agent-{CALL_ID}",
                    "sip_call_id": "abc123xyz@sip.telnyx.com",
                },
                status=201,
            )
        )
        async with client as c:
            result = await c.calls.initiate_outbound_call(
                OutboundCallRequest(
                    from_number="+31201234567",
                    destination_number="+49301234567",
                    agent_id=AGENT_ID,
                )
            )
        assert isinstance(result, OutboundCallResponse)
        assert result.call_id == CALL_ID
        assert result.room_name == f"call-{CALL_ID}"
        assert result.sip_call_id == "abc123xyz@sip.telnyx.com"

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_body_auth_and_idempotency_key(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {"call_id": str(CALL_ID), "room_name": "call-x"}, status=201
            )

        respx.post(f"{BASE}/v1/sip/calls/outbound").mock(side_effect=_handler)
        async with client as c:
            await c.calls.initiate_outbound_call(
                OutboundCallRequest(
                    from_number="+31201234567",
                    destination_number="+49301234567",
                    max_duration_seconds=180,
                ),
                idempotency_key="idem-outbound-1",
            )
        request = captured[0]
        assert request.headers["authorization"] == "Bearer aud_live_test123"
        assert request.headers["idempotency-key"] == "idem-outbound-1"
        body = json.loads(request.content)
        assert body == {
            "from_number": "+31201234567",
            "destination_number": "+49301234567",
            "max_duration_seconds": 180,
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_blocked_by_policy_raises_forbidden(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/calls/outbound").mock(
            return_value=_error_response(
                403, "CALL_BLOCKED_BY_POLICY", "outside permitted calling hours"
            )
        )
        with pytest.raises(AudactForbiddenError) as exc_info:
            async with client as c:
                await c.calls.initiate_outbound_call(
                    OutboundCallRequest(
                        from_number="+31201234567", destination_number="+49301234567"
                    )
                )
        assert exc_info.value.code == "CALL_BLOCKED_BY_POLICY"


# ─────────────────────────────────────────────────────────────────────────────
# initiate_inbound_call — POST /v1/sip/calls/inbound
# ─────────────────────────────────────────────────────────────────────────────

class TestInitiateInboundCall:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/calls/inbound").mock(
            return_value=_json_response(
                {
                    "call_id": str(CALL_ID),
                    "room_name": f"call-{CALL_ID}",
                    "trunk_id": "trunk_abc123",
                },
                status=201,
            )
        )
        async with client as c:
            result = await c.calls.initiate_inbound_call(
                InboundCallRequest(caller_number="+31612345678", called_did="+31201234567")
            )
        assert isinstance(result, InboundCallResponse)
        assert result.call_id == CALL_ID
        assert result.trunk_id == "trunk_abc123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_body_and_idempotency_key(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response({"call_id": str(CALL_ID), "room_name": "call-x"}, status=201)

        respx.post(f"{BASE}/v1/sip/calls/inbound").mock(side_effect=_handler)
        async with client as c:
            await c.calls.initiate_inbound_call(
                InboundCallRequest(caller_number="+31612345678", called_did="+31201234567"),
                idempotency_key="idem-inbound-1",
            )
        request = captured[0]
        assert request.headers["idempotency-key"] == "idem-inbound-1"
        assert json.loads(request.content) == {
            "caller_number": "+31612345678",
            "called_did": "+31201234567",
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_rejected_by_admission_raises_forbidden(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/calls/inbound").mock(
            return_value=_error_response(
                403, "CALL_REJECTED_BY_ADMISSION", "admission_url rejected this call"
            )
        )
        with pytest.raises(AudactForbiddenError):
            async with client as c:
                await c.calls.initiate_inbound_call(
                    InboundCallRequest(caller_number="+31612345678", called_did="+31201234567")
                )

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_routing_rule_raises_not_found(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/calls/inbound").mock(
            return_value=_error_response(404, "not_found", "no routing rule for this DID")
        )
        with pytest.raises(AudactNotFoundError):
            async with client as c:
                await c.calls.initiate_inbound_call(
                    InboundCallRequest(caller_number="+31612345678", called_did="+31201234567")
                )


# ─────────────────────────────────────────────────────────────────────────────
# create_browser_call — POST /v1/sip/calls/browser
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateBrowserCall:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic_returns_livekit_details(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/calls/browser").mock(
            return_value=_json_response(
                {
                    "call_id": str(CALL_ID),
                    "room_name": f"call-{CALL_ID}",
                    "livekit_url": "wss://livekit.example.test",
                    "livekit_token": "eyJhbGciOiJIUzI1NiJ9.example",
                },
                status=201,
            )
        )
        async with client as c:
            result = await c.calls.create_browser_call(BrowserCallRequest(agent_id=AGENT_ID))
        assert isinstance(result, BrowserCallResponse)
        assert result.call_id == CALL_ID
        assert result.livekit_url == "wss://livekit.example.test"
        assert result.livekit_token == "eyJhbGciOiJIUzI1NiJ9.example"

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_body_and_idempotency_key(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {
                    "call_id": str(CALL_ID),
                    "room_name": "call-x",
                    "livekit_url": "wss://livekit.example.test",
                    "livekit_token": "tok",
                },
                status=201,
            )

        respx.post(f"{BASE}/v1/sip/calls/browser").mock(side_effect=_handler)
        async with client as c:
            await c.calls.create_browser_call(
                BrowserCallRequest(agent_id=AGENT_ID, metadata={"source": "test"}),
                idempotency_key="idem-browser-1",
            )
        request = captured[0]
        assert request.headers["idempotency-key"] == "idem-browser-1"
        assert json.loads(request.content) == {
            "agent_id": str(AGENT_ID),
            "metadata": {"source": "test"},
        }


# ─────────────────────────────────────────────────────────────────────────────
# hangup_call — POST /v1/sip/calls/{call_id}/hangup
# ─────────────────────────────────────────────────────────────────────────────

class TestHangupCall:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/calls/{CALL_ID}/hangup").mock(
            return_value=_json_response(
                {"call_id": str(CALL_ID), "room_name": f"call-{CALL_ID}", "status": "terminated"}
            )
        )
        async with client as c:
            result = await c.calls.hangup_call(CALL_ID)
        assert isinstance(result, HangupResponse)
        assert result.status == "terminated"

    @pytest.mark.asyncio
    @respx.mock
    async def test_not_found_cross_tenant(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/calls/{CALL_ID}/hangup").mock(
            return_value=_error_response(404, "not_found", "call not found")
        )
        with pytest.raises(AudactNotFoundError):
            async with client as c:
                await c.calls.hangup_call(CALL_ID)

    @pytest.mark.asyncio
    @respx.mock
    async def test_already_terminated_conflict(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/calls/{CALL_ID}/hangup").mock(
            return_value=_error_response(409, "conflict", "call is already terminated")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.calls.hangup_call(CALL_ID)
        assert exc_info.value.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# get_call_status — GET /v1/sip/calls/{call_id}/status
# ─────────────────────────────────────────────────────────────────────────────

class TestGetCallStatus:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        respx.get(f"{BASE}/v1/sip/calls/{CALL_ID}/status").mock(
            return_value=_json_response(
                {
                    "call_id": str(CALL_ID),
                    "room_name": f"call-{CALL_ID}",
                    "status": "active",
                    "started_at": "2026-09-18T10:00:00Z",
                }
            )
        )
        async with client as c:
            result = await c.calls.get_call_status(CALL_ID)
        assert isinstance(result, CallStatusResponse)
        assert result.status == "active"
        assert result.started_at is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_auth_header(self, client: AudactClient):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return _json_response(
                {"call_id": str(CALL_ID), "room_name": "call-x", "status": "terminated"}
            )

        respx.get(f"{BASE}/v1/sip/calls/{CALL_ID}/status").mock(side_effect=_handler)
        async with client as c:
            await c.calls.get_call_status(CALL_ID)
        assert captured_headers[0]["authorization"] == "Bearer aud_live_test123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_not_found(self, client: AudactClient):
        respx.get(f"{BASE}/v1/sip/calls/{CALL_ID}/status").mock(
            return_value=_error_response(404, "not_found", "call not found")
        )
        with pytest.raises(AudactNotFoundError):
            async with client as c:
                await c.calls.get_call_status(CALL_ID)


# ─────────────────────────────────────────────────────────────────────────────
# initiate_handover — POST /v1/sip/calls/{call_id}/handover
# get_handover — GET /v1/sip/handovers/{handover_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestHandover:
    @pytest.mark.asyncio
    @respx.mock
    async def test_initiate_handover_basic(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/calls/{CALL_ID}/handover").mock(
            return_value=_json_response(
                {
                    "call_id": str(CALL_ID),
                    "handover_id": str(HANDOVER_ID),
                    "state": "initiated",
                },
                status=201,
            )
        )
        async with client as c:
            result = await c.calls.initiate_handover(
                CALL_ID,
                HandoverRequest(destination="+49301234567", handover_reason="escalation"),
            )
        assert isinstance(result, HandoverResponse)
        assert result.handover_id == HANDOVER_ID
        assert result.state == "initiated"

    @pytest.mark.asyncio
    @respx.mock
    async def test_initiate_handover_sends_body(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {"call_id": str(CALL_ID), "handover_id": str(HANDOVER_ID), "state": "initiated"},
                status=201,
            )

        respx.post(f"{BASE}/v1/sip/calls/{CALL_ID}/handover").mock(side_effect=_handler)
        async with client as c:
            await c.calls.initiate_handover(
                CALL_ID,
                HandoverRequest(
                    destination="+49301234567",
                    handover_reason="escalation",
                    whisper_mode="spoken",
                ),
            )
        assert json.loads(captured[0].content) == {
            "destination": "+49301234567",
            "handover_reason": "escalation",
            "whisper_mode": "spoken",
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_handover_basic(self, client: AudactClient):
        respx.get(f"{BASE}/v1/sip/handovers/{HANDOVER_ID}").mock(
            return_value=_json_response(
                {
                    "handover_id": str(HANDOVER_ID),
                    "call_id": str(CALL_ID),
                    "state": "whispering",
                    "handover_reason": "agent_requested",
                    "whisper_mode": "spoken",
                    "destination_hash": "abc123",
                }
            )
        )
        async with client as c:
            result = await c.calls.get_handover(HANDOVER_ID)
        assert isinstance(result, HandoverStateResponse)
        assert result.state == "whispering"
        assert result.destination_hash == "abc123"
        # Raw phone number is never returned by this endpoint.
        assert "destination" not in result.model_dump()

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_handover_not_found(self, client: AudactClient):
        respx.get(f"{BASE}/v1/sip/handovers/{HANDOVER_ID}").mock(
            return_value=_error_response(404, "not_found", "handover not found")
        )
        with pytest.raises(AudactNotFoundError):
            async with client as c:
                await c.calls.get_handover(HANDOVER_ID)


# ─────────────────────────────────────────────────────────────────────────────
# initiate_transfer / get_transfer_state / bridge / cancel / end
# ─────────────────────────────────────────────────────────────────────────────

class TestTransfers:
    @pytest.mark.asyncio
    @respx.mock
    async def test_initiate_transfer_basic(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/calls/{CALL_ID}/transfer").mock(
            return_value=_json_response(
                {
                    "call_id": str(CALL_ID),
                    "transfer_id": str(TRANSFER_ID),
                    "status": "started",
                    "transfer_option": "blind",
                },
                status=201,
            )
        )
        async with client as c:
            result = await c.calls.initiate_transfer(
                CALL_ID, TransferRequest(destination="+49301234567")
            )
        assert isinstance(result, TransferResponse)
        assert result.transfer_id == TRANSFER_ID
        assert result.status == "started"
        assert result.transfer_option == "blind"

    @pytest.mark.asyncio
    @respx.mock
    async def test_initiate_transfer_sends_idempotency_key(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {
                    "call_id": str(CALL_ID),
                    "transfer_id": str(TRANSFER_ID),
                    "status": "started",
                    "transfer_option": "warm",
                },
                status=201,
            )

        respx.post(f"{BASE}/v1/sip/calls/{CALL_ID}/transfer").mock(side_effect=_handler)
        async with client as c:
            await c.calls.initiate_transfer(
                CALL_ID,
                TransferRequest(destination="+49301234567", transfer_option="warm"),
                idempotency_key="idem-transfer-1",
            )
        request = captured[0]
        assert request.headers["idempotency-key"] == "idem-transfer-1"
        assert json.loads(request.content) == {
            "destination": "+49301234567",
            "transfer_option": "warm",
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_transfer_state_basic(self, client: AudactClient):
        respx.get(f"{BASE}/v1/sip/transfers/{TRANSFER_ID}").mock(
            return_value=_json_response(
                {
                    "transfer_id": str(TRANSFER_ID),
                    "call_id": str(CALL_ID),
                    "status": "bridged",
                    "transfer_option": "blind",
                    "destination_hash": "deadbeef",
                }
            )
        )
        async with client as c:
            result = await c.calls.get_transfer_state(TRANSFER_ID)
        assert isinstance(result, TransferSessionResponse)
        assert result.status == "bridged"
        assert "destination" not in result.model_dump()

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_transfer_state_not_found(self, client: AudactClient):
        respx.get(f"{BASE}/v1/sip/transfers/{TRANSFER_ID}").mock(
            return_value=_error_response(404, "not_found", "transfer not found")
        )
        with pytest.raises(AudactNotFoundError):
            async with client as c:
                await c.calls.get_transfer_state(TRANSFER_ID)

    @pytest.mark.asyncio
    @respx.mock
    async def test_bridge_transfer(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/transfers/{TRANSFER_ID}/bridge").mock(
            return_value=_json_response({"transfer_id": str(TRANSFER_ID), "status": "bridged"})
        )
        async with client as c:
            result = await c.calls.bridge_transfer(TRANSFER_ID)
        assert isinstance(result, TransferStateResponse)
        assert result.status == "bridged"

    @pytest.mark.asyncio
    @respx.mock
    async def test_cancel_transfer(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/transfers/{TRANSFER_ID}/cancel").mock(
            return_value=_json_response({"transfer_id": str(TRANSFER_ID), "status": "cancelled"})
        )
        async with client as c:
            result = await c.calls.cancel_transfer(TRANSFER_ID)
        assert isinstance(result, TransferStateResponse)
        assert result.status == "cancelled"

    @pytest.mark.asyncio
    @respx.mock
    async def test_end_transfer(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/transfers/{TRANSFER_ID}/end").mock(
            return_value=_json_response({"transfer_id": str(TRANSFER_ID), "status": "ended"})
        )
        async with client as c:
            result = await c.calls.end_transfer(TRANSFER_ID)
        assert isinstance(result, TransferStateResponse)
        assert result.status == "ended"

    @pytest.mark.asyncio
    @respx.mock
    async def test_bridge_transfer_not_found(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/transfers/{TRANSFER_ID}/bridge").mock(
            return_value=_error_response(404, "not_found", "transfer not found")
        )
        with pytest.raises(AudactNotFoundError):
            async with client as c:
                await c.calls.bridge_transfer(TRANSFER_ID)

    @pytest.mark.asyncio
    @respx.mock
    async def test_bridge_transfer_sends_auth_header(self, client: AudactClient):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return _json_response({"transfer_id": str(TRANSFER_ID), "status": "bridged"})

        respx.post(f"{BASE}/v1/sip/transfers/{TRANSFER_ID}/bridge").mock(side_effect=_handler)
        async with client as c:
            await c.calls.bridge_transfer(TRANSFER_ID)
        assert captured_headers[0]["authorization"] == "Bearer aud_live_test123"


# ─────────────────────────────────────────────────────────────────────────────
# list_trunks — GET /v1/sip/trunks
# create_inbound_trunk — POST /v1/sip/trunks/inbound
# create_outbound_trunk — POST /v1/sip/trunks/outbound
# ─────────────────────────────────────────────────────────────────────────────

class TestListTrunks:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        respx.get(f"{BASE}/v1/sip/trunks").mock(
            return_value=_json_response(
                {
                    "inbound_trunks": [
                        {
                            "sip_trunk_id": "ST_abc123",
                            "provider": "telnyx",
                            "did": "+31201234567",
                        }
                    ],
                    "outbound_trunks": [
                        {
                            "sip_trunk_id": "SOT_abc123",
                            "provider": "telnyx",
                            "address": "sip.telnyx.com",
                        }
                    ],
                    "has_more": False,
                }
            )
        )
        async with client as c:
            result = await c.calls.list_trunks()
        assert isinstance(result, ListTrunksResponse)
        assert len(result.inbound_trunks) == 1
        assert result.inbound_trunks[0].sip_trunk_id == "ST_abc123"
        assert len(result.outbound_trunks) == 1
        assert result.outbound_trunks[0].address == "sip.telnyx.com"
        assert result.has_more is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_limit_and_cursor_query_params(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/sip/trunks").mock(
            return_value=_json_response({"inbound_trunks": [], "outbound_trunks": []})
        )
        async with client as c:
            await c.calls.list_trunks(cursor="opaque-cursor", limit=25)
        request = route.calls[0].request
        assert request.url.params["cursor"] == "opaque-cursor"
        assert request.url.params["limit"] == "25"

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_query_params_by_default(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/sip/trunks").mock(
            return_value=_json_response({"inbound_trunks": [], "outbound_trunks": []})
        )
        async with client as c:
            await c.calls.list_trunks()
        request = route.calls[0].request
        assert request.url.query == b""

    @pytest.mark.asyncio
    @respx.mock
    async def test_invalid_cursor_raises_api_error(self, client: AudactClient):
        respx.get(f"{BASE}/v1/sip/trunks").mock(
            return_value=_error_response(400, "INVALID_REQUEST", "bad cursor")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.calls.list_trunks(cursor="not-valid")
        assert exc_info.value.status_code == 400


class TestCreateInboundTrunk:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/trunks/inbound").mock(
            return_value=_json_response(
                {
                    "sip_trunk_id": "ST_abc123",
                    "provider": "telnyx",
                    "inbound_numbers": ["+31201234567"],
                    "status": "registered",
                },
                status=201,
            )
        )
        async with client as c:
            result = await c.calls.create_inbound_trunk(
                CreateInboundTrunkRequest(
                    provider="telnyx",
                    inbound_numbers=["+31201234567"],
                    allowed_addresses=["192.76.120.0/22"],
                )
            )
        assert isinstance(result, CreateInboundTrunkResponse)
        assert result.sip_trunk_id == "ST_abc123"
        assert result.status == "registered"

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_body_and_idempotency_key(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {
                    "sip_trunk_id": "ST_abc123",
                    "provider": "telnyx",
                    "inbound_numbers": ["+31201234567"],
                    "status": "registered",
                },
                status=200,
            )

        respx.post(f"{BASE}/v1/sip/trunks/inbound").mock(side_effect=_handler)
        async with client as c:
            await c.calls.create_inbound_trunk(
                CreateInboundTrunkRequest(
                    provider="telnyx", inbound_numbers=["+31201234567"]
                ),
                idempotency_key="idem-trunk-in-1",
            )
        request = captured[0]
        assert request.headers["idempotency-key"] == "idem-trunk-in-1"
        assert json.loads(request.content) == {
            "provider": "telnyx",
            "inbound_numbers": ["+31201234567"],
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_idempotency_conflict_raises_api_error(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/trunks/inbound").mock(
            return_value=_error_response(409, "conflict", "idempotency key reused")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.calls.create_inbound_trunk(
                    CreateInboundTrunkRequest(
                        provider="telnyx", inbound_numbers=["+31201234567"]
                    ),
                    idempotency_key="idem-trunk-in-1",
                )
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    @respx.mock
    async def test_missing_field_raises_api_error(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/trunks/inbound").mock(
            return_value=_error_response(400, "INVALID_REQUEST", "missing provider")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.calls.create_inbound_trunk(
                    CreateInboundTrunkRequest(provider="telnyx", inbound_numbers=[])
                )
        assert exc_info.value.status_code == 400


class TestCreateOutboundTrunk:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/trunks/outbound").mock(
            return_value=_json_response(
                {
                    "sip_trunk_id": "SOT_abc123",
                    "provider": "telnyx",
                    "address": "sip.telnyx.com",
                    "status": "registered",
                },
                status=201,
            )
        )
        async with client as c:
            result = await c.calls.create_outbound_trunk(
                CreateOutboundTrunkRequest(
                    provider="telnyx",
                    address="sip.telnyx.com",
                    numbers=["+31201234567"],
                    transport="tcp",
                )
            )
        assert isinstance(result, CreateOutboundTrunkResponse)
        assert result.address == "sip.telnyx.com"
        assert result.status == "registered"

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_idempotency_key(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {
                    "sip_trunk_id": "SOT_abc123",
                    "provider": "telnyx",
                    "address": "sip.telnyx.com",
                    "status": "registered",
                }
            )

        respx.post(f"{BASE}/v1/sip/trunks/outbound").mock(side_effect=_handler)
        async with client as c:
            await c.calls.create_outbound_trunk(
                CreateOutboundTrunkRequest(
                    provider="telnyx",
                    address="sip.telnyx.com",
                    numbers=["+31201234567"],
                ),
                idempotency_key="idem-trunk-out-1",
            )
        assert captured[0].headers["idempotency-key"] == "idem-trunk-out-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_missing_address_raises_api_error(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/trunks/outbound").mock(
            return_value=_error_response(400, "INVALID_REQUEST", "missing address")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.calls.create_outbound_trunk(
                    CreateOutboundTrunkRequest(
                        provider="telnyx", address="", numbers=[]
                    )
                )
        assert exc_info.value.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# list_dispatch_rules — GET /v1/sip/routes
# create_dispatch_rule — POST /v1/sip/routes
# ─────────────────────────────────────────────────────────────────────────────

class TestListDispatchRules:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        respx.get(f"{BASE}/v1/sip/routes").mock(
            return_value=_json_response(
                {
                    "routes": [
                        {
                            "dispatch_rule_id": "SDR_abc123",
                            "did": "+31201234567",
                            "agent_id": str(AGENT_ID),
                            "room_prefix": f"call-{AGENT_ID}-",
                        }
                    ],
                    "has_more": False,
                }
            )
        )
        async with client as c:
            result = await c.calls.list_dispatch_rules()
        assert isinstance(result, ListRoutesResponse)
        assert len(result.routes) == 1
        assert result.routes[0].dispatch_rule_id == "SDR_abc123"
        assert result.routes[0].agent_id == AGENT_ID

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_limit_and_cursor_query_params(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/sip/routes").mock(
            return_value=_json_response({"routes": []})
        )
        async with client as c:
            await c.calls.list_dispatch_rules(cursor="next-page", limit=10)
        request = route.calls[0].request
        assert request.url.params["cursor"] == "next-page"
        assert request.url.params["limit"] == "10"

    @pytest.mark.asyncio
    @respx.mock
    async def test_invalid_limit_raises_api_error(self, client: AudactClient):
        respx.get(f"{BASE}/v1/sip/routes").mock(
            return_value=_error_response(400, "INVALID_REQUEST", "bad limit")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.calls.list_dispatch_rules(limit=99999)
        assert exc_info.value.status_code == 400


class TestCreateDispatchRule:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/routes").mock(
            return_value=_json_response(
                {"dispatch_rule_id": "dr-abc123", "status": "routed"},
                status=201,
            )
        )
        async with client as c:
            result = await c.calls.create_dispatch_rule(
                CreateDispatchRuleRequest(did="+31201234567", agent_id=AGENT_ID)
            )
        assert isinstance(result, CreateDispatchRuleResponse)
        assert result.dispatch_rule_id == "dr-abc123"
        assert result.status == "routed"

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_body_and_idempotency_key(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {"dispatch_rule_id": "dr-abc123", "status": "routed"}, status=200
            )

        respx.post(f"{BASE}/v1/sip/routes").mock(side_effect=_handler)
        async with client as c:
            await c.calls.create_dispatch_rule(
                CreateDispatchRuleRequest(did="+31201234567", agent_id=AGENT_ID),
                idempotency_key="idem-route-1",
            )
        request = captured[0]
        assert request.headers["idempotency-key"] == "idem-route-1"
        assert json.loads(request.content) == {
            "did": "+31201234567",
            "agent_id": str(AGENT_ID),
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_missing_did_raises_api_error(self, client: AudactClient):
        respx.post(f"{BASE}/v1/sip/routes").mock(
            return_value=_error_response(400, "INVALID_REQUEST", "missing did")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.calls.create_dispatch_rule(
                    CreateDispatchRuleRequest(did="", agent_id=AGENT_ID)
                )
        assert exc_info.value.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# get_admission_url — GET /v1/sip/admission-url
# set_admission_url — PUT /v1/sip/admission-url
# ─────────────────────────────────────────────────────────────────────────────

class TestAdmissionUrl:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_basic(self, client: AudactClient):
        respx.get(f"{BASE}/v1/sip/admission-url").mock(
            return_value=_json_response(
                {"admission_url": "https://tenant.example.com/admission"}
            )
        )
        async with client as c:
            result = await c.calls.get_admission_url()
        assert isinstance(result, AdmissionURLResponse)
        assert result.admission_url == "https://tenant.example.com/admission"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_unauthorized_raises_auth_error(self, client: AudactClient):
        from audact.exceptions import AudactAuthError

        respx.get(f"{BASE}/v1/sip/admission-url").mock(
            return_value=_error_response(401, "UNAUTHORIZED", "auth required")
        )
        with pytest.raises(AudactAuthError):
            async with client as c:
                await c.calls.get_admission_url()

    @pytest.mark.asyncio
    @respx.mock
    async def test_set_basic(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {"admission_url": "https://tenant.example.com/admission"}
            )

        respx.put(f"{BASE}/v1/sip/admission-url").mock(side_effect=_handler)
        async with client as c:
            result = await c.calls.set_admission_url(
                SetAdmissionURLRequest(
                    admission_url="https://tenant.example.com/admission"
                )
            )
        assert isinstance(result, AdmissionURLResponse)
        assert result.admission_url == "https://tenant.example.com/admission"
        assert json.loads(captured[0].content) == {
            "admission_url": "https://tenant.example.com/admission"
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_set_invalid_url_raises_api_error(self, client: AudactClient):
        respx.put(f"{BASE}/v1/sip/admission-url").mock(
            return_value=_error_response(
                400, "INVALID_REQUEST", "not a valid http(s) URL"
            )
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.calls.set_admission_url(
                    SetAdmissionURLRequest(admission_url="not-a-url")
                )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    @respx.mock
    async def test_set_no_configuration_raises_not_found(self, client: AudactClient):
        respx.put(f"{BASE}/v1/sip/admission-url").mock(
            return_value=_error_response(404, "not_found", "no configuration")
        )
        with pytest.raises(AudactNotFoundError):
            async with client as c:
                await c.calls.set_admission_url(
                    SetAdmissionURLRequest(admission_url="")
                )


# ─────────────────────────────────────────────────────────────────────────────
# create_ws_ticket — POST /v1/ws/ticket
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateWsTicket:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        ticket_value = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        respx.post(f"{BASE}/v1/ws/ticket").mock(
            return_value=_json_response({"ticket": ticket_value})
        )
        async with client as c:
            result = await c.calls.create_ws_ticket()
        assert isinstance(result, WsTicketResponse)
        assert result.ticket == ticket_value

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_auth_header(self, client: AudactClient):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return _json_response({"ticket": "tick-1"})

        respx.post(f"{BASE}/v1/ws/ticket").mock(side_effect=_handler)
        async with client as c:
            await c.calls.create_ws_ticket()
        assert captured_headers[0]["authorization"] == "Bearer aud_live_test123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_unauthorized_raises_auth_error(self, client: AudactClient):
        from audact.exceptions import AudactAuthError

        respx.post(f"{BASE}/v1/ws/ticket").mock(
            return_value=_error_response(401, "UNAUTHORIZED", "missing bearer token")
        )
        with pytest.raises(AudactAuthError):
            async with client as c:
                await c.calls.create_ws_ticket()

