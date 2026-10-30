"""
Tests for the transport foundations:

- OrgBearer / PlatformBearer token storage + selection (``auth_token`` on
  ``_auth_headers``/``_request``), with fall-back to the tenant ``api_key``.
- The 4 new base URLs (audio-validator :8086, aggregator :8087,
  agent-worker :8089, org-management :8092) — kwargs, env fallbacks,
  defaults, and trailing-slash stripping (matching the existing 6-URL
  pattern).
- The uniform ``idempotency_key`` param on ``_request``.
- The cursor-pagination ``Page`` model (``{items, has_more, next_cursor}``).

Uses ``respx`` to mock httpx transports so no real network calls are made.
"""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
import respx

from audact import AudactClient
from audact.models import Page


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


# ─────────────────────────────────────────────────────────────────────────────
# New base URLs — kwargs + env fallbacks + defaults
# ─────────────────────────────────────────────────────────────────────────────

class TestNewServiceURLs:
    def test_default_urls(self):
        c = AudactClient()
        assert c._audio_validator_url == "http://localhost:8086"
        assert c._aggregator_url == "http://localhost:8087"
        assert c._agent_worker_url == "http://localhost:8089"
        assert c._org_management_url == "http://localhost:8092"

    def test_custom_urls_from_kwargs(self):
        c = AudactClient(
            audio_validator_url="http://audio:8086",
            aggregator_url="http://agg:8087",
            agent_worker_url="http://agent:8089",
            org_management_url="http://org:8092",
        )
        assert c._audio_validator_url == "http://audio:8086"
        assert c._aggregator_url == "http://agg:8087"
        assert c._agent_worker_url == "http://agent:8089"
        assert c._org_management_url == "http://org:8092"

    def test_urls_from_env(self, monkeypatch):
        monkeypatch.setenv("AUDACT_AUDIO_VALIDATOR_URL", "http://envaudio:8086")
        monkeypatch.setenv("AUDACT_AGGREGATOR_URL", "http://envagg:8087")
        monkeypatch.setenv("AUDACT_AGENT_WORKER_URL", "http://envagent:8089")
        monkeypatch.setenv("AUDACT_ORG_MANAGEMENT_URL", "http://envorg:8092")
        c = AudactClient()
        assert c._audio_validator_url == "http://envaudio:8086"
        assert c._aggregator_url == "http://envagg:8087"
        assert c._agent_worker_url == "http://envagent:8089"
        assert c._org_management_url == "http://envorg:8092"

    def test_kwarg_takes_precedence_over_env(self, monkeypatch):
        monkeypatch.setenv("AUDACT_ORG_MANAGEMENT_URL", "http://envorg:8092")
        c = AudactClient(org_management_url="http://explicit:8092")
        assert c._org_management_url == "http://explicit:8092"

    def test_trailing_slash_stripped(self):
        c = AudactClient(agent_worker_url="http://agent:8089/")
        assert c._agent_worker_url == "http://agent:8089"


# ─────────────────────────────────────────────────────────────────────────────
# OrgBearer / PlatformBearer token storage
# ─────────────────────────────────────────────────────────────────────────────

class TestOrgAndPlatformTokenStorage:
    def test_unset_by_default(self):
        c = AudactClient(api_key="aud_live_x")
        assert c.org_token is None
        assert c.platform_token is None

    def test_org_token_from_kwarg(self):
        c = AudactClient(org_token="org_jwt_abc")
        assert c.org_token == "org_jwt_abc"

    def test_platform_token_from_kwarg(self):
        c = AudactClient(platform_token="platform_ed25519_abc")
        assert c.platform_token == "platform_ed25519_abc"

    def test_org_token_from_env(self, monkeypatch):
        monkeypatch.setenv("AUDACT_ORG_TOKEN", "org_jwt_env")
        c = AudactClient()
        assert c.org_token == "org_jwt_env"

    def test_platform_token_from_env(self, monkeypatch):
        monkeypatch.setenv("AUDACT_PLATFORM_TOKEN", "platform_env")
        c = AudactClient()
        assert c.platform_token == "platform_env"

    def test_kwarg_takes_precedence_over_env(self, monkeypatch):
        monkeypatch.setenv("AUDACT_ORG_TOKEN", "org_jwt_env")
        c = AudactClient(org_token="org_jwt_explicit")
        assert c.org_token == "org_jwt_explicit"

    def test_set_org_token_updates_in_memory_state(self):
        c = AudactClient()
        assert c.org_token is None
        c.set_org_token("org_jwt_after_login")
        assert c.org_token == "org_jwt_after_login"
        c.set_org_token(None)
        assert c.org_token is None

    def test_set_platform_token_updates_in_memory_state(self):
        c = AudactClient()
        c.set_platform_token("platform_after_construction")
        assert c.platform_token == "platform_after_construction"
        c.set_platform_token(None)
        assert c.platform_token is None


