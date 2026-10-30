"""
Tests for the ``client.agents`` sub-client: agent CRUD (full PUT +
partial PATCH), duplication, TTS voice catalog CRUD (including the multipart
voice-clone upload), and pipeline-load status — agent-worker (8089).

Uses ``respx`` to mock the agent-worker transport (``http://localhost:8089``)
so no real network calls are made.
"""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
import respx

from audact import AudactClient
from audact.client import AgentsClient
from audact.exceptions import AudactAPIError, AudactNotFoundError
from audact.models import (
    Agent,
    CreateAgentRequest,
    CreateAgentResponse,
    CreateVoiceResponse,
    DeleteAgentResponse,
    Page,
    PatchAgentRequest,
    PipelineStatusResponse,
    UpdateAgentRequest,
    Voice,
    VoiceProvider,
)

BASE = "http://localhost:8089"

AGENT_ID = uuid4()
TENANT_ID = uuid4()
VOICE_ID = "en_paul_neutral"


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _no_content_response() -> httpx.Response:
    return httpx.Response(204)


def _error_response(status: int, code: str, message: str) -> httpx.Response:
    """The server's real nested error envelope."""
    return httpx.Response(status, json={"error": {"code": code, "message": message}})


@pytest.fixture()
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_test123")


def _agent_payload(**overrides) -> dict:
    payload = {
        "agent_id": str(AGENT_ID),
        "tenant_id": str(TENANT_ID),
        "name": "Support Bot",
        "prompt": "You are a helpful support agent for Acme Corp.",
        "language": "en-US",
        "voice_id": VOICE_ID,
        "llm_provider": "openai",
        "llm_model": "gpt-4.1-mini",
        "stt_provider": "deepgram",
        "tts_provider": "voxtral",
        "status": "published",
        "version": 1,
        "created_at": "2026-03-18T15:17:00Z",
        "updated_at": "2026-03-18T15:17:00Z",
    }
    payload.update(overrides)
    return payload


def test_agents_is_agents_client(client: AudactClient) -> None:
    assert isinstance(client.agents, AgentsClient)


# ─────────────────────────────────────────────────────────────────────────────
# list_agents — GET /v1/agents (paginated, cursor convention)
# ─────────────────────────────────────────────────────────────────────────────

