"""
Tests for the ``client.knowledge_bases`` sub-client: knowledge-base
CRUD, sources (JSON url/text, multipart file, re-ingest), agent links, crawl
exclusions and the retrieval test harness — tenant-management (8085).

Uses ``respx`` to mock the tenant-management transport
(``http://localhost:8085``). Every route is registered on its exact method and
path, so a method that hits the wrong path or verb fails with respx's
"not mocked" error rather than passing.
"""

from __future__ import annotations

import json as _json
import typing
from typing import Any
from uuid import uuid4

import httpx
import pytest
import respx
from pydantic import ValidationError

from audact import AudactClient
from audact.client import KnowledgeBasesClient
from audact.exceptions import AudactAPIError, AudactNotFoundError
from audact.models import (
    AddKBExclusionRequest,
    AddKBSourceRequest,
    CreateKnowledgeBaseRequest,
    KBAgentLink,
    KBCrawlCoverage,
    KBCrawlExclusion,
    KBRetrievalTurnRole,
    KBRobotsPolicy,
    KBSource,
    KBTestHarnessTurn,
    KBTestRetrievalRequest,
    KBTestRetrievalResponse,
    KnowledgeBase,
    ListKBAgentLinksResponse,
    ListKBExclusionsResponse,
    ListKBSourcesResponse,
    Page,
    PatchKBAgentLinkRequest,
    PatchKBSourceRequest,
    PatchKnowledgeBaseRequest,
    PutKBAgentLinkRequest,
)

BASE = "http://localhost:8085/v1/knowledge-bases"

KB_ID = uuid4()
TENANT_ID = uuid4()
SOURCE_ID = uuid4()
AGENT_ID = uuid4()
EXCLUSION_ID = uuid4()

# A hostile identifier: unescaped it would traverse to another route.
EVIL = "../x?y#z"
EVIL_ENC = "..%2Fx%3Fy%23z"


def _error_response(status: int, code: str, message: str) -> httpx.Response:
    """The server's real nested error envelope."""
    return httpx.Response(status, json={"error": {"code": code, "message": message}})


def _body(route: respx.Route) -> Any:
    return _json.loads(route.calls.last.request.content)


