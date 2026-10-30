"""
Offline end-to-end flow through a single ``base_url``.

One client, one host: list agents -> place an outbound call -> poll the call
-> read the summary, all against ``https://api.example.test/v1/...``. Proves
every service client resolves to the shared host and the ``/v1`` prefix is
not doubled, and that a mid-flow 404 surfaces as a typed error.
"""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest
import respx

from audact import AudactClient
from audact.exceptions import AudactNotFoundError
from audact.models import OutboundCallRequest

HOST = "https://api.example.test"
V1 = f"{HOST}/v1"
CALL_ID = uuid4()
AGENT_ID = uuid4()
TENANT_ID = uuid4()
NOW = "2026-10-01T10:00:00Z"


def _agent() -> dict:
    return {
        "agent_id": str(AGENT_ID),
        "tenant_id": str(TENANT_ID),
        "name": "Support",
        "prompt": "Be helpful",
        "language": "en",
        "created_at": NOW,
        "updated_at": NOW,
    }


def _status(status: str) -> dict:
    return {
        "call_id": str(CALL_ID),
        "room_name": f"call-{CALL_ID}",
        "status": status,
        "started_at": NOW,
    }


def _summary() -> dict:
    return {
        "call_id": str(CALL_ID),
        "tenant_id": str(TENANT_ID),
        "status": "completed",
        "started_at": NOW,
        "ended_at": "2026-10-01T10:02:00Z",
        "event_count": 3,
        "allow_count": 3,
    }


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    for key in list(os.environ):
        if key.startswith("AUDACT_"):
            monkeypatch.delenv(key)


def _assert_all_on_host(calls: list) -> None:
    assert calls
    for call in calls:
        request = call.request
        assert request.url.scheme == "https"
        assert request.url.host == "api.example.test"
        assert request.url.path.startswith("/v1/")
        assert not request.url.path.startswith("/v1/v1")
        assert request.headers["authorization"] == "Bearer k"


async def _run_flow(client: AudactClient, mock: respx.MockRouter) -> None:
    mock.get(f"{V1}/agents").mock(
        return_value=httpx.Response(200, json={"agents": [_agent()], "has_more": False})
    )
    outbound = mock.post(f"{V1}/sip/calls/outbound").mock(
        return_value=httpx.Response(
            201, json={"call_id": str(CALL_ID), "room_name": f"call-{CALL_ID}"}
        )
    )
    mock.get(f"{V1}/sip/calls/{CALL_ID}/status").mock(
        side_effect=[
            httpx.Response(200, json=_status("active")),
            httpx.Response(200, json=_status("terminated")),
        ]
    )
    mock.get(f"{V1}/calls/{CALL_ID}/summary").mock(
        return_value=httpx.Response(200, json=_summary())
    )

    async with client as c:
        page = await c.agents.list_agents()
        assert [a.agent_id for a in page.items] == [AGENT_ID]

        placed = await c.calls.initiate_outbound_call(
            OutboundCallRequest(
                from_number="+31201234567",
                destination_number="+49301234567",
                agent_id=page.items[0].agent_id,
            )
        )
        assert placed.call_id == CALL_ID
        body = json.loads(outbound.calls.last.request.content)
        assert body == {
            "from_number": "+31201234567",
            "destination_number": "+49301234567",
            "agent_id": str(AGENT_ID),
        }

        first = await c.calls.get_call_status(placed.call_id)
        assert first.status == "active"
        second = await c.calls.get_call_status(placed.call_id)
        assert second.status == "terminated"

        summary = await c.get_call_summary(placed.call_id)
        assert summary.call_id == CALL_ID
        assert summary.event_count == 3

    _assert_all_on_host(list(mock.calls))
    assert len(mock.calls) == 5


@pytest.mark.asyncio
async def test_base_url_kwarg_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    client = AudactClient(api_key="k", base_url=f"{V1}/")
    with respx.mock(assert_all_called=True) as mock:
        await _run_flow(client, mock)


@pytest.mark.asyncio
async def test_audact_base_url_env_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("AUDACT_BASE_URL", HOST)
    client = AudactClient(api_key="k")
    with respx.mock(assert_all_called=True) as mock:
        await _run_flow(client, mock)


@pytest.mark.asyncio
async def test_not_found_mid_flow_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch)
    client = AudactClient(api_key="k", base_url=f"{V1}/")
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{V1}/agents").mock(
            return_value=httpx.Response(200, json={"agents": [_agent()], "has_more": False})
        )
        mock.post(f"{V1}/sip/calls/outbound").mock(
            return_value=httpx.Response(
                201, json={"call_id": str(CALL_ID), "room_name": "r"}
            )
        )
        mock.get(f"{V1}/sip/calls/{CALL_ID}/status").mock(
            return_value=httpx.Response(
                404,
                json={
                    "error": {
                        "code": "not_found",
                        "message": "call not found",
                        "request_id": "req_123",
                    }
                },
            )
        )
        async with client as c:
            page = await c.agents.list_agents()
            placed = await c.calls.initiate_outbound_call(
                OutboundCallRequest(
                    from_number="+31201234567",
                    destination_number="+49301234567",
                    agent_id=page.items[0].agent_id,
                )
            )
            with pytest.raises(AudactNotFoundError) as exc_info:
                await c.calls.get_call_status(placed.call_id)

        _assert_all_on_host(list(mock.calls))

    assert exc_info.value.code == "not_found"
    assert exc_info.value.message == "call not found"
    assert exc_info.value.request_id == "req_123"
