"""
Tests for the numbers lifecycle completion surface: list/create/
lookup/assign/suspend/resume/release/delete/set_trunk on top of the Telnyx
order flow — voice-gateway (8088).

Uses ``respx`` to mock the voice-gateway transport (``http://localhost:8088``)
so no real network calls are made.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import respx

from audact import AudactClient
from audact.exceptions import AudactAPIError, AudactNotFoundError
from audact.models import (
    AssignNumberRequest,
    CreateNumberRequest,
    Page,
    PhoneNumber,
    SetNumberTrunkRequest,
)

BASE = "http://localhost:8088"

NUMBER_ID = uuid4()
AGENT_ID = uuid4()
NOW = datetime.now(tz=UTC).isoformat()


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _error_response(status: int, code: str, message: str) -> httpx.Response:
    """The server's real nested error envelope."""
    return httpx.Response(status, json={"error": {"code": code, "message": message}})


@pytest.fixture()
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_test123")


def _phone_number_payload(**overrides) -> dict:
    payload = {
        "id": str(NUMBER_ID),
        "did": "+31201234567",
        "country_code": "NL",
        "trunk_provider": "telnyx",
        "trunk_id": "ST_abc123",
        "status": "available",
        "created_at": NOW,
        "updated_at": NOW,
    }
    payload.update(overrides)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# list_numbers — GET /v1/numbers (paginated, cursor convention)
# ─────────────────────────────────────────────────────────────────────────────

