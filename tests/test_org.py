"""
Tests for the ``client.org`` sub-client: org self-service
(signup/login/refresh/logout, profile, KYC), verified against
the documented Audact API's ``org`` tag (Org Management service, port 8092).

Unlike every other sub-client, ``OrgClient`` authenticates with **OrgBearer**
— an in-memory access token minted by ``signup()``/``login()``/``refresh()``
— instead of the tenant ``api_key``. The auth-flow tests below are the
positive control for that: they assert the token returned by signup/login/
refresh is stored on the parent client and sent as
``Authorization: Bearer <jwt>`` on subsequent ``client.org.*`` calls, and
that ``logout()`` clears it (falling back to the tenant ``api_key``, if any).

Uses ``respx`` to mock the org-management transport
(``http://localhost:8092``) so no real network calls are made.
"""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
import respx

from audact import AudactClient
from audact.client import OrgClient
from audact.exceptions import (
    AudactAPIError,
    AudactAuthError,
    AudactForbiddenError,
    AudactNotFoundError,
    AudactRateLimitError,
)
from audact.models import (
    OrgCreateTenantRequest,
    OrgIssueKeyRequest,
    OrgKYCPatchRequest,
    OrgLoginRequest,
    OrgSignupRequest,
    OrgTenantSummary,
    OrgUpdateProfileRequest,
    Page,
)

BASE = "http://localhost:8092"

ORG_ID = uuid4()
ADMIN_ID = uuid4()
TENANT_ID = uuid4()


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