def _kb(**overrides: Any) -> dict[str, Any]:
    payload = {
        "kb_id": str(KB_ID),
        "tenant_id": str(TENANT_ID),
        "name": "Product FAQ",
        "auto_refresh": False,
        "robots_policy": "honor",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def _source(**overrides: Any) -> dict[str, Any]:
    payload = {
        "source_id": str(SOURCE_ID),
        "tenant_id": str(TENANT_ID),
        "kb_id": str(KB_ID),
        "type": "url",
        "uri": "https://docs.example.com",
        "status": "pending",
        "ingest_version": 1,
        "config": {"auto_crawl": True, "depth": 2},
        "created_at": "2026-06-22T12:00:00Z",
        "updated_at": "2026-06-22T12:00:00Z",
    }
    payload.update(overrides)
    return payload


def _link(**overrides: Any) -> dict[str, Any]:
    payload = {
        "kb_id": str(KB_ID),
        "agent_id": str(AGENT_ID),
        "tenant_id": str(TENANT_ID),
        "top_k": 3,
        "similarity_threshold": 0.6,
        "retrieval_instruction": "",
        "created_at": "2026-06-22T12:00:00Z",
    }
    payload.update(overrides)
    return payload


def _exclusion(**overrides: Any) -> dict[str, Any]:
    payload = {
        "id": str(EXCLUSION_ID),
        "kb_id": str(KB_ID),
        "tenant_id": str(TENANT_ID),
        "crawl_path": "/admin",
        "created_at": "2026-06-22T12:00:00Z",
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_test123")


def test_knowledge_bases_is_knowledge_bases_client(client: AudactClient) -> None:
    assert isinstance(client.knowledge_bases, KnowledgeBasesClient)


def test_honours_tenant_management_url() -> None:
    c = AudactClient(api_key="k", tenant_management_url="https://tm.example.com/")
    assert c.knowledge_bases._base_url == "https://tm.example.com/v1/knowledge-bases"


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge-base CRUD
# ─────────────────────────────────────────────────────────────────────────────


class TestListKnowledgeBases:
    @respx.mock
    async def test_basic(self, client: AudactClient) -> None:
        route = respx.get(BASE).mock(
            return_value=httpx.Response(200, json={"items": [_kb()], "has_more": False})
        )

        result = await client.knowledge_bases.list_knowledge_bases()

        request = route.calls.last.request
        assert request.headers["Authorization"] == "Bearer aud_live_test123"
        assert request.url.query == b""
        assert isinstance(result, Page)
        assert len(result.items) == 1
        kb = result.items[0]
        assert isinstance(kb, KnowledgeBase)
        assert kb.kb_id == KB_ID
        assert kb.tenant_id == TENANT_ID
        assert kb.robots_policy == "honor"
        assert kb.created_at is not None and kb.created_at.year == 2026
        assert result.has_more is False
        assert result.next_cursor is None

    @respx.mock
    async def test_cursor_and_limit(self, client: AudactClient) -> None:
        route = respx.get(BASE).mock(
            return_value=httpx.Response(
                200, json={"items": [], "has_more": True, "next_cursor": "c1"}
            )
        )

        result = await client.knowledge_bases.list_knowledge_bases(cursor="c0", limit=5)

        params = route.calls.last.request.url.params
        assert params["cursor"] == "c0"
        assert params["limit"] == "5"
        assert result.has_more is True
        assert result.next_cursor == "c1"

    @respx.mock
    async def test_empty_next_cursor_is_none(self, client: AudactClient) -> None:
        respx.get(BASE).mock(
            return_value=httpx.Response(
                200, json={"items": [], "has_more": False, "next_cursor": ""}
            )
        )
        result = await client.knowledge_bases.list_knowledge_bases()
        assert result.next_cursor is None

    @respx.mock
    async def test_unauthorized(self, client: AudactClient) -> None:
        respx.get(BASE).mock(return_value=_error_response(401, "UNAUTHORIZED", "no token"))
        with pytest.raises(AudactAPIError) as exc_info:
            await client.knowledge_bases.list_knowledge_bases()
        assert exc_info.value.status_code == 401


class TestCreateKnowledgeBase:
    @respx.mock
    async def test_posts_body_and_decodes(self, client: AudactClient) -> None:
        route = respx.post(BASE).mock(return_value=httpx.Response(201, json=_kb()))

        result = await client.knowledge_bases.create_knowledge_base(
            CreateKnowledgeBaseRequest(name="Product FAQ", robots_policy="override")
        )

        assert _body(route) == {"name": "Product FAQ", "robots_policy": "override"}
        assert isinstance(result, KnowledgeBase)
        assert result.kb_id == KB_ID

    @respx.mock
    async def test_validation_error(self, client: AudactClient) -> None:
        respx.post(BASE).mock(return_value=_error_response(400, "INVALID_REQUEST", "name required"))
        with pytest.raises(AudactAPIError) as exc_info:
            await client.knowledge_bases.create_knowledge_base(CreateKnowledgeBaseRequest(name=""))
        assert exc_info.value.status_code == 400


class TestGetKnowledgeBase:
    @respx.mock
    async def test_get(self, client: AudactClient) -> None:
        route = respx.get(f"{BASE}/{KB_ID}").mock(return_value=httpx.Response(200, json=_kb()))

        result = await client.knowledge_bases.get_knowledge_base(KB_ID)

        assert route.called
        assert result.name == "Product FAQ"

    @respx.mock
    async def test_escapes_path_segment(self, client: AudactClient) -> None:
        route = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, json=_kb()))

        await client.knowledge_bases.get_knowledge_base(EVIL)

        assert route.calls.last.request.url.raw_path == f"/v1/knowledge-bases/{EVIL_ENC}".encode()

    @respx.mock
    async def test_not_found(self, client: AudactClient) -> None:
        respx.get(f"{BASE}/{KB_ID}").mock(return_value=_error_response(404, "NOT_FOUND", "no kb"))
        with pytest.raises(AudactNotFoundError):
            await client.knowledge_bases.get_knowledge_base(KB_ID)


class TestPatchKnowledgeBase:
    @respx.mock
    async def test_patch_sends_only_set_fields(self, client: AudactClient) -> None:
        route = respx.patch(f"{BASE}/{KB_ID}").mock(
            return_value=httpx.Response(200, json=_kb(auto_refresh=True))
        )

        result = await client.knowledge_bases.patch_knowledge_base(
            KB_ID, PatchKnowledgeBaseRequest(auto_refresh=True)
        )

        assert _body(route) == {"auto_refresh": True}
        assert result.auto_refresh is True