class TestListNumbers:
    @pytest.mark.asyncio
    @respx.mock
    async def test_list_numbers_basic(self, client: AudactClient):
        respx.get(f"{BASE}/v1/numbers").mock(
            return_value=_json_response(
                {"numbers": [_phone_number_payload()], "next_cursor": None, "total_count": 1}
            )
        )
        async with client as c:
            page = await c.list_numbers()
        assert isinstance(page, Page)
        assert page.has_more is False
        assert page.next_cursor is None
        assert len(page.items) == 1
        assert isinstance(page.items[0], PhoneNumber)
        assert page.items[0].id == NUMBER_ID
        assert page.items[0].did == "+31201234567"

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_numbers_has_more_derived_from_next_cursor(self, client: AudactClient):
        respx.get(f"{BASE}/v1/numbers").mock(
            return_value=_json_response(
                {"numbers": [], "next_cursor": "cursor-2", "total_count": 5}
            )
        )
        async with client as c:
            page = await c.list_numbers()
        assert page.has_more is True
        assert page.next_cursor == "cursor-2"

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_numbers_sends_filters_and_cursor(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response({"numbers": [], "next_cursor": None, "total_count": 0})

        respx.get(f"{BASE}/v1/numbers").mock(side_effect=_handler)
        async with client as c:
            await c.list_numbers(country="NL", status="available", cursor="cursor-1", limit=25)
        sent = dict(captured[0].url.params)
        assert sent == {
            "country": "NL",
            "status": "available",
            "cursor": "cursor-1",
            "limit": "25",
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_numbers_sends_auth_header(self, client: AudactClient):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return _json_response({"numbers": [], "next_cursor": None, "total_count": 0})

        respx.get(f"{BASE}/v1/numbers").mock(side_effect=_handler)
        async with client as c:
            await c.list_numbers()
        assert captured_headers[0]["authorization"] == "Bearer aud_live_test123"


# ─────────────────────────────────────────────────────────────────────────────
# create_number — POST /v1/numbers
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateNumber:
    @pytest.mark.asyncio
    @respx.mock
    async def test_create_number_basic(self, client: AudactClient):
        respx.post(f"{BASE}/v1/numbers").mock(
            return_value=_json_response(_phone_number_payload(), status=201)
        )
        async with client as c:
            result = await c.create_number(
                CreateNumberRequest(did="+31201234567", country_code="NL")
            )
        assert isinstance(result, PhoneNumber)
        assert result.id == NUMBER_ID
        assert result.status == "available"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_number_sends_body_and_idempotency_key(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_phone_number_payload(), status=201)

        respx.post(f"{BASE}/v1/numbers").mock(side_effect=_handler)
        async with client as c:
            await c.create_number(
                CreateNumberRequest(
                    did="+442045136446", country_code="GB", trunk_provider="telnyx"
                ),
                idempotency_key="idem-create-number-1",
            )
        request = captured[0]
        assert request.headers["idempotency-key"] == "idem-create-number-1"
        body = json.loads(request.content)
        assert body == {
            "did": "+442045136446",
            "country_code": "GB",
            "trunk_provider": "telnyx",
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_number_conflict_raises(self, client: AudactClient):
        respx.post(f"{BASE}/v1/numbers").mock(
            return_value=_error_response(409, "conflict", "phone number already exists")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.create_number(CreateNumberRequest(did="+31201234567", country_code="NL"))
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "conflict"


# ─────────────────────────────────────────────────────────────────────────────
# lookup_number — GET /v1/numbers/lookup
# ─────────────────────────────────────────────────────────────────────────────

class TestLookupNumber:
    @pytest.mark.asyncio
    @respx.mock
    async def test_lookup_number_basic(self, client: AudactClient):
        respx.get(f"{BASE}/v1/numbers/lookup").mock(
            return_value=_json_response(_phone_number_payload())
        )
        async with client as c:
            result = await c.lookup_number("+31201234567")
        assert isinstance(result, PhoneNumber)
        assert result.did == "+31201234567"

    @pytest.mark.asyncio
    @respx.mock
    async def test_lookup_number_sends_did_query_param(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_phone_number_payload())

        respx.get(f"{BASE}/v1/numbers/lookup").mock(side_effect=_handler)
        async with client as c:
            await c.lookup_number("+31201234567")
        assert dict(captured[0].url.params) == {"did": "+31201234567"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_lookup_number_not_found(self, client: AudactClient):
        respx.get(f"{BASE}/v1/numbers/lookup").mock(
            return_value=_error_response(404, "not_found", "DID not found for this tenant")
        )
        with pytest.raises(AudactNotFoundError):
            async with client as c:
                await c.lookup_number("+31200000000")


# ─────────────────────────────────────────────────────────────────────────────
# assign_number — POST /v1/numbers/{id}/assign
# ─────────────────────────────────────────────────────────────────────────────

class TestAssignNumber:
    @pytest.mark.asyncio
    @respx.mock
    async def test_assign_number_success(self, client: AudactClient):
        respx.post(f"{BASE}/v1/numbers/{NUMBER_ID}/assign").mock(
            return_value=httpx.Response(204)
        )
        async with client as c:
            result = await c.assign_number(NUMBER_ID, AssignNumberRequest(agent_id=AGENT_ID))
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_assign_number_sends_body_and_idempotency_key(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(204)

        respx.post(f"{BASE}/v1/numbers/{NUMBER_ID}/assign").mock(side_effect=_handler)
        async with client as c:
            await c.assign_number(
                NUMBER_ID,
                AssignNumberRequest(agent_id=AGENT_ID),
                idempotency_key="idem-assign-1",
            )
        request = captured[0]
        assert request.headers["idempotency-key"] == "idem-assign-1"
        assert json.loads(request.content) == {"agent_id": str(AGENT_ID)}

    @pytest.mark.asyncio
    @respx.mock
    async def test_assign_number_already_assigned_conflict(self, client: AudactClient):
        respx.post(f"{BASE}/v1/numbers/{NUMBER_ID}/assign").mock(
            return_value=_error_response(409, "conflict", "phone number is already assigned")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.assign_number(NUMBER_ID, AssignNumberRequest(agent_id=AGENT_ID))
        assert exc_info.value.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# suspend_number / resume_number — POST /v1/numbers/{id}/suspend|resume
# ─────────────────────────────────────────────────────────────────────────────

class TestSuspendResumeNumber:
    @pytest.mark.asyncio
    @respx.mock
    async def test_suspend_number_success(self, client: AudactClient):
        respx.post(f"{BASE}/v1/numbers/{NUMBER_ID}/suspend").mock(
            return_value=httpx.Response(204)
        )
        async with client as c:
            result = await c.suspend_number(NUMBER_ID)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_suspend_number_sends_idempotency_key(self, client: AudactClient):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return httpx.Response(200)

        respx.post(f"{BASE}/v1/numbers/{NUMBER_ID}/suspend").mock(side_effect=_handler)
        async with client as c:
            await c.suspend_number(NUMBER_ID, idempotency_key="idem-suspend-1")
        assert captured_headers[0]["idempotency-key"] == "idem-suspend-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_suspend_number_not_assigned_conflict(self, client: AudactClient):
        respx.post(f"{BASE}/v1/numbers/{NUMBER_ID}/suspend").mock(
            return_value=_error_response(409, "conflict", "phone number is not currently assigned")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.suspend_number(NUMBER_ID)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    @respx.mock
    async def test_resume_number_success(self, client: AudactClient):
        respx.post(f"{BASE}/v1/numbers/{NUMBER_ID}/resume").mock(
            return_value=httpx.Response(204)
        )
        async with client as c:
            result = await c.resume_number(NUMBER_ID)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_resume_number_not_suspended_conflict(self, client: AudactClient):
        respx.post(f"{BASE}/v1/numbers/{NUMBER_ID}/resume").mock(
            return_value=_error_response(409, "conflict", "phone number is not currently suspended")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.resume_number(NUMBER_ID)
        assert exc_info.value.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# release_number — DELETE /v1/numbers/{id}/release
# ─────────────────────────────────────────────────────────────────────────────

class TestReleaseNumber:
    @pytest.mark.asyncio
    @respx.mock
    async def test_release_number_success(self, client: AudactClient):
        respx.delete(f"{BASE}/v1/numbers/{NUMBER_ID}/release").mock(
            return_value=httpx.Response(204)
        )
        async with client as c:
            result = await c.release_number(NUMBER_ID)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_release_number_sends_idempotency_key(self, client: AudactClient):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return httpx.Response(200)

        respx.delete(f"{BASE}/v1/numbers/{NUMBER_ID}/release").mock(side_effect=_handler)
        async with client as c:
            await c.release_number(NUMBER_ID, idempotency_key="idem-release-1")
        assert captured_headers[0]["idempotency-key"] == "idem-release-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_release_number_dependency_error_surfaced(self, client: AudactClient):
        respx.delete(f"{BASE}/v1/numbers/{NUMBER_ID}/release").mock(
            return_value=_error_response(502, "dependency_error", "call-routing teardown failed")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.release_number(NUMBER_ID)
        assert exc_info.value.status_code == 502
        assert exc_info.value.code == "dependency_error"


# ─────────────────────────────────────────────────────────────────────────────
# delete_number — DELETE /v1/numbers/{id}
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteNumber:
    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_number_success(self, client: AudactClient):
        respx.delete(f"{BASE}/v1/numbers/{NUMBER_ID}").mock(return_value=httpx.Response(204))
        async with client as c:
            result = await c.delete_number(NUMBER_ID)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_number_sends_auth_header(self, client: AudactClient):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return httpx.Response(204)

        respx.delete(f"{BASE}/v1/numbers/{NUMBER_ID}").mock(side_effect=_handler)
        async with client as c:
            await c.delete_number(NUMBER_ID)
        assert captured_headers[0]["authorization"] == "Bearer aud_live_test123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_number_still_assigned_conflict(self, client: AudactClient):
        respx.delete(f"{BASE}/v1/numbers/{NUMBER_ID}").mock(
            return_value=_error_response(409, "conflict", "phone number is still assigned")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.delete_number(NUMBER_ID)
        assert exc_info.value.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# set_number_trunk — PUT /v1/numbers/{id}/trunk
# ─────────────────────────────────────────────────────────────────────────────

class TestSetNumberTrunk:
    @pytest.mark.asyncio
    @respx.mock
    async def test_set_number_trunk_basic(self, client: AudactClient):
        respx.put(f"{BASE}/v1/numbers/{NUMBER_ID}/trunk").mock(
            return_value=_json_response(_phone_number_payload(trunk_id="ST_UdxCXESXmgr5"))
        )
        async with client as c:
            result = await c.set_number_trunk(
                NUMBER_ID, SetNumberTrunkRequest(trunk_id="ST_UdxCXESXmgr5")
            )
        assert isinstance(result, PhoneNumber)
        assert result.trunk_id == "ST_UdxCXESXmgr5"

    @pytest.mark.asyncio
    @respx.mock
    async def test_set_number_trunk_sends_body(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_phone_number_payload())

        respx.put(f"{BASE}/v1/numbers/{NUMBER_ID}/trunk").mock(side_effect=_handler)
        async with client as c:
            await c.set_number_trunk(NUMBER_ID, SetNumberTrunkRequest(trunk_id="ST_abc"))
        body = json.loads(captured[0].content)
        assert body == {"trunk_id": "ST_abc"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_set_number_trunk_clears_link_with_empty_string(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_phone_number_payload(trunk_id=None))

        respx.put(f"{BASE}/v1/numbers/{NUMBER_ID}/trunk").mock(side_effect=_handler)
        async with client as c:
            result = await c.set_number_trunk(NUMBER_ID, SetNumberTrunkRequest(trunk_id=""))
        assert json.loads(captured[0].content) == {"trunk_id": ""}
        assert result.trunk_id is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_set_number_trunk_not_found(self, client: AudactClient):
        respx.put(f"{BASE}/v1/numbers/{NUMBER_ID}/trunk").mock(
            return_value=_error_response(404, "not_found", "number not found")
        )
        with pytest.raises(AudactNotFoundError):
            async with client as c:
                await c.set_number_trunk(NUMBER_ID, SetNumberTrunkRequest(trunk_id="ST_abc"))
