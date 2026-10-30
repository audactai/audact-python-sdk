"""
Tests for the completion surfaces: ``client.audio`` (Audio
Validator, port 8086 — per-turn audio validation + post-call audio
reconciliation) and ``client.auth`` (Tenant Management, port 8085 —
API-key <-> JWT session bridge), verified against
the documented Audact API's ``audio``/``auth`` tags.

Uses ``respx`` to mock the transport for each target service so no real
network calls are made.
"""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pydantic
import pytest
import respx

from audact import AudactClient
from audact.client import AudioClient, AuthClient
from audact.exceptions import (
    AudactAPIError,
    AudactAuthError,
    AudactForbiddenError,
)
from audact.models import (
    AudioReconciliationRequest,
    AudioReconciliationResponse,
    AudioSegmentResult,
    ExchangeKeyResponse,
    RefreshTokenResponse,
    ValidateAudioRequest,
    ValidateAudioResponse,
)

AUDIO_BASE = "http://localhost:8086"
TENANT_MGMT_BASE = "http://localhost:8085"

CALL_ID = uuid4()
CONFIG_ID = uuid4()


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _error_response(status: int, code: str, message: str, **extra: object) -> httpx.Response:
    """The server's real nested error envelope."""
    body = {"code": code, "message": message, **extra}
    return httpx.Response(status, json={"error": body})


@pytest.fixture()
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_test123")


def test_audio_is_audio_client(client: AudactClient) -> None:
    assert isinstance(client.audio, AudioClient)


def test_auth_is_auth_client(client: AudactClient) -> None:
    assert isinstance(client.auth, AuthClient)


# ─────────────────────────────────────────────────────────────────────────────
# validate_audio — POST /v1/validate-audio (audio-validator :8086)
# ─────────────────────────────────────────────────────────────────────────────

def _validate_audio_response_payload(**overrides: object) -> dict:
    payload = {
        "verdict": "ALLOW",
        "segments": [
            {
                "segment_index": 0,
                "verdict": "ALLOW",
                "action": "forward",
                "audio_hash": "a" * 64,
                "text_hash": "b" * 64,
                "transcribed_text": "Hello, this is an automated call.",
                "asr_confidence": 0.94,
                "asr_model_id": "deepgram:nova-2",
                "segmentation_method": "asr_first",
                "check_results": [
                    {"check_id": "blocklist_scan", "verdict": "ALLOW", "reason": ""}
                ],
            }
        ],
        "receipt": {
            "verdict": "ALLOW",
            "input_hash": "c" * 64,
            "output_hash": "c" * 64,
            "text_hash": "b" * 64,
            "evidence_hash": "d" * 64,
            "asr_confidence": 0.94,
            "config_version": 1,
            "policy_version": "2026-01",
            "segmentation_method": "asr_first",
            "signature": "e" * 64,
        },
        "fail_open": False,
        "evidence_event_id": str(uuid4()),
        "evidence_hash": "d" * 64,
        "evidence_write_status": "success",
    }
    payload.update(overrides)
    return payload


class TestValidateAudio:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient) -> None:
        route = respx.post(f"{AUDIO_BASE}/v1/validate-audio").mock(
            return_value=_json_response(_validate_audio_response_payload())
        )

        req = ValidateAudioRequest(
            call_id=str(CALL_ID),
            turn_number=1,
            audio_data="UklGRiQAAABXQVZFZm10IBAAAAABAAEAgLsAAAB3AQACABAAZGF0YQAAAAA=",
            audio_format="wav",
        )
        result = await client.audio.validate_audio(req)

        assert route.called
        request = route.calls.last.request
        assert request.method == "POST"
        assert request.headers["Authorization"] == "Bearer aud_live_test123"
        sent_body = json.loads(request.content)
        assert sent_body["call_id"] == str(CALL_ID)
        assert sent_body["turn_number"] == 1
        assert sent_body["audio_format"] == "wav"
        assert "configuration_id" not in sent_body

        assert isinstance(result, ValidateAudioResponse)
        assert result.verdict == "ALLOW"
        assert len(result.segments) == 1
        assert result.segments[0].action == "forward"
        assert result.segments[0].check_results[0].check_id == "blocklist_scan"
        assert result.receipt is not None
        assert result.receipt.signature == "e" * 64
        assert result.evidence_write_status == "success"

    @pytest.mark.asyncio
    @respx.mock
    async def test_block_verdict_with_optional_fields(self, client: AudactClient) -> None:
        route = respx.post(f"{AUDIO_BASE}/v1/validate-audio").mock(
            return_value=_json_response(
                _validate_audio_response_payload(verdict="BLOCK", fail_open=True)
            )
        )

        req = ValidateAudioRequest(
            call_id=str(CALL_ID),
            turn_number=2,
            audio_data="//uQxAA==",
            audio_format="pcm_s16le_16000",
            configuration_id=CONFIG_ID,
            asr_provider="deepgram",
            segmentation_method="prosodic_first",
            parallel_asr=True,
            call_context={"language": "nl", "disclosure_delivered": True},
        )
        result = await client.audio.validate_audio(req)

        request = route.calls.last.request
        sent_body = json.loads(request.content)
        assert sent_body["configuration_id"] == str(CONFIG_ID)
        assert sent_body["asr_provider"] == "deepgram"
        assert sent_body["parallel_asr"] is True
        assert sent_body["call_context"] == {"language": "nl", "disclosure_delivered": True}
        assert result.verdict == "BLOCK"
        assert result.fail_open is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_bad_request_raises(self, client: AudactClient) -> None:
        respx.post(f"{AUDIO_BASE}/v1/validate-audio").mock(
            return_value=_error_response(400, "invalid_request", "missing audio_data")
        )
        req = ValidateAudioRequest(call_id=str(CALL_ID), turn_number=1, audio_data="")
        with pytest.raises(AudactAPIError) as exc_info:
            await client.audio.validate_audio(req)
        assert exc_info.value.status_code == 400
        assert exc_info.value.code == "invalid_request"

    @pytest.mark.asyncio
    @respx.mock
    async def test_unauthorized_raises(self, client: AudactClient) -> None:
        respx.post(f"{AUDIO_BASE}/v1/validate-audio").mock(
            return_value=_error_response(401, "unauthorized", "missing bearer token")
        )
        req = ValidateAudioRequest(call_id=str(CALL_ID), turn_number=1, audio_data="x")
        with pytest.raises(AudactAuthError):
            await client.audio.validate_audio(req)


