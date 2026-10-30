"""
Tests for the ``client.platform.orgs`` sub-client: the
platform-admin org-management surface (organizations list/verify/reject,
org_admin find/change-email/reset-password), verified against
the documented Audact API's ``org-platform`` tag (Org Management service,
port 8092).

Unlike ``client.org`` (OrgBearer), this surface authenticates with
**PlatformBearer** — a pre-minted Ed25519 platform-admin token the SDK never
mints itself. The auth tests below are the positive control for that: they
assert a ``platform_token`` supplied at construction (or via
``set_platform_token``) is sent as ``Authorization: Bearer <token>`` instead
of the tenant ``api_key``, and that it falls back to ``api_key`` when unset.

Uses ``respx`` to mock the org-management transport
(``http://localhost:8092``) so no real network calls are made.
"""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
import respx

from audact import AudactClient
from audact.client import PlatformClient, PlatformOrgsClient
from audact.exceptions import (
    AudactAPIError,
    AudactAuthError,
    AudactNotFoundError,
)
from audact.models import (
    Organization,
    Page,
    PlatformChangeOrgAdminEmailRequest,
    PlatformRejectOrganizationRequest,
    PlatformResetOrgAdminPasswordRequest,
)

BASE = "http://localhost:8092"

PLATFORM_TOKEN = "platform-ed25519-token-abc123"
ORG_ID = uuid4()
ADMIN_ID = uuid4()


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _error_response(status: int, code: str, message: str, **extra: object) -> httpx.Response:
    """The server's real nested error envelope."""
    body = {"code": code, "message": message, **extra}
    return httpx.Response(status, json={"error": body})


def _org_payload(**overrides) -> dict:
    payload = {
        "org_id": str(ORG_ID),
        "name": "Acme Agency",
        "legal_name": "Acme Agency Ltd",
        "entity_type": "company",
        "country": "GB",
        "verification_status": "unverified",
        "created_at": "2026-03-18T15:17:00Z",
        "updated_at": "2026-03-18T15:17:00Z",
    }
    payload.update(overrides)
    return payload


