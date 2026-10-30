"""
Tests for the error-envelope fix + rate-limit headers + opt-in retries.

The server writes every error as a NESTED envelope
(the API's error envelope)::

    {"error": {"code", "message", "hint", "details", "request_id"}}

The pre-fix ``_raise_for_status()`` read ``code``/``message``/``details`` at
the TOP LEVEL of the body — which is *always* absent on a real response,
since the server never puts those keys outside ``"error"``. Every test
fixture in this module uses ONLY the nested shape (no duplicated top-level
keys), so any assertion here that reads back the real ``code``/``message``/
``hint``/``request_id`` is a **positive control**: it necessarily FAILS
against the old flat-parsing implementation (which would see no top-level
``code``/``message`` and fall back to ``"UNKNOWN"``/the raw response text)
and PASSES only once ``body["error"]`` is parsed.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from audact import AudactClient
from audact.exceptions import (
    AudactAPIError,
    AudactNotFoundError,
    AudactRateLimitError,
)
from audact.models import RateLimitInfo


async def _no_op_sleep(*_args: object, **_kwargs: object) -> None:
    """Replaces ``asyncio.sleep`` in retry tests so they run instantly."""
    return None


def _nested_error_response(
    status: int,
    code: str,
    message: str,
    *,
    hint: str | None = None,
    details: dict | None = None,
    request_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """The real server wire shape — nested under ``"error"``, nothing else."""
    error: dict = {"code": code, "message": message}
    if hint is not None:
        error["hint"] = hint
    if details is not None:
        error["details"] = details
    if request_id is not None:
        error["request_id"] = request_id
    return httpx.Response(status, json={"error": error}, headers=headers or {})


# ─────────────────────────────────────────────────────────────────────────────
# Positive control — nested envelope parse
# ─────────────────────────────────────────────────────────────────────────────

class TestNestedErrorEnvelopePositiveControl:
    @pytest.mark.asyncio
    @respx.mock
    async def test_code_and_message_read_from_nested_error_object(self):
        """
        POSITIVE CONTROL: the fixture carries `code`/`message` ONLY
        under `error`. The old parser (`body.get("code")` at the top level)
        would see nothing there and fall back to `code="UNKNOWN"` and
        `message=<raw response text>` — so this assertion FAILS against the
        old flat-parse and PASSES only with the `body["error"]` fix.
        """
        respx.get("http://localhost:8085/v1/tenants/x").mock(
            return_value=_nested_error_response(
                404, "NOT_FOUND", "tenant x not found"
            )
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactNotFoundError) as exc_info:
                await c._request("GET", f"{c._tenant_management_url}/v1/tenants/x")

        assert exc_info.value.code == "NOT_FOUND"
        assert exc_info.value.message == "tenant x not found"
        # Would be "UNKNOWN" under the old top-level-only parser.
        assert exc_info.value.code != "UNKNOWN"

    @pytest.mark.asyncio
    @respx.mock
    async def test_hint_and_request_id_populated_from_nested_body(self):
        """
        POSITIVE CONTROL: `hint`/`request_id` live ONLY under `error` on the
        wire (both are `omitempty` at the top level, which doesn't exist).
        The old parser never read them at all — `hint`/`request_id` weren't
        even attributes on `AudactAPIError`. This fails outright pre-fix.
        """
        respx.post("http://localhost:8085/v1/tenants").mock(
            return_value=_nested_error_response(
                400,
                "INVALID_REQUEST",
                "name is required",
                hint="supply a non-empty 'name' field",
                request_id="req_abc123",
            )
        )
        async with AudactClient() as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c._request(
                    "POST",
                    f"{c._tenant_management_url}/v1/tenants",
                    json={},
                )

        assert exc_info.value.code == "INVALID_REQUEST"
        assert exc_info.value.message == "name is required"
        assert exc_info.value.hint == "supply a non-empty 'name' field"
        assert exc_info.value.request_id == "req_abc123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_details_read_from_nested_error_object(self):
        respx.post("http://localhost:8085/v1/configurations").mock(
            return_value=_nested_error_response(
                422,
                "missing_requirement",
                "one or more required requirements are unsatisfied",
                details={"missing": ["req-2", "req-3"]},
            )
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c._request(
                    "POST",
                    f"{c._tenant_management_url}/v1/configurations",
                    json={},
                )
        assert exc_info.value.details == {"missing": ["req-2", "req-3"]}

    @pytest.mark.asyncio
    @respx.mock
    async def test_request_id_falls_back_to_header_when_body_omits_it(self):
        """`request_id` is `omitempty` in the body — the SDK also reads the
        `X-Request-ID` response header (mirrors the TS SDK's base.ts)."""
        respx.get("http://localhost:8085/v1/tenants/x").mock(
            return_value=_nested_error_response(
                404,
                "NOT_FOUND",
                "tenant x not found",
                headers={"X-Request-ID": "req_from_header"},
            )
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactNotFoundError) as exc_info:
                await c._request("GET", f"{c._tenant_management_url}/v1/tenants/x")
        assert exc_info.value.request_id == "req_from_header"

    @pytest.mark.asyncio
    @respx.mock
    async def test_body_request_id_wins_over_header(self):
        respx.get("http://localhost:8085/v1/tenants/x").mock(
            return_value=_nested_error_response(
                404,
                "NOT_FOUND",
                "tenant x not found",
                request_id="req_from_body",
                headers={"X-Request-ID": "req_from_header"},
            )
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactNotFoundError) as exc_info:
                await c._request("GET", f"{c._tenant_management_url}/v1/tenants/x")
        assert exc_info.value.request_id == "req_from_body"

    @pytest.mark.asyncio
    @respx.mock
    async def test_flat_top_level_body_still_parses_for_forward_compat(self):
        """A body with no `error` key at all falls back to top-level fields."""
        respx.get("http://localhost:8085/v1/tenants/x").mock(
            return_value=httpx.Response(
                404, json={"code": "NOT_FOUND", "message": "flat fallback"}
            )
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactNotFoundError) as exc_info:
                await c._request("GET", f"{c._tenant_management_url}/v1/tenants/x")
        assert exc_info.value.code == "NOT_FOUND"
        assert exc_info.value.message == "flat fallback"

    @pytest.mark.asyncio
    @respx.mock
    async def test_non_json_body_still_falls_back_to_raw_text(self):
        respx.get("http://localhost:8085/v1/tenants/x").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c._request("GET", f"{c._tenant_management_url}/v1/tenants/x")
        assert "Service Unavailable" in exc_info.value.message
        assert exc_info.value.hint is None
        assert exc_info.value.request_id is None


# ─────────────────────────────────────────────────────────────────────────────
# Rate limits — Retry-After + X-RateLimit-*
# ─────────────────────────────────────────────────────────────────────────────

class TestRateLimitHeaders:
    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_after_populates_retry_after_attribute(self):
        respx.post("http://localhost:8082/v1/validate").mock(
            return_value=_nested_error_response(
                429,
                "RATE_LIMIT_EXCEEDED",
                "rate limit of 1000 req/min exceeded",
                headers={"Retry-After": "30"},
            )
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactRateLimitError) as exc_info:
                await c._request("POST", f"{c._validator_url}/v1/validate", json={})
        assert exc_info.value.retry_after == 30

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_after_absent_leaves_retry_after_none(self):
        respx.post("http://localhost:8082/v1/validate").mock(
            return_value=_nested_error_response(
                429, "RATE_LIMIT_EXCEEDED", "too many requests"
            )
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactRateLimitError) as exc_info:
                await c._request("POST", f"{c._validator_url}/v1/validate", json={})
        assert exc_info.value.retry_after is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_x_rate_limit_headers_populate_rate_limit_on_429(self):
        respx.post("http://localhost:8082/v1/validate").mock(
            return_value=_nested_error_response(
                429,
                "RATE_LIMIT_EXCEEDED",
                "too many requests",
                headers={
                    "X-RateLimit-Limit": "1000",
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": "1234567890",
                },
            )
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactRateLimitError) as exc_info:
                await c._request("POST", f"{c._validator_url}/v1/validate", json={})
        rl = exc_info.value.rate_limit
        assert isinstance(rl, RateLimitInfo)
        assert rl.limit == 1000
        assert rl.remaining == 0
        assert rl.reset == 1234567890

    @pytest.mark.asyncio
    @respx.mock
    async def test_x_rate_limit_headers_recorded_on_successful_response(self):
        respx.get("http://localhost:8085/v1/tenants/x").mock(
            return_value=httpx.Response(
                200,
                json={"ok": True},
                headers={
                    "X-RateLimit-Limit": "500",
                    "X-RateLimit-Remaining": "499",
                    "X-RateLimit-Reset": "1111111111",
                },
            )
        )
        async with AudactClient(api_key="key") as c:
            assert c.last_rate_limit is None
            await c._request("GET", f"{c._tenant_management_url}/v1/tenants/x")
            assert c.last_rate_limit is not None
            assert c.last_rate_limit.limit == 500
            assert c.last_rate_limit.remaining == 499
            assert c.last_rate_limit.reset == 1111111111

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_rate_limit_headers_leaves_rate_limit_none(self):
        respx.post("http://localhost:8082/v1/validate").mock(
            return_value=_nested_error_response(
                429, "RATE_LIMIT_EXCEEDED", "too many requests"
            )
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactRateLimitError) as exc_info:
                await c._request("POST", f"{c._validator_url}/v1/validate", json={})
        assert exc_info.value.rate_limit is None


# ─────────────────────────────────────────────────────────────────────────────
# Opt-in retry-with-backoff
# ─────────────────────────────────────────────────────────────────────────────

class TestOptInRetries:
    @pytest.mark.asyncio
    @respx.mock
    async def test_retries_off_by_default(self):
        route = respx.get("http://localhost:8085/v1/tenants/x").mock(
            return_value=httpx.Response(
                500, json={"error": {"code": "INTERNAL_ERROR", "message": "boom"}}
            )
        )
        async with AudactClient(api_key="key") as c:
            assert c._max_retries == 0
            with pytest.raises(AudactAPIError):
                await c._request("GET", f"{c._tenant_management_url}/v1/tenants/x")
        assert route.call_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_retried_on_500_then_succeeds(self, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", _no_op_sleep)
        route = respx.get("http://localhost:8085/v1/tenants/x").mock(
            side_effect=[
                httpx.Response(500, json={"error": {"code": "INTERNAL_ERROR", "message": "boom"}}),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        async with AudactClient(api_key="key", max_retries=2) as c:
            response = await c._request(
                "GET", f"{c._tenant_management_url}/v1/tenants/x"
            )
        assert response.json() == {"ok": True}
        assert route.call_count == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_retried_on_429_honors_retry_after(self, monkeypatch):
        delays: list[float] = []

        async def _fake_sleep(delay: float) -> None:
            delays.append(delay)

        monkeypatch.setattr(asyncio, "sleep", _fake_sleep)
        route = respx.get("http://localhost:8085/v1/tenants/x").mock(
            side_effect=[
                _nested_error_response(
                    429, "RATE_LIMIT_EXCEEDED", "slow down", headers={"Retry-After": "7"}
                ),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        async with AudactClient(api_key="key", max_retries=1) as c:
            response = await c._request(
                "GET", f"{c._tenant_management_url}/v1/tenants/x"
            )
        assert response.json() == {"ok": True}
        assert route.call_count == 2
        assert delays == [7.0]

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_exhausted_raises_final_error(self, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", _no_op_sleep)
        route = respx.get("http://localhost:8085/v1/tenants/x").mock(
            return_value=httpx.Response(
                503, json={"error": {"code": "SERVICE_UNAVAILABLE", "message": "down"}}
            )
        )
        async with AudactClient(api_key="key", max_retries=2) as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c._request("GET", f"{c._tenant_management_url}/v1/tenants/x")
        assert exc_info.value.status_code == 503
        # 1 initial attempt + 2 retries = 3 total requests.
        assert route.call_count == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_retries_never_applied_to_non_get_methods(self, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", _no_op_sleep)
        route = respx.post("http://localhost:8085/v1/tenants").mock(
            return_value=httpx.Response(
                500, json={"error": {"code": "INTERNAL_ERROR", "message": "boom"}}
            )
        )
        async with AudactClient(api_key="key", max_retries=3) as c:
            with pytest.raises(AudactAPIError):
                await c._request(
                    "POST", f"{c._tenant_management_url}/v1/tenants", json={}
                )
        assert route.call_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_retries_never_applied_to_validator_calls(self, monkeypatch):
        """
        Even a (hypothetical) GET against the Validator base URL must never
        be retried — the 40ms hard-deadline invariant forbids it regardless
        of method/status. Real Validator calls are POST-only; this directly
        exercises the URL guard in ``_should_retry``/``_is_validator_request``.
        """
        monkeypatch.setattr(asyncio, "sleep", _no_op_sleep)
        route = respx.get("http://localhost:8082/v1/validate/health").mock(
            return_value=httpx.Response(
                500, json={"error": {"code": "INTERNAL_ERROR", "message": "boom"}}
            )
        )
        async with AudactClient(api_key="key", max_retries=3) as c:
            with pytest.raises(AudactAPIError):
                await c._request(
                    "GET", f"{c._validator_url}/v1/validate/health"
                )
        assert route.call_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_retries_not_applied_to_4xx_other_than_429(self, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", _no_op_sleep)
        route = respx.get("http://localhost:8085/v1/tenants/x").mock(
            return_value=httpx.Response(
                404, json={"error": {"code": "NOT_FOUND", "message": "nope"}}
            )
        )
        async with AudactClient(api_key="key", max_retries=3) as c:
            with pytest.raises(AudactAPIError):
                await c._request("GET", f"{c._tenant_management_url}/v1/tenants/x")
        assert route.call_count == 1

    def test_negative_max_retries_rejected(self):
        with pytest.raises(ValueError, match="max_retries"):
            AudactClient(max_retries=-1)


# ─────────────────────────────────────────────────────────────────────────────
# Error-envelope behaviour locked in (table-driven, direct on
# ``_raise_for_status`` so no transport/retry layer is involved)
# ─────────────────────────────────────────────────────────────────────────────

from audact.client import _raise_for_status  # noqa: E402
from audact.exceptions import (  # noqa: E402
    AudactAuthError,
    AudactForbiddenError,
)


def _raised(response: httpx.Response) -> AudactAPIError:
    with pytest.raises(AudactAPIError) as excinfo:
        _raise_for_status(response)
    return excinfo.value


def test_nested_envelope_sets_all_attributes():
    exc = _raised(
        httpx.Response(
            400,
            json={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "bad field",
                    "hint": "check agent_id",
                    "details": {"field": "agent_id"},
                    "request_id": "req_abc",
                }
            },
        )
    )
    assert exc.status_code == 400
    assert exc.code == "INVALID_REQUEST"
    assert exc.message == "bad field"
    assert exc.hint == "check agent_id"
    assert exc.details == {"field": "agent_id"}
    assert exc.request_id == "req_abc"


def test_flat_legacy_body_still_parsed():
    exc = _raised(
        httpx.Response(400, json={"code": "LEGACY", "message": "old shape"})
    )
    assert exc.code == "LEGACY"
    assert exc.message == "old shape"


def test_non_json_body_gives_generic_message_with_status():
    exc = _raised(httpx.Response(502, text="<html>Bad Gateway</html>"))
    assert exc.status_code == 502
    assert exc.code == "UNKNOWN"
    assert "Bad Gateway" in exc.message

    empty = _raised(httpx.Response(500))
    assert empty.status_code == 500
    assert "500" in empty.message


def test_request_id_header_fallback():
    exc = _raised(
        httpx.Response(
            500,
            json={"error": {"code": "INTERNAL", "message": "boom"}},
            headers={"X-Request-ID": "req_hdr"},
        )
    )
    assert exc.request_id == "req_hdr"

    no_json = _raised(httpx.Response(500, text="oops", headers={"X-Request-ID": "req_h2"}))
    assert no_json.request_id == "req_h2"


def test_body_request_id_wins_over_header():
    exc = _raised(
        httpx.Response(
            500,
            json={"error": {"code": "INTERNAL", "message": "boom", "request_id": "req_body"}},
            headers={"X-Request-ID": "req_hdr"},
        )
    )
    assert exc.request_id == "req_body"


def test_no_request_id_anywhere_is_none():
    exc = _raised(httpx.Response(500, json={"error": {"code": "X", "message": "y"}}))
    assert exc.request_id is None


def test_rate_limit_retry_after_seconds():
    exc = _raised(
        httpx.Response(
            429,
            json={"error": {"code": "RATE_LIMITED", "message": "slow down"}},
            headers={"Retry-After": "7"},
        )
    )
    assert isinstance(exc, AudactRateLimitError)
    assert exc.retry_after == 7
    assert exc.code == "RATE_LIMITED"


def test_rate_limit_without_retry_after_header():
    exc = _raised(httpx.Response(429, json={"error": {"code": "R", "message": "m"}}))
    assert isinstance(exc, AudactRateLimitError)
    assert exc.retry_after is None


@pytest.mark.parametrize(
    ("status", "exc_type"),
    [
        (401, AudactAuthError),
        (403, AudactForbiddenError),
        (404, AudactNotFoundError),
        (409, AudactAPIError),
    ],
)
def test_status_maps_to_typed_exception(status, exc_type):
    exc = _raised(httpx.Response(status, json={"error": {"code": "C", "message": "m"}}))
    assert type(exc) is exc_type
    assert exc.status_code == status