# ─────────────────────────────────────────────────────────────────────────────
# _auth_headers / _request auth_token selection
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthTokenSelection:
    def test_auth_headers_default_uses_api_key(self):
        c = AudactClient(api_key="aud_live_key")
        assert c._auth_headers() == {"Authorization": "Bearer aud_live_key"}

    def test_auth_headers_explicit_token_overrides_api_key(self):
        c = AudactClient(api_key="aud_live_key")
        assert c._auth_headers(auth_token="org_jwt_abc") == {
            "Authorization": "Bearer org_jwt_abc"
        }

    def test_auth_headers_no_token_no_api_key(self):
        c = AudactClient(api_key="")
        assert c._auth_headers() == {}

    @pytest.mark.asyncio
    @respx.mock
    async def test_request_with_org_token_sends_org_bearer_not_api_key(self):
        route = respx.get("http://localhost:8092/v1/org/profile").mock(
            return_value=_json_response({"ok": True})
        )
        async with AudactClient(api_key="aud_live_key", org_token="org_jwt_abc") as c:
            await c._request(
                "GET",
                f"{c._org_management_url}/v1/org/profile",
                auth_token=c.org_token,
            )
        assert route.called
        sent = route.calls.last.request
        assert sent.headers["Authorization"] == "Bearer org_jwt_abc"

    @pytest.mark.asyncio
    @respx.mock
    async def test_request_without_auth_token_falls_back_to_api_key(self):
        route = respx.get("http://localhost:8085/v1/tenants/x").mock(
            return_value=_json_response({"ok": True})
        )
        async with AudactClient(api_key="aud_live_key", org_token="org_jwt_abc") as c:
            # No auth_token override supplied: must use the tenant api_key,
            # not the org token that happens to be configured.
            await c._request("GET", f"{c._tenant_management_url}/v1/tenants/x")
        sent = route.calls.last.request
        assert sent.headers["Authorization"] == "Bearer aud_live_key"

    @pytest.mark.asyncio
    @respx.mock
    async def test_request_with_platform_token_sends_platform_bearer(self):
        route = respx.get("http://localhost:8092/v1/platform/organizations").mock(
            return_value=_json_response({"ok": True})
        )
        async with AudactClient(
            api_key="aud_live_key", platform_token="platform_ed25519_abc"
        ) as c:
            await c._request(
                "GET",
                f"{c._org_management_url}/v1/platform/organizations",
                auth_token=c.platform_token,
            )
        sent = route.calls.last.request
        assert sent.headers["Authorization"] == "Bearer platform_ed25519_abc"


# ─────────────────────────────────────────────────────────────────────────────
# Uniform Idempotency-Key
# ─────────────────────────────────────────────────────────────────────────────

class TestUniformIdempotencyKey:
    @pytest.mark.asyncio
    @respx.mock
    async def test_request_sends_idempotency_key_when_supplied(self):
        route = respx.post("http://localhost:8085/v1/tenants").mock(
            return_value=_json_response({"ok": True})
        )
        async with AudactClient(api_key="k") as c:
            await c._request(
                "POST",
                f"{c._tenant_management_url}/v1/tenants",
                json={"name": "x"},
                idempotency_key="idem-123",
            )
        sent = route.calls.last.request
        assert sent.headers["Idempotency-Key"] == "idem-123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_request_omits_idempotency_key_when_not_supplied(self):
        route = respx.post("http://localhost:8085/v1/tenants").mock(
            return_value=_json_response({"ok": True})
        )
        async with AudactClient(api_key="k") as c:
            await c._request(
                "POST",
                f"{c._tenant_management_url}/v1/tenants",
                json={"name": "x"},
            )
        sent = route.calls.last.request
        assert "Idempotency-Key" not in sent.headers

    @pytest.mark.asyncio
    @respx.mock
    async def test_existing_post_event_still_threads_idempotency_key_uniformly(self):
        """
        post_event() accepted ``idempotency_key`` ad hoc before this task;
        verify it now flows through the single ``_request(idempotency_key=)``
        mechanism instead of building its own header dict.
        """
        route = respx.post("http://localhost:8083/v1/events").mock(
            return_value=_json_response(
                {
                    "event_id": str(uuid4()),
                    "call_id": str(uuid4()),
                    "tenant_id": str(uuid4()),
                    "sequence": 1,
                    "hash": "a" * 64,
                    "previous_hash": "0" * 64,
                    "timestamp": "2026-09-18T00:00:00+00:00",
                }
            )
        )
        async with AudactClient(api_key="k") as c:
            await c.post_event(
                call_id=uuid4(),
                tenant_id=uuid4(),
                event_type="CALL_START",
                idempotency_key="idem-abc",
            )
        sent = route.calls.last.request
        assert sent.headers["Idempotency-Key"] == "idem-abc"


# ─────────────────────────────────────────────────────────────────────────────
# Pagination — Page model (manual cursor, no auto-iterator)
# ─────────────────────────────────────────────────────────────────────────────

class TestPageModel:
    def test_defaults(self):
        page: Page[int] = Page(items=[1, 2, 3])
        assert page.items == [1, 2, 3]
        assert page.has_more is False
        assert page.next_cursor is None

    def test_full_page_from_dict(self):
        page = Page[dict].model_validate(
            {"items": [{"a": 1}], "has_more": True, "next_cursor": "cursor-2"}
        )
        assert page.items == [{"a": 1}]
        assert page.has_more is True
        assert page.next_cursor == "cursor-2"

    def test_empty_page_no_more(self):
        page: Page[str] = Page(items=[], has_more=False, next_cursor=None)
        assert page.items == []
        assert page.has_more is False
        assert page.next_cursor is None

    def test_no_auto_iterator(self):
        # Manual-cursor convention: Page has no __aiter__
        # page-walking helper — callers pass next_cursor back explicitly as
        # the `cursor` param on the next call, matching the shipped TS SDK.
        page: Page[str] = Page(items=[], has_more=True, next_cursor="c1")
        assert not hasattr(page, "__aiter__")
