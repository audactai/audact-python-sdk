"""
Tests for the ``client.tools`` sub-client: tool CRUD (full PUT +
partial PATCH), platform-tool test/validation, and agent-tool
list/attach/detach — agent-worker (8089).

Uses ``respx`` to mock the agent-worker transport (``http://localhost:8089``)
so no real network calls are made.
"""

from __future__ import annotations

import json as _json
from uuid import uuid4

import httpx
import pytest
import respx

from audact import AudactClient
from audact.client import ToolsClient
from audact.exceptions import AudactAPIError, AudactNotFoundError
from audact.models import (
    AttachToolResponse,
    CreateToolRequest,
    DeleteToolResponse,
    DetachToolResponse,
    Page,
    TestToolResponse,
    ToolConfig,
    UpdateToolRequest,
)

BASE = "http://localhost:8089"

TOOL_ID = uuid4()
TENANT_ID = uuid4()
AGENT_ID = uuid4()
CONNECTION_ID = uuid4()


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _error_response(status: int, code: str, message: str) -> httpx.Response:
    """The server's real nested error envelope."""
    return httpx.Response(status, json={"error": {"code": code, "message": message}})


@pytest.fixture()
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_test123")


def _tool_payload(**overrides) -> dict:
    payload = {
        "tool_id": str(TOOL_ID),
        "tenant_id": str(TENANT_ID),
        "name": "lookup_customer",
        "description": "Look up a customer by email",
        "method": "POST",
        "url": "https://api.example.com/v1/lookup",
        "headers": [{"key": "X-Api-Key", "value": "{{api_key}}"}],
        "query_params": [],
        "parameters": {"type": "object", "properties": {"email": {"type": "string"}}},
        "response_vars": [],
        "execution": {"timeout_ms": 5000},
        "args_only": False,
        "created_at": "2026-03-18T15:17:00Z",
        "updated_at": "2026-03-18T15:17:00Z",
    }
    payload.update(overrides)
    return payload


def test_tools_is_tools_client(client: AudactClient) -> None:
    assert isinstance(client.tools, ToolsClient)


# ─────────────────────────────────────────────────────────────────────────────
# list_tools — GET /v1/tools (paginated, cursor convention)
# ─────────────────────────────────────────────────────────────────────────────

