"""
Wire-type tests.

The fixtures in ``tests/testdata/wire`` are the real JSON the server sends
(byte-equal to the Go SDK's copies). Every response model must accept them,
both directly and through the client method with mocked HTTP.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
import respx

from audact import AudactClient
from audact.models import (
    CallDetail,
    ListCallsResponse,
    ListViolationsResponse,
    PolicyFileResponse,
    ReconstructResponse,
)

WIRE = Path(__file__).parent / "testdata" / "wire"
EVIDENCE = "http://localhost:8083"
POLICY = "http://localhost:8081"


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((WIRE / name).read_text(encoding="utf-8"))
    return data


def _call_id() -> UUID:
    return UUID(_load("call_detail.json")["call_id"])


def _assert_calls(calls: list[Any]) -> None:
    assert calls
    assert any(c.metadata and c.metadata.get("country") == "DE" for c in calls)


def _assert_policy(policy: PolicyFileResponse) -> None:
    assert policy.use_cases
    values = [c.value for uc in policy.use_cases for c in (uc.conditions or [])]
    assert any(isinstance(v, str) for v in values)
    assert any(isinstance(v, bool) for v in values)
    assert any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values)
    assert any(isinstance(v, list) for v in values)


@pytest.fixture()
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_test123")


class TestModelsAcceptWireFixtures:
    def test_calls_list(self) -> None:
        parsed = ListCallsResponse.model_validate(_load("calls_list.json"))
        _assert_calls(parsed.calls)

    def test_call_detail(self) -> None:
        detail = CallDetail.model_validate(_load("call_detail.json"))
        assert detail.metadata is not None
        assert detail.metadata["country"] == "DE"

    def test_reconstruct(self) -> None:
        parsed = ReconstructResponse.model_validate(_load("reconstruct.json"))
        assert parsed.event_count == 2

    def test_violations(self) -> None:
        parsed = ListViolationsResponse.model_validate(_load("violations.json"))
        assert parsed.violations
        assert all(isinstance(v.data, dict) for v in parsed.violations)

    def test_policy(self) -> None:
        _assert_policy(PolicyFileResponse.model_validate(_load("policy_de.json")))


class TestClientAcceptsWireFixtures:
    @pytest.mark.asyncio
    @respx.mock
    async def test_list_calls(self, client: AudactClient) -> None:
        respx.get(f"{EVIDENCE}/v1/calls").mock(
            return_value=httpx.Response(200, json=_load("calls_list.json"))
        )
        async with client as c:
            page = await c.list_calls()
        _assert_calls(page.items)

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_call_detail(self, client: AudactClient) -> None:
        cid = _call_id()
        respx.get(f"{EVIDENCE}/v1/calls/{cid}").mock(
            return_value=httpx.Response(200, json=_load("call_detail.json"))
        )
        async with client as c:
            detail = await c.get_call_detail(cid)
        assert detail.metadata is not None
        assert detail.metadata["country"] == "DE"

    @pytest.mark.asyncio
    @respx.mock
    async def test_reconstruct_chain(self, client: AudactClient) -> None:
        cid = _call_id()
        respx.get(f"{EVIDENCE}/v1/reconstruct/{cid}").mock(
            return_value=httpx.Response(200, json=_load("reconstruct.json"))
        )
        async with client as c:
            parsed = await c.reconstruct_chain(cid)
        assert parsed.event_count == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_violations(self, client: AudactClient) -> None:
        respx.get(f"{EVIDENCE}/v1/violations").mock(
            return_value=httpx.Response(200, json=_load("violations.json"))
        )
        async with client as c:
            page = await c.list_violations()
        assert page.items
        assert all(isinstance(v.data, dict) for v in page.items)

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_policy(self, client: AudactClient) -> None:
        respx.get(f"{POLICY}/v1/policies/DE").mock(
            return_value=httpx.Response(200, json=_load("policy_de.json"))
        )
        async with client as c:
            raw = await c.get_policy("DE")
        _assert_policy(PolicyFileResponse.model_validate(raw))
