"""
Tests for the ``client.webhooks`` sub-client: CRUD, test, deliveries
(+ resend), event-types, event-schemas, secret status/rotate, and the
``verify_webhook_signature`` helper.

Uses ``respx`` to mock the tenant-management transport
(``http://localhost:8085``, the settled host for the webhooks surface) so no real
network calls are made.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from uuid import uuid4

import httpx
import pytest
import respx

from audact import AudactClient
from audact.client import WebhooksClient, verify_webhook_signature
from audact.exceptions import AudactAPIError, AudactNotFoundError
from audact.models import (
    CreateWebhookRequest,
    CreateWebhookResponse,
    ListWebhookDeliveriesResponse,
    ListWebhookEventTypesResponse,
    Page,
    ResendWebhookDeliveryResponse,
    RotateWebhookSecretResponse,
    UpdateWebhookRequest,
    WebhookDeliveryRecord,
    WebhookEndpoint,
    WebhookEventSchema,
    WebhookSecretStatus,
    WebhookTestPingResponse,
)

BASE = "http://localhost:8085"

ENDPOINT_ID = uuid4()
AGENT_ID = uuid4()
TENANT_ID = uuid4()


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _error_response(status: int, code: str, message: str) -> httpx.Response:
    """The server's real nested error envelope."""
    return httpx.Response(status, json={"error": {"code": code, "message": message}})


@pytest.fixture()
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_test123")


def _endpoint_payload(**overrides) -> dict:
    payload = {
        "id": str(ENDPOINT_ID),
        "tenant_id": str(TENANT_ID),
        "url": "https://example.com/webhooks",
        "scope": "account",
        "events": ["call_ended"],
        "is_active": True,
        "agent_id": None,
    }
    payload.update(overrides)
    return payload


def test_webhooks_is_webhooks_client(client: AudactClient) -> None:
    assert isinstance(client.webhooks, WebhooksClient)


# ─────────────────────────────────────────────────────────────────────────────
# list_webhooks — GET /v1/webhooks (paginated, cursor convention)
# ─────────────────────────────────────────────────────────────────────────────