class TestListTools:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/tools").mock(
            return_value=_json_response({"tools": [_tool_payload()], "has_more": False})
        )

        result = await client.tools.list_tools()

        assert route.called
        request = route.calls.last.request
        assert request.headers["Authorization"] == "Bearer aud_live_test123"
        assert isinstance(result, Page)
        assert len(result.items) == 1
        assert isinstance(result.items[0], ToolConfig)
        assert result.items[0].tool_id == TOOL_ID
        assert result.has_more is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_appends_name_limit_cursor_query_params(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/tools").mock(
            return_value=_json_response(
                {"tools": [], "has_more": True, "cursor": "abc"}
            )
        )

        result = await client.tools.list_tools(
            name="lookup_customer", limit=10, cursor="c0"
        )

        request = route.calls.last.request
        assert request.url.params["name"] == "lookup_customer"
        assert request.url.params["limit"] == "10"
        assert request.url.params["cursor"] == "c0"
        assert result.has_more is True
        assert result.next_cursor == "abc"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_unauthorized(self, client: AudactClient):
        respx.get(f"{BASE}/v1/tools").mock(
            return_value=_error_response(401, "UNAUTHORIZED", "missing bearer token")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.tools.list_tools()
        assert exc_info.value.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# create_tool — POST /v1/tools
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateTool:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.post(f"{BASE}/v1/tools").mock(
            return_value=_json_response(_tool_payload(), status=201)
        )

        result = await client.tools.create_tool(
            CreateToolRequest(
                name="lookup_customer",
                description="Look up a customer by email",
                method="POST",
                url="https://api.example.com/v1/lookup",
            )
        )

        assert isinstance(result, ToolConfig)
        assert result.tool_id == TOOL_ID
        request = route.calls.last.request
        body = _json.loads(request.content)
        assert body == {
            "name": "lookup_customer",
            "description": "Look up a customer by email",
            "method": "POST",
            "url": "https://api.example.com/v1/lookup",
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_idempotency_key_header(self, client: AudactClient):
        respx.post(f"{BASE}/v1/tools").mock(
            return_value=_json_response(_tool_payload(), status=201)
        )

        await client.tools.create_tool(
            CreateToolRequest(name="lookup_customer", description="desc"),
            idempotency_key="idem-tool-1",
        )

        request = respx.calls.last.request
        assert request.headers["Idempotency-Key"] == "idem-tool-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_platform_tool(self, client: AudactClient):
        payload = _tool_payload(
            name="book_appointment",
            provider="cal_com",
            provider_tool="book_appointment",
            connection_id=str(CONNECTION_ID),
            provider_config={"event_type_id": 123},
        )
        del payload["method"]
        del payload["url"]
        route = respx.post(f"{BASE}/v1/tools").mock(
            return_value=_json_response(payload, status=201)
        )

        result = await client.tools.create_tool(
            CreateToolRequest(
                name="book_appointment",
                description="Book an appointment",
                provider="cal_com",
                provider_tool="book_appointment",
                connection_id=CONNECTION_ID,
                provider_config={"event_type_id": 123},
            )
        )

        assert result.provider == "cal_com"
        assert result.connection_id == CONNECTION_ID
        body = _json.loads(route.calls.last.request.content)
        assert body["provider"] == "cal_com"
        assert body["connection_id"] == str(CONNECTION_ID)
        assert "method" not in body
        assert "url" not in body

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_connection_not_found(self, client: AudactClient):
        respx.post(f"{BASE}/v1/tools").mock(
            return_value=_error_response(404, "NOT_FOUND", "connection not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.tools.create_tool(
                CreateToolRequest(
                    name="book_appointment",
                    description="desc",
                    provider="cal_com",
                    connection_id=uuid4(),
                )
            )

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_name_conflict(self, client: AudactClient):
        respx.post(f"{BASE}/v1/tools").mock(
            return_value=_error_response(409, "CONFLICT", "name already exists")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.tools.create_tool(
                CreateToolRequest(name="lookup_customer", description="desc")
            )
        assert exc_info.value.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# get_tool — GET /v1/tools/{tool_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestGetTool:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/tools/{TOOL_ID}").mock(
            return_value=_json_response(_tool_payload())
        )

        result = await client.tools.get_tool(TOOL_ID)

        assert isinstance(result, ToolConfig)
        assert result.tool_id == TOOL_ID
        assert route.calls.last.request.method == "GET"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_not_found(self, client: AudactClient):
        respx.get(f"{BASE}/v1/tools/{TOOL_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.tools.get_tool(TOOL_ID)


# ─────────────────────────────────────────────────────────────────────────────
# replace_tool — PUT /v1/tools/{tool_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestReplaceTool:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.put(f"{BASE}/v1/tools/{TOOL_ID}").mock(
            return_value=_json_response(_tool_payload(description="Updated description"))
        )

        result = await client.tools.replace_tool(
            TOOL_ID,
            CreateToolRequest(
                name="lookup_customer",
                description="Updated description",
                method="POST",
                url="https://api.example.com/v1/lookup",
            ),
        )

        assert result.description == "Updated description"
        request = route.calls.last.request
        assert request.method == "PUT"
        body = _json.loads(request.content)
        assert body["description"] == "Updated description"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_not_found(self, client: AudactClient):
        respx.put(f"{BASE}/v1/tools/{TOOL_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.tools.replace_tool(
                TOOL_ID, CreateToolRequest(name="x", description="d")
            )


# ─────────────────────────────────────────────────────────────────────────────
# update_tool — PATCH /v1/tools/{tool_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdateTool:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.patch(f"{BASE}/v1/tools/{TOOL_ID}").mock(
            return_value=_json_response(_tool_payload(description="Patched"))
        )

        result = await client.tools.update_tool(
            TOOL_ID, UpdateToolRequest(description="Patched")
        )

        assert result.description == "Patched"
        request = route.calls.last.request
        assert request.method == "PATCH"
        assert _json.loads(request.content) == {"description": "Patched"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_name_conflict(self, client: AudactClient):
        respx.patch(f"{BASE}/v1/tools/{TOOL_ID}").mock(
            return_value=_error_response(409, "CONFLICT", "name already exists")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.tools.update_tool(TOOL_ID, UpdateToolRequest(name="taken"))
        assert exc_info.value.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# delete_tool — DELETE /v1/tools/{tool_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteTool:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.delete(f"{BASE}/v1/tools/{TOOL_ID}").mock(
            return_value=_json_response({"deleted": True})
        )

        result = await client.tools.delete_tool(TOOL_ID)

        assert isinstance(result, DeleteToolResponse)
        assert result.deleted is True
        assert route.calls.last.request.method == "DELETE"
        assert "force" not in route.calls.last.request.url.params

    @pytest.mark.asyncio
    @respx.mock
    async def test_force_query_param(self, client: AudactClient):
        route = respx.delete(f"{BASE}/v1/tools/{TOOL_ID}").mock(
            return_value=_json_response({"deleted": True})
        )

        await client.tools.delete_tool(TOOL_ID, force=True)

        assert route.calls.last.request.url.params["force"] == "true"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_active_attachments(self, client: AudactClient):
        respx.delete(f"{BASE}/v1/tools/{TOOL_ID}").mock(
            return_value=_error_response(409, "CONFLICT", "tool has active agent attachments")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.tools.delete_tool(TOOL_ID)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_not_found(self, client: AudactClient):
        respx.delete(f"{BASE}/v1/tools/{TOOL_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.tools.delete_tool(TOOL_ID)


# ─────────────────────────────────────────────────────────────────────────────
# test_tool — POST /v1/tools/{tool_id}/test
# ─────────────────────────────────────────────────────────────────────────────

class TestTestTool:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.post(f"{BASE}/v1/tools/{TOOL_ID}/test").mock(
            return_value=_json_response(
                {
                    "tool_id": str(TOOL_ID),
                    "healthy": True,
                    "checks_passed": ["connection_active", "event_type_resolved"],
                    "dynamic_var_fields": [],
                    "error": "",
                }
            )
        )

        result = await client.tools.test_tool(TOOL_ID)

        assert isinstance(result, TestToolResponse)
        assert result.healthy is True
        assert result.checks_passed == ["connection_active", "event_type_resolved"]
        assert route.calls.last.request.method == "POST"

    @pytest.mark.asyncio
    @respx.mock
    async def test_reports_unhealthy(self, client: AudactClient):
        respx.post(f"{BASE}/v1/tools/{TOOL_ID}/test").mock(
            return_value=_json_response(
                {
                    "tool_id": str(TOOL_ID),
                    "healthy": False,
                    "checks_passed": ["connection_active"],
                    "error": "event_type_not_found",
                }
            )
        )

        result = await client.tools.test_tool(TOOL_ID)

        assert result.healthy is False
        assert result.error == "event_type_not_found"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_connection_not_active(self, client: AudactClient):
        respx.post(f"{BASE}/v1/tools/{TOOL_ID}/test").mock(
            return_value=_error_response(409, "CONFLICT", "connection not active")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.tools.test_tool(TOOL_ID)
        assert exc_info.value.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# list_agent_tools — GET /v1/agents/{agent_id}/tools (paginated)
# ─────────────────────────────────────────────────────────────────────────────

class TestListAgentTools:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/agents/{AGENT_ID}/tools").mock(
            return_value=_json_response(
                {"items": [_tool_payload()], "has_more": False, "next_cursor": ""}
            )
        )

        result = await client.tools.list_agent_tools(AGENT_ID)

        assert route.called
        assert isinstance(result, Page)
        assert len(result.items) == 1
        assert isinstance(result.items[0], ToolConfig)
        assert result.items[0].tool_id == TOOL_ID

    @pytest.mark.asyncio
    @respx.mock
    async def test_appends_limit_cursor_query_params(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/agents/{AGENT_ID}/tools").mock(
            return_value=_json_response(
                {"items": [], "has_more": True, "next_cursor": "abc"}
            )
        )

        result = await client.tools.list_agent_tools(AGENT_ID, limit=5, cursor="c0")

        request = route.calls.last.request
        assert request.url.params["limit"] == "5"
        assert request.url.params["cursor"] == "c0"
        assert result.has_more is True
        assert result.next_cursor == "abc"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_invalid_uuid_like_error(self, client: AudactClient):
        respx.get(f"{BASE}/v1/agents/{AGENT_ID}/tools").mock(
            return_value=_error_response(400, "INVALID_REQUEST", "invalid cursor")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.tools.list_agent_tools(AGENT_ID, cursor="!!!")
        assert exc_info.value.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# attach_tool_to_agent — POST /v1/agents/{agent_id}/tools
# ─────────────────────────────────────────────────────────────────────────────

class TestAttachToolToAgent:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.post(f"{BASE}/v1/agents/{AGENT_ID}/tools").mock(
            return_value=_json_response(
                {"agent_id": str(AGENT_ID), "tool_id": str(TOOL_ID), "attached": True},
                status=201,
            )
        )

        result = await client.tools.attach_tool_to_agent(AGENT_ID, TOOL_ID)

        assert isinstance(result, AttachToolResponse)
        assert result.attached is True
        assert result.agent_id == AGENT_ID
        assert result.tool_id == TOOL_ID
        request = route.calls.last.request
        assert request.method == "POST"
        assert _json.loads(request.content) == {"tool_id": str(TOOL_ID)}

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_not_found(self, client: AudactClient):
        respx.post(f"{BASE}/v1/agents/{AGENT_ID}/tools").mock(
            return_value=_error_response(404, "NOT_FOUND", "agent or tool not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.tools.attach_tool_to_agent(AGENT_ID, TOOL_ID)


# ─────────────────────────────────────────────────────────────────────────────
# detach_tool_from_agent — DELETE /v1/agents/{agent_id}/tools/{tool_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestDetachToolFromAgent:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.delete(f"{BASE}/v1/agents/{AGENT_ID}/tools/{TOOL_ID}").mock(
            return_value=_json_response({"detached": True})
        )

        result = await client.tools.detach_tool_from_agent(AGENT_ID, TOOL_ID)

        assert isinstance(result, DetachToolResponse)
        assert result.detached is True
        assert route.calls.last.request.method == "DELETE"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_invalid_uuid(self, client: AudactClient):
        respx.delete(f"{BASE}/v1/agents/{AGENT_ID}/tools/{TOOL_ID}").mock(
            return_value=_error_response(400, "INVALID_REQUEST", "invalid uuid")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.tools.detach_tool_from_agent(AGENT_ID, TOOL_ID)
        assert exc_info.value.status_code == 400