def _admin_payload(**overrides) -> dict:
    payload = {
        "admin_id": str(ADMIN_ID),
        "org_id": str(ORG_ID),
        "email": "admin@acme.example",
        "name": "Jane Doe",
        "role": "org_admin",
        "created_at": "2026-03-18T15:17:00Z",
        "updated_at": "2026-03-18T15:17:00Z",
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_test123", platform_token=PLATFORM_TOKEN)


@pytest.fixture()
def unauthenticated_client() -> AudactClient:
    """No platform_token set — client.platform.orgs.* falls back to api_key."""
    return AudactClient(api_key="aud_live_test123")


def test_platform_is_platform_client(client: AudactClient) -> None:
    assert isinstance(client.platform, PlatformClient)
    assert isinstance(client.platform.orgs, PlatformOrgsClient)


# ─────────────────────────────────────────────────────────────────────────────
# Auth: PlatformBearer, never the tenant api_key when set
# ─────────────────────────────────────────────────────────────────────────────

class TestAuth:
    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_platform_token_when_set(self, client: AudactClient) -> None:
        route = respx.get(f"{BASE}/v1/platform/organizations").mock(
            return_value=_json_response({"organizations": [_org_payload()], "next_cursor": ""})
        )
        await client.platform.orgs.list_organizations()

        sent = route.calls.last.request
        assert sent.headers["Authorization"] == f"Bearer {PLATFORM_TOKEN}"

    @pytest.mark.asyncio
    @respx.mock
    async def test_falls_back_to_api_key_when_unset(
        self, unauthenticated_client: AudactClient
    ) -> None:
        route = respx.get(f"{BASE}/v1/platform/organizations").mock(
            return_value=_json_response({"organizations": [], "next_cursor": ""})
        )
        await unauthenticated_client.platform.orgs.list_organizations()

        sent = route.calls.last.request
        assert sent.headers["Authorization"] == "Bearer aud_live_test123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_set_platform_token_after_construction(self) -> None:
        c = AudactClient(api_key="aud_live_test123")
        c.set_platform_token(PLATFORM_TOKEN)
        route = respx.get(f"{BASE}/v1/platform/organizations").mock(
            return_value=_json_response({"organizations": [], "next_cursor": ""})
        )
        await c.platform.orgs.list_organizations()

        sent = route.calls.last.request
        assert sent.headers["Authorization"] == f"Bearer {PLATFORM_TOKEN}"

    def test_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUDACT_PLATFORM_TOKEN", "env-platform-token")
        c = AudactClient(api_key="aud_live_test123")
        assert c.platform_token == "env-platform-token"


# ─────────────────────────────────────────────────────────────────────────────
# list_organizations()
# ─────────────────────────────────────────────────────────────────────────────

class TestListOrganizations:
    @pytest.mark.asyncio
    @respx.mock
    async def test_no_query_params_by_default(self, client: AudactClient) -> None:
        route = respx.get(f"{BASE}/v1/platform/organizations").mock(
            return_value=_json_response({"organizations": [_org_payload()], "next_cursor": ""})
        )
        result = await client.platform.orgs.list_organizations()

        sent = route.calls.last.request
        assert sent.method == "GET"
        assert dict(sent.url.params) == {}
        assert isinstance(result, Page)
        assert len(result.items) == 1
        assert isinstance(result.items[0], Organization)
        assert result.items[0].org_id == ORG_ID
        assert result.has_more is False
        assert result.next_cursor is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_serializes_filters_as_query_params(self, client: AudactClient) -> None:
        route = respx.get(f"{BASE}/v1/platform/organizations").mock(
            return_value=_json_response(
                {"organizations": [_org_payload()], "next_cursor": "opaque-cursor-1"}
            )
        )
        result = await client.platform.orgs.list_organizations(
            status="unverified", email="admin@acme.example", limit=25, cursor="prev-cursor"
        )

        sent = route.calls.last.request
        assert dict(sent.url.params) == {
            "status": "unverified",
            "email": "admin@acme.example",
            "limit": "25",
            "cursor": "prev-cursor",
        }
        assert result.has_more is True
        assert result.next_cursor == "opaque-cursor-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_invalid_status_raises(self, client: AudactClient) -> None:
        respx.get(f"{BASE}/v1/platform/organizations").mock(
            return_value=_error_response(400, "invalid_status", "invalid status filter")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.platform.orgs.list_organizations(status="bogus")
        assert exc_info.value.status_code == 400
        assert exc_info.value.code == "invalid_status"

    @pytest.mark.asyncio
    @respx.mock
    async def test_unauthorized_raises(self, client: AudactClient) -> None:
        respx.get(f"{BASE}/v1/platform/organizations").mock(
            return_value=_error_response(401, "unauthorized", "missing bearer token")
        )
        with pytest.raises(AudactAuthError):
            await client.platform.orgs.list_organizations()


# ─────────────────────────────────────────────────────────────────────────────
# verify_organization()
# ─────────────────────────────────────────────────────────────────────────────

class TestVerifyOrganization:
    @pytest.mark.asyncio
    @respx.mock
    async def test_verify_organization(self, client: AudactClient) -> None:
        route = respx.post(f"{BASE}/v1/platform/organizations/{ORG_ID}/verify").mock(
            return_value=_json_response(
                {
                    "organization": _org_payload(
                        verification_status="verified",
                        verified_at="2026-06-01T09:00:00Z",
                        verified_by_kid="pak_2026_01",
                    )
                }
            )
        )
        result = await client.platform.orgs.verify_organization(ORG_ID)

        sent = route.calls.last.request
        assert sent.method == "POST"
        assert sent.headers["Authorization"] == f"Bearer {PLATFORM_TOKEN}"
        assert result.organization is not None
        assert result.organization.verification_status == "verified"
        assert result.organization.verified_by_kid == "pak_2026_01"

    @pytest.mark.asyncio
    @respx.mock
    async def test_verify_organization_not_found(self, client: AudactClient) -> None:
        respx.post(f"{BASE}/v1/platform/organizations/{ORG_ID}/verify").mock(
            return_value=_error_response(404, "not_found", "organization not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.platform.orgs.verify_organization(ORG_ID)


# ─────────────────────────────────────────────────────────────────────────────
# reject_organization()
# ─────────────────────────────────────────────────────────────────────────────

class TestRejectOrganization:
    @pytest.mark.asyncio
    @respx.mock
    async def test_reject_organization_sends_reason(self, client: AudactClient) -> None:
        route = respx.post(f"{BASE}/v1/platform/organizations/{ORG_ID}/reject").mock(
            return_value=_json_response(
                {"organization": _org_payload(verification_status="rejected")}
            )
        )
        result = await client.platform.orgs.reject_organization(
            ORG_ID,
            PlatformRejectOrganizationRequest(reason="KYC documents did not match legal_name"),
        )

        sent = route.calls.last.request
        assert sent.method == "POST"
        assert sent.headers["Authorization"] == f"Bearer {PLATFORM_TOKEN}"
        import json as _json

        assert _json.loads(sent.content) == {
            "reason": "KYC documents did not match legal_name"
        }
        assert result.organization is not None
        assert result.organization.verification_status == "rejected"

    @pytest.mark.asyncio
    @respx.mock
    async def test_reject_organization_empty_reason_raises(self, client: AudactClient) -> None:
        respx.post(f"{BASE}/v1/platform/organizations/{ORG_ID}/reject").mock(
            return_value=_error_response(422, "reason_required", "reason is required")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.platform.orgs.reject_organization(
                ORG_ID, PlatformRejectOrganizationRequest(reason="")
            )
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    @respx.mock
    async def test_reject_organization_not_found(self, client: AudactClient) -> None:
        respx.post(f"{BASE}/v1/platform/organizations/{ORG_ID}/reject").mock(
            return_value=_error_response(404, "not_found", "organization not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.platform.orgs.reject_organization(
                ORG_ID, PlatformRejectOrganizationRequest(reason="bad kyc")
            )


# ─────────────────────────────────────────────────────────────────────────────
# find_org_admins()
# ─────────────────────────────────────────────────────────────────────────────

class TestFindOrgAdmins:
    @pytest.mark.asyncio
    @respx.mock
    async def test_no_query_params_by_default(self, client: AudactClient) -> None:
        route = respx.get(f"{BASE}/v1/platform/org-admins").mock(
            return_value=_json_response({"org_admins": [_admin_payload()]})
        )
        result = await client.platform.orgs.find_org_admins()

        sent = route.calls.last.request
        assert sent.method == "GET"
        assert dict(sent.url.params) == {}
        assert sent.headers["Authorization"] == f"Bearer {PLATFORM_TOKEN}"
        assert len(result.org_admins) == 1
        assert result.org_admins[0].admin_id == ADMIN_ID

    @pytest.mark.asyncio
    @respx.mock
    async def test_serializes_email_and_org_id_filters(self, client: AudactClient) -> None:
        route = respx.get(f"{BASE}/v1/platform/org-admins").mock(
            return_value=_json_response({"org_admins": [_admin_payload()]})
        )
        await client.platform.orgs.find_org_admins(email="admin@acme.example", org_id=ORG_ID)

        sent = route.calls.last.request
        assert dict(sent.url.params) == {
            "email": "admin@acme.example",
            "org_id": str(ORG_ID),
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_never_surfaces_password_hash(self, client: AudactClient) -> None:
        respx.get(f"{BASE}/v1/platform/org-admins").mock(
            return_value=_json_response({"org_admins": [_admin_payload()]})
        )
        result = await client.platform.orgs.find_org_admins()
        assert not hasattr(result.org_admins[0], "password_hash")

    @pytest.mark.asyncio
    @respx.mock
    async def test_invalid_org_id_raises(self, client: AudactClient) -> None:
        respx.get(f"{BASE}/v1/platform/org-admins").mock(
            return_value=_error_response(400, "invalid_org_id", "org_id is not a valid UUID")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.platform.orgs.find_org_admins()
        assert exc_info.value.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# change_org_admin_email()
# ─────────────────────────────────────────────────────────────────────────────

class TestChangeOrgAdminEmail:
    @pytest.mark.asyncio
    @respx.mock
    async def test_change_org_admin_email(self, client: AudactClient) -> None:
        route = respx.patch(f"{BASE}/v1/platform/org-admins/{ADMIN_ID}").mock(
            return_value=_json_response(
                {"org_admin": _admin_payload(email="new-admin@acme.example")}
            )
        )
        result = await client.platform.orgs.change_org_admin_email(
            ADMIN_ID, PlatformChangeOrgAdminEmailRequest(email="new-admin@acme.example")
        )

        sent = route.calls.last.request
        assert sent.method == "PATCH"
        assert sent.headers["Authorization"] == f"Bearer {PLATFORM_TOKEN}"
        import json as _json

        assert _json.loads(sent.content) == {"email": "new-admin@acme.example"}
        assert result.org_admin is not None
        assert result.org_admin.email == "new-admin@acme.example"

    @pytest.mark.asyncio
    @respx.mock
    async def test_email_taken_raises_conflict(self, client: AudactClient) -> None:
        respx.patch(f"{BASE}/v1/platform/org-admins/{ADMIN_ID}").mock(
            return_value=_error_response(409, "email_taken", "email already in use")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.platform.orgs.change_org_admin_email(
                ADMIN_ID, PlatformChangeOrgAdminEmailRequest(email="taken@acme.example")
            )
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "email_taken"

    @pytest.mark.asyncio
    @respx.mock
    async def test_not_found(self, client: AudactClient) -> None:
        respx.patch(f"{BASE}/v1/platform/org-admins/{ADMIN_ID}").mock(
            return_value=_error_response(404, "not_found", "no org_admin with this id")
        )
        with pytest.raises(AudactNotFoundError):
            await client.platform.orgs.change_org_admin_email(
                ADMIN_ID, PlatformChangeOrgAdminEmailRequest(email="x@acme.example")
            )


# ─────────────────────────────────────────────────────────────────────────────
# reset_org_admin_password()
# ─────────────────────────────────────────────────────────────────────────────

class TestResetOrgAdminPassword:
    @pytest.mark.asyncio
    @respx.mock
    async def test_reset_with_new_password(self, client: AudactClient) -> None:
        route = respx.post(
            f"{BASE}/v1/platform/org-admins/{ADMIN_ID}/reset-password"
        ).mock(return_value=_json_response({"reset": "password_set"}))
        result = await client.platform.orgs.reset_org_admin_password(
            ADMIN_ID,
            PlatformResetOrgAdminPasswordRequest(new_password="a-very-long-new-passphrase"),
        )

        sent = route.calls.last.request
        assert sent.method == "POST"
        assert sent.headers["Authorization"] == f"Bearer {PLATFORM_TOKEN}"
        import json as _json

        assert _json.loads(sent.content) == {
            "new_password": "a-very-long-new-passphrase"
        }
        assert result.reset == "password_set"
        assert result.token is None
        assert result.expires_in is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_reset_without_body_mints_token(self, client: AudactClient) -> None:
        route = respx.post(
            f"{BASE}/v1/platform/org-admins/{ADMIN_ID}/reset-password"
        ).mock(
            return_value=_json_response(
                {"reset": "token", "token": "9f3a1c-redacted", "expires_in": 1800}
            )
        )
        result = await client.platform.orgs.reset_org_admin_password(ADMIN_ID)

        sent = route.calls.last.request
        import json as _json

        assert _json.loads(sent.content) == {}
        assert result.reset == "token"
        assert result.token == "9f3a1c-redacted"
        assert result.expires_in == 1800

    @pytest.mark.asyncio
    @respx.mock
    async def test_not_found(self, client: AudactClient) -> None:
        respx.post(f"{BASE}/v1/platform/org-admins/{ADMIN_ID}/reset-password").mock(
            return_value=_error_response(404, "not_found", "no org_admin with this id")
        )
        with pytest.raises(AudactNotFoundError):
            await client.platform.orgs.reset_org_admin_password(ADMIN_ID)