def _tenant_payload(**overrides) -> dict:
    payload = {
        "tenant_id": str(TENANT_ID),
        "name": "Acme Voice Tenant",
        "status": "active",
        "created_at": "2026-03-18T15:17:00Z",
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
    return AudactClient(api_key="aud_live_test123")


def test_org_is_org_client(client: AudactClient) -> None:
    assert isinstance(client.org, OrgClient)


# ─────────────────────────────────────────────────────────────────────────────
# signup()
# ─────────────────────────────────────────────────────────────────────────────

class TestSignup:
    @pytest.mark.asyncio
    @respx.mock
    async def test_signup_posts_body_and_stores_token(self, client: AudactClient) -> None:
        route = respx.post(f"{BASE}/v1/org/signup").mock(
            return_value=_json_response(
                {
                    "token": "org-jwt-signup-abc123",
                    "expires_in": 3600,
                    "org": _org_payload(),
                    "admin": _admin_payload(),
                },
                status=201,
            )
        )
        req = OrgSignupRequest(
            org_name="Acme Agency",
            email="admin@acme.example",
            password="hunter2222222",
            entity_type="company",
            legal_name="Acme Agency Ltd",
            country="GB",
        )
        result = await client.org.signup(req)

        assert route.called
        sent = route.calls.last.request
        assert sent.method == "POST"
        assert sent.url == f"{BASE}/v1/org/signup"
        assert result.token == "org-jwt-signup-abc123"
        assert result.org is not None and result.org.org_id == ORG_ID
        assert result.admin is not None and result.admin.email == "admin@acme.example"

        # Signup issues the client's OrgBearer token in-memory.
        assert client.org_token == "org-jwt-signup-abc123"

        # Subsequent client.org.* calls now carry the signup-issued token.
        profile_route = respx.get(f"{BASE}/v1/org/profile").mock(
            return_value=_json_response({"org": _org_payload(), "admin": _admin_payload()})
        )
        await client.org.get_profile()
        assert profile_route.calls.last.request.headers["Authorization"] == (
            "Bearer org-jwt-signup-abc123"
        )

    @pytest.mark.asyncio
    @respx.mock
    async def test_signup_conflict_raises_on_email_taken(self, client: AudactClient) -> None:
        respx.post(f"{BASE}/v1/org/signup").mock(
            return_value=_error_response(409, "email_taken", "email already registered")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.org.signup(
                OrgSignupRequest(
                    org_name="Acme Agency",
                    email="admin@acme.example",
                    password="hunter2222222",
                    entity_type="company",
                    legal_name="Acme Agency Ltd",
                    country="GB",
                )
            )
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "email_taken"


# ─────────────────────────────────────────────────────────────────────────────
# login()
# ─────────────────────────────────────────────────────────────────────────────

class TestLogin:
    @pytest.mark.asyncio
    @respx.mock
    async def test_login_posts_credentials_and_stores_token(self, client: AudactClient) -> None:
        assert client.org_token is None
        route = respx.post(f"{BASE}/v1/org/login").mock(
            return_value=_json_response(
                {"token": "org-jwt-login-def456", "expires_in": 3600, "ver": False}
            )
        )
        result = await client.org.login(
            OrgLoginRequest(email="admin@acme.example", password="hunter2222222")
        )

        sent = route.calls.last.request
        assert sent.method == "POST"
        import json as _json

        assert _json.loads(sent.content) == {
            "email": "admin@acme.example",
            "password": "hunter2222222",
        }
        assert result.token == "org-jwt-login-def456"
        assert result.ver is False
        assert client.org_token == "org-jwt-login-def456"

        profile_route = respx.get(f"{BASE}/v1/org/profile").mock(
            return_value=_json_response({"org": _org_payload(), "admin": _admin_payload()})
        )
        await client.org.get_profile()
        assert profile_route.calls.last.request.headers["Authorization"] == (
            "Bearer org-jwt-login-def456"
        )

    @pytest.mark.asyncio
    @respx.mock
    async def test_login_before_credentials_sends_configured_api_key(
        self, client: AudactClient
    ) -> None:
        """Before any org token is minted, org.* calls fall back to api_key."""
        route = respx.post(f"{BASE}/v1/org/login").mock(
            return_value=_json_response({"token": "t", "expires_in": 60, "ver": False})
        )
        await client.org.login(
            OrgLoginRequest(email="admin@acme.example", password="hunter2222222")
        )
        sent = route.calls.last.request
        assert sent.headers["Authorization"] == "Bearer aud_live_test123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_login_invalid_credentials_raises_auth_error(
        self, client: AudactClient
    ) -> None:
        respx.post(f"{BASE}/v1/org/login").mock(
            return_value=_error_response(401, "invalid_credentials", "invalid email or password")
        )
        with pytest.raises(AudactAuthError):
            await client.org.login(
                OrgLoginRequest(email="admin@acme.example", password="wrong")
            )

    @pytest.mark.asyncio
    @respx.mock
    async def test_login_rate_limited_raises_rate_limit_error(
        self, client: AudactClient
    ) -> None:
        response = _error_response(429, "rate_limit_exceeded", "too many attempts")
        response.headers["Retry-After"] = "900"
        respx.post(f"{BASE}/v1/org/login").mock(return_value=response)
        with pytest.raises(AudactRateLimitError) as exc_info:
            await client.org.login(
                OrgLoginRequest(email="admin@acme.example", password="wrong")
            )
        assert exc_info.value.retry_after == 900


# ─────────────────────────────────────────────────────────────────────────────
# refresh()
# ─────────────────────────────────────────────────────────────────────────────

class TestRefresh:
    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_rotates_stored_token(self, client: AudactClient) -> None:
        client.set_org_token("stale-org-jwt")
        route = respx.post(f"{BASE}/v1/org/refresh").mock(
            return_value=_json_response({"token": "org-jwt-refresh-ghi789", "expires_in": 3600})
        )
        result = await client.org.refresh()

        sent = route.calls.last.request
        assert sent.method == "POST"
        assert sent.headers["Authorization"] == "Bearer stale-org-jwt"
        assert result.token == "org-jwt-refresh-ghi789"
        assert client.org_token == "org-jwt-refresh-ghi789"

        profile_route = respx.get(f"{BASE}/v1/org/profile").mock(
            return_value=_json_response({"org": _org_payload(), "admin": _admin_payload()})
        )
        await client.org.get_profile()
        assert profile_route.calls.last.request.headers["Authorization"] == (
            "Bearer org-jwt-refresh-ghi789"
        )

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_missing_token_raises_auth_error(self, client: AudactClient) -> None:
        respx.post(f"{BASE}/v1/org/refresh").mock(
            return_value=_error_response(401, "unauthorized", "no refresh token")
        )
        with pytest.raises(AudactAuthError):
            await client.org.refresh()


# ─────────────────────────────────────────────────────────────────────────────
# logout()
# ─────────────────────────────────────────────────────────────────────────────

class TestLogout:
    @pytest.mark.asyncio
    @respx.mock
    async def test_logout_sends_org_token_then_clears_it(self, client: AudactClient) -> None:
        client.set_org_token("active-org-jwt")
        route = respx.post(f"{BASE}/v1/org/logout").mock(return_value=httpx.Response(204))

        await client.org.logout()

        sent = route.calls.last.request
        assert sent.method == "POST"
        assert sent.headers["Authorization"] == "Bearer active-org-jwt"
        assert client.org_token is None

        # Subsequent client.org.* calls fall back to the tenant api_key.
        profile_route = respx.get(f"{BASE}/v1/org/profile").mock(
            return_value=_json_response({"org": _org_payload(), "admin": _admin_payload()})
        )
        await client.org.get_profile()
        assert profile_route.calls.last.request.headers["Authorization"] == (
            "Bearer aud_live_test123"
        )

    @pytest.mark.asyncio
    @respx.mock
    async def test_logout_unauthenticated_raises_auth_error(self, client: AudactClient) -> None:
        respx.post(f"{BASE}/v1/org/logout").mock(
            return_value=_error_response(401, "unauthorized", "no session")
        )
        with pytest.raises(AudactAuthError):
            await client.org.logout()


# ─────────────────────────────────────────────────────────────────────────────
# Profile
# ─────────────────────────────────────────────────────────────────────────────

class TestProfile:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_profile(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        route = respx.get(f"{BASE}/v1/org/profile").mock(
            return_value=_json_response({"org": _org_payload(), "admin": _admin_payload()})
        )
        result = await client.org.get_profile()

        sent = route.calls.last.request
        assert sent.method == "GET"
        assert sent.headers["Authorization"] == "Bearer org-jwt"
        assert result.org is not None and result.org.name == "Acme Agency"
        assert result.admin is not None and result.admin.name == "Jane Doe"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_profile_not_found(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        respx.get(f"{BASE}/v1/org/profile").mock(
            return_value=_error_response(404, "not_found", "org not found")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.org.get_profile()
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @respx.mock
    async def test_update_profile_patches_fields(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        route = respx.patch(f"{BASE}/v1/org/profile").mock(
            return_value=_json_response(
                {
                    "org": _org_payload(name="New Name"),
                    "admin": _admin_payload(name="New Admin Name"),
                }
            )
        )
        result = await client.org.update_profile(
            OrgUpdateProfileRequest(org_name="New Name", admin_name="New Admin Name")
        )

        sent = route.calls.last.request
        assert sent.method == "PATCH"
        assert sent.headers["Authorization"] == "Bearer org-jwt"
        import json as _json

        assert _json.loads(sent.content) == {
            "org_name": "New Name",
            "admin_name": "New Admin Name",
        }
        assert result.org is not None and result.org.name == "New Name"
        assert result.admin is not None and result.admin.name == "New Admin Name"


# ─────────────────────────────────────────────────────────────────────────────
# KYC
# ─────────────────────────────────────────────────────────────────────────────

class TestKYC:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_kyc(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        route = respx.get(f"{BASE}/v1/org/kyc").mock(
            return_value=_json_response(
                {
                    "kyc": {
                        "org_id": str(ORG_ID),
                        "legal_name": "Acme Agency Ltd",
                        "contact_email": "billing@acme.example",
                        "created_at": "2026-03-18T15:17:00Z",
                        "updated_at": "2026-03-18T15:17:00Z",
                    }
                }
            )
        )
        result = await client.org.get_kyc()

        sent = route.calls.last.request
        assert sent.method == "GET"
        assert sent.headers["Authorization"] == "Bearer org-jwt"
        assert result.kyc is not None
        assert result.kyc.legal_name == "Acme Agency Ltd"
        assert result.kyc.contact_email == "billing@acme.example"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_kyc_not_found(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        respx.get(f"{BASE}/v1/org/kyc").mock(
            return_value=_error_response(404, "not_found", "kyc not found")
        )
        with pytest.raises(AudactAPIError):
            await client.org.get_kyc()

    @pytest.mark.asyncio
    @respx.mock
    async def test_update_kyc_patches_subset(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        route = respx.patch(f"{BASE}/v1/org/kyc").mock(
            return_value=_json_response(
                {
                    "kyc": {
                        "org_id": str(ORG_ID),
                        "legal_name": "Acme Agency Ltd",
                        "vat_id": "GB123456789",
                        "created_at": "2026-03-18T15:17:00Z",
                        "updated_at": "2026-06-01T09:00:00Z",
                    }
                }
            )
        )
        result = await client.org.update_kyc(OrgKYCPatchRequest(vat_id="GB123456789"))

        sent = route.calls.last.request
        assert sent.method == "PATCH"
        assert sent.headers["Authorization"] == "Bearer org-jwt"
        import json as _json

        assert _json.loads(sent.content) == {"vat_id": "GB123456789"}
        assert result.kyc is not None and result.kyc.vat_id == "GB123456789"

    @pytest.mark.asyncio
    @respx.mock
    async def test_update_kyc_invalid_field_raises(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        respx.patch(f"{BASE}/v1/org/kyc").mock(
            return_value=_error_response(422, "kyc_invalid", "malformed tax_id")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.org.update_kyc(OrgKYCPatchRequest(tax_id="not-an-ein"))
        assert exc_info.value.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# Org-tenant lifecycle
# ─────────────────────────────────────────────────────────────────────────────

class TestListTenants:
    @pytest.mark.asyncio
    @respx.mock
    async def test_list_tenants_sends_query_params(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        route = respx.get(f"{BASE}/v1/org/tenants").mock(
            return_value=_json_response(
                {
                    "tenants": [_tenant_payload()],
                    "next_cursor": "opaque-cursor-1",
                }
            )
        )
        result = await client.org.list_tenants(
            include_deleted=True, cursor="prev-cursor", limit=25
        )

        sent = route.calls.last.request
        assert sent.method == "GET"
        assert sent.headers["Authorization"] == "Bearer org-jwt"
        assert dict(sent.url.params) == {
            "include_deleted": "true",
            "cursor": "prev-cursor",
            "limit": "25",
        }
        assert isinstance(result, Page)
        assert len(result.items) == 1
        assert isinstance(result.items[0], OrgTenantSummary)
        assert result.items[0].tenant_id == TENANT_ID
        assert result.has_more is True
        assert result.next_cursor == "opaque-cursor-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_tenants_no_next_cursor_means_no_more(
        self, client: AudactClient
    ) -> None:
        client.set_org_token("org-jwt")
        respx.get(f"{BASE}/v1/org/tenants").mock(
            return_value=_json_response({"tenants": [_tenant_payload()]})
        )
        result = await client.org.list_tenants()
        assert result.has_more is False
        assert result.next_cursor is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_tenants_unauthorized_raises(self, client: AudactClient) -> None:
        respx.get(f"{BASE}/v1/org/tenants").mock(
            return_value=_error_response(401, "unauthorized", "missing bearer token")
        )
        with pytest.raises(AudactAuthError):
            await client.org.list_tenants()


class TestCreateTenant:
    @pytest.mark.asyncio
    @respx.mock
    async def test_create_tenant_posts_body(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        route = respx.post(f"{BASE}/v1/org/tenants").mock(
            return_value=_json_response({"tenant": _tenant_payload()}, status=201)
        )
        result = await client.org.create_tenant(OrgCreateTenantRequest(name="Acme Voice Tenant"))

        sent = route.calls.last.request
        assert sent.method == "POST"
        assert sent.headers["Authorization"] == "Bearer org-jwt"
        import json as _json

        assert _json.loads(sent.content) == {"name": "Acme Voice Tenant"}
        assert result.tenant is not None
        assert result.tenant.tenant_id == TENANT_ID
        assert result.tenant.name == "Acme Voice Tenant"
        assert result.tenant.status == "active"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_tenant_org_not_verified_raises_forbidden(
        self, client: AudactClient
    ) -> None:
        client.set_org_token("org-jwt")
        respx.post(f"{BASE}/v1/org/tenants").mock(
            return_value=_error_response(403, "org_not_verified", "organization not verified")
        )
        with pytest.raises(AudactForbiddenError):
            await client.org.create_tenant(OrgCreateTenantRequest(name="Acme Voice Tenant"))


class TestGetTenant:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_tenant(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        route = respx.get(f"{BASE}/v1/org/tenants/{TENANT_ID}").mock(
            return_value=_json_response({"tenant": _tenant_payload()})
        )
        result = await client.org.get_tenant(TENANT_ID)

        sent = route.calls.last.request
        assert sent.method == "GET"
        assert sent.headers["Authorization"] == "Bearer org-jwt"
        assert result.tenant is not None
        assert result.tenant.tenant_id == TENANT_ID

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_tenant_not_found(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        respx.get(f"{BASE}/v1/org/tenants/{TENANT_ID}").mock(
            return_value=_error_response(404, "tenant_not_found", "tenant not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.org.get_tenant(TENANT_ID)


class TestSoftDeleteTenant:
    @pytest.mark.asyncio
    @respx.mock
    async def test_soft_delete_tenant(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        route = respx.delete(f"{BASE}/v1/org/tenants/{TENANT_ID}").mock(
            return_value=_json_response(
                {"tenant": _tenant_payload(deleted_at="2026-06-01T09:00:00Z")}
            )
        )
        result = await client.org.soft_delete_tenant(TENANT_ID)

        sent = route.calls.last.request
        assert sent.method == "DELETE"
        assert sent.headers["Authorization"] == "Bearer org-jwt"
        assert result.tenant is not None
        assert result.tenant.deleted_at is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_soft_delete_tenant_not_found(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        respx.delete(f"{BASE}/v1/org/tenants/{TENANT_ID}").mock(
            return_value=_error_response(404, "tenant_not_found", "tenant not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.org.soft_delete_tenant(TENANT_ID)


class TestDisableEnableRestoreTenant:
    @pytest.mark.asyncio
    @respx.mock
    async def test_disable_tenant(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        route = respx.post(f"{BASE}/v1/org/tenants/{TENANT_ID}/disable").mock(
            return_value=_json_response({"tenant": _tenant_payload(status="disabled")})
        )
        result = await client.org.disable_tenant(TENANT_ID)

        sent = route.calls.last.request
        assert sent.method == "POST"
        assert sent.headers["Authorization"] == "Bearer org-jwt"
        assert result.tenant is not None and result.tenant.status == "disabled"

    @pytest.mark.asyncio
    @respx.mock
    async def test_enable_tenant(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        route = respx.post(f"{BASE}/v1/org/tenants/{TENANT_ID}/enable").mock(
            return_value=_json_response({"tenant": _tenant_payload(status="active")})
        )
        result = await client.org.enable_tenant(TENANT_ID)

        sent = route.calls.last.request
        assert sent.method == "POST"
        assert sent.headers["Authorization"] == "Bearer org-jwt"
        assert result.tenant is not None and result.tenant.status == "active"

    @pytest.mark.asyncio
    @respx.mock
    async def test_restore_tenant(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        route = respx.post(f"{BASE}/v1/org/tenants/{TENANT_ID}/restore").mock(
            return_value=_json_response({"tenant": _tenant_payload(deleted_at=None)})
        )
        result = await client.org.restore_tenant(TENANT_ID)

        sent = route.calls.last.request
        assert sent.method == "POST"
        assert sent.headers["Authorization"] == "Bearer org-jwt"
        assert result.tenant is not None and result.tenant.deleted_at is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_restore_tenant_not_deleted_raises_conflict(
        self, client: AudactClient
    ) -> None:
        client.set_org_token("org-jwt")
        respx.post(f"{BASE}/v1/org/tenants/{TENANT_ID}/restore").mock(
            return_value=_error_response(409, "not_deleted", "tenant is not deleted")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.org.restore_tenant(TENANT_ID)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    @respx.mock
    async def test_disable_tenant_org_not_verified_raises_forbidden(
        self, client: AudactClient
    ) -> None:
        client.set_org_token("org-jwt")
        respx.post(f"{BASE}/v1/org/tenants/{TENANT_ID}/disable").mock(
            return_value=_error_response(403, "org_not_verified", "organization not verified")
        )
        with pytest.raises(AudactForbiddenError):
            await client.org.disable_tenant(TENANT_ID)


class TestInitializeTenant:
    @pytest.mark.asyncio
    @respx.mock
    async def test_initialize_tenant_sends_idempotency_key(
        self, client: AudactClient
    ) -> None:
        client.set_org_token("org-jwt")
        route = respx.post(f"{BASE}/v1/org/tenants/{TENANT_ID}/initialize").mock(
            return_value=_json_response(
                {
                    "tenant": _tenant_payload(initialized_at="2026-06-01T09:00:00Z"),
                    "api_key": {
                        "api_key_id": str(uuid4()),
                        "key": "aud_live_EXAMPLEKEY0000000000000000001",
                        "key_prefix": "a1b2c3d4",
                        "role": "owner",
                    },
                },
                status=201,
            )
        )
        result = await client.org.initialize_tenant(
            TENANT_ID, idempotency_key="idem-init-1"
        )

        sent = route.calls.last.request
        assert sent.method == "POST"
        assert sent.headers["Authorization"] == "Bearer org-jwt"
        assert sent.headers["idempotency-key"] == "idem-init-1"
        assert result.tenant is not None and result.tenant.initialized_at is not None
        assert result.api_key is not None
        assert result.api_key.key == "aud_live_EXAMPLEKEY0000000000000000001"
        assert result.api_key.role == "owner"

    @pytest.mark.asyncio
    @respx.mock
    async def test_initialize_tenant_already_initialized_raises(
        self, client: AudactClient
    ) -> None:
        client.set_org_token("org-jwt")
        respx.post(f"{BASE}/v1/org/tenants/{TENANT_ID}/initialize").mock(
            return_value=_error_response(
                409, "already_initialized", "tenant already initialized"
            )
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.org.initialize_tenant(TENANT_ID)
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "already_initialized"


class TestIssueTenantKey:
    @pytest.mark.asyncio
    @respx.mock
    async def test_issue_tenant_key_sends_body_and_idempotency_key(
        self, client: AudactClient
    ) -> None:
        client.set_org_token("org-jwt")
        route = respx.post(f"{BASE}/v1/org/tenants/{TENANT_ID}/keys").mock(
            return_value=_json_response(
                {
                    "api_key": {
                        "api_key_id": str(uuid4()),
                        "key": "aud_live_EXAMPLEKEY0000000000000000002",
                        "key_prefix": "f6e5d4c3",
                        "role": "owner",
                    }
                },
                status=201,
            )
        )
        result = await client.org.issue_tenant_key(
            TENANT_ID,
            OrgIssueKeyRequest(name="ci-key"),
            idempotency_key="idem-key-1",
        )

        sent = route.calls.last.request
        assert sent.method == "POST"
        assert sent.headers["Authorization"] == "Bearer org-jwt"
        assert sent.headers["idempotency-key"] == "idem-key-1"
        import json as _json

        assert _json.loads(sent.content) == {"name": "ci-key"}
        assert result.api_key is not None
        assert result.api_key.key == "aud_live_EXAMPLEKEY0000000000000000002"

    @pytest.mark.asyncio
    @respx.mock
    async def test_issue_tenant_key_without_body_defaults(
        self, client: AudactClient
    ) -> None:
        client.set_org_token("org-jwt")
        route = respx.post(f"{BASE}/v1/org/tenants/{TENANT_ID}/keys").mock(
            return_value=_json_response(
                {
                    "api_key": {
                        "api_key_id": str(uuid4()),
                        "key": "aud_live_0000000000000000000000000000000",
                        "key_prefix": "00000000",
                        "role": "owner",
                    }
                },
                status=201,
            )
        )
        await client.org.issue_tenant_key(TENANT_ID)

        sent = route.calls.last.request
        import json as _json

        assert _json.loads(sent.content) == {}

    @pytest.mark.asyncio
    @respx.mock
    async def test_issue_tenant_key_not_found(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        respx.post(f"{BASE}/v1/org/tenants/{TENANT_ID}/keys").mock(
            return_value=_error_response(404, "tenant_not_found", "tenant not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.org.issue_tenant_key(TENANT_ID)


class TestImpersonateTenant:
    @pytest.mark.asyncio
    @respx.mock
    async def test_impersonate_tenant(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        route = respx.post(f"{BASE}/v1/org/tenants/{TENANT_ID}/impersonate").mock(
            return_value=_json_response(
                {"tenant_token": "tenant-jwt-abc123", "expires_in": 1200}
            )
        )
        result = await client.org.impersonate_tenant(TENANT_ID)

        sent = route.calls.last.request
        assert sent.method == "POST"
        assert sent.headers["Authorization"] == "Bearer org-jwt"
        assert result.tenant_token == "tenant-jwt-abc123"
        assert result.expires_in == 1200

    @pytest.mark.asyncio
    @respx.mock
    async def test_impersonate_tenant_inactive_raises_conflict(
        self, client: AudactClient
    ) -> None:
        client.set_org_token("org-jwt")
        respx.post(f"{BASE}/v1/org/tenants/{TENANT_ID}/impersonate").mock(
            return_value=_error_response(409, "tenant_inactive", "tenant is not active")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.org.impersonate_tenant(TENANT_ID)
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "tenant_inactive"

    @pytest.mark.asyncio
    @respx.mock
    async def test_impersonate_tenant_not_found(self, client: AudactClient) -> None:
        client.set_org_token("org-jwt")
        respx.post(f"{BASE}/v1/org/tenants/{TENANT_ID}/impersonate").mock(
            return_value=_error_response(404, "not_found", "tenant not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.org.impersonate_tenant(TENANT_ID)
