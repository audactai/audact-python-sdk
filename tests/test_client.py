"""
Tests for AudactClient (M4-013).

Uses ``respx`` to mock httpx transports so no real network calls are made.
Each test group is isolated to a single service endpoint.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import respx
import yaml

from audact import AudactClient
from audact.exceptions import (
    AudactAPIError,
    AudactAuthError,
    AudactConnectionError,
    AudactForbiddenError,
    AudactNotFoundError,
    AudactRateLimitError,
    AudactTimeoutError,
)
from audact.models import (
    Configuration,
    CreateTenantResponse,
    EvaluateResponse,
    GenerateKeyResponse,
    GetChainResponse,
    PlatformBundle,
    PlatformImportResult,
    PostEventResponse,
    Tenant,
    ValidateResponse,
    VerifyChainResponse,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

TENANT_ID = uuid4()
CONFIG_ID = uuid4()
CALL_ID = uuid4()
EVENT_ID = uuid4()
KEY_ID = str(uuid4())
NOW = datetime.now(tz=UTC).isoformat()
AGENT_ID = uuid4()
TARGET_TENANT_ID = uuid4()
PLATFORM_TOKEN = "platform_admin_test_token"  # noqa: S105 - test fixture, not a real secret


@pytest.fixture()
def client(respx_mock: respx.MockRouter) -> AudactClient:  # noqa: ARG001
    """Return a pre-configured AudactClient with a shared httpx transport."""
    return AudactClient(api_key="aud_live_test123")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _error_response(
    status: int,
    code: str,
    message: str,
    *,
    hint: str | None = None,
    details: dict | None = None,
    request_id: str | None = None,
) -> httpx.Response:
    """
    Build a response with the server's REAL nested error envelope:
    ``{"error": {"code", "message", "hint", "details", "request_id"}}``. The old fixture
    built a flat ``{"code": ..., "message": ...}`` body, which does not match production
    and let the error-envelope parser bug go undetected — see test_errors.py for
    the positive control that catches this class of fixture bug directly.
    """
    error: dict = {"code": code, "message": message}
    if hint is not None:
        error["hint"] = hint
    if details is not None:
        error["details"] = details
    if request_id is not None:
        error["request_id"] = request_id
    return httpx.Response(status, json={"error": error})


# ─────────────────────────────────────────────────────────────────────────────
# Construction & configuration
# ─────────────────────────────────────────────────────────────────────────────

class TestClientConstruction:
    def test_default_urls(self):
        c = AudactClient()
        assert c._validator_url == "http://localhost:8082"
        assert c._policy_engine_url == "http://localhost:8081"
        assert c._evidence_layer_url == "http://localhost:8083"
        assert c._llm_proxy_url == "http://localhost:8084"
        assert c._tenant_management_url == "http://localhost:8085"

    def test_custom_urls(self):
        c = AudactClient(
            validator_url="http://validator:8082",
            tenant_management_url="http://tenant:8085",
        )
        assert c._validator_url == "http://validator:8082"
        assert c._tenant_management_url == "http://tenant:8085"

    def test_trailing_slash_stripped(self):
        c = AudactClient(validator_url="http://validator:8082/")
        assert c._validator_url == "http://validator:8082"

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("AUDACT_API_KEY", "aud_live_from_env")
        c = AudactClient()
        assert c._api_key == "aud_live_from_env"

    def test_api_key_kwarg_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("AUDACT_API_KEY", "aud_live_from_env")
        c = AudactClient(api_key="aud_live_explicit")
        assert c._api_key == "aud_live_explicit"

    def test_auth_header_set(self):
        c = AudactClient(api_key="aud_live_xyz")
        assert c._auth_headers() == {"Authorization": "Bearer aud_live_xyz"}

    def test_no_auth_header_when_no_key(self):
        c = AudactClient(api_key="")
        assert c._auth_headers() == {}

    def test_external_httpx_client_not_owned(self):
        ext = httpx.AsyncClient()
        c = AudactClient(httpx_client=ext)
        assert not c._owned_client

    @pytest.mark.asyncio
    async def test_context_manager_closes_owned_client(self):
        async with AudactClient() as c:
            assert not c._http.is_closed
        assert c._http.is_closed


# ─────────────────────────────────────────────────────────────────────────────
# Error mapping
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorMapping:
    @pytest.mark.asyncio
    @respx.mock
    async def test_401_raises_auth_error(self):
        respx.post("http://localhost:8082/v1/validate").mock(
            return_value=_error_response(401, "UNAUTHORIZED", "bad key")
        )
        async with AudactClient(api_key="bad") as c:
            with pytest.raises(AudactAuthError) as exc_info:
                await c.validate(
                    call_id=CALL_ID,
                    tenant_id=TENANT_ID,
                    config_id=CONFIG_ID,
                    turn=1,
                    content="test",
                )
        assert exc_info.value.status_code == 401
        assert exc_info.value.code == "UNAUTHORIZED"

    @pytest.mark.asyncio
    @respx.mock
    async def test_403_raises_forbidden_error(self):
        respx.post("http://localhost:8082/v1/validate").mock(
            return_value=_error_response(403, "FORBIDDEN", "wrong tenant")
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactForbiddenError):
                await c.validate(
                    call_id=CALL_ID,
                    tenant_id=TENANT_ID,
                    config_id=CONFIG_ID,
                    turn=1,
                    content="test",
                )

    @pytest.mark.asyncio
    @respx.mock
    async def test_404_raises_not_found_error(self):
        respx.get(f"http://localhost:8085/v1/tenants/{TENANT_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "tenant not found")
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactNotFoundError):
                await c.get_tenant(TENANT_ID)

    @pytest.mark.asyncio
    @respx.mock
    async def test_429_raises_rate_limit_error(self):
        respx.post("http://localhost:8085/v1/tenants").mock(
            return_value=_error_response(429, "RATE_LIMITED", "too many requests")
        )
        async with AudactClient() as c:
            with pytest.raises(AudactRateLimitError):
                await c.create_tenant("acme")

    @pytest.mark.asyncio
    @respx.mock
    async def test_500_raises_generic_api_error(self):
        respx.post("http://localhost:8082/v1/validate").mock(
            return_value=_error_response(500, "INTERNAL_ERROR", "server error")
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.validate(
                    call_id=CALL_ID,
                    tenant_id=TENANT_ID,
                    config_id=CONFIG_ID,
                    turn=1,
                    content="test",
                )
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout_raises_timeout_error(self):
        respx.post("http://localhost:8082/v1/validate").mock(
            side_effect=httpx.ReadTimeout("timed out", request=None)
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactTimeoutError):
                await c.validate(
                    call_id=CALL_ID,
                    tenant_id=TENANT_ID,
                    config_id=CONFIG_ID,
                    turn=1,
                    content="test",
                )

    @pytest.mark.asyncio
    @respx.mock
    async def test_connect_error_raises_connection_error(self):
        respx.post("http://localhost:8082/v1/validate").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactConnectionError):
                await c.validate(
                    call_id=CALL_ID,
                    tenant_id=TENANT_ID,
                    config_id=CONFIG_ID,
                    turn=1,
                    content="test",
                )

    @pytest.mark.asyncio
    @respx.mock
    async def test_non_json_error_body(self):
        respx.post("http://localhost:8082/v1/validate").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.validate(
                    call_id=CALL_ID,
                    tenant_id=TENANT_ID,
                    config_id=CONFIG_ID,
                    turn=1,
                    content="test",
                )
        assert "Service Unavailable" in exc_info.value.message


# ─────────────────────────────────────────────────────────────────────────────
# Policy Engine
# ─────────────────────────────────────────────────────────────────────────────

class TestPolicyEngine:
    @pytest.mark.asyncio
    @respx.mock
    async def test_evaluate_allow(self):
        payload = {
            "verdict": "ALLOW",
            "reasons": [],
            "applicable_rules": [],
            "policy_version": "NL_v1.1.0",
        }
        respx.post("http://localhost:8081/v1/evaluate").mock(
            return_value=_json_response(payload)
        )
        async with AudactClient(api_key="key") as c:
            resp = await c.evaluate(country="NL", context={"dnc_registered": False})
        assert isinstance(resp, EvaluateResponse)
        assert resp.verdict == "ALLOW"
        assert resp.policy_version == "NL_v1.1.0"

    @pytest.mark.asyncio
    @respx.mock
    async def test_evaluate_block(self):
        payload = {
            "verdict": "BLOCK",
            "reasons": ["DNC registered"],
            "applicable_rules": ["dnc_check"],
            "policy_version": "NL_v1.1.0",
        }
        respx.post("http://localhost:8081/v1/evaluate").mock(
            return_value=_json_response(payload)
        )
        async with AudactClient(api_key="key") as c:
            resp = await c.evaluate(country="NL", context={"dnc_registered": True})
        assert resp.verdict == "BLOCK"
        assert "DNC registered" in resp.reasons

    @pytest.mark.asyncio
    @respx.mock
    async def test_evaluate_sends_correct_body(self):
        captured: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(json.loads(request.content))
            return _json_response(
                {
                    "verdict": "ALLOW",
                    "reasons": [],
                    "applicable_rules": [],
                    "policy_version": "DE_v1.0.0",
                }
            )

        respx.post("http://localhost:8081/v1/evaluate").mock(side_effect=_handler)
        async with AudactClient(api_key="key") as c:
            await c.evaluate(
                country="de",  # should be uppercased by model
                context={"consent_status": "granted"},
            )
        assert captured[0]["country"] == "de"  # SDK passes as-is; server normalises
        assert captured[0]["context"]["consent_status"] == "granted"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_policy(self):
        payload = {"country": "NL", "version": "1.1.0", "rules": []}
        respx.get("http://localhost:8081/v1/policies/NL").mock(
            return_value=_json_response(payload)
        )
        async with AudactClient() as c:
            result = await c.get_policy("nl")
        assert result["country"] == "NL"


# ─────────────────────────────────────────────────────────────────────────────
# Validator
# ─────────────────────────────────────────────────────────────────────────────

class TestValidator:
    def _validate_payload(self) -> dict:
        return {
            "call_id": str(CALL_ID),
            "turn": 1,
            "verdict": "ALLOW",
            "content": "Hello, this is an automated message.",
            "fail_open": False,
            "checks": [],
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_validate_allow(self):
        respx.post("http://localhost:8082/v1/validate").mock(
            return_value=_json_response(self._validate_payload())
        )
        async with AudactClient(api_key="key") as c:
            resp = await c.validate(
                call_id=CALL_ID,
                tenant_id=TENANT_ID,
                config_id=CONFIG_ID,
                turn=1,
                content="Hello, this is an automated message.",
            )
        assert isinstance(resp, ValidateResponse)
        assert resp.verdict == "ALLOW"
        assert resp.fail_open is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_validate_sends_correct_structure(self):
        captured: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(json.loads(request.content))
            return _json_response(self._validate_payload())

        respx.post("http://localhost:8082/v1/validate").mock(side_effect=_handler)
        async with AudactClient(api_key="key") as c:
            await c.validate(
                call_id=CALL_ID,
                tenant_id=TENANT_ID,
                config_id=CONFIG_ID,
                turn=2,
                content="second turn",
                disclosure_delivered=True,
            )
        body = captured[0]
        assert body["turn"] == 2
        assert body["content"] == "second turn"
        assert body["context"]["call_state"]["disclosure_delivered"] is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_validate_with_previous_turns(self):
        captured: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(json.loads(request.content))
            return _json_response(self._validate_payload())

        respx.post("http://localhost:8082/v1/validate").mock(side_effect=_handler)
        prev = [{"turn": 1, "content": "Hi", "verdict": "ALLOW"}]
        async with AudactClient(api_key="key") as c:
            await c.validate(
                call_id=CALL_ID,
                tenant_id=TENANT_ID,
                config_id=CONFIG_ID,
                turn=2,
                content="follow-up",
                previous_turns=prev,
            )
        turns = captured[0]["context"]["previous_turns"]
        assert len(turns) == 1
        assert turns[0]["content"] == "Hi"

    @pytest.mark.asyncio
    @respx.mock
    async def test_validate_fail_open(self):
        payload = {
            **self._validate_payload(),
            "fail_open": True,
            "fail_open_meta": {
                "reason": "deadline_exceeded",
                "deadline_ms": 40.0,
                "elapsed_ms": 42.5,
                "checks_completed": 3,
            },
        }
        respx.post("http://localhost:8082/v1/validate").mock(
            return_value=_json_response(payload)
        )
        async with AudactClient(api_key="key") as c:
            resp = await c.validate(
                call_id=CALL_ID,
                tenant_id=TENANT_ID,
                config_id=CONFIG_ID,
                turn=1,
                content="test",
            )
        assert resp.fail_open is True
        assert resp.fail_open_meta is not None
        assert resp.fail_open_meta.reason == "deadline_exceeded"
        assert resp.fail_open_meta.checks_completed == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_validate_with_receipt(self):
        receipt = {
            "receipt_format_version": "1",
            "call_id": str(CALL_ID),
            "timestamp": NOW,
            "input_hash": "abc",
            "output_hash": "abc",
            "verdict": "ALLOW",
            "config_version": 1,
            "config_seal_hash": "seal",
            "policy_version": "NL_v1.1.0",
            "evidence_hash": "",
            "auth_mechanism": "hmac-sha256",
            "signature": "sig",
        }
        payload = {**self._validate_payload(), "receipt": receipt}
        respx.post("http://localhost:8082/v1/validate").mock(
            return_value=_json_response(payload)
        )
        async with AudactClient(api_key="key") as c:
            resp = await c.validate(
                call_id=CALL_ID,
                tenant_id=TENANT_ID,
                config_id=CONFIG_ID,
                turn=1,
                content="test",
            )
        assert resp.receipt is not None
        assert resp.receipt.auth_mechanism == "hmac-sha256"

    @pytest.mark.asyncio
    @respx.mock
    async def test_validate_sets_auth_header(self):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return _json_response(self._validate_payload())

        respx.post("http://localhost:8082/v1/validate").mock(side_effect=_handler)
        async with AudactClient(api_key="aud_live_abc123") as c:
            await c.validate(
                call_id=CALL_ID,
                tenant_id=TENANT_ID,
                config_id=CONFIG_ID,
                turn=1,
                content="test",
            )
        assert captured_headers[0]["authorization"] == "Bearer aud_live_abc123"


# ─────────────────────────────────────────────────────────────────────────────
# Evidence Layer
# ─────────────────────────────────────────────────────────────────────────────

class TestEvidenceLayer:
    def _event_response(self) -> dict:
        return {
            "event_id": str(EVENT_ID),
            "call_id": str(CALL_ID),
            "tenant_id": str(TENANT_ID),
            "event_type": "CALL_START",
            "sequence": 1,
            "hash": "abc123",
            "previous_hash": "0" * 64,
            "timestamp": NOW,
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_post_event(self):
        respx.post("http://localhost:8083/v1/events").mock(
            return_value=httpx.Response(201, json=self._event_response())
        )
        async with AudactClient(api_key="key") as c:
            resp = await c.post_event(
                call_id=CALL_ID,
                tenant_id=TENANT_ID,
                event_type="CALL_START",
            )
        assert isinstance(resp, PostEventResponse)
        assert resp.sequence == 1
        assert resp.hash == "abc123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_post_event_with_data(self):
        captured: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(json.loads(request.content))
            return httpx.Response(201, json=self._event_response())

        respx.post("http://localhost:8083/v1/events").mock(side_effect=_handler)
        async with AudactClient(api_key="key") as c:
            await c.post_event(
                call_id=CALL_ID,
                tenant_id=TENANT_ID,
                event_type="VALIDATION_RESULT",
                data={"verdict": "ALLOW"},
            )
        assert captured[0]["data"] == {"verdict": "ALLOW"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_post_event_with_idempotency_key(self):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return httpx.Response(201, json=self._event_response())

        respx.post("http://localhost:8083/v1/events").mock(side_effect=_handler)
        async with AudactClient(api_key="key") as c:
            await c.post_event(
                call_id=CALL_ID,
                tenant_id=TENANT_ID,
                event_type="CALL_START",
                idempotency_key="idem-key-xyz",
            )
        assert captured_headers[0]["idempotency-key"] == "idem-key-xyz"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_chain(self):
        payload = {
            "call_id": str(CALL_ID),
            "events": [self._event_response()],
        }
        respx.get(f"http://localhost:8083/v1/chains/{CALL_ID}").mock(
            return_value=_json_response(payload)
        )
        async with AudactClient(api_key="key") as c:
            resp = await c.get_chain(CALL_ID)
        assert isinstance(resp, GetChainResponse)
        assert len(resp.events) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_verify_chain(self):
        payload = {
            "call_id": str(CALL_ID),
            "valid": True,
            "event_count": 5,
            "message": "",
        }
        respx.get(f"http://localhost:8083/v1/verify/{CALL_ID}").mock(
            return_value=_json_response(payload)
        )
        async with AudactClient(api_key="key") as c:
            resp = await c.verify_chain(CALL_ID)
        assert isinstance(resp, VerifyChainResponse)
        assert resp.valid is True
        assert resp.event_count == 5

    @pytest.mark.asyncio
    @respx.mock
    async def test_reconstruct_chain(self):
        payload = {
            "call_id": str(CALL_ID),
            "events": [self._event_response(), self._event_response()],
        }
        respx.get(f"http://localhost:8083/v1/reconstruct/{CALL_ID}").mock(
            return_value=_json_response(payload)
        )
        async with AudactClient(api_key="key") as c:
            resp = await c.reconstruct_chain(CALL_ID)
        assert len(resp.events) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Tenant Management — tenants
# ─────────────────────────────────────────────────────────────────────────────

class TestTenants:
    def _tenant_payload(self) -> dict:
        return {
            "tenant_id": str(TENANT_ID),
            "name": "Acme Corp",
            "plan": "starter",
            "hmac_key_arn": "arn:aws:kms:eu-west-1:123456789:key/mock-key",
            "created_at": NOW,
            "updated_at": NOW,
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_tenant(self):
        payload = {
            **self._tenant_payload(),
            "api_key": {
                "key_id": KEY_ID,
                "key": "aud_live_abc123xyz",
                "key_prefix": "aud_live",
                "name": "default",
                "role": "owner",
            },
        }
        respx.post("http://localhost:8085/v1/tenants").mock(
            return_value=httpx.Response(201, json=payload)
        )
        async with AudactClient() as c:
            resp = await c.create_tenant("Acme Corp")
        assert isinstance(resp, CreateTenantResponse)
        assert resp.name == "Acme Corp"
        assert resp.api_key.key == "aud_live_abc123xyz"
        assert resp.api_key.role == "owner"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_tenant_does_not_send_auth_header(self):
        """POST /v1/tenants is unauthenticated — API key should still be sent
        if configured, but absence of key is valid too."""
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return httpx.Response(
                201,
                json={
                    **self._tenant_payload(),
                    "api_key": {
                        "key_id": KEY_ID,
                        "key": "k",
                        "key_prefix": "aud_live",
                        "name": "default",
                        "role": "owner",
                    },
                },
            )

        respx.post("http://localhost:8085/v1/tenants").mock(side_effect=_handler)
        async with AudactClient(api_key="") as c:
            await c.create_tenant("Test")
        assert "authorization" not in captured_headers[0]

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_tenant(self):
        respx.get(f"http://localhost:8085/v1/tenants/{TENANT_ID}").mock(
            return_value=_json_response(self._tenant_payload())
        )
        async with AudactClient(api_key="key") as c:
            tenant = await c.get_tenant(TENANT_ID)
        assert isinstance(tenant, Tenant)
        assert tenant.name == "Acme Corp"
        assert tenant.plan == "starter"

    @pytest.mark.asyncio
    @respx.mock
    async def test_update_tenant(self):
        updated = {**self._tenant_payload(), "plan": "professional"}
        respx.put(f"http://localhost:8085/v1/tenants/{TENANT_ID}").mock(
            return_value=_json_response(updated)
        )
        async with AudactClient(api_key="key") as c:
            tenant = await c.update_tenant(TENANT_ID, plan="professional")
        assert tenant.plan == "professional"

    @pytest.mark.asyncio
    @respx.mock
    async def test_update_tenant_only_sends_non_none_fields(self):
        captured: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(json.loads(request.content))
            return _json_response(self._tenant_payload())

        respx.put(f"http://localhost:8085/v1/tenants/{TENANT_ID}").mock(
            side_effect=_handler
        )
        async with AudactClient(api_key="key") as c:
            await c.update_tenant(TENANT_ID, name="New Name")
        assert "plan" not in captured[0]
        assert captured[0]["name"] == "New Name"


# ─────────────────────────────────────────────────────────────────────────────
# Tenant Management — API keys
# ─────────────────────────────────────────────────────────────────────────────

class TestAPIKeys:
    @pytest.mark.asyncio
    @respx.mock
    async def test_generate_key(self):
        payload = {
            "key_id": KEY_ID,
            "key": "aud_live_newkey123",
            "key_prefix": "aud_live",
            "name": "ci-key",
            "role": "developer",
            "created_at": NOW,
        }
        respx.post(f"http://localhost:8085/v1/tenants/{TENANT_ID}/keys").mock(
            return_value=httpx.Response(201, json=payload)
        )
        async with AudactClient(api_key="key") as c:
            resp = await c.generate_key(TENANT_ID, name="ci-key", role="developer")
        assert isinstance(resp, GenerateKeyResponse)
        assert resp.key == "aud_live_newkey123"
        assert resp.role == "developer"

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_keys(self):
        payload = {
            "keys": [
                {
                    "key_id": KEY_ID,
                    "key_prefix": "aud_live",
                    "name": "default",
                    "role": "owner",
                    "created_at": NOW,
                    "revoked_at": None,
                }
            ]
        }
        respx.get(f"http://localhost:8085/v1/tenants/{TENANT_ID}/keys").mock(
            return_value=_json_response(payload)
        )
        async with AudactClient(api_key="key") as c:
            keys = await c.list_keys(TENANT_ID)
        assert len(keys) == 1
        assert keys[0].role == "owner"

    @pytest.mark.asyncio
    @respx.mock
    async def test_revoke_key(self):
        respx.delete(
            f"http://localhost:8085/v1/tenants/{TENANT_ID}/keys/{KEY_ID}"
        ).mock(return_value=httpx.Response(204))
        async with AudactClient(api_key="key") as c:
            # Should not raise
            await c.revoke_key(TENANT_ID, KEY_ID)


# ─────────────────────────────────────────────────────────────────────────────
# Tenant Management — configurations
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigurations:
    def _config_payload(self) -> dict:
        return {
            "config_id": str(CONFIG_ID),
            "tenant_id": str(TENANT_ID),
            "name": "My Config",
            "version": 1,
            "countries": ["NL", "DE"],
            "validator_modes": {},
            "blocklist_patterns": [],
            "pricing_bands": {},
            "disclosure_texts": {},
            "fallback_response": {},
            "config_seal_hash": "deadbeef",
            "created_at": NOW,
            "updated_at": NOW,
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_configuration(self):
        respx.post("http://localhost:8085/v1/configurations").mock(
            return_value=httpx.Response(201, json=self._config_payload())
        )
        async with AudactClient(api_key="key") as c:
            cfg = await c.create_configuration(
                name="My Config",
                countries=["NL", "DE"],
            )
        assert isinstance(cfg, Configuration)
        assert cfg.name == "My Config"
        assert "NL" in cfg.countries

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_configuration_with_blocklist(self):
        captured: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(json.loads(request.content))
            return httpx.Response(201, json=self._config_payload())

        respx.post("http://localhost:8085/v1/configurations").mock(
            side_effect=_handler
        )
        patterns = [{"id": "p1", "terms": ["bad word"], "severity": "block"}]
        async with AudactClient(api_key="key") as c:
            await c.create_configuration(
                name="My Config",
                countries=["NL"],
                blocklist_patterns=patterns,
            )
        assert len(captured[0]["blocklist_patterns"]) == 1
        assert captured[0]["blocklist_patterns"][0]["id"] == "p1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_configuration(self):
        respx.get(f"http://localhost:8085/v1/configurations/{CONFIG_ID}").mock(
            return_value=_json_response(self._config_payload())
        )
        async with AudactClient(api_key="key") as c:
            cfg = await c.get_configuration(CONFIG_ID)
        assert cfg.version == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_configuration_version(self):
        earlier = {**self._config_payload(), "version": 2}
        route = respx.get(
            f"http://localhost:8085/v1/configurations/{CONFIG_ID}/versions/2"
        ).mock(return_value=_json_response(earlier))
        async with AudactClient(api_key="key") as c:
            cfg = await c.get_configuration_version(CONFIG_ID, 2)
        assert route.called
        assert cfg.version == 2

    @pytest.mark.asyncio
    async def test_get_configuration_version_rejects_version_below_one(self):
        async with AudactClient(api_key="key") as c:
            with pytest.raises(ValueError, match="version must be >= 1"):
                await c.get_configuration_version(CONFIG_ID, 0)

    @pytest.mark.asyncio
    @respx.mock
    async def test_update_configuration(self):
        updated = {**self._config_payload(), "name": "Updated Config", "version": 2}
        respx.put(f"http://localhost:8085/v1/configurations/{CONFIG_ID}").mock(
            return_value=_json_response(updated)
        )
        async with AudactClient(api_key="key") as c:
            cfg = await c.update_configuration(CONFIG_ID, name="Updated Config")
        assert cfg.name == "Updated Config"
        assert cfg.version == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_update_configuration_excludes_none_fields(self):
        captured: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(json.loads(request.content))
            return _json_response(self._config_payload())

        respx.put(f"http://localhost:8085/v1/configurations/{CONFIG_ID}").mock(
            side_effect=_handler
        )
        async with AudactClient(api_key="key") as c:
            await c.update_configuration(CONFIG_ID, name="New Name")
        assert "countries" not in captured[0]
        assert captured[0]["name"] == "New Name"

    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_configuration(self):
        respx.delete(f"http://localhost:8085/v1/configurations/{CONFIG_ID}").mock(
            return_value=httpx.Response(204)
        )
        async with AudactClient(api_key="key") as c:
            await c.delete_configuration(CONFIG_ID)  # should not raise

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_configurations(self):
        payload = {"configurations": [self._config_payload(), self._config_payload()]}
        respx.get(
            f"http://localhost:8085/v1/tenants/{TENANT_ID}/configurations"
        ).mock(return_value=_json_response(payload))
        async with AudactClient(api_key="key") as c:
            configs = await c.list_configurations(TENANT_ID)
        assert len(configs) == 2
        assert all(isinstance(c, Configuration) for c in configs)


# ─────────────────────────────────────────────────────────────────────────────
# LLM Proxy — streaming
# ─────────────────────────────────────────────────────────────────────────────

class TestLLMProxy:
    @pytest.mark.asyncio
    @respx.mock
    async def test_proxy_request(self):
        payload = {"id": "chatcmpl-abc", "choices": [{"message": {"content": "Hi!"}}]}
        respx.post("http://localhost:8084/v1/chat/completions").mock(
            return_value=_json_response(payload)
        )
        async with AudactClient(api_key="key") as c:
            result = await c.proxy_request(
                "/v1/chat/completions",
                json={"model": "gpt-4", "messages": []},
            )
        assert result["id"] == "chatcmpl-abc"

    @pytest.mark.asyncio
    @respx.mock
    async def test_proxy_stream(self):
        chunks = [b"data: chunk1\n\n", b"data: chunk2\n\n", b"data: [DONE]\n\n"]
        respx.post("http://localhost:8084/v1/chat/completions").mock(
            return_value=httpx.Response(200, content=b"".join(chunks))
        )
        collected: list[bytes] = []
        async with AudactClient(api_key="key") as c:
            async for chunk in c.proxy_stream(
                "/v1/chat/completions",
                json={"model": "gpt-4", "messages": [], "stream": True},
            ):
                collected.append(chunk)
        assert b"".join(collected) == b"".join(chunks)

    @pytest.mark.asyncio
    @respx.mock
    async def test_proxy_stream_error(self):
        respx.post("http://localhost:8084/v1/chat/completions").mock(
            return_value=_error_response(401, "UNAUTHORIZED", "bad key")
        )
        async with AudactClient(api_key="bad") as c:
            with pytest.raises(AudactAuthError):
                async for _ in c.proxy_stream("/v1/chat/completions"):
                    pass

    @pytest.mark.asyncio
    @respx.mock
    async def test_proxy_stream_timeout(self):
        respx.post("http://localhost:8084/v1/chat/completions").mock(
            side_effect=httpx.ReadTimeout("stream timed out", request=None)
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactTimeoutError):
                async for _ in c.proxy_stream("/v1/chat/completions"):
                    pass

    @pytest.mark.asyncio
    @respx.mock
    async def test_proxy_stream_connect_error(self):
        respx.post("http://localhost:8084/v1/chat/completions").mock(
            side_effect=httpx.ConnectError("refused")
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactConnectionError):
                async for _ in c.proxy_stream("/v1/chat/completions"):
                    pass

    @pytest.mark.asyncio
    @respx.mock
    async def test_proxy_complete_with_configuration_id(self):
        """proxy_complete passes configuration_id as a query parameter."""
        captured_urls: list[str] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_urls.append(str(request.url))
            return _json_response({"id": "chatcmpl-xyz", "choices": []})

        respx.post("http://localhost:8084/v1/proxy/openai").mock(side_effect=_handler)
        cfg_id = str(CONFIG_ID)
        async with AudactClient(api_key="key") as c:
            result = await c.proxy_complete(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hello"}],
                configuration_id=cfg_id,
            )
        assert result["id"] == "chatcmpl-xyz"
        assert len(captured_urls) == 1
        assert f"configuration_id={cfg_id}" in captured_urls[0]

    @pytest.mark.asyncio
    @respx.mock
    async def test_proxy_complete_without_configuration_id(self):
        """proxy_complete omits configuration_id query param when not supplied."""
        captured_urls: list[str] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_urls.append(str(request.url))
            return _json_response({"id": "chatcmpl-abc", "choices": []})

        respx.post("http://localhost:8084/v1/proxy/openai").mock(side_effect=_handler)
        async with AudactClient(api_key="key") as c:
            await c.proxy_complete(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hi"}],
            )
        assert "configuration_id" not in captured_urls[0]

    @pytest.mark.asyncio
    @respx.mock
    async def test_proxy_stream_with_configuration_id(self):
        """proxy_stream passes configuration_id as a query parameter."""
        captured_urls: list[str] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_urls.append(str(request.url))
            return httpx.Response(200, content=b"data: chunk\n\n")

        respx.post("http://localhost:8084/v1/proxy/openai/stream").mock(
            side_effect=_handler
        )
        cfg_id = str(CONFIG_ID)
        async with AudactClient(api_key="key") as c:
            chunks = []
            async for chunk in c.proxy_stream(
                "/v1/proxy/openai/stream",
                json={"model": "gpt-4o", "messages": [], "stream": True},
                configuration_id=cfg_id,
            ):
                chunks.append(chunk)
        assert len(captured_urls) == 1
        assert f"configuration_id={cfg_id}" in captured_urls[0]
        assert b"data: chunk\n\n" in b"".join(chunks)


# ─────────────────────────────────────────────────────────────────────────────
# Platform admin — export_tenant / export_agent / import_tenant
# ─────────────────────────────────────────────────────────────────────────────

class TestPlatformAdmin:
    def _bundle_payload(self) -> dict:
        return {
            "apiVersion": "audact.ai/v1",
            "kind": "TenantBundle",
            "metadata": {"name": "Acme Corp"},
            "spec": {
                "configurations": [
                    {
                        "ref": "configuration-acme-default-1",
                        "name": "Acme Default",
                        "countries": ["NL", "DE"],
                    }
                ],
                "tools": [],
                "agents": [
                    {
                        "ref": "agent-acme-support-1",
                        "name": "Acme Support",
                        "prompt": "You are a helpful assistant.",
                        "configRef": "configuration-acme-default-1",
                    }
                ],
            },
        }

    def _import_response_payload(self) -> dict:
        return {
            "dry_run": False,
            "mode": "create-only",
            "bundle_sha256": "a" * 64,
            "counts": {"configuration": 1, "agent": 1},
            "entities": [
                {
                    "ref": "configuration-acme-default-1",
                    "kind": "configuration",
                    "name": "Acme Default",
                    "status": "created",
                    "new_id": str(uuid4()),
                    "needs_secret": False,
                },
                {
                    "ref": "agent-acme-support-1",
                    "kind": "agent",
                    "name": "Acme Support",
                    "status": "created",
                    "new_id": str(uuid4()),
                    "needs_secret": False,
                },
            ],
            "warnings": [],
        }

    # ── export_tenant ────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    @respx.mock
    async def test_export_tenant_path_and_verb(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=self._bundle_payload())

        respx.get(
            f"http://localhost:8085/v1/platform/export/tenants/{TENANT_ID}"
        ).mock(side_effect=_handler)

        async with AudactClient() as c:
            bundle = await c.export_tenant(TENANT_ID, platform_token=PLATFORM_TOKEN)

        assert len(captured) == 1
        assert captured[0].method == "GET"
        assert isinstance(bundle, PlatformBundle)
        assert bundle.api_version == "audact.ai/v1"
        assert bundle.kind == "TenantBundle"
        assert bundle.metadata.name == "Acme Corp"
        assert bundle.spec.configurations[0].ref == "configuration-acme-default-1"
        assert bundle.spec.agents[0].config_ref == "configuration-acme-default-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_export_tenant_sends_platform_token_not_api_key(self):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return httpx.Response(200, json=self._bundle_payload())

        respx.get(
            f"http://localhost:8085/v1/platform/export/tenants/{TENANT_ID}"
        ).mock(side_effect=_handler)

        # A tenant API key is configured, but the platform-admin surface must
        # authenticate with the platform token, never the tenant API key.
        async with AudactClient(api_key="aud_live_tenant_key") as c:
            await c.export_tenant(TENANT_ID, platform_token=PLATFORM_TOKEN)

        assert captured_headers[0]["authorization"] == f"Bearer {PLATFORM_TOKEN}"

    @pytest.mark.asyncio
    @respx.mock
    async def test_export_tenant_format_json_sets_accept_header(self):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return httpx.Response(200, json=self._bundle_payload())

        respx.get(
            f"http://localhost:8085/v1/platform/export/tenants/{TENANT_ID}"
        ).mock(side_effect=_handler)

        async with AudactClient() as c:
            await c.export_tenant(TENANT_ID, platform_token=PLATFORM_TOKEN, format="json")

        assert captured_headers[0]["accept"] == "application/json"

    @pytest.mark.asyncio
    @respx.mock
    async def test_export_tenant_format_yaml_sets_accept_header(self):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return httpx.Response(
                200, content=yaml.safe_dump(self._bundle_payload()).encode("utf-8")
            )

        respx.get(
            f"http://localhost:8085/v1/platform/export/tenants/{TENANT_ID}"
        ).mock(side_effect=_handler)

        async with AudactClient() as c:
            bundle = await c.export_tenant(TENANT_ID, platform_token=PLATFORM_TOKEN, format="yaml")

        assert captured_headers[0]["accept"] == "application/yaml"
        assert bundle.kind == "TenantBundle"

    @pytest.mark.asyncio
    @respx.mock
    async def test_export_tenant_default_format_sends_no_accept_override(self):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return httpx.Response(200, json=self._bundle_payload())

        respx.get(
            f"http://localhost:8085/v1/platform/export/tenants/{TENANT_ID}"
        ).mock(side_effect=_handler)

        async with AudactClient() as c:
            await c.export_tenant(TENANT_ID, platform_token=PLATFORM_TOKEN)

        # httpx's own default ("*/*") is sent — the SDK does not override it
        # with an explicit YAML/JSON Accept header unless format= is given.
        assert captured_headers[0]["accept"] == "*/*"

    @pytest.mark.asyncio
    async def test_export_tenant_invalid_format_raises(self):
        async with AudactClient() as c:
            with pytest.raises(ValueError, match="format"):
                await c.export_tenant(
                    TENANT_ID, platform_token=PLATFORM_TOKEN, format="xml"
                )

    @pytest.mark.asyncio
    @respx.mock
    async def test_export_tenant_parses_yaml_body(self):
        """The server's default response is YAML text, not JSON."""
        yaml_body = yaml.safe_dump(self._bundle_payload(), sort_keys=False)
        respx.get(
            f"http://localhost:8085/v1/platform/export/tenants/{TENANT_ID}"
        ).mock(return_value=httpx.Response(200, content=yaml_body.encode("utf-8")))

        async with AudactClient() as c:
            bundle = await c.export_tenant(TENANT_ID, platform_token=PLATFORM_TOKEN)

        assert bundle.kind == "TenantBundle"
        assert bundle.spec.agents[0].name == "Acme Support"

    # ── export_agent ─────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    @respx.mock
    async def test_export_agent_path_verb_and_tenant_query_param(self):
        captured: list[httpx.Request] = []

        agent_bundle = {**self._bundle_payload(), "kind": "AgentBundle"}

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=agent_bundle)

        respx.get(
            f"http://localhost:8085/v1/platform/export/agents/{AGENT_ID}"
        ).mock(side_effect=_handler)

        async with AudactClient() as c:
            bundle = await c.export_agent(
                AGENT_ID, tenant_id=TENANT_ID, platform_token=PLATFORM_TOKEN
            )

        assert len(captured) == 1
        assert captured[0].method == "GET"
        assert captured[0].url.params["tenant_id"] == str(TENANT_ID)
        assert captured[0].headers["authorization"] == f"Bearer {PLATFORM_TOKEN}"
        assert bundle.kind == "AgentBundle"

    # ── import_tenant ────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    @respx.mock
    async def test_import_tenant_path_verb_and_auth_header(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=self._import_response_payload())

        respx.post(
            f"http://localhost:8085/v1/platform/import/tenants/{TARGET_TENANT_ID}"
        ).mock(side_effect=_handler)

        async with AudactClient() as c:
            result = await c.import_tenant(
                TARGET_TENANT_ID,
                self._bundle_payload(),
                platform_token=PLATFORM_TOKEN,
            )

        assert len(captured) == 1
        assert captured[0].method == "POST"
        assert captured[0].headers["authorization"] == f"Bearer {PLATFORM_TOKEN}"
        assert isinstance(result, PlatformImportResult)
        assert result.mode == "create-only"
        assert result.counts == {"configuration": 1, "agent": 1}
        assert len(result.entities) == 2
        assert result.entities[0].status == "created"

    @pytest.mark.asyncio
    @respx.mock
    async def test_import_tenant_forwards_dry_run_and_mode(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            payload = {**self._import_response_payload(), "dry_run": True}
            return httpx.Response(200, json=payload)

        respx.post(
            f"http://localhost:8085/v1/platform/import/tenants/{TARGET_TENANT_ID}"
        ).mock(side_effect=_handler)

        async with AudactClient() as c:
            result = await c.import_tenant(
                TARGET_TENANT_ID,
                self._bundle_payload(),
                platform_token=PLATFORM_TOKEN,
                dry_run=True,
                mode="create-only",
            )

        params = captured[0].url.params
        assert params["dryRun"] == "true"
        assert params["mode"] == "create-only"
        assert result.dry_run is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_import_tenant_omits_dry_run_query_param_by_default(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=self._import_response_payload())

        respx.post(
            f"http://localhost:8085/v1/platform/import/tenants/{TARGET_TENANT_ID}"
        ).mock(side_effect=_handler)

        async with AudactClient() as c:
            await c.import_tenant(
                TARGET_TENANT_ID, self._bundle_payload(), platform_token=PLATFORM_TOKEN
            )

        assert "dryRun" not in captured[0].url.params

    @pytest.mark.asyncio
    @respx.mock
    async def test_import_tenant_forwards_set_secret_list(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=self._import_response_payload())

        respx.post(
            f"http://localhost:8085/v1/platform/import/tenants/{TARGET_TENANT_ID}"
        ).mock(side_effect=_handler)

        async with AudactClient() as c:
            await c.import_tenant(
                TARGET_TENANT_ID,
                self._bundle_payload(),
                platform_token=PLATFORM_TOKEN,
                set_secret=["tool-acme-crm-1.headers.Authorization=Bearer sekret"],
            )

        # SECURITY: the plaintext secret must travel as a repeated
        # X-Audact-Set-Secret request header, NEVER a URL query param (which
        # reverse proxies log).
        assert captured[0].headers.get_list("X-Audact-Set-Secret") == [
            "tool-acme-crm-1.headers.Authorization=Bearer sekret"
        ]
        assert "setSecret" not in captured[0].url.params
        assert "sekret" not in str(captured[0].url)

    @pytest.mark.asyncio
    @respx.mock
    async def test_import_tenant_forwards_set_secret_mapping(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=self._import_response_payload())

        respx.post(
            f"http://localhost:8085/v1/platform/import/tenants/{TARGET_TENANT_ID}"
        ).mock(side_effect=_handler)

        async with AudactClient() as c:
            await c.import_tenant(
                TARGET_TENANT_ID,
                self._bundle_payload(),
                platform_token=PLATFORM_TOKEN,
                set_secret={"tool-acme-crm-1.headers.Authorization": "Bearer sekret"},
            )

        assert captured[0].headers.get_list("X-Audact-Set-Secret") == [
            "tool-acme-crm-1.headers.Authorization=Bearer sekret"
        ]
        assert "setSecret" not in captured[0].url.params
        assert "sekret" not in str(captured[0].url)

    @pytest.mark.asyncio
    @respx.mock
    async def test_import_tenant_accepts_platform_bundle_instance(self):
        """A PlatformBundle (e.g. returned by export_tenant()) can be re-imported directly."""
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=self._import_response_payload())

        respx.get(
            f"http://localhost:8085/v1/platform/export/tenants/{TENANT_ID}"
        ).mock(return_value=httpx.Response(200, json=self._bundle_payload()))
        respx.post(
            f"http://localhost:8085/v1/platform/import/tenants/{TARGET_TENANT_ID}"
        ).mock(side_effect=_handler)

        async with AudactClient() as c:
            bundle = await c.export_tenant(TENANT_ID, platform_token=PLATFORM_TOKEN)
            result = await c.import_tenant(
                TARGET_TENANT_ID, bundle, platform_token=PLATFORM_TOKEN
            )

        assert isinstance(result, PlatformImportResult)
        sent_body = yaml.safe_load(captured[0].content)
        assert sent_body["metadata"]["name"] == "Acme Corp"
        assert sent_body["spec"]["agents"][0]["configRef"] == "configuration-acme-default-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_import_tenant_accepts_raw_bytes(self):
        """Raw YAML/JSON bytes (e.g. read from a file) are forwarded unmodified."""
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=self._import_response_payload())

        respx.post(
            f"http://localhost:8085/v1/platform/import/tenants/{TARGET_TENANT_ID}"
        ).mock(side_effect=_handler)

        raw = json.dumps(self._bundle_payload()).encode("utf-8")
        async with AudactClient() as c:
            await c.import_tenant(TARGET_TENANT_ID, raw, platform_token=PLATFORM_TOKEN)

        assert captured[0].content == raw

    @pytest.mark.asyncio
    @respx.mock
    async def test_import_tenant_accepts_raw_str(self):
        """A raw YAML/JSON string (e.g. read from a text file) is UTF-8 encoded and forwarded."""
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=self._import_response_payload())

        respx.post(
            f"http://localhost:8085/v1/platform/import/tenants/{TARGET_TENANT_ID}"
        ).mock(side_effect=_handler)

        raw = json.dumps(self._bundle_payload())
        async with AudactClient() as c:
            await c.import_tenant(TARGET_TENANT_ID, raw, platform_token=PLATFORM_TOKEN)

        assert captured[0].content == raw.encode("utf-8")

    @pytest.mark.asyncio
    @respx.mock
    async def test_import_tenant_streams_file_handle(self, tmp_path):
        """An open binary file handle is streamed through to the request body."""
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=self._import_response_payload())

        respx.post(
            f"http://localhost:8085/v1/platform/import/tenants/{TARGET_TENANT_ID}"
        ).mock(side_effect=_handler)

        bundle_path = tmp_path / "bundle.yaml"
        raw = json.dumps(self._bundle_payload()).encode("utf-8")
        bundle_path.write_bytes(raw)

        async with AudactClient() as c:
            with bundle_path.open("rb") as fh:
                await c.import_tenant(TARGET_TENANT_ID, fh, platform_token=PLATFORM_TOKEN)

        assert captured[0].content == raw

    @pytest.mark.asyncio
    @respx.mock
    async def test_export_then_import_round_trip_parses_manifest(self):
        """Full round trip: export a bundle, import it, and parse the result manifest."""
        respx.get(
            f"http://localhost:8085/v1/platform/export/tenants/{TENANT_ID}"
        ).mock(return_value=httpx.Response(200, json=self._bundle_payload()))
        respx.post(
            f"http://localhost:8085/v1/platform/import/tenants/{TARGET_TENANT_ID}"
        ).mock(
            return_value=httpx.Response(
                200, json={**self._import_response_payload(), "dry_run": True}
            )
        )

        async with AudactClient() as c:
            bundle = await c.export_tenant(TENANT_ID, platform_token=PLATFORM_TOKEN)
            result = await c.import_tenant(
                TARGET_TENANT_ID, bundle, platform_token=PLATFORM_TOKEN, dry_run=True
            )

        assert result.dry_run is True
        assert result.counts["configuration"] == 1
        assert result.counts["agent"] == 1
        assert {e.ref for e in result.entities} == {
            "configuration-acme-default-1",
            "agent-acme-support-1",
        }
        assert all(e.status == "created" for e in result.entities)