class TestListAgents:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/agents").mock(
            return_value=_json_response(
                {"agents": [_agent_payload()], "has_more": False}
            )
        )

        result = await client.agents.list_agents()

        assert route.called
        request = route.calls.last.request
        assert request.headers["Authorization"] == "Bearer aud_live_test123"
        assert isinstance(result, Page)
        assert len(result.items) == 1
        assert isinstance(result.items[0], Agent)
        assert result.items[0].agent_id == AGENT_ID
        assert result.has_more is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_appends_limit_cursor_query_params(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/agents").mock(
            return_value=_json_response(
                {"agents": [], "has_more": True, "next_cursor": "abc"}
            )
        )

        result = await client.agents.list_agents(limit=10, cursor="c0")

        request = route.calls.last.request
        assert request.url.params["limit"] == "10"
        assert request.url.params["cursor"] == "c0"
        assert result.has_more is True
        assert result.next_cursor == "abc"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_invalid_limit(self, client: AudactClient):
        respx.get(f"{BASE}/v1/agents").mock(
            return_value=_error_response(400, "INVALID_REQUEST", "limit must be positive")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.agents.list_agents(limit=-1)
        assert exc_info.value.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# create_agent — POST /v1/agents
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateAgent:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.post(f"{BASE}/v1/agents").mock(
            return_value=_json_response(
                {
                    "agent_id": str(AGENT_ID),
                    "tenant_id": str(TENANT_ID),
                    "name": "Support Bot",
                    "prompt": "You are a helpful support agent for Acme Corp.",
                    "language": "en-US",
                    "voice_id": VOICE_ID,
                    "llm_provider": "openai",
                    "llm_model": "gpt-4.1-mini",
                    "stt_provider": "deepgram",
                    "tts_provider": "voxtral",
                    "status": "published",
                    "created_at": "2026-03-18T15:17:00Z",
                },
                status=201,
            )
        )

        result = await client.agents.create_agent(
            CreateAgentRequest(name="Support Bot", language="en-US", voice_id=VOICE_ID)
        )

        assert isinstance(result, CreateAgentResponse)
        assert result.agent_id == AGENT_ID
        request = route.calls.last.request
        import json as _json

        body = _json.loads(request.content)
        assert body == {"name": "Support Bot", "language": "en-US", "voice_id": VOICE_ID}

    @pytest.mark.asyncio
    @respx.mock
    async def test_idempotency_key_header(self, client: AudactClient):
        route = respx.post(f"{BASE}/v1/agents").mock(
            return_value=_json_response(
                {
                    "agent_id": str(AGENT_ID),
                    "tenant_id": str(TENANT_ID),
                    "name": "Bot",
                    "language": "en-US",
                    "status": "published",
                    "created_at": "2026-03-18T15:17:00Z",
                },
                status=201,
            )
        )

        await client.agents.create_agent(
            CreateAgentRequest(name="Bot", language="en-US"),
            idempotency_key="idem-agent-1",
        )

        request = route.calls.last.request
        assert request.headers["Idempotency-Key"] == "idem-agent-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_agent_elevenlabs_serialises_tts_model(self, client: AudactClient):
        """tts_model is sent when given, omitted when not, and parsed back."""
        route = respx.post(f"{BASE}/v1/agents").mock(
            return_value=_json_response(
                {
                    "agent_id": str(AGENT_ID),
                    "tenant_id": str(TENANT_ID),
                    "name": "Concierge",
                    "language": "en-US",
                    "voice_id": "EXAVITQu4vr4xnSDxMaL",
                    "tts_provider": "elevenlabs",
                    "tts_model": "eleven_turbo_v2_5",
                    "status": "published",
                    "created_at": "2026-03-18T15:17:00Z",
                },
                status=201,
            )
        )
        import json as _json

        result = await client.agents.create_agent(
            CreateAgentRequest(
                name="Concierge",
                language="en-US",
                voice_id="EXAVITQu4vr4xnSDxMaL",
                tts_provider="elevenlabs",
                tts_model="eleven_turbo_v2_5",
            )
        )
        body = _json.loads(route.calls.last.request.content)
        assert body["tts_provider"] == "elevenlabs"
        assert body["tts_model"] == "eleven_turbo_v2_5"
        assert result.tts_model == "eleven_turbo_v2_5"

        # Not set → omitted, so the server applies the provider default.
        await client.agents.create_agent(
            CreateAgentRequest(
                name="Default",
                language="en-US",
                tts_provider="elevenlabs",
                voice_id="EXAVITQu4vr4xnSDxMaL",
            )
        )
        assert "tts_model" not in _json.loads(route.calls.last.request.content)

    @pytest.mark.asyncio
    @respx.mock
    async def test_cloned_voice_id(self, client: AudactClient):
        """voice_id is open-ended server-side: a tenant-cloned voice id is valid."""
        route = respx.post(f"{BASE}/v1/agents").mock(
            return_value=_json_response(
                {
                    "agent_id": str(AGENT_ID),
                    "tenant_id": str(TENANT_ID),
                    "name": "Bot",
                    "language": "en-US",
                    "voice_id": "cloned-voice-123",
                    "status": "published",
                    "created_at": "2026-03-18T15:17:00Z",
                },
                status=201,
            )
        )

        await client.agents.create_agent(
            CreateAgentRequest(name="Bot", language="en-US", voice_id="cloned-voice-123")
        )
        import json as _json

        assert _json.loads(route.calls.last.request.content)["voice_id"] == "cloned-voice-123"
        update = UpdateAgentRequest(
            name="Bot", language="en-US", prompt="p", voice_id="cloned-voice-123"
        )
        assert update.voice_id == "cloned-voice-123"
        assert PatchAgentRequest(voice_id="cloned-voice-123").voice_id == "cloned-voice-123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_missing_name(self, client: AudactClient):
        respx.post(f"{BASE}/v1/agents").mock(
            return_value=_error_response(400, "INVALID_REQUEST", "name is required")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.agents.create_agent(CreateAgentRequest(name="", language="en-US"))
        assert exc_info.value.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# get_agent — GET /v1/agents/{agent_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestGetAgent:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/agents/{AGENT_ID}").mock(
            return_value=_json_response(_agent_payload())
        )

        result = await client.agents.get_agent(AGENT_ID)

        assert isinstance(result, Agent)
        assert result.agent_id == AGENT_ID
        assert route.calls.last.request.method == "GET"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_not_found(self, client: AudactClient):
        respx.get(f"{BASE}/v1/agents/{AGENT_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.agents.get_agent(AGENT_ID)


# ─────────────────────────────────────────────────────────────────────────────
# update_agent — PUT /v1/agents/{agent_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdateAgent:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.put(f"{BASE}/v1/agents/{AGENT_ID}").mock(
            return_value=_json_response(_agent_payload(name="Renamed Bot"))
        )

        result = await client.agents.update_agent(
            AGENT_ID,
            UpdateAgentRequest(
                name="Renamed Bot",
                language="en-US",
                prompt="You are a helpful support agent for Acme Corp.",
            ),
        )

        assert result.name == "Renamed Bot"
        request = route.calls.last.request
        assert request.method == "PUT"
        import json as _json

        body = _json.loads(request.content)
        assert body == {
            "name": "Renamed Bot",
            "language": "en-US",
            "prompt": "You are a helpful support agent for Acme Corp.",
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_not_found(self, client: AudactClient):
        respx.put(f"{BASE}/v1/agents/{AGENT_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.agents.update_agent(
                AGENT_ID, UpdateAgentRequest(name="X", language="en-US", prompt="x")
            )


# ─────────────────────────────────────────────────────────────────────────────
# patch_agent — PATCH /v1/agents/{agent_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestPatchAgent:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.patch(f"{BASE}/v1/agents/{AGENT_ID}").mock(
            return_value=_json_response(_agent_payload(status="draft"))
        )

        result = await client.agents.patch_agent(AGENT_ID, PatchAgentRequest(status="draft"))

        assert result.status == "draft"
        request = route.calls.last.request
        assert request.method == "PATCH"
        import json as _json

        assert _json.loads(request.content) == {"status": "draft"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_invalid_status(self, client: AudactClient):
        respx.patch(f"{BASE}/v1/agents/{AGENT_ID}").mock(
            return_value=_error_response(400, "INVALID_REQUEST", "invalid status")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.agents.patch_agent(AGENT_ID, PatchAgentRequest(status="draft"))
        assert exc_info.value.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# delete_agent — DELETE /v1/agents/{agent_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteAgent:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.delete(f"{BASE}/v1/agents/{AGENT_ID}").mock(
            return_value=_json_response({"deleted": True})
        )

        result = await client.agents.delete_agent(AGENT_ID)

        assert isinstance(result, DeleteAgentResponse)
        assert result.deleted is True
        assert route.calls.last.request.method == "DELETE"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_not_found(self, client: AudactClient):
        respx.delete(f"{BASE}/v1/agents/{AGENT_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.agents.delete_agent(AGENT_ID)


# ─────────────────────────────────────────────────────────────────────────────
# duplicate_agent — POST /v1/agents/{agent_id}/duplicate
# ─────────────────────────────────────────────────────────────────────────────

class TestDuplicateAgent:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        copy_id = uuid4()
        route = respx.post(f"{BASE}/v1/agents/{AGENT_ID}/duplicate").mock(
            return_value=_json_response(
                _agent_payload(agent_id=str(copy_id), name="Support Bot (Copy)"),
                status=201,
            )
        )

        result = await client.agents.duplicate_agent(AGENT_ID)

        assert result.name == "Support Bot (Copy)"
        assert result.agent_id == copy_id
        assert route.calls.last.request.method == "POST"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_not_found(self, client: AudactClient):
        respx.post(f"{BASE}/v1/agents/{AGENT_ID}/duplicate").mock(
            return_value=_error_response(404, "NOT_FOUND", "not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.agents.duplicate_agent(AGENT_ID)


# ─────────────────────────────────────────────────────────────────────────────
# list_voices — GET /v1/voices
# ─────────────────────────────────────────────────────────────────────────────

class TestListVoices:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/voices").mock(
            return_value=_json_response(
                {
                    "voxtral": {
                        "display_name": "Voxtral",
                        "voices": [
                            {
                                "voice_id": VOICE_ID,
                                "name": "Paul (Neutral)",
                                "language": "en",
                                "gender": "male",
                                "style": "neutral",
                            }
                        ],
                    }
                }
            )
        )

        result = await client.agents.list_voices()

        assert route.calls.last.request.method == "GET"
        assert "voxtral" in result
        assert isinstance(result["voxtral"], VoiceProvider)
        assert len(result["voxtral"].voices) == 1
        assert result["voxtral"].voices[0].voice_id == VOICE_ID

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_unauthorized(self, client: AudactClient):
        respx.get(f"{BASE}/v1/voices").mock(
            return_value=_error_response(401, "UNAUTHORIZED", "missing bearer token")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.agents.list_voices()
        assert exc_info.value.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# create_voice — POST /v1/voices (multipart/form-data)
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateVoice:
    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_multipart_with_no_manual_content_type(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {
                    "voice_id": "cloned-voice-123",
                    "name": "British Receptionist (female)",
                    "language": "en-GB",
                    "gender": "female",
                    "style": "professional",
                    "accent": "British",
                    "provider": "voxtral",
                },
                status=201,
            )

        respx.post(f"{BASE}/v1/voices").mock(side_effect=_handler)

        result = await client.agents.create_voice(
            b"fake audio bytes",
            "British Receptionist (female)",
            True,
            filename="clip.mp3",
            language="en-GB",
            accent="British",
            gender="female",
            style="professional",
        )

        assert isinstance(result, CreateVoiceResponse)
        assert result.voice_id == "cloned-voice-123"

        request = captured[0]
        content_type = request.headers["content-type"]
        # Positive control: httpx must have written a real multipart boundary
        # header itself (never a manually-set application/json body).
        assert content_type.startswith("multipart/form-data")
        assert "boundary=" in content_type

        body = request.content
        assert b'name="audio"' in body
        assert b'filename="clip.mp3"' in body
        assert b"audio/mpeg" in body
        assert b"fake audio bytes" in body
        assert b'name="name"' in body
        assert b"British Receptionist (female)" in body
        assert b'name="consent_confirmed"' in body
        assert b"true" in body
        assert b'name="language"' in body
        assert b"en-GB" in body
        assert b'name="accent"' in body
        assert b"British" in body
        assert b'name="gender"' in body
        assert b'name="style"' in body

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_consent_confirmed_literal_false(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {
                    "voice_id": "cloned-voice-456",
                    "name": "Test Voice",
                    "language": "en",
                    "gender": "male",
                    "provider": "voxtral",
                },
                status=201,
            )

        respx.post(f"{BASE}/v1/voices").mock(side_effect=_handler)

        await client.agents.create_voice(b"fake audio bytes", "Test Voice", False)

        body = captured[0].content
        assert b'name="consent_confirmed"' in body
        assert b"false" in body
        # Defaults when filename/content_type are omitted.
        assert b'filename="clip.mp3"' in body

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_voice_rejected(self, client: AudactClient):
        respx.post(f"{BASE}/v1/voices").mock(
            return_value=_error_response(422, "VOICE_REJECTED", "sample rejected")
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.agents.create_voice(b"bytes", "Bad Voice", True)
        assert exc_info.value.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# get_voice — GET /v1/voices/{voice_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestGetVoice:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/voices/{VOICE_ID}").mock(
            return_value=_json_response(
                {
                    "voice_id": VOICE_ID,
                    "name": "Paul (Neutral)",
                    "language": "en",
                    "gender": "male",
                    "style": "neutral",
                }
            )
        )

        result = await client.agents.get_voice(VOICE_ID)

        assert isinstance(result, Voice)
        assert result.voice_id == VOICE_ID
        assert route.calls.last.request.method == "GET"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_not_found(self, client: AudactClient):
        respx.get(f"{BASE}/v1/voices/{VOICE_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "not found")
        )
        with pytest.raises(AudactNotFoundError):
            await client.agents.get_voice(VOICE_ID)


# ─────────────────────────────────────────────────────────────────────────────
# delete_voice — DELETE /v1/voices/{voice_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteVoice:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.delete(f"{BASE}/v1/voices/cloned-voice-123").mock(
            return_value=_no_content_response()
        )

        result = await client.agents.delete_voice("cloned-voice-123")

        assert result is None
        assert route.calls.last.request.method == "DELETE"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_builtin_preset(self, client: AudactClient):
        respx.delete(f"{BASE}/v1/voices/{VOICE_ID}").mock(
            return_value=_error_response(
                400, "INVALID_REQUEST", "Built-in preset voices cannot be deleted"
            )
        )
        with pytest.raises(AudactAPIError) as exc_info:
            await client.agents.delete_voice(VOICE_ID)
        assert exc_info.value.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# get_pipeline_status — GET /v1/pipeline/status
# ─────────────────────────────────────────────────────────────────────────────

class TestGetPipelineStatus:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/pipeline/status").mock(
            return_value=_json_response(
                {"active_pipelines": 3, "timestamp": "2026-09-15T12:00:00Z"}
            )
        )

        result = await client.agents.get_pipeline_status()

        assert isinstance(result, PipelineStatusResponse)
        assert result.active_pipelines == 3
        assert route.calls.last.request.method == "GET"


class TestListVoicesLanguages:
    @pytest.mark.asyncio
    @respx.mock
    async def test_list_voices_filters_and_languages(self, client: AudactClient):
        """language/provider filters reach the query; languages and models parse."""
        route = respx.get(f"{BASE}/v1/voices").mock(
            return_value=_json_response(
                {
                    "elevenlabs": {
                        "display_name": "ElevenLabs",
                        "models": [
                            {"id": "eleven_flash_v2_5", "default": True, "languages": ["de", "en"]}
                        ],
                        "voices": [
                            {
                                "voice_id": "DeDeDeDeDeDeDeDeDeDe",
                                "name": "Lena",
                                "language": "de",
                                "gender": "female",
                                "languages": ["de", "en"],
                            }
                        ],
                    }
                }
            )
        )
        out = await client.agents.list_voices(language="de-DE", provider="elevenlabs")
        assert route.calls.last.request.url.params["language"] == "de-DE"
        assert route.calls.last.request.url.params["provider"] == "elevenlabs"
        assert out["elevenlabs"].models[0].languages == ["de", "en"]
        assert out["elevenlabs"].models[0].default is True
        assert "de" in out["elevenlabs"].voices[0].languages

        await client.agents.list_voices()
        assert str(route.calls.last.request.url.query, "ascii") == ""