class TestDeleteKnowledgeBase:
    @respx.mock
    async def test_delete(self, client: AudactClient) -> None:
        route = respx.delete(f"{BASE}/{KB_ID}").mock(return_value=httpx.Response(204))

        await client.knowledge_bases.delete_knowledge_base(KB_ID)

        assert route.called

    @respx.mock
    async def test_delete_not_found(self, client: AudactClient) -> None:
        respx.delete(f"{BASE}/{KB_ID}").mock(return_value=_error_response(404, "NOT_FOUND", "x"))
        with pytest.raises(AudactNotFoundError):
            await client.knowledge_bases.delete_knowledge_base(KB_ID)


# ─────────────────────────────────────────────────────────────────────────────
# Sources
# ─────────────────────────────────────────────────────────────────────────────


class TestSources:
    @respx.mock
    async def test_list(self, client: AudactClient) -> None:
        route = respx.get(f"{BASE}/{KB_ID}/sources").mock(
            return_value=httpx.Response(
                200,
                json={"items": [_source(), _source(type="text", status="ready")], "total": 2},
            )
        )

        result = await client.knowledge_bases.list_kb_sources(KB_ID)

        assert route.called
        assert isinstance(result, ListKBSourcesResponse)
        assert result.total == 2
        assert [s.type for s in result.items] == ["url", "text"]
        assert result.items[1].status == "ready"

    @respx.mock
    async def test_add_json(self, client: AudactClient) -> None:
        route = respx.post(f"{BASE}/{KB_ID}/sources").mock(
            return_value=httpx.Response(202, json=_source())
        )

        result = await client.knowledge_bases.add_kb_source(
            KB_ID,
            AddKBSourceRequest(
                type="url", url="https://docs.example.com", config={"auto_crawl": True}
            ),
        )

        request = route.calls.last.request
        assert request.headers["Content-Type"] == "application/json"
        assert _body(route) == {
            "type": "url",
            "url": "https://docs.example.com",
            "config": {"auto_crawl": True},
        }
        assert isinstance(result, KBSource)
        assert result.source_id == SOURCE_ID
        assert result.status == "pending"
        assert result.config == {"auto_crawl": True, "depth": 2}

    @respx.mock
    async def test_add_queue_unavailable(self, client: AudactClient) -> None:
        respx.post(f"{BASE}/{KB_ID}/sources").mock(
            return_value=_error_response(503, "SERVICE_UNAVAILABLE", "queue down")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.knowledge_bases.add_kb_source(
                KB_ID, AddKBSourceRequest(type="text", content="hello")
            )
        assert exc_info.value.status_code == 503

    @respx.mock
    async def test_upload_file_is_multipart(self, client: AudactClient) -> None:
        route = respx.post(f"{BASE}/{KB_ID}/sources").mock(
            return_value=httpx.Response(202, json=_source(type="file", uri="faq.pdf"))
        )

        result = await client.knowledge_bases.upload_kb_source_file(
            KB_ID,
            b"%PDF-1.7 bytes",
            filename="faq.pdf",
            content_type="application/pdf",
            config={"auto_refresh": False},
        )

        request = route.calls.last.request
        assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
        raw = request.content
        assert b'name="file"; filename="faq.pdf"' in raw
        assert b"Content-Type: application/pdf" in raw
        assert b"%PDF-1.7 bytes" in raw
        assert b'name="filename"\r\n\r\nfaq.pdf' in raw
        assert b'name="config"\r\n\r\n{"auto_refresh": false}' in raw
        assert result.type == "file"
        assert result.uri == "faq.pdf"

    @respx.mock
    async def test_upload_file_without_optional_fields(self, client: AudactClient) -> None:
        route = respx.post(f"{BASE}/{KB_ID}/sources").mock(
            return_value=httpx.Response(202, json=_source(type="file"))
        )

        await client.knowledge_bases.upload_kb_source_file(KB_ID, b"data")

        raw = route.calls.last.request.content
        assert b'name="file"; filename="upload"' in raw
        assert b'name="filename"' not in raw
        assert b'name="config"' not in raw

    @respx.mock
    async def test_get(self, client: AudactClient) -> None:
        route = respx.get(f"{BASE}/{KB_ID}/sources/{SOURCE_ID}").mock(
            return_value=httpx.Response(200, json=_source(status="failed", error="timeout"))
        )

        result = await client.knowledge_bases.get_kb_source(KB_ID, SOURCE_ID)

        assert route.called
        assert result.status == "failed"
        assert result.error == "timeout"

    @respx.mock
    async def test_get_ingestion_outcome(self, client: AudactClient) -> None:
        """chunk count, crawl coverage and last ingestion time decode;
        a zero chunk count stays 0, not None."""
        respx.get(f"{BASE}/{KB_ID}/sources/{SOURCE_ID}").mock(
            return_value=httpx.Response(
                200,
                json=_source(
                    status="ready",
                    chunk_count=0,
                    crawl_coverage={"discovered": 12, "stored": 10, "excluded": 1, "failed": 1},
                    last_ingested_at="2026-06-22T12:05:00Z",
                ),
            )
        )

        result = await client.knowledge_bases.get_kb_source(KB_ID, SOURCE_ID)

        assert result.chunk_count == 0
        assert isinstance(result.crawl_coverage, KBCrawlCoverage)
        assert result.crawl_coverage.discovered == 12
        assert result.crawl_coverage.stored == 10
        assert result.crawl_coverage.excluded == 1
        assert result.crawl_coverage.failed == 1
        assert result.last_ingested_at is not None
        assert result.last_ingested_at.isoformat() == "2026-06-22T12:05:00+00:00"

    @respx.mock
    async def test_get_without_ingestion_outcome(self, client: AudactClient) -> None:
        """A source that has never finished an ingestion carries none of those fields."""
        respx.get(f"{BASE}/{KB_ID}/sources/{SOURCE_ID}").mock(
            return_value=httpx.Response(200, json=_source(status="pending"))
        )

        result = await client.knowledge_bases.get_kb_source(KB_ID, SOURCE_ID)

        assert result.chunk_count is None
        assert result.crawl_coverage is None
        assert result.last_ingested_at is None

    @respx.mock
    async def test_get_escapes_both_segments(self, client: AudactClient) -> None:
        route = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, json=_source()))

        await client.knowledge_bases.get_kb_source(EVIL, "a/b")

        assert (
            route.calls.last.request.url.raw_path
            == f"/v1/knowledge-bases/{EVIL_ENC}/sources/a%2Fb".encode()
        )

    @respx.mock
    async def test_get_not_found(self, client: AudactClient) -> None:
        respx.get(f"{BASE}/{KB_ID}/sources/{SOURCE_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "no source")
        )
        with pytest.raises(AudactNotFoundError):
            await client.knowledge_bases.get_kb_source(KB_ID, SOURCE_ID)

    @respx.mock
    async def test_patch(self, client: AudactClient) -> None:
        route = respx.patch(f"{BASE}/{KB_ID}/sources/{SOURCE_ID}").mock(
            return_value=httpx.Response(200, json=_source(title="Refunds"))
        )

        result = await client.knowledge_bases.patch_kb_source(
            KB_ID, SOURCE_ID, PatchKBSourceRequest(title="Refunds")
        )

        assert _body(route) == {"title": "Refunds"}
        assert result.title == "Refunds"

    @respx.mock
    async def test_reingest(self, client: AudactClient) -> None:
        route = respx.post(f"{BASE}/{KB_ID}/sources/{SOURCE_ID}/reingest").mock(
            return_value=httpx.Response(202, json=_source(ingest_version=2))
        )

        result = await client.knowledge_bases.reingest_kb_source(KB_ID, SOURCE_ID)

        assert route.calls.last.request.content == b""
        assert result.ingest_version == 2

    @respx.mock
    async def test_delete(self, client: AudactClient) -> None:
        route = respx.delete(f"{BASE}/{KB_ID}/sources/{SOURCE_ID}").mock(
            return_value=httpx.Response(204)
        )
        await client.knowledge_bases.delete_kb_source(KB_ID, SOURCE_ID)
        assert route.called

    def test_blank_enums_decode_to_none(self) -> None:
        src = KBSource.model_validate(_source(type="", status=""))
        assert src.type is None
        assert src.status is None


