"""
Tests for ``client.platform.{list,get,soft_delete,restore}_tenant(s)`` - the
``platform-tenants`` tag of the documented Audact API (Org Management,
port 8092, PlatformBearer).
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from pydantic import ValidationError

from audact import AudactClient
from audact.exceptions import AudactAPIError, AudactNotFoundError
from audact.models import (
    PlatformListTenantsResponse,
    PlatformSoftDeleteTenantRequest,
    PlatformTenantResponse,
)

BASE = "http://localhost:8092"
URL = f"{BASE}/v1/platform/tenants"
TOKEN = "platform-token-xyz"
TID = "550e8400-e29b-41d4-a716-446655440000"


def _tenant(**over: object) -> dict:
    return {
        "tenant_id": TID,
        "name": "Acme Corp",
        "plan": "professional",
        "status": "active",
        "organization_id": None,
        "created_at": "2026-10-01T00:00:00Z",
        **over,
    }


def _err(status: int, code: str, message: str) -> httpx.Response:
    return httpx.Response(status, json={"error": {"code": code, "message": message}})


@pytest.fixture
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_api", platform_token=TOKEN)


@respx.mock
async def test_list_tenants_defaults_send_no_query(client: AudactClient) -> None:
    route = respx.get(URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "tenants": [_tenant(), _tenant(tenant_id="t2", organization_id="org-1")],
                "next_cursor": "c2",
            },
        )
    )
    result = await client.platform.list_tenants()
    assert isinstance(result, PlatformListTenantsResponse)
    assert [t.tenant_id for t in result.tenants] == [TID, "t2"]
    assert result.tenants[0].organization_id is None
    assert result.tenants[1].organization_id == "org-1"
    assert result.next_cursor == "c2"
    req = route.calls.last.request
    assert req.url.query == b""
    assert req.headers["authorization"] == f"Bearer {TOKEN}"


@respx.mock
async def test_list_tenants_sends_all_filters(client: AudactClient) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={"tenants": []}))
    result = await client.platform.list_tenants(
        q="acme", organization="none", include_deleted=True, limit=25, cursor="abc"
    )
    assert result.tenants == []
    assert result.next_cursor is None
    params = route.calls.last.request.url.params
    assert dict(params) == {
        "q": "acme",
        "organization": "none",
        "include_deleted": "true",
        "limit": "25",
        "cursor": "abc",
    }


@respx.mock
async def test_list_tenants_bad_filter_maps_to_api_error(client: AudactClient) -> None:
    respx.get(URL).mock(return_value=_err(400, "invalid_request", "bad organization"))
    with pytest.raises(AudactAPIError) as exc:
        await client.platform.list_tenants(organization="bogus")
    assert exc.value.status_code == 400


@respx.mock
async def test_get_tenant(client: AudactClient) -> None:
    route = respx.get(f"{URL}/{TID}").mock(
        return_value=httpx.Response(
            200, json={"tenant": _tenant(deleted_at="2026-10-02T00:00:00Z")}
        )
    )
    result = await client.platform.get_tenant(TID)
    assert isinstance(result, PlatformTenantResponse)
    assert result.tenant is not None
    assert result.tenant.deleted_at == "2026-10-02T00:00:00Z"
    assert route.calls.last.request.headers["authorization"] == f"Bearer {TOKEN}"


@respx.mock
async def test_get_tenant_escapes_id(client: AudactClient) -> None:
    route = respx.get(url__regex=r".*/v1/platform/tenants/.*").mock(
        return_value=httpx.Response(200, json={"tenant": _tenant()})
    )
    await client.platform.get_tenant("a/b")
    assert route.calls.last.request.url.raw_path == b"/v1/platform/tenants/a%2Fb"


@respx.mock
async def test_get_tenant_404(client: AudactClient) -> None:
    respx.get(f"{URL}/{TID}").mock(return_value=_err(404, "tenant_not_found", "no such tenant"))
    with pytest.raises(AudactNotFoundError):
        await client.platform.get_tenant(TID)


@respx.mock
async def test_soft_delete_tenant_body(client: AudactClient) -> None:
    route = respx.post(f"{URL}/{TID}/soft-delete").mock(
        return_value=httpx.Response(
            200, json={"tenant": _tenant(deleted_at="2026-10-02T00:00:00Z")}
        )
    )
    result = await client.platform.soft_delete_tenant(TID, "test tenant, key discarded")
    assert result.tenant is not None
    assert result.tenant.deleted_at is not None
    req = route.calls.last.request
    assert json.loads(req.content) == {"reason": "test tenant, key discarded"}
    assert req.headers["authorization"] == f"Bearer {TOKEN}"


@pytest.mark.parametrize("reason", ["", "   ", "\n\t"])
@respx.mock
async def test_soft_delete_tenant_empty_reason_sends_nothing(
    client: AudactClient, reason: str
) -> None:
    route = respx.post(f"{URL}/{TID}/soft-delete").mock(
        return_value=httpx.Response(200, json={"tenant": _tenant()})
    )
    with pytest.raises(ValueError, match="reason"):
        await client.platform.soft_delete_tenant(TID, reason)
    assert route.call_count == 0


@respx.mock
async def test_soft_delete_tenant_404_and_409(client: AudactClient) -> None:
    route = respx.post(f"{URL}/{TID}/soft-delete").mock(
        side_effect=[
            _err(404, "tenant_not_found", "no such tenant"),
            _err(409, "already_deleted", "tenant is already deleted"),
        ]
    )
    with pytest.raises(AudactNotFoundError):
        await client.platform.soft_delete_tenant(TID, "why")
    with pytest.raises(AudactAPIError) as exc:
        await client.platform.soft_delete_tenant(TID, "why")
    assert exc.value.status_code == 409
    assert route.call_count == 2


@respx.mock
async def test_restore_tenant_with_and_without_reason(client: AudactClient) -> None:
    route = respx.post(f"{URL}/{TID}/restore").mock(
        return_value=httpx.Response(200, json={"tenant": _tenant()})
    )
    result = await client.platform.restore_tenant(TID, "deleted by mistake")
    assert result.tenant is not None
    assert result.tenant.deleted_at is None
    assert json.loads(route.calls.last.request.content) == {"reason": "deleted by mistake"}
    await client.platform.restore_tenant(TID)
    assert json.loads(route.calls.last.request.content) == {}


@respx.mock
async def test_restore_tenant_404_and_409(client: AudactClient) -> None:
    respx.post(f"{URL}/{TID}/restore").mock(
        side_effect=[
            _err(404, "tenant_not_found", "no such tenant"),
            _err(409, "not_deleted", "tenant is not deleted"),
        ]
    )
    with pytest.raises(AudactNotFoundError):
        await client.platform.restore_tenant(TID)
    with pytest.raises(AudactAPIError) as exc:
        await client.platform.restore_tenant(TID)
    assert exc.value.status_code == 409


def test_soft_delete_request_requires_reason() -> None:
    with pytest.raises(ValidationError):
        PlatformSoftDeleteTenantRequest()  # type: ignore[call-arg]
