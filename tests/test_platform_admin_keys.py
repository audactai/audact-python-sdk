"""
Tests for ``client.platform.{list,add,disable}_admin_key(s)`` — the
``platform-admin-keys`` tag of the documented Audact API (Org Management,
port 8092, PlatformBearer).
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from audact import AudactClient
from audact.exceptions import AudactAPIError, AudactAuthError, AudactNotFoundError
from audact.models import AdminKeyResponse, ListAdminKeysResponse

BASE = "http://localhost:8092"
URL = f"{BASE}/v1/platform/admin-keys"
TOKEN = "platform-token-xyz"


def _key(kid: str = "k1", **over: object) -> dict:
    return {
        "active": True,
        "added_at": "2026-10-01T00:00:00Z",
        "kid": kid,
        "operator": "alice",
        **over,
    }


def _err(status: int, code: str, message: str) -> httpx.Response:
    return httpx.Response(status, json={"error": {"code": code, "message": message}})


@pytest.fixture
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_api", platform_token=TOKEN)


@respx.mock
async def test_list_admin_keys(client: AudactClient) -> None:
    route = respx.get(URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "admin_keys": [
                    _key("a"),
                    _key("b", active=False, disabled_at="2026-10-02T00:00:00Z"),
                ]
            },
        )
    )
    result = await client.platform.list_admin_keys()
    assert isinstance(result, ListAdminKeysResponse)
    assert [k.kid for k in result.admin_keys] == ["a", "b"]
    assert result.admin_keys[1].disabled_at == "2026-10-02T00:00:00Z"
    req = route.calls.last.request
    assert req.headers["Authorization"] == f"Bearer {TOKEN}"
    assert "aud_live_api" not in req.headers["Authorization"]


@respx.mock
async def test_add_admin_key_201_with_operator(client: AudactClient) -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(201, json={"admin_key": _key("k9")}))
    result = await client.platform.add_admin_key(kid="k9", public_key_pem="PEM", operator="alice")
    assert isinstance(result, AdminKeyResponse)
    assert result.admin_key.kid == "k9"
    req = route.calls.last.request
    assert req.headers["Authorization"] == f"Bearer {TOKEN}"
    assert json.loads(req.content) == {"kid": "k9", "public_key_pem": "PEM", "operator": "alice"}


@respx.mock
async def test_add_admin_key_omits_operator_when_none(client: AudactClient) -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(201, json={"admin_key": _key("k9")}))
    await client.platform.add_admin_key(kid="k9", public_key_pem="PEM")
    assert json.loads(route.calls.last.request.content) == {"kid": "k9", "public_key_pem": "PEM"}


@respx.mock
async def test_add_admin_key_409_duplicate(client: AudactClient) -> None:
    respx.post(URL).mock(return_value=_err(409, "conflict", "kid exists"))
    with pytest.raises(AudactAPIError) as ei:
        await client.platform.add_admin_key(kid="k1", public_key_pem="PEM")
    assert ei.value.status_code == 409


@respx.mock
async def test_disable_admin_key(client: AudactClient) -> None:
    route = respx.post(f"{URL}/k1/disable").mock(
        return_value=httpx.Response(200, json={"admin_key": _key("k1", active=False)})
    )
    result = await client.platform.disable_admin_key("k1")
    assert result.admin_key.active is False
    req = route.calls.last.request
    assert req.method == "POST"
    assert req.headers["Authorization"] == f"Bearer {TOKEN}"


@respx.mock
async def test_disable_admin_key_escapes_kid(client: AudactClient) -> None:
    route = respx.post(url__regex=r".*/v1/platform/admin-keys/.*/disable").mock(
        return_value=httpx.Response(200, json={"admin_key": _key("a/b c")})
    )
    await client.platform.disable_admin_key("a/b c")
    assert route.calls.last.request.url.raw_path.decode().endswith(
        "/v1/platform/admin-keys/a%2Fb%20c/disable"
    )


@respx.mock
async def test_disable_admin_key_404(client: AudactClient) -> None:
    respx.post(f"{URL}/nope/disable").mock(return_value=_err(404, "not_found", "no such key"))
    with pytest.raises(AudactNotFoundError) as ei:
        await client.platform.disable_admin_key("nope")
    assert ei.value.code == "not_found"


@respx.mock
async def test_disable_admin_key_409_last_active_key(client: AudactClient) -> None:
    respx.post(f"{URL}/k1/disable").mock(
        return_value=_err(409, "conflict", "cannot disable the last active admin key")
    )
    with pytest.raises(AudactAPIError) as ei:
        await client.platform.disable_admin_key("k1")
    assert ei.value.status_code == 409


@respx.mock
async def test_list_admin_keys_401(client: AudactClient) -> None:
    respx.get(URL).mock(return_value=_err(401, "unauthorized", "bad token"))
    with pytest.raises(AudactAuthError):
        await client.platform.list_admin_keys()


@respx.mock
async def test_disable_admin_key_already_disabled_succeeds(client: AudactClient) -> None:
    respx.post(f"{URL}/k1/disable").mock(
        return_value=httpx.Response(200, json={"admin_key": _key("k1", active=False)})
    )
    result = await client.platform.disable_admin_key("k1")
    assert result.admin_key.active is False