# ─────────────────────────────────────────────────────────────────────────────
# Agent links
# ─────────────────────────────────────────────────────────────────────────────


class TestAgentLinks:
    @respx.mock
    async def test_list_for_kb(self, client: AudactClient) -> None:
        route = respx.get(f"{BASE}/{KB_ID}/agents").mock(
            return_value=httpx.Response(200, json={"items": [_link()], "total": 1})
        )

        result = await client.knowledge_bases.list_kb_agent_links(KB_ID)

        assert route.called
        assert isinstance(result, ListKBAgentLinksResponse)
        assert result.total == 1
        assert result.items[0].agent_id == AGENT_ID
        assert result.items[0].similarity_threshold == 0.6

    @respx.mock
    async def test_list_by_agent_uses_query(self, client: AudactClient) -> None:
        route = respx.get(f"{BASE}/agent-links").mock(
            return_value=httpx.Response(200, json={"items": [_link()], "total": 1})
        )

        result = await client.knowledge_bases.list_kb_links_by_agent(AGENT_ID)

        assert route.calls.last.request.url.params["agent_id"] == str(AGENT_ID)
        assert result.items[0].kb_id == KB_ID

    @respx.mock
    async def test_put_with_tuning(self, client: AudactClient) -> None:
        route = respx.put(f"{BASE}/{KB_ID}/agents/{AGENT_ID}").mock(
            return_value=httpx.Response(200, json=_link(top_k=5))
        )

        result = await client.knowledge_bases.put_kb_agent_link(
            KB_ID, AGENT_ID, PutKBAgentLinkRequest(top_k=5, similarity_threshold=0.75)
        )

        assert _body(route) == {"top_k": 5, "similarity_threshold": 0.75}
        assert isinstance(result, KBAgentLink)
        assert result.top_k == 5

    @respx.mock
    async def test_put_without_body_sends_empty_object(self, client: AudactClient) -> None:
        route = respx.put(f"{BASE}/{KB_ID}/agents/{AGENT_ID}").mock(
            return_value=httpx.Response(200, json=_link())
        )
        await client.knowledge_bases.put_kb_agent_link(KB_ID, AGENT_ID)
        assert _body(route) == {}

    @respx.mock
    async def test_put_out_of_range(self, client: AudactClient) -> None:
        respx.put(f"{BASE}/{KB_ID}/agents/{AGENT_ID}").mock(
            return_value=_error_response(400, "INVALID_REQUEST", "top_k must be between 1 and 10")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.knowledge_bases.put_kb_agent_link(
                KB_ID, AGENT_ID, PutKBAgentLinkRequest(top_k=11)
            )
        assert exc_info.value.status_code == 400

    @respx.mock
    async def test_patch(self, client: AudactClient) -> None:
        route = respx.patch(f"{BASE}/{KB_ID}/agents/{AGENT_ID}").mock(
            return_value=httpx.Response(200, json=_link(retrieval_instruction="Pricing only."))
        )

        result = await client.knowledge_bases.patch_kb_agent_link(
            KB_ID, AGENT_ID, PatchKBAgentLinkRequest(retrieval_instruction="Pricing only.")
        )

        assert _body(route) == {"retrieval_instruction": "Pricing only."}
        assert result.retrieval_instruction == "Pricing only."

    @respx.mock
    async def test_delete_escapes_agent_segment(self, client: AudactClient) -> None:
        route = respx.delete(url__regex=r".*").mock(return_value=httpx.Response(204))

        await client.knowledge_bases.delete_kb_agent_link(KB_ID, EVIL)

        assert (
            route.calls.last.request.url.raw_path
            == f"/v1/knowledge-bases/{KB_ID}/agents/{EVIL_ENC}".encode()
        )

    @respx.mock
    async def test_delete_not_found(self, client: AudactClient) -> None:
        respx.delete(f"{BASE}/{KB_ID}/agents/{AGENT_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "no link")
        )
        with pytest.raises(AudactNotFoundError):
            await client.knowledge_bases.delete_kb_agent_link(KB_ID, AGENT_ID)


# ─────────────────────────────────────────────────────────────────────────────
# Crawl exclusions
# ─────────────────────────────────────────────────────────────────────────────


class TestExclusions:
    @respx.mock
    async def test_list(self, client: AudactClient) -> None:
        route = respx.get(f"{BASE}/{KB_ID}/exclusions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [_exclusion(), _exclusion(crawl_path=None, url="https://e.com/p")],
                    "total": 2,
                },
            )
        )

        result = await client.knowledge_bases.list_exclusions(KB_ID)

        assert route.called
        assert isinstance(result, ListKBExclusionsResponse)
        assert result.items[0].crawl_path == "/admin"
        assert result.items[0].url is None
        assert result.items[1].crawl_path is None
        assert result.items[1].url == "https://e.com/p"

    @respx.mock
    async def test_add(self, client: AudactClient) -> None:
        route = respx.post(f"{BASE}/{KB_ID}/exclusions").mock(
            return_value=httpx.Response(201, json=_exclusion())
        )

        result = await client.knowledge_bases.add_exclusion(
            KB_ID, AddKBExclusionRequest(crawl_path="/admin")
        )

        assert _body(route) == {"crawl_path": "/admin"}
        assert isinstance(result, KBCrawlExclusion)
        assert result.id == EXCLUSION_ID

    @respx.mock
    async def test_add_invalid(self, client: AudactClient) -> None:
        respx.post(f"{BASE}/{KB_ID}/exclusions").mock(
            return_value=_error_response(400, "INVALID_REQUEST", "exactly one of url, crawl_path")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.knowledge_bases.add_exclusion(KB_ID, AddKBExclusionRequest())
        assert exc_info.value.status_code == 400

    @respx.mock
    async def test_delete(self, client: AudactClient) -> None:
        route = respx.delete(f"{BASE}/{KB_ID}/exclusions/{EXCLUSION_ID}").mock(
            return_value=httpx.Response(204)
        )
        await client.knowledge_bases.delete_exclusion(KB_ID, EXCLUSION_ID)
        assert route.called

    @respx.mock
    async def test_delete_escapes_id(self, client: AudactClient) -> None:
        route = respx.delete(url__regex=r".*").mock(return_value=httpx.Response(204))

        await client.knowledge_bases.delete_exclusion(KB_ID, EVIL)

        assert (
            route.calls.last.request.url.raw_path
            == f"/v1/knowledge-bases/{KB_ID}/exclusions/{EVIL_ENC}".encode()
        )


# ─────────────────────────────────────────────────────────────────────────────
# Retrieval test harness
# ─────────────────────────────────────────────────────────────────────────────


class TestRetrievalHarness:
    @respx.mock
    async def test_turns(self, client: AudactClient) -> None:
        hit = {
            "text": "Our return window is 30 days.",
            "source_id": str(SOURCE_ID),
            "kb_id": str(KB_ID),
            "similarity": 0.87,
        }
        route = respx.post(f"{BASE}/{KB_ID}/test-retrieval").mock(
            return_value=httpx.Response(
                200, json={"condensed_query": "refund window", "hits": [hit], "empty": False}
            )
        )

        result = await client.knowledge_bases.test_kb_retrieval(
            KB_ID,
            KBTestRetrievalRequest(
                turns=[KBTestHarnessTurn(role="user", content="What is the refund policy?")],
                top_k=5,
                threshold=0.7,
            ),
        )

        assert _body(route) == {
            "turns": [{"role": "user", "content": "What is the refund policy?"}],
            "top_k": 5,
            "threshold": 0.7,
        }
        assert isinstance(result, KBTestRetrievalResponse)
        assert result.condensed_query == "refund window"
        assert result.hits[0].similarity == 0.87
        assert result.hits[0].source_id == SOURCE_ID
        assert result.empty is False

    @respx.mock
    async def test_empty_result_is_not_an_error(self, client: AudactClient) -> None:
        route = respx.post(f"{BASE}/{KB_ID}/test-retrieval").mock(
            return_value=httpx.Response(
                200, json={"condensed_query": "", "hits": [], "empty": True}
            )
        )

        result = await client.knowledge_bases.test_kb_retrieval(
            KB_ID, KBTestRetrievalRequest(question="anything?")
        )

        assert _body(route) == {"question": "anything?"}
        assert result.empty is True
        assert result.hits == []

    @respx.mock
    async def test_not_found(self, client: AudactClient) -> None:
        respx.post(f"{BASE}/{KB_ID}/test-retrieval").mock(
            return_value=_error_response(404, "NOT_FOUND", "no kb")
        )
        with pytest.raises(AudactNotFoundError):
            await client.knowledge_bases.test_kb_retrieval(
                KB_ID, KBTestRetrievalRequest(question="q")
            )


def test_kb_enum_types() -> None:
    assert typing.get_args(KBRobotsPolicy) == ("honor", "override")
    assert typing.get_args(KBRetrievalTurnRole) == ("user", "assistant", "system")
    with pytest.raises(ValidationError):
        CreateKnowledgeBaseRequest(name="x", robots_policy="ignore")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        KBTestHarnessTurn(role="narrator", content="x")  # type: ignore[arg-type]
    for value in ("honor", "override"):
        kb = KnowledgeBase.model_validate(_kb(robots_policy=value))
        assert kb.robots_policy == value