class TestListWebhooks:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        respx.get(f"{BASE}/v1/webhooks").mock(
            return_value=_json_response(
                {"items": [_endpoint_payload()], "has_more": False, "next_cursor": None}
            )
        )
        async with client as c:
            page = await c.webhooks.list_webhooks()
        assert isinstance(page, Page)
        assert page.has_more is False
        assert page.next_cursor is None
        assert len(page.items) == 1
        assert isinstance(page.items[0], WebhookEndpoint)
        assert page.items[0].id == str(ENDPOINT_ID)
        assert page.items[0].url == "https://example.com/webhooks"
        assert page.items[0].events == ["call_ended"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_cursor_and_limit_and_auth(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {"items": [], "has_more": True, "next_cursor": "cursor-2"}
            )

        respx.get(f"{BASE}/v1/webhooks").mock(side_effect=_handler)
        async with client as c:
            page = await c.webhooks.list_webhooks(cursor="cursor-1", limit=10)
        assert page.has_more is True
        assert page.next_cursor == "cursor-2"
        request = captured[0]
        assert dict(request.url.params) == {"cursor": "cursor-1", "limit": "10"}
        assert request.headers["authorization"] == "Bearer aud_live_test123"


# ─────────────────────────────────────────────────────────────────────────────
# create_webhook — POST /v1/webhooks
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateWebhook:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic_with_signing_secret(self, client: AudactClient):
        respx.post(f"{BASE}/v1/webhooks").mock(
            return_value=_json_response(
                {**_endpoint_payload(), "signing_secret": "f" * 64},
                status=201,
            )
        )
        async with client as c:
            result = await c.webhooks.create_webhook(
                CreateWebhookRequest(
                    scope="account", url="https://example.com/webhooks", events=["call_ended"]
                )
            )
        assert isinstance(result, CreateWebhookResponse)
        assert result.id == str(ENDPOINT_ID)
        assert result.signing_secret == "f" * 64

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_body_auth_and_idempotency_key(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_endpoint_payload(), status=201)

        respx.post(f"{BASE}/v1/webhooks").mock(side_effect=_handler)
        async with client as c:
            await c.webhooks.create_webhook(
                CreateWebhookRequest(
                    scope="agent",
                    url="https://example.com/webhooks",
                    events=["call_ended", "call_started"],
                    agent_id=str(AGENT_ID),
                ),
                idempotency_key="idem-webhook-1",
            )
        request = captured[0]
        assert request.headers["authorization"] == "Bearer aud_live_test123"
        assert request.headers["idempotency-key"] == "idem-webhook-1"
        body = json.loads(request.content)
        assert body == {
            "scope": "agent",
            "url": "https://example.com/webhooks",
            "events": ["call_ended", "call_started"],
            "agent_id": str(AGENT_ID),
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_error_maps_nested_envelope(self, client: AudactClient):
        respx.post(f"{BASE}/v1/webhooks").mock(
            return_value=_error_response(400, "INVALID_REQUEST", "url must use https")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.webhooks.create_webhook(
                    CreateWebhookRequest(
                        scope="account", url="http://insecure", events=["call_ended"]
                    )
                )
        assert exc_info.value.code == "INVALID_REQUEST"
        assert exc_info.value.message == "url must use https"


# ─────────────────────────────────────────────────────────────────────────────
# get_webhook / update_webhook / delete_webhook — /v1/webhooks/{id}
# ─────────────────────────────────────────────────────────────────────────────

class TestGetWebhook:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        respx.get(f"{BASE}/v1/webhooks/{ENDPOINT_ID}").mock(
            return_value=_json_response(_endpoint_payload())
        )
        async with client as c:
            result = await c.webhooks.get_webhook(ENDPOINT_ID)
        assert isinstance(result, WebhookEndpoint)
        assert result.id == str(ENDPOINT_ID)

    @pytest.mark.asyncio
    @respx.mock
    async def test_not_found(self, client: AudactClient):
        respx.get(f"{BASE}/v1/webhooks/{ENDPOINT_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "webhook endpoint not found")
        )
        with pytest.raises(AudactNotFoundError):
            async with client as c:
                await c.webhooks.get_webhook(ENDPOINT_ID)


class TestUpdateWebhook:
    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_partial_body(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_endpoint_payload(is_active=False))

        respx.put(f"{BASE}/v1/webhooks/{ENDPOINT_ID}").mock(side_effect=_handler)
        async with client as c:
            result = await c.webhooks.update_webhook(
                ENDPOINT_ID, UpdateWebhookRequest(is_active=False)
            )
        assert isinstance(result, WebhookEndpoint)
        assert result.is_active is False
        body = json.loads(captured[0].content)
        assert body == {"is_active": False}


class TestDeleteWebhook:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.delete(f"{BASE}/v1/webhooks/{ENDPOINT_ID}").mock(
            return_value=httpx.Response(204)
        )
        async with client as c:
            result = await c.webhooks.delete_webhook(ENDPOINT_ID)
        assert result is None
        assert route.called


# ─────────────────────────────────────────────────────────────────────────────
# test_webhook — POST /v1/webhooks/{id}/test
# ─────────────────────────────────────────────────────────────────────────────

class TestTestWebhook:
    @pytest.mark.asyncio
    @respx.mock
    async def test_success(self, client: AudactClient):
        respx.post(f"{BASE}/v1/webhooks/{ENDPOINT_ID}/test").mock(
            return_value=_json_response(
                {"success": True, "status_code": 200, "latency_ms": 142.5}
            )
        )
        async with client as c:
            result = await c.webhooks.test_webhook(ENDPOINT_ID)
        assert isinstance(result, WebhookTestPingResponse)
        assert result.success is True
        assert result.status_code == 200
        assert result.latency_ms == 142.5
        assert result.error is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_failure(self, client: AudactClient):
        respx.post(f"{BASE}/v1/webhooks/{ENDPOINT_ID}/test").mock(
            return_value=_json_response({"success": False, "error": "connection refused"})
        )
        async with client as c:
            result = await c.webhooks.test_webhook(ENDPOINT_ID)
        assert result.success is False
        assert result.error == "connection refused"


# ─────────────────────────────────────────────────────────────────────────────
# list_webhook_deliveries — GET /v1/webhooks/{id}/deliveries (offset paginated)
# ─────────────────────────────────────────────────────────────────────────────

class TestListWebhookDeliveries:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        delivery = {
            "id": "dlv_" + str(uuid4()),
            "endpoint_id": str(ENDPOINT_ID),
            "event_id": str(uuid4()),
            "event_type": "call_ended",
            "status": "success",
            "attempt_count": 1,
            "http_status": 200,
            "latency_ms": 88.1,
            "last_error": None,
            "created_at": "2026-09-18T00:00:00Z",
            "completed_at": "2026-09-18T00:00:01Z",
        }
        respx.get(f"{BASE}/v1/webhooks/{ENDPOINT_ID}/deliveries").mock(
            return_value=_json_response({"deliveries": [delivery], "total": 1})
        )
        async with client as c:
            result = await c.webhooks.list_webhook_deliveries(ENDPOINT_ID)
        assert isinstance(result, ListWebhookDeliveriesResponse)
        assert result.total == 1
        assert len(result.deliveries) == 1
        assert isinstance(result.deliveries[0], WebhookDeliveryRecord)
        assert result.deliveries[0].status == "success"

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_limit_and_offset(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response({"deliveries": [], "total": 0})

        respx.get(f"{BASE}/v1/webhooks/{ENDPOINT_ID}/deliveries").mock(side_effect=_handler)
        async with client as c:
            await c.webhooks.list_webhook_deliveries(ENDPOINT_ID, limit=25, offset=50)
        assert dict(captured[0].url.params) == {"limit": "25", "offset": "50"}


# ─────────────────────────────────────────────────────────────────────────────
# resend_webhook_delivery — POST /v1/webhooks/deliveries/{id}/resend
# ─────────────────────────────────────────────────────────────────────────────

class TestResendWebhookDelivery:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        delivery_id = "dlv_" + str(uuid4())
        respx.post(f"{BASE}/v1/webhooks/deliveries/{delivery_id}/resend").mock(
            return_value=_json_response({"delivery_id": delivery_id, "requeued": True})
        )
        async with client as c:
            result = await c.webhooks.resend_webhook_delivery(delivery_id)
        assert isinstance(result, ResendWebhookDeliveryResponse)
        assert result.delivery_id == delivery_id
        assert result.requeued is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_url_encodes_delivery_id(self, client: AudactClient):
        # A delivery id containing characters that must be percent-encoded in a
        # path segment (never string-concat unencoded input into a URL path).
        raw_id = "dlv_abc/def"
        respx.post(f"{BASE}/v1/webhooks/deliveries/dlv_abc%2Fdef/resend").mock(
            return_value=_json_response({"delivery_id": raw_id, "requeued": True})
        )
        async with client as c:
            result = await c.webhooks.resend_webhook_delivery(raw_id)
        assert result.requeued is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_conflict_maps_to_api_error(self, client: AudactClient):
        delivery_id = "dlv_" + str(uuid4())
        respx.post(f"{BASE}/v1/webhooks/deliveries/{delivery_id}/resend").mock(
            return_value=_error_response(409, "CONFLICT", "delivery is not dead-lettered")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            async with client as c:
                await c.webhooks.resend_webhook_delivery(delivery_id)
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "CONFLICT"


# ─────────────────────────────────────────────────────────────────────────────
# list_webhook_event_types — GET /v1/webhooks/event-types
# ─────────────────────────────────────────────────────────────────────────────

class TestListWebhookEventTypes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        respx.get(f"{BASE}/v1/webhooks/event-types").mock(
            return_value=_json_response(
                {
                    "event_types": [
                        {
                            "name": "call_ended",
                            "description": "Fired when a call ends.",
                            "category": "voice",
                            "schema_url": "/v1/webhooks/event-schemas?type=call_ended",
                        }
                    ]
                }
            )
        )
        async with client as c:
            result = await c.webhooks.list_webhook_event_types()
        assert isinstance(result, ListWebhookEventTypesResponse)
        assert len(result.event_types) == 1
        assert result.event_types[0].name == "call_ended"
        assert result.event_types[0].category == "voice"


# ─────────────────────────────────────────────────────────────────────────────
# get_webhook_event_schema — GET /v1/webhooks/event-schemas?type=...
# ─────────────────────────────────────────────────────────────────────────────

class TestGetWebhookEventSchema:
    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_type_query_param(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {
                    "event_type": "call_ended",
                    "category": "voice",
                    "description": "Fired when a call ends.",
                    "schema_version": "1.0.0",
                    "example_payload": {"id": "dlv_x", "event_type": "call_ended", "data": {}},
                    "pii_handling_note": "Phone numbers are SHA-256 hashed.",
                }
            )

        respx.get(f"{BASE}/v1/webhooks/event-schemas").mock(side_effect=_handler)
        async with client as c:
            result = await c.webhooks.get_webhook_event_schema("call_ended")
        assert isinstance(result, WebhookEventSchema)
        assert result.event_type == "call_ended"
        assert result.example_payload == {"id": "dlv_x", "event_type": "call_ended", "data": {}}
        assert result.pii_handling_note == "Phone numbers are SHA-256 hashed."
        assert dict(captured[0].url.params) == {"type": "call_ended"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_unknown_type_maps_to_not_found(self, client: AudactClient):
        respx.get(f"{BASE}/v1/webhooks/event-schemas").mock(
            return_value=_error_response(404, "NOT_FOUND", "unknown event type")
        )
        with pytest.raises(AudactNotFoundError):
            async with client as c:
                await c.webhooks.get_webhook_event_schema("not_a_real_event")


# ─────────────────────────────────────────────────────────────────────────────
# get_webhook_secret_status / rotate_webhook_secret — /v1/webhooks/secrets/*
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookSecretStatus:
    @pytest.mark.asyncio
    @respx.mock
    async def test_not_in_rotation(self, client: AudactClient):
        respx.get(f"{BASE}/v1/webhooks/secrets/status").mock(
            return_value=_json_response(
                {"in_rotation": False, "created_at": "2026-03-18T15:17:00Z"}
            )
        )
        async with client as c:
            result = await c.webhooks.get_webhook_secret_status()
        assert isinstance(result, WebhookSecretStatus)
        assert result.in_rotation is False
        assert result.grace_period_ends is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_in_rotation(self, client: AudactClient):
        respx.get(f"{BASE}/v1/webhooks/secrets/status").mock(
            return_value=_json_response(
                {
                    "in_rotation": True,
                    "created_at": "2026-03-18T15:17:00Z",
                    "grace_period_ends": "2026-06-04T09:00:00Z",
                }
            )
        )
        async with client as c:
            result = await c.webhooks.get_webhook_secret_status()
        assert result.in_rotation is True
        assert result.grace_period_ends == "2026-06-04T09:00:00Z"


class TestRotateWebhookSecret:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {
                    "rotated": True,
                    "signing_secret": "a" * 64,
                    "grace_period_ends": "2026-06-04T09:00:00Z",
                }
            )

        respx.post(f"{BASE}/v1/webhooks/secrets/rotate").mock(side_effect=_handler)
        async with client as c:
            result = await c.webhooks.rotate_webhook_secret()
        assert isinstance(result, RotateWebhookSecretResponse)
        assert result.rotated is True
        assert result.signing_secret == "a" * 64
        assert captured[0].headers["authorization"] == "Bearer aud_live_test123"


# ─────────────────────────────────────────────────────────────────────────────
# verify_webhook_signature — HMAC-SHA256 over "<ts>.<raw body>"
# (the webhook signing scheme)
# ─────────────────────────────────────────────────────────────────────────────

def _sign(secret: str, timestamp: int, body: bytes) -> str:
    message = f"{timestamp}".encode() + b"." + body
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


class TestVerifyWebhookSignature:
    def test_valid_signature_passes(self):
        secret = "f" * 64
        body = b'{"event_type":"call_ended"}'
        ts = int(time.time())
        header = _sign(secret, ts, body)
        assert verify_webhook_signature(body, header, secret) is True

    def test_wrong_secret_fails(self):
        secret = "f" * 64
        wrong_secret = "e" * 64
        body = b'{"event_type":"call_ended"}'
        ts = int(time.time())
        header = _sign(secret, ts, body)
        assert verify_webhook_signature(body, header, wrong_secret) is False

    def test_tampered_body_fails(self):
        secret = "f" * 64
        body = b'{"event_type":"call_ended"}'
        ts = int(time.time())
        header = _sign(secret, ts, body)
        tampered_body = b'{"event_type":"call_started"}'
        assert verify_webhook_signature(tampered_body, header, secret) is False

    def test_malformed_header_fails(self):
        secret = "f" * 64
        body = b'{"event_type":"call_ended"}'
        assert verify_webhook_signature(body, "not-a-valid-header", secret) is False
        assert verify_webhook_signature(body, "", secret) is False
        assert verify_webhook_signature(body, "t=123", secret) is False

    def test_rotation_grace_period_matches_either_key(self):
        # During the 72h dual-signature grace window the header carries two
        # v1= values (old key, new key); either must verify successfully.
        old_secret = "1" * 64
        new_secret = "2" * 64
        body = b'{"event_type":"call_ended"}'
        ts = int(time.time())
        old_digest = hmac.new(
            old_secret.encode("utf-8"), f"{ts}".encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        new_digest = hmac.new(
            new_secret.encode("utf-8"), f"{ts}".encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        header = f"t={ts},v1={old_digest},v1={new_digest}"
        assert verify_webhook_signature(body, header, old_secret) is True
        assert verify_webhook_signature(body, header, new_secret) is True

    def test_neither_key_matches_fails(self):
        body = b'{"event_type":"call_ended"}'
        ts = int(time.time())
        header = _sign("1" * 64, ts, body)
        assert verify_webhook_signature(body, header, "9" * 64) is False