# ─────────────────────────────────────────────────────────────────────────────
# reconcile_audio — POST /v1/audio-reconciliation (audio-validator :8086)
# ─────────────────────────────────────────────────────────────────────────────

def _reconciliation_response_payload(**overrides: object) -> dict:
    payload = {
        "call_id": str(CALL_ID),
        "total_segments": 12,
        "matched_segments": 10,
        "mismatched_segments": 1,
        "unvalidated_segments": 1,
        "has_more": False,
        "asr_confidence": 0.94,
        "asr_model_id": "deepgram:nova-2",
        "segment_results": [
            {
                "sequence_number": 1,
                "status": "matched",
                "transcript_hash": "a" * 64,
                "validated_hash": "a" * 64,
            },
            {
                "sequence_number": 2,
                "status": "mismatched",
                "mismatch_classification": "content_substitution",
                "transcript_hash": "b" * 64,
                "validated_hash": "c" * 64,
            },
        ],
    }
    payload.update(overrides)
    return payload


class TestReconcileAudio:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient) -> None:
        route = respx.post(f"{AUDIO_BASE}/v1/audio-reconciliation").mock(
            return_value=_json_response(_reconciliation_response_payload())
        )

        req = AudioReconciliationRequest(
            call_id=CALL_ID,
            audio_data="UklGRiQAAABXQVZFZm10IBAAAAABAAEAgLsAAAB3AQACABAAZGF0YQAAAAA=",
            audio_format="wav",
        )
        result = await client.audio.reconcile_audio(req)

        assert route.called
        request = route.calls.last.request
        assert request.method == "POST"
        assert request.headers["Authorization"] == "Bearer aud_live_test123"
        assert dict(request.url.params) == {}
        sent_body = json.loads(request.content)
        assert sent_body["call_id"] == str(CALL_ID)
        assert sent_body["audio_format"] == "wav"
        assert "configuration_id" not in sent_body

        assert isinstance(result, AudioReconciliationResponse)
        assert result.total_segments == 12
        assert result.matched_segments == 10
        assert result.mismatched_segments == 1
        assert len(result.segment_results) == 2
        assert result.segment_results[1].status == "mismatched"
        assert result.segment_results[1].mismatch_classification == "content_substitution"

    @pytest.mark.asyncio
    @respx.mock
    async def test_pagination_params_and_idempotency_key(self, client: AudactClient) -> None:
        route = respx.post(f"{AUDIO_BASE}/v1/audio-reconciliation").mock(
            return_value=_json_response(
                _reconciliation_response_payload(has_more=True, segment_results=[])
            )
        )

        req = AudioReconciliationRequest(
            call_id=CALL_ID,
            audio_data="x",
            audio_format="mp3",
            configuration_id=CONFIG_ID,
            asr_provider="deepgram",
            language="nl",
        )
        result = await client.audio.reconcile_audio(
            req, limit=50, after_sequence=10, idempotency_key="idem-key-audio-1"
        )

        request = route.calls.last.request
        assert dict(request.url.params) == {"limit": "50", "after_sequence": "10"}
        assert request.headers["Idempotency-Key"] == "idem-key-audio-1"
        sent_body = json.loads(request.content)
        assert sent_body["configuration_id"] == str(CONFIG_ID)
        assert sent_body["asr_provider"] == "deepgram"
        assert sent_body["language"] == "nl"
        assert result.has_more is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_forbidden_raises(self, client: AudactClient) -> None:
        respx.post(f"{AUDIO_BASE}/v1/audio-reconciliation").mock(
            return_value=_error_response(
                403, "forbidden", "call does not belong to authenticated tenant"
            )
        )
        req = AudioReconciliationRequest(call_id=CALL_ID, audio_data="x", audio_format="wav")
        with pytest.raises(AudactForbiddenError):
            await client.audio.reconcile_audio(req)

    @pytest.mark.asyncio
    @respx.mock
    async def test_bad_request_raises(self, client: AudactClient) -> None:
        respx.post(f"{AUDIO_BASE}/v1/audio-reconciliation").mock(
            return_value=_error_response(400, "invalid_request", "bad audio format")
        )
        req = AudioReconciliationRequest(call_id=CALL_ID, audio_data="", audio_format="wav")
        with pytest.raises(AudactAPIError) as exc_info:
            await client.audio.reconcile_audio(req)
        assert exc_info.value.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# exchange_key — POST /v1/auth/exchange-key (tenant-management :8085)
