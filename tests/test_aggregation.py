"""
Tests for the ``client.aggregation`` sub-client: the Merkle
aggregation surface — per-tenant proof list/get, the public meta-chain,
public inclusion verification, and the owner-only manual aggregation
trigger — verified against the documented Audact API's ``aggregation`` tag
(Aggregator service, port 8087).

``get_metachain`` and ``verify_inclusion`` are public endpoints per the
spec (no authentication required server-side); ``list_proofs``/``get_proof``
are tenant-scoped (``BearerAuth``); ``trigger_aggregation`` requires the
owner role.

Uses ``respx`` to mock the aggregator transport (``http://localhost:8087``)
so no real network calls are made.
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from audact import AudactClient
from audact.client import AggregationClient
from audact.exceptions import (
    AudactAPIError,
    AudactAuthError,
    AudactForbiddenError,
    AudactNotFoundError,
)
from audact.models import (
    AdminAggregateRequest,
    AdminAggregateResponse,
    MetaChainEntry,
    Page,
    ProofResponse,
    ProofSummary,
    VerifyInclusionRequest,
    VerifyInclusionResponse,
)

BASE = "http://localhost:8087"


def _json_response(data: dict, status: int = 200) -> Response:
    return Response(status, json=data)


def _error_response(status: int, code: str, message: str, **extra: object) -> Response:
    """The server's real nested error envelope."""
    body = {"code": code, "message": message, **extra}
    return Response(status, json={"error": body})


@pytest.fixture()
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_test123")


def _proof_summary_payload(**overrides: object) -> dict:
    payload = {
        "window_id": "2026-09-18T00:00:00Z",
        "window_start": "2026-09-18T00:00:00Z",
        "window_end": "2026-09-18T01:00:00Z",
        "aggregation_id": "agg-1",
        "batch_number": 42,
        "merkle_root": "a" * 64,
        "tenant_aggregate_hash": "b" * 64,
        "status": "complete",
        "timestamp_time": "2026-09-18T01:00:05Z",
        "tsa_url": "https://tsa.example.com",
        "created_at": "2026-09-18T01:00:05Z",
    }
    payload.update(overrides)
    return payload


def _branch_proof_payload(**overrides: object) -> dict:
    payload = {
        "root": "a" * 64,
        "leaf_hash": "b" * 64,
        "leaf_index": 3,
        "leaf_count": 16,
        "pad_count": 5,
        "tree_depth": 4,
        "steps": [{"hash": "c" * 64, "position": "left"}],
    }
    payload.update(overrides)
    return payload


def _proof_response_payload(**overrides: object) -> dict:
    payload = {
        "window_id": "2026-09-18T00:00:00Z",
        "aggregation_id": "agg-1",
        "batch_number": 42,
        "merkle_root": "a" * 64,
        "tenant_aggregate_hash": "b" * 64,
        "branch_proof": _branch_proof_payload(),
        "timestamp_token": "base64token==",
        "timestamp_time": "2026-09-18T01:00:05Z",
        "tsa_url": "https://tsa.example.com",
    }
    payload.update(overrides)
    return payload


def _metachain_entry_payload(**overrides: object) -> dict:
    payload = {
        "meta_id": "meta-1",
        "sequence": 7,
        "aggregation_id": "agg-1",
        "merkle_root": "a" * 64,
        "previous_hash": "d" * 64,
        "chain_hash": "e" * 64,
    }
    payload.update(overrides)
    return payload


def test_aggregation_is_aggregation_client(client: AudactClient) -> None:
    assert isinstance(client.aggregation, AggregationClient)


# ─────────────────────────────────────────────────────────────────────────────
# list_proofs — GET /v1/proofs
# ─────────────────────────────────────────────────────────────────────────────

class TestListProofs:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient) -> None:
        route = respx.get(f"{BASE}/v1/proofs").mock(
            return_value=_json_response(
                {
                    "proofs": [_proof_summary_payload()],
                    "count": 1,
                    "has_more": False,
                    "next_cursor": None,
                }
            )
        )

        result = await client.aggregation.list_proofs()

        assert route.called
        request = route.calls.last.request
        assert request.method == "GET"
        assert request.headers["Authorization"] == "Bearer aud_live_test123"
        assert dict(request.url.params) == {}
        assert isinstance(result, Page)
        assert len(result.items) == 1
        assert isinstance(result.items[0], ProofSummary)
        assert result.items[0].window_id == "2026-09-18T00:00:00Z"
        assert result.items[0].status == "complete"
        assert result.has_more is False
        assert result.next_cursor is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_pagination_cursor_and_limit(self, client: AudactClient) -> None:
        route = respx.get(f"{BASE}/v1/proofs").mock(
            return_value=_json_response(
                {"proofs": [], "count": 0, "has_more": True, "next_cursor": "cursor-2"}
            )
        )

        result = await client.aggregation.list_proofs(cursor="cursor-1", limit=10)

        request = route.calls.last.request
        assert dict(request.url.params) == {"cursor": "cursor-1", "limit": "10"}
        assert result.has_more is True
        assert result.next_cursor == "cursor-2"

    @pytest.mark.asyncio
    @respx.mock
    async def test_unauthorized_raises(self, client: AudactClient) -> None:
        respx.get(f"{BASE}/v1/proofs").mock(
            return_value=_error_response(401, "unauthorized", "missing bearer token")
        )
        with pytest.raises(AudactAuthError):
            await client.aggregation.list_proofs()