# ─────────────────────────────────────────────────────────────────────────────
# base_url / AUDACT_BASE_URL
# ─────────────────────────────────────────────────────────────────────────────

_SERVICE_URLS = [
    ("policy_engine_url", "AUDACT_POLICY_ENGINE_URL", "http://localhost:8081"),
    ("validator_url", "AUDACT_VALIDATOR_URL", "http://localhost:8082"),
    ("evidence_layer_url", "AUDACT_EVIDENCE_LAYER_URL", "http://localhost:8083"),
    ("llm_proxy_url", "AUDACT_LLM_PROXY_URL", "http://localhost:8084"),
    ("tenant_management_url", "AUDACT_TENANT_MANAGEMENT_URL", "http://localhost:8085"),
    ("audio_validator_url", "AUDACT_AUDIO_VALIDATOR_URL", "http://localhost:8086"),
    ("aggregator_url", "AUDACT_AGGREGATOR_URL", "http://localhost:8087"),
    ("voice_gateway_url", "AUDACT_VOICE_GATEWAY_URL", "http://localhost:8088"),
    ("agent_worker_url", "AUDACT_AGENT_WORKER_URL", "http://localhost:8089"),
    ("org_management_url", "AUDACT_ORG_MANAGEMENT_URL", "http://localhost:8092"),
]


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    import os

    for key in list(os.environ):
        if key.startswith("AUDACT_"):
            monkeypatch.delenv(key)
    return monkeypatch