# ─────────────────────────────────────────────────────────────────────────────

class TestExchangeKey:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient) -> None:
        route = respx.post(f"{TENANT_MGMT_BASE}/v1/auth/exchange-key").mock(
            return_value=_json_response(
                {
                    "access_token": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJrZXktaWQifQ.sig",
                    "token_type": "Bearer",
                    "expires_in": 900,
                }
            )
        )

        result = await client.auth.exchange_key()

        assert route.called
        request = route.calls.last.request
        assert request.method == "POST"
        assert request.headers["Authorization"] == "Bearer aud_live_test123"
        assert isinstance(result, ExchangeKeyResponse)
        assert result.token_type == "Bearer"
        assert result.expires_in == 900
        assert result.access_token.startswith("eyJ")

    @pytest.mark.asyncio
    @respx.mock
    async def test_unauthorized_raises(self, client: AudactClient) -> None:
        respx.post(f"{TENANT_MGMT_BASE}/v1/auth/exchange-key").mock(
            return_value=_error_response(401, "unauthorized", "invalid api key")
        )
        with pytest.raises(AudactAuthError) as exc_info:
            await client.auth.exchange_key()
        assert exc_info.value.code == "unauthorized"


# ─────────────────────────────────────────────────────────────────────────────
# refresh_token — POST /v1/auth/refresh (tenant-management :8085)
# ─────────────────────────────────────────────────────────────────────────────

class TestRefreshToken:
    @pytest.mark.asyncio
    @respx.mock
    async def test_basic(self, client: AudactClient) -> None:
        route = respx.post(f"{TENANT_MGMT_BASE}/v1/auth/refresh").mock(
            return_value=_json_response(
                {
                    "access_token": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJrZXktaWQyIn0.sig2",
                    "token_type": "Bearer",
                    "expires_in": 900,
                }
            )
        )

        result = await client.auth.refresh_token()

        assert route.called
        assert route.calls.last.request.method == "POST"
        assert isinstance(result, RefreshTokenResponse)
        assert result.access_token.endswith("sig2")

    @pytest.mark.asyncio
    @respx.mock
    async def test_unauthorized_raises(self, client: AudactClient) -> None:
        respx.post(f"{TENANT_MGMT_BASE}/v1/auth/refresh").mock(
            return_value=_error_response(401, "unauthorized", "refresh token missing or expired")
        )
        with pytest.raises(AudactAuthError):
            await client.auth.refresh_token()

    @pytest.mark.asyncio
    @respx.mock
    async def test_cookie_from_exchange_key_carried_to_refresh(
        self, client: AudactClient
    ) -> None:
        """
        Positive control: the httpOnly refresh-token cookie set by
        ``exchange_key()`` is retained by the underlying ``httpx.AsyncClient``
        and automatically presented on a subsequent ``refresh_token()`` call
        made on the *same* ``AudactClient`` instance — no manual cookie
        plumbing required by the caller.
        """
        respx.post(f"{TENANT_MGMT_BASE}/v1/auth/exchange-key").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "access-1",
                    "token_type": "Bearer",
                    "expires_in": 900,
                },
                headers={
                    "Set-Cookie": "refresh_token=rt-abc123; HttpOnly; "
                    "SameSite=Strict; Path=/v1/auth"
                },
            )
        )
        refresh_route = respx.post(f"{TENANT_MGMT_BASE}/v1/auth/refresh").mock(
            return_value=_json_response(
                {"access_token": "access-2", "token_type": "Bearer", "expires_in": 900}
            )
        )

        await client.auth.exchange_key()
        await client.auth.refresh_token()

        refresh_request = refresh_route.calls.last.request
        assert "refresh_token=rt-abc123" in refresh_request.headers.get("cookie", "")


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"transcription_status": "transcribed"}, "transcribed"),
        ({"transcription_status": "no_speech"}, "no_speech"),
        ({}, None),
    ],
)
def test_audio_segment_result_transcription_status(payload: dict, expected: str | None) -> None:
    seg = AudioSegmentResult.model_validate({"segment_index": 0, **payload})
    assert seg.transcription_status == expected


def test_audio_segment_result_transcription_status_rejects_unknown() -> None:
    with pytest.raises(pydantic.ValidationError):
        AudioSegmentResult.model_validate({"transcription_status": "bogus"})