# ─────────────────────────────────────────────────────────────────────────────
# get_proof — GET /v1/proofs/{window_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestGetProof:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient) -> None:
        window_id = "2026-09-18T00:00:00Z"
        route = respx.get(f"{BASE}/v1/proofs/{window_id}").mock(
            return_value=_json_response(_proof_response_payload())
        )

        result = await client.aggregation.get_proof(window_id)

        assert route.called
        request = route.calls.last.request
        assert request.method == "GET"
        assert request.headers["Authorization"] == "Bearer aud_live_test123"
        assert isinstance(result, ProofResponse)
        assert result.window_id == window_id
        assert result.merkle_root == "a" * 64
        assert result.branch_proof.leaf_index == 3
        assert result.branch_proof.steps[0].position == "left"

    @pytest.mark.asyncio
    @respx.mock
    async def test_url_encodes_window_id(self, client: AudactClient) -> None:
        # RFC3339 timestamps contain ":" — must be percent-encoded in the path.
        window_id = "2026-09-18T00:00:00Z"
        route = respx.get(f"{BASE}/v1/proofs/2026-09-18T00%3A00%3A00Z").mock(
            return_value=_json_response(_proof_response_payload(window_id=window_id))
        )

        await client.aggregation.get_proof(window_id)

        assert route.called

    @pytest.mark.asyncio
    @respx.mock
    async def test_not_found_raises(self, client: AudactClient) -> None:
        respx.get(f"{BASE}/v1/proofs/2026-09-18T00%3A00%3A00Z").mock(
            return_value=_error_response(
                404, "not_found", "proof not found or tenant not in window"
            )
        )
        with pytest.raises(AudactNotFoundError):
            await client.aggregation.get_proof("2026-09-18T00:00:00Z")


# ─────────────────────────────────────────────────────────────────────────────
# get_metachain — GET /v1/metachain (public)
# ─────────────────────────────────────────────────────────────────────────────