def _urls(client: AudactClient) -> dict[str, str]:
    return {kw: getattr(client, "_" + kw) for kw, _, _ in _SERVICE_URLS}


def test_defaults_unchanged_without_base_url(clean_env: pytest.MonkeyPatch) -> None:
    urls = _urls(AudactClient(api_key="k"))
    assert urls == {kw: default for kw, _, default in _SERVICE_URLS}


def test_base_url_kwarg_applies_to_all_services(clean_env: pytest.MonkeyPatch) -> None:
    urls = _urls(AudactClient(api_key="k", base_url="https://h"))
    assert set(urls.values()) == {"https://h"}
    assert len(urls) == 10


def test_audact_base_url_env_alone_applies(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("AUDACT_BASE_URL", "https://env.h")
    assert set(_urls(AudactClient(api_key="k")).values()) == {"https://env.h"}


def test_base_url_kwarg_beats_env(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("AUDACT_BASE_URL", "https://env.h")
    client = AudactClient(api_key="k", base_url="https://kw.h")
    assert set(_urls(client).values()) == {"https://kw.h"}


@pytest.mark.parametrize(("kwarg", "env_key", "default"), _SERVICE_URLS)
def test_per_service_kwarg_beats_base_url(
    clean_env: pytest.MonkeyPatch, kwarg: str, env_key: str, default: str
) -> None:
    clean_env.setenv("AUDACT_BASE_URL", "https://env.h")
    client = AudactClient(api_key="k", base_url="https://h", **{kwarg: "https://own/"})
    urls = _urls(client)
    assert urls[kwarg] == "https://own"
    assert all(v == "https://h" for k, v in urls.items() if k != kwarg)


@pytest.mark.parametrize(("kwarg", "env_key", "default"), _SERVICE_URLS)
def test_per_service_env_beats_base_url(
    clean_env: pytest.MonkeyPatch, kwarg: str, env_key: str, default: str
) -> None:
    clean_env.setenv(env_key, "https://own-env")
    client = AudactClient(api_key="k", base_url="https://h")
    urls = _urls(client)
    assert urls[kwarg] == "https://own-env"
    assert all(v == "https://h" for k, v in urls.items() if k != kwarg)


@pytest.mark.parametrize("raw", ["https://h/", "https://h/v1", "https://h/v1/", "https://h"])
def test_base_url_normalized(clean_env: pytest.MonkeyPatch, raw: str) -> None:
    assert set(_urls(AudactClient(api_key="k", base_url=raw)).values()) == {"https://h"}


@pytest.mark.asyncio
async def test_base_url_request_hits_v1_path(clean_env: pytest.MonkeyPatch) -> None:
    client = AudactClient(api_key="k", base_url="https://h/v1/")
    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://h/v1/calls/c1/summary").respond(404, json={})
        with pytest.raises(AudactNotFoundError):
            await client._request("GET", f"{client._agent_worker_url}/v1/calls/c1/summary")
        assert route.called
