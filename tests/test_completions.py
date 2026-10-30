"""
Tests for the completion surface: tenant usage, validator
finalize-score (+ mode-marker/config-seal fields on the verdict model),
policy calling-hours, the typed LLM-proxy OpenAI stream, and the platform
health check.

Uses ``respx`` to mock the transport for each target service so no real
network calls are made.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import respx

from audact import AudactClient
from audact.models import (
    CallingHoursCheckResponse,
    FinalizeScoreResponse,
    HealthResponse,
    UsageRecord,
    ValidateResponse,
)

TENANT_ID = uuid4()
CALL_ID = uuid4()
CONFIG_ID = uuid4()
USAGE_ID = uuid4()
NOW = datetime.now(tz=UTC).isoformat()


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


@pytest.fixture()
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_test123")


# ─────────────────────────────────────────────────────────────────────────────
# get_tenant_usage — GET /v1/tenants/{tenant_id}/usage (tenant-management :8085)
# ─────────────────────────────────────────────────────────────────────────────

class TestGetTenantUsage:
    def _payload(self, **overrides) -> dict:
        payload = {
            "usage_id": str(USAGE_ID),
            "tenant_id": str(TENANT_ID),
            "period_start": "2026-03-01T00:00:00Z",
            "period_end": "2026-04-01T00:00:00Z",
            "calls_total": 1234,
            "calls_inbound": 800,
            "calls_outbound": 434,
            "validator_checks": 5678,
            "evidence_events_count": 12345,
            "fail_open_count": 3,
            "llm_tokens_in": 500000,
            "llm_tokens_out": 200000,
            "created_at": NOW,
            "updated_at": NOW,
        }
        payload.update(overrides)
        return payload

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_tenant_usage_basic(self, client: AudactClient):
        respx.get(f"http://localhost:8085/v1/tenants/{TENANT_ID}/usage").mock(
            return_value=_json_response(self._payload())
        )
        async with client as c:
            result = await c.get_tenant_usage(TENANT_ID)
        assert isinstance(result, UsageRecord)
        assert result.tenant_id == TENANT_ID
        assert result.calls_total == 1234
        assert result.fail_open_count == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_tenant_usage_sends_period_query_params(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(self._payload())

        respx.get(f"http://localhost:8085/v1/tenants/{TENANT_ID}/usage").mock(
            side_effect=_handler
        )
        async with client as c:
            await c.get_tenant_usage(
                TENANT_ID,
                period_start="2026-03-01T00:00:00Z",
                period_end="2026-04-01T00:00:00Z",
            )
        params = dict(captured[0].url.params)
        assert params["period_start"] == "2026-03-01T00:00:00Z"
        assert params["period_end"] == "2026-04-01T00:00:00Z"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_tenant_usage_sends_auth_header(self, client: AudactClient):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return _json_response(self._payload())

        respx.get(f"http://localhost:8085/v1/tenants/{TENANT_ID}/usage").mock(
            side_effect=_handler
        )
        async with client as c:
            await c.get_tenant_usage(TENANT_ID)
        assert captured_headers[0]["authorization"] == "Bearer aud_live_test123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_tenant_usage_all_zero_when_no_row(self, client: AudactClient):
        respx.get(f"http://localhost:8085/v1/tenants/{TENANT_ID}/usage").mock(
            return_value=_json_response(
                self._payload(
                    calls_total=0,
                    calls_inbound=0,
                    calls_outbound=0,
                    validator_checks=0,
                    evidence_events_count=0,
                    fail_open_count=0,
                    llm_tokens_in=0,
                    llm_tokens_out=0,
                )
            )
        )
        async with client as c:
            result = await c.get_tenant_usage(TENANT_ID)
        assert result.calls_total == 0
        assert result.tenant_id == TENANT_ID


# ─────────────────────────────────────────────────────────────────────────────
# finalize_call_score — POST /v1/calls/{call_id}/finalize-score (validator :8082)
# ─────────────────────────────────────────────────────────────────────────────

class TestFinalizeCallScore:
    @pytest.mark.asyncio
    @respx.mock
    async def test_finalize_call_score_finalized(self, client: AudactClient):
        respx.post(f"http://localhost:8082/v1/calls/{CALL_ID}/finalize-score").mock(
            return_value=_json_response(
                {
                    "status": "finalized",
                    "composite_score": 0.92,
                    "total_turns": 5,
                    "turns_with_violations": 1,
                    "fail_open_count": 0,
                }
            )
        )
        async with client as c:
            with pytest.warns(DeprecationWarning):
                result = await c.finalize_call_score(CALL_ID)
        assert isinstance(result, FinalizeScoreResponse)
        assert result.status == "finalized"
        assert result.composite_score == 0.92
        assert result.total_turns == 5
        assert result.turns_with_violations == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_finalize_call_score_skipped(self, client: AudactClient):
        respx.post(f"http://localhost:8082/v1/calls/{CALL_ID}/finalize-score").mock(
            return_value=_json_response({"status": "skipped", "composite_score": None})
        )
        async with client as c:
            with pytest.warns(DeprecationWarning):
                result = await c.finalize_call_score(CALL_ID)
        assert result.status == "skipped"
        assert result.composite_score is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_finalize_call_score_sends_agent_id_body(self, client: AudactClient):
        captured: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(json.loads(request.content))
            return _json_response({"status": "finalized", "composite_score": 1.0})

        respx.post(f"http://localhost:8082/v1/calls/{CALL_ID}/finalize-score").mock(
            side_effect=_handler
        )
        async with client as c:
            with pytest.warns(DeprecationWarning):
                await c.finalize_call_score(CALL_ID, agent_id="agent-123")
        assert captured[0]["agent_id"] == "agent-123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_finalize_call_score_sends_idempotency_key(self, client: AudactClient):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return _json_response({"status": "finalized", "composite_score": 1.0})

        respx.post(f"http://localhost:8082/v1/calls/{CALL_ID}/finalize-score").mock(
            side_effect=_handler
        )
        async with client as c:
            with pytest.warns(DeprecationWarning):
                await c.finalize_call_score(CALL_ID, idempotency_key="idem-fcs-1")
        assert captured_headers[0]["idempotency-key"] == "idem-fcs-1"


# ─────────────────────────────────────────────────────────────────────────────
# validate() — mode markers / config_seal_hash surfaced on the verdict model
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateModeMarkersAndConfigSeal:
    @pytest.mark.asyncio
    @respx.mock
    async def test_validate_request_carries_config_seal_hash(self, client: AudactClient):
        captured: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(json.loads(request.content))
            return _json_response(
                {
                    "call_id": str(CALL_ID),
                    "turn": 1,
                    "verdict": "ALLOW",
                    "content": "hi",
                }
            )

        respx.post("http://localhost:8082/v1/validate").mock(side_effect=_handler)
        async with client as c:
            await c.validate(
                call_id=CALL_ID,
                tenant_id=TENANT_ID,
                config_id=CONFIG_ID,
                turn=1,
                content="hi",
                config_seal_hash="a3f1b2c4d5e6f7a8",
            )
        assert captured[0]["config_seal_hash"] == "a3f1b2c4d5e6f7a8"

    @pytest.mark.asyncio
    @respx.mock
    async def test_validate_response_surfaces_check_mode_markers(self, client: AudactClient):
        respx.post("http://localhost:8082/v1/validate").mock(
            return_value=_json_response(
                {
                    "call_id": str(CALL_ID),
                    "turn": 1,
                    "verdict": "ALLOW",
                    "content": "hi",
                    "checks": [
                        {
                            "check_id": "disclosure_gate",
                            "verdict": "ALLOW",
                            "mode": "shadow",
                            "shadow_detection": True,
                            "shadow_verdict": "BLOCK",
                            "shadow_findings": 2,
                        },
                        {
                            "check_id": "toxicity",
                            "verdict": "ALLOW",
                            "mode": "off",
                            "not_run": True,
                        },
                    ],
                }
            )
        )
        async with client as c:
            result = await c.validate(
                call_id=CALL_ID,
                tenant_id=TENANT_ID,
                config_id=CONFIG_ID,
                turn=1,
                content="hi",
            )
        assert isinstance(result, ValidateResponse)
        assert result.checks[0].mode == "shadow"
        assert result.checks[0].shadow_detection is True
        assert result.checks[0].shadow_verdict == "BLOCK"
        assert result.checks[0].shadow_findings == 2
        assert result.checks[1].mode == "off"
        assert result.checks[1].not_run is True


# ─────────────────────────────────────────────────────────────────────────────
# check_calling_hours — GET /v1/calling-hours/check (policy-engine :8081)
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckCallingHours:
    @pytest.mark.asyncio
    @respx.mock
    async def test_check_calling_hours_allowed(self, client: AudactClient):
        respx.get("http://localhost:8081/v1/calling-hours/check").mock(
            return_value=_json_response({"allowed": True, "policy_version": "NL_v1.1.0"})
        )
        async with client as c:
            result = await c.check_calling_hours("NL")
        assert isinstance(result, CallingHoursCheckResponse)
        assert result.allowed is True
        assert result.reason is None  # empty enum string is modelled as None

    @pytest.mark.asyncio
    @respx.mock
    async def test_check_calling_hours_blocked_quiet_hours(self, client: AudactClient):
        respx.get("http://localhost:8081/v1/calling-hours/check").mock(
            return_value=_json_response(
                {
                    "allowed": False,
                    "reason": "quiet_hours",
                    "next_permitted_at": "2026-03-10T08:00:00Z",
                    "policy_version": "NL_v1.1.0",
                }
            )
        )
        async with client as c:
            result = await c.check_calling_hours("NL", call_time="2026-03-09T22:00:00+01:00")
        assert result.allowed is False
        assert result.reason == "quiet_hours"
        assert result.next_permitted_at is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_check_calling_hours_sends_query_params(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response({"allowed": True})

        respx.get("http://localhost:8081/v1/calling-hours/check").mock(side_effect=_handler)
        async with client as c:
            await c.check_calling_hours("DE", call_time="2026-03-09T22:00:00+01:00")
        params = dict(captured[0].url.params)
        assert params["country"] == "DE"
        assert params["call_time"] == "2026-03-09T22:00:00+01:00"


# ─────────────────────────────────────────────────────────────────────────────
# proxy_openai_stream — POST /v1/proxy/openai/stream (llm-proxy :8084)
# ─────────────────────────────────────────────────────────────────────────────

class TestProxyOpenAIStream:
    @pytest.mark.asyncio
    @respx.mock
    async def test_proxy_openai_stream_yields_chunks(self, client: AudactClient):
        respx.post("http://localhost:8084/v1/proxy/openai/stream").mock(
            return_value=httpx.Response(
                200,
                content=b'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n',
                headers={"Content-Type": "text/event-stream"},
            )
        )
        chunks = []
        async with client as c:
            async for chunk in c.proxy_openai_stream(
                call_id=CALL_ID,
                tenant_id=TENANT_ID,
                config_id=CONFIG_ID,
                turn=1,
                model="gpt-4o",
                messages=[{"role": "user", "content": "hi"}],
            ):
                chunks.append(chunk)
        assert b"".join(chunks) == b'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n'

    @pytest.mark.asyncio
    @respx.mock
    async def test_proxy_openai_stream_sends_required_headers_and_body(
        self, client: AudactClient
    ):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, content=b"data: done\n\n")

        respx.post("http://localhost:8084/v1/proxy/openai/stream").mock(side_effect=_handler)
        async with client as c:
            async for _ in c.proxy_openai_stream(
                call_id=CALL_ID,
                tenant_id=TENANT_ID,
                config_id=CONFIG_ID,
                turn=3,
                model="gpt-4o",
                messages=[{"role": "user", "content": "hi"}],
                configuration_id="cfg-override",
            ):
                pass
        request = captured[0]
        assert request.headers["X-Audact-Call-ID"] == str(CALL_ID)
        assert request.headers["X-Audact-Tenant-ID"] == str(TENANT_ID)
        assert request.headers["X-Audact-Config-ID"] == str(CONFIG_ID)
        assert request.headers["X-Audact-Turn"] == "3"
        assert request.headers["authorization"] == "Bearer aud_live_test123"
        assert dict(request.url.params)["configuration_id"] == "cfg-override"
        body = json.loads(request.content)
        assert body["model"] == "gpt-4o"
        assert body["stream"] is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_proxy_openai_stream_raises_on_error(self, client: AudactClient):
        from audact.exceptions import AudactAPIError

        respx.post("http://localhost:8084/v1/proxy/openai/stream").mock(
            return_value=httpx.Response(
                409,
                json={"error": {"code": "model_mismatch", "message": "model mismatch"}},
            )
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                async for _ in c.proxy_openai_stream(
                    call_id=CALL_ID,
                    tenant_id=TENANT_ID,
                    config_id=CONFIG_ID,
                    turn=1,
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "hi"}],
                ):
                    pass
        assert exc_info.value.code == "model_mismatch"


# ─────────────────────────────────────────────────────────────────────────────
# health — GET /v1/health
# ─────────────────────────────────────────────────────────────────────────────

class TestHealth:
    @pytest.mark.asyncio
    @respx.mock
    async def test_health_ok(self, client: AudactClient):
        respx.get("http://localhost:8082/v1/health").mock(
            return_value=_json_response(
                {
                    "status": "ok",
                    "timestamp": NOW,
                    "components": {
                        "redis": {"status": "ok", "latency": "0.4ms"},
                        "postgres": {"status": "ok", "latency": "1.1ms"},
                    },
                }
            )
        )
        async with client as c:
            result = await c.health()
        assert isinstance(result, HealthResponse)
        assert result.status == "ok"
        assert result.components["redis"].status == "ok"

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_degraded_503(self, client: AudactClient):
        from audact.exceptions import AudactAPIError

        respx.get("http://localhost:8082/v1/health").mock(
            return_value=_json_response(
                {
                    "status": "degraded",
                    "components": {"redis": {"status": "error", "error": "timeout"}},
                },
                status=503,
            )
        )
        with pytest.raises(AudactAPIError):
            async with client as c:
                await c.health()