class TestGetMetachain:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient) -> None:
        route = respx.get(f"{BASE}/v1/metachain").mock(
            return_value=_json_response(
                {
                    "entries": [_metachain_entry_payload()],
                    "count": 1,
                    "has_more": False,
                    "next_cursor": None,
                }
            )
        )

        result = await client.aggregation.get_metachain()

        assert route.called
        assert isinstance(result, Page)
        assert len(result.items) == 1
        assert isinstance(result.items[0], MetaChainEntry)
        assert result.items[0].sequence == 7
        assert result.has_more is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_auth_required(self) -> None:
        """
        Positive control: a client with NO api_key configured can still
        call the public ``get_metachain`` endpoint (no Authorization
        header is required by the server).
        """
        anon_client = AudactClient(api_key="")
        route = respx.get(f"{BASE}/v1/metachain").mock(
            return_value=_json_response(
                {"entries": [], "count": 0, "has_more": False, "next_cursor": None}
            )
        )

        result = await anon_client.aggregation.get_metachain()

        assert route.called
        request = route.calls.last.request
        assert "Authorization" not in request.headers
        assert result.items == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_pagination_cursor_and_limit(self, client: AudactClient) -> None:
        route = respx.get(f"{BASE}/v1/metachain").mock(
            return_value=_json_response(
                {"entries": [], "count": 0, "has_more": True, "next_cursor": "cursor-9"}
            )
        )

        result = await client.aggregation.get_metachain(cursor="cursor-8", limit=100)

        request = route.calls.last.request
        assert dict(request.url.params) == {"cursor": "cursor-8", "limit": "100"}
        assert result.next_cursor == "cursor-9"

    @pytest.mark.asyncio
    @respx.mock
    async def test_invalid_cursor_raises(self, client: AudactClient) -> None:
        respx.get(f"{BASE}/v1/metachain").mock(
            return_value=_error_response(400, "invalid_cursor", "invalid limit or cursor")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.aggregation.get_metachain(cursor="garbage")
        assert exc_info.value.status_code == 400
        assert exc_info.value.code == "invalid_cursor"


# ─────────────────────────────────────────────────────────────────────────────
# verify_inclusion — POST /v1/verify-inclusion (public)
# ─────────────────────────────────────────────────────────────────────────────

class TestVerifyInclusion:
    @pytest.mark.asyncio
    @respx.mock
    async def test_valid_proof(self, client: AudactClient) -> None:
        route = respx.post(f"{BASE}/v1/verify-inclusion").mock(
            return_value=_json_response({"valid": True})
        )

        req = VerifyInclusionRequest(
            leaf_hash="b" * 64,
            root="a" * 64,
            steps=[{"hash": "c" * 64, "position": "left"}],
            leaf_index=3,
            leaf_count=16,
            pad_count=5,
            tree_depth=4,
        )
        result = await client.aggregation.verify_inclusion(req)

        assert route.called
        request = route.calls.last.request
        assert request.method == "POST"
        import json as _json

        sent_body = _json.loads(request.content)
        assert sent_body["leaf_hash"] == "b" * 64
        assert sent_body["root"] == "a" * 64
        assert sent_body["steps"] == [{"hash": "c" * 64, "position": "left"}]
        assert isinstance(result, VerifyInclusionResponse)
        assert result.valid is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_auth_required(self) -> None:
        anon_client = AudactClient(api_key="")
        respx.post(f"{BASE}/v1/verify-inclusion").mock(
            return_value=_json_response({"valid": False})
        )

        req = VerifyInclusionRequest(leaf_hash="b" * 64, root="a" * 64, steps=[])
        result = await anon_client.aggregation.verify_inclusion(req)

        assert result.valid is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_invalid_body_raises(self, client: AudactClient) -> None:
        respx.post(f"{BASE}/v1/verify-inclusion").mock(
            return_value=_error_response(400, "invalid_request", "missing required fields")
        )
        req = VerifyInclusionRequest(leaf_hash="", root="", steps=[])
        with pytest.raises(AudactAPIError) as exc_info:
            await client.aggregation.verify_inclusion(req)
        assert exc_info.value.status_code == 400
        assert exc_info.value.code == "invalid_request"


# ─────────────────────────────────────────────────────────────────────────────
# trigger_aggregation — POST /v1/admin/aggregate
# ─────────────────────────────────────────────────────────────────────────────

class TestTriggerAggregation:
    @pytest.mark.asyncio
    @respx.mock
    async def test_no_body(self, client: AudactClient) -> None:
        route = respx.post(f"{BASE}/v1/admin/aggregate").mock(
            return_value=_json_response(
                {
                    "aggregation_id": "agg-1",
                    "batch_number": 43,
                    "window_start": "2026-09-18T01:00:00Z",
                    "window_end": "2026-09-18T02:00:00Z",
                    "merkle_root": "f" * 64,
                    "leaf_count": 16,
                    "tenant_count": 3,
                    "ts_timestamp": "2026-09-18T02:00:05Z",
                    "tsa_name": "Example TSA",
                }
            )
        )

        result = await client.aggregation.trigger_aggregation()

        assert route.called
        request = route.calls.last.request
        assert request.method == "POST"
        assert request.headers["Authorization"] == "Bearer aud_live_test123"
        import json as _json

        assert _json.loads(request.content) == {}
        assert isinstance(result, AdminAggregateResponse)
        assert result.aggregation_id == "agg-1"
        assert result.tenant_count == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_with_window_and_idempotency_key(self, client: AudactClient) -> None:
        route = respx.post(f"{BASE}/v1/admin/aggregate").mock(
            return_value=_json_response(
                {
                    "aggregation_id": "agg-2",
                    "batch_number": 44,
                    "merkle_root": "f" * 64,
                    "leaf_count": 16,
                    "tenant_count": 1,
                }
            )
        )

        req = AdminAggregateRequest(
            window_start="2026-09-18T00:00:00Z", window_end="2026-09-18T01:00:00Z"
        )
        await client.aggregation.trigger_aggregation(req, idempotency_key="idem-key-1")

        request = route.calls.last.request
        assert request.headers["Idempotency-Key"] == "idem-key-1"
        import json as _json

        sent_body = _json.loads(request.content)
        assert sent_body == {
            "window_start": "2026-09-18T00:00:00Z",
            "window_end": "2026-09-18T01:00:00Z",
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_forbidden_raises(self, client: AudactClient) -> None:
        respx.post(f"{BASE}/v1/admin/aggregate").mock(
            return_value=_error_response(403, "forbidden", "owner role required")
        )
        with pytest.raises(AudactForbiddenError):
            await client.aggregation.trigger_aggregation()

    @pytest.mark.asyncio
    @respx.mock
    async def test_invalid_window_raises(self, client: AudactClient) -> None:
        respx.post(f"{BASE}/v1/admin/aggregate").mock(
            return_value=_error_response(400, "invalid_window", "invalid window parameters")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.aggregation.trigger_aggregation()
        assert exc_info.value.status_code == 400
        assert exc_info.value.code == "invalid_window"
