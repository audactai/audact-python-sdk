"""
Tests for the evidence-layer completion surface: calls, recording,
summary, violations, article50, evidence-exports, c2pa, receipts, delivery,
transcript reconciliation, and the public Article-50 verification key.

Uses ``respx`` to mock the evidence-layer transport (``http://localhost:8083``)
so no real network calls are made.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import respx

from audact import AudactClient
from audact.exceptions import AudactNotFoundError
from audact.models import (
    Article50Report,
    C2PAHashDataAssertionData,
    C2PAManifest,
    CallDetail,
    CallRecord,
    CallSummary,
    ConfirmDeliveryRequest,
    GetReceiptResponse,
    Page,
    ProcessConfirmationResult,
    ReconcileTranscriptRequest,
    ReconcileTranscriptResponse,
    RecordingResponse,
    TurnDeliveryStatus,
    ViolationRecord,
)

BASE = "http://localhost:8083"

TENANT_ID = uuid4()
CALL_ID = uuid4()
EVENT_ID = uuid4()
NOW = datetime.now(tz=UTC).isoformat()


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _error_response(status: int, code: str, message: str) -> httpx.Response:
    """The server's real nested error envelope."""
    return httpx.Response(status, json={"error": {"code": code, "message": message}})


@pytest.fixture()
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_test123")


def _call_record_payload(**overrides) -> dict:
    payload = {
        "call_id": str(CALL_ID),
        "tenant_id": str(TENANT_ID),
        "direction": "inbound",
        "status": "completed",
        "started_at": NOW,
        "ended_at": NOW,
        "metadata": {"country": "DE"},
        "created_at": NOW,
    }
    payload.update(overrides)
    return payload


def _violation_payload(**overrides) -> dict:
    payload = {
        "call_id": str(CALL_ID),
        "tenant_id": str(TENANT_ID),
        "event_id": str(EVENT_ID),
        "event_type": "CHECK_RESULT",
        "sequence": 3,
        "hash": "a" * 64,
        "data": {"result": "BLOCK", "rule_id": "profanity_v2"},
        "timestamp": NOW,
    }
    payload.update(overrides)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# list_calls — GET /v1/calls (paginated, cursor convention)
# ─────────────────────────────────────────────────────────────────────────────

class TestListCalls:
    @pytest.mark.asyncio
    @respx.mock
    async def test_list_calls_basic(self, client: AudactClient):
        respx.get(f"{BASE}/v1/calls").mock(
            return_value=_json_response(
                {"calls": [_call_record_payload()], "has_more": False, "next_cursor": None}
            )
        )
        async with client as c:
            page = await c.list_calls()
        assert isinstance(page, Page)
        assert page.has_more is False
        assert page.next_cursor is None
        assert len(page.items) == 1
        assert isinstance(page.items[0], CallRecord)
        assert page.items[0].call_id == CALL_ID
        assert page.items[0].direction == "inbound"

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_calls_sends_filters_and_cursor(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {"calls": [], "has_more": True, "next_cursor": "cursor-2"}
            )

        respx.get(f"{BASE}/v1/calls").mock(side_effect=_handler)
        async with client as c:
            page = await c.list_calls(
                date_from="2026-06-01",
                date_to="2026-06-30",
                status="completed",
                verdict="BLOCK",
                shadow=True,
                country="DE",
                cursor="cursor-1",
                limit=25,
            )
        assert page.has_more is True
        assert page.next_cursor == "cursor-2"
        sent = dict(captured[0].url.params)
        assert sent == {
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
            "status": "completed",
            "verdict": "BLOCK",
            "shadow": "true",
            "country": "DE",
            "cursor": "cursor-1",
            "limit": "25",
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_calls_sends_auth_header(self, client: AudactClient):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return _json_response({"calls": [], "has_more": False, "next_cursor": None})

        respx.get(f"{BASE}/v1/calls").mock(side_effect=_handler)
        async with client as c:
            await c.list_calls()
        assert captured_headers[0]["authorization"] == "Bearer aud_live_test123"


# ─────────────────────────────────────────────────────────────────────────────
# get_call_detail — GET /v1/calls/{call_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestGetCallDetail:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_call_detail(self, client: AudactClient):
        payload = {
            "call_id": str(CALL_ID),
            "tenant_id": str(TENANT_ID),
            "direction": "outbound",
            "status": "completed",
            "connected": True,
            "termination_class": "answered",
            "started_at": NOW,
            "ended_at": NOW,
            "duration_ms": 332000,
            "metadata": {"country": "DE"},
            "recording_available": True,
            "recording_ref": "s3://bucket/key",
            "transcript": [{"role": "agent", "content": "Hello"}],
            "compliance_score": None,
            "evidence_link": "",
        }
        respx.get(f"{BASE}/v1/calls/{CALL_ID}").mock(return_value=_json_response(payload))
        async with client as c:
            detail = await c.get_call_detail(CALL_ID)
        assert isinstance(detail, CallDetail)
        assert detail.call_id == CALL_ID
        assert detail.connected is True
        assert detail.transcript[0].role == "agent"
        assert detail.transcript[0].content == "Hello"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_call_detail_not_found(self, client: AudactClient):
        respx.get(f"{BASE}/v1/calls/{CALL_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "call not found")
        )
        async with client as c:
            with pytest.raises(AudactNotFoundError) as exc_info:
                await c.get_call_detail(CALL_ID)
        assert exc_info.value.code == "NOT_FOUND"


# ─────────────────────────────────────────────────────────────────────────────
# get_call_recording / delete_call_recording
# ─────────────────────────────────────────────────────────────────────────────

class TestCallRecording:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_call_recording(self, client: AudactClient):
        payload = {
            "call_id": str(CALL_ID),
            "url": "https://s3.example.com/signed",
            "expires_at": NOW,
        }
        respx.get(f"{BASE}/v1/calls/{CALL_ID}/recording").mock(
            return_value=_json_response(payload)
        )
        async with client as c:
            recording = await c.get_call_recording(CALL_ID)
        assert isinstance(recording, RecordingResponse)
        assert recording.url == "https://s3.example.com/signed"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_call_recording_not_found(self, client: AudactClient):
        respx.get(f"{BASE}/v1/calls/{CALL_ID}/recording").mock(
            return_value=_error_response(404, "NOT_FOUND", "no recording")
        )
        async with client as c:
            with pytest.raises(AudactNotFoundError):
                await c.get_call_recording(CALL_ID)

    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_call_recording(self, client: AudactClient):
        route = respx.delete(f"{BASE}/v1/calls/{CALL_ID}/recording").mock(
            return_value=httpx.Response(204)
        )
        async with client as c:
            result = await c.delete_call_recording(CALL_ID)
        assert result is None
        assert route.called


# ─────────────────────────────────────────────────────────────────────────────
# get_call_summary
# ─────────────────────────────────────────────────────────────────────────────

class TestGetCallSummary:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_call_summary(self, client: AudactClient):
        payload = {
            "call_id": str(CALL_ID),
            "tenant_id": str(TENANT_ID),
            "status": "completed",
            "started_at": NOW,
            "ended_at": NOW,
            "event_count": 12,
            "allow_count": 9,
            "modify_count": 2,
            "block_count": 1,
            "handover": None,
            "call_end": None,
        }
        respx.get(f"{BASE}/v1/calls/{CALL_ID}/summary").mock(
            return_value=_json_response(payload)
        )
        async with client as c:
            summary = await c.get_call_summary(CALL_ID)
        assert isinstance(summary, CallSummary)
        assert summary.event_count == 12
        assert summary.allow_count == 9
        assert summary.handover is None
        assert summary.call_end is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_call_summary_with_handover(self, client: AudactClient):
        payload = {
            "call_id": str(CALL_ID),
            "tenant_id": str(TENANT_ID),
            "status": "completed",
            "started_at": NOW,
            "ended_at": NOW,
            "event_count": 4,
            "allow_count": 4,
            "modify_count": 0,
            "block_count": 0,
            "handover": {
                "handover_id": "hid-1",
                "handover_reason": "escalation_threshold_breach",
                "whisper_mode": False,
                "destination_hash": "abc",
                "summary_text": "Caller requested billing dispute [REDACTED]",
                "summary_source": "llm",
                "outcome": "bridged",
                "completed_at": NOW,
            },
            "call_end": None,
        }
        respx.get(f"{BASE}/v1/calls/{CALL_ID}/summary").mock(
            return_value=_json_response(payload)
        )
        async with client as c:
            summary = await c.get_call_summary(CALL_ID)
        assert summary.handover is not None
        assert summary.handover.outcome == "bridged"


# ─────────────────────────────────────────────────────────────────────────────
# list_violations — GET /v1/violations (paginated)
# ─────────────────────────────────────────────────────────────────────────────

class TestListViolations:
    @pytest.mark.asyncio
    @respx.mock
    async def test_list_violations_basic(self, client: AudactClient):
        respx.get(f"{BASE}/v1/violations").mock(
            return_value=_json_response(
                {"violations": [_violation_payload()], "has_more": False, "next_cursor": None}
            )
        )
        async with client as c:
            page = await c.list_violations()
        assert isinstance(page, Page)
        assert len(page.items) == 1
        assert isinstance(page.items[0], ViolationRecord)
        assert page.items[0].event_type == "CHECK_RESULT"
        assert page.items[0].data == {"result": "BLOCK", "rule_id": "profanity_v2"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_violations_sends_filters(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response({"violations": [], "has_more": False, "next_cursor": None})

        respx.get(f"{BASE}/v1/violations").mock(side_effect=_handler)
        async with client as c:
            await c.list_violations(
                call_id=CALL_ID,
                date_from="2026-06-01",
                date_to="2026-06-30",
                verdict="BLOCK",
                cursor="cursor-1",
                limit=10,
            )
        sent = dict(captured[0].url.params)
        assert sent == {
            "call_id": str(CALL_ID),
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
            "verdict": "BLOCK",
            "cursor": "cursor-1",
            "limit": "10",
        }


# ─────────────────────────────────────────────────────────────────────────────
# get_article50_report / get_evidence_export
# ─────────────────────────────────────────────────────────────────────────────

def _article50_report_payload(**overrides) -> dict:
    payload = {
        "report_type": "article_50_evidence_export",
        "report_format_version": "2.1.0",
        "call_id": str(CALL_ID),
        "tenant_id": str(TENANT_ID),
        "direction": "outbound",
        "generated_at": NOW,
        "configuration_seal": {
            "call_config_seal_hash": "a" * 64,
            "config_version": 3,
            "policy_version": "DE_v1.1.0",
            "seal_algorithm": "sha256-rfc8785",
        },
        "disclosure": {
            "status": "delivered",
            "delivered": True,
            "utterance": "This call may be handled by an AI assistant.",
            "language": "de-DE",
            "duration_ms": 3200,
            "played_at": NOW,
            "jurisdiction": "DE",
            "config_seal_hash": "a" * 64,
            "acknowledgement": {
                "type": "disclosure_delivered",
                "basis": "tts_emitted",
                "event_id": str(uuid4()),
                "event_hash": "b" * 64,
            },
        },
        "receipts": [
            {
                "event_id": str(EVENT_ID),
                "sequence": 1,
                "turn": 1,
                "verdict": "ALLOW",
                "receipt_format_version": "1.2.0",
                "input_hash": "c" * 64,
                "output_hash": "c" * 64,
                "auth_mechanism": "hmac-sha256",
                "signature": "d" * 64,
                "verifiability": "verifiable",
            }
        ],
        "evidence_chain": {
            "chain_status": "valid",
            "event_count": 5,
            "genesis_hash": "e" * 64,
            "head_hash": "f" * 64,
            "ordering": "sequence",
            "events": [],
        },
        "merkle_proof": {
            "status": "pending",
            "window_id": "",
            "merkle_root": "",
            "tenant_leaf": "",
            "available_after": NOW,
            "retrieve_via": "/v1/proofs/{window_id}",
        },
        "tsa_timestamp": {
            "status": "pending",
            "covers": "merkle_root",
            "timestamp_time": None,
            "timestamp_token": "",
            "tsa_url": "",
        },
        "signature": {
            "auth_mechanism": "ecdsa-p256",
            "key_id": "kid-1",
            "public_key_url": "https://api.audact.ai/v1/keys/kid-1",
            "scope": "audact-article50-report:2.1.0",
            "value": "0" * 10,
        },
    }
    payload.update(overrides)
    return payload


class TestArticle50Report:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_article50_report_json_default(self, client: AudactClient):
        respx.get(f"{BASE}/v1/calls/{CALL_ID}/article50-report").mock(
            return_value=_json_response(_article50_report_payload())
        )
        async with client as c:
            report = await c.get_article50_report(CALL_ID)
        assert isinstance(report, Article50Report)
        assert report.call_id == CALL_ID
        assert report.disclosure is not None
        assert report.disclosure.delivered is True
        assert report.receipts[0].verifiability == "verifiable"
        assert report.merkle_proof is not None
        assert report.merkle_proof.status == "pending"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_article50_report_pdf_returns_bytes(self, client: AudactClient):
        pdf_bytes = b"%PDF-1.4 fake pdf content"
        respx.get(f"{BASE}/v1/calls/{CALL_ID}/article50-report").mock(
            return_value=httpx.Response(
                200, content=pdf_bytes, headers={"Content-Type": "application/pdf"}
            )
        )
        async with client as c:
            result = await c.get_article50_report(CALL_ID, format="pdf")
        assert result == pdf_bytes

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_article50_report_sends_format_query_param(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_article50_report_payload())

        respx.get(f"{BASE}/v1/calls/{CALL_ID}/article50-report").mock(side_effect=_handler)
        async with client as c:
            await c.get_article50_report(CALL_ID, format="json")
        assert dict(captured[0].url.params) == {"format": "json"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_article50_report_not_completed(self, client: AudactClient):
        respx.get(f"{BASE}/v1/calls/{CALL_ID}/article50-report").mock(
            return_value=_error_response(422, "CALL_NOT_COMPLETED", "call has not completed")
        )
        async with client as c:
            with pytest.raises(Exception) as exc_info:
                await c.get_article50_report(CALL_ID)
        assert exc_info.value.status_code == 422  # type: ignore[attr-defined]


class TestGetEvidenceExport:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_evidence_export_json(self, client: AudactClient):
        respx.get(f"{BASE}/v1/evidence-exports/{CALL_ID}").mock(
            return_value=_json_response(_article50_report_payload())
        )
        async with client as c:
            report = await c.get_evidence_export(CALL_ID, "ev1.payload.sig")
        assert isinstance(report, Article50Report)
        assert report.call_id == CALL_ID

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_evidence_export_sends_token_query_param(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_article50_report_payload())

        respx.get(f"{BASE}/v1/evidence-exports/{CALL_ID}").mock(side_effect=_handler)
        async with client as c:
            await c.get_evidence_export(CALL_ID, "ev1.payload.sig", format="json")
        assert dict(captured[0].url.params) == {"token": "ev1.payload.sig", "format": "json"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_evidence_export_pdf(self, client: AudactClient):
        pdf_bytes = b"%PDF-1.4 fake"
        respx.get(f"{BASE}/v1/evidence-exports/{CALL_ID}").mock(
            return_value=httpx.Response(
                200, content=pdf_bytes, headers={"Content-Type": "application/pdf"}
            )
        )
        async with client as c:
            result = await c.get_evidence_export(CALL_ID, "ev1.payload.sig", format="pdf")
        assert result == pdf_bytes


# ─────────────────────────────────────────────────────────────────────────────
# generate_c2pa_manifest — POST /v1/calls/{call_id}/c2pa
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateC2PAManifest:
    @pytest.mark.asyncio
    @respx.mock
    async def test_generate_c2pa_manifest(self, client: AudactClient):
        payload = {
            "claim": {
                "claim_generator": "audact/1.0.0",
                "claim_generator_info": [{"name": "audact", "version": "1.0.0"}],
                "dc:format": "audio/wav",
                "dc:title": "Call recording",
            },
            "assertions": [
                {
                    "label": "com.audact.compliance",
                    "data": {
                        "call_id": str(CALL_ID),
                        "tenant_id": str(TENANT_ID),
                        "overall_compliance": "compliant",
                        "segments_validated": 5,
                        "segments_compliant": 5,
                        "segments_modified": 0,
                        "evidence_chain_verified": True,
                        "delivery_attestation_status": "attested",
                        "receipt_references": [
                            {
                                "event_id": str(EVENT_ID),
                                "receipt_hash": "a" * 64,
                                "verdict": "ALLOW",
                            }
                        ],
                        "merkle_proof_reference": None,
                    },
                }
            ],
            "signature_algorithm": "ES256",
            "generated_at": NOW,
        }
        route = respx.post(f"{BASE}/v1/calls/{CALL_ID}/c2pa").mock(
            return_value=_json_response(payload)
        )
        async with client as c:
            manifest = await c.generate_c2pa_manifest(CALL_ID)
            assert "idempotency-key" not in route.calls.last.request.headers
            await c.generate_c2pa_manifest(CALL_ID, idempotency_key="c2pa-idem-1")
            assert route.calls.last.request.headers["idempotency-key"] == "c2pa-idem-1"
        assert route.called
        assert isinstance(manifest, C2PAManifest)
        assert manifest.claim.dc_format == "audio/wav"
        assert manifest.assertions[0].data.overall_compliance == "compliant"
        assert manifest.assertions[0].data.receipt_references[0].verdict == "ALLOW"

    @pytest.mark.asyncio
    @respx.mock
    async def test_generate_c2pa_manifest_with_actions_assertion(self, client: AudactClient):
        """a manifest with a c2pa.actions assertion must parse, and
        compliance stays assertions[0]."""
        payload = {
            "claim": {
                "claim_generator": "Audact/1.1.0",
                "claim_generator_info": [{"name": "Audact", "version": "1.1.0"}],
                "dc:format": "audio/x-call-recording",
                "dc:title": f"Call {CALL_ID}",
            },
            "assertions": [
                {
                    "label": "com.audact.compliance",
                    "data": {
                        "call_id": str(CALL_ID),
                        "tenant_id": str(TENANT_ID),
                        "overall_compliance": "compliant",
                        "receipt_references": [],
                    },
                },
                {
                    "label": "c2pa.actions",
                    "data": {
                        "actions": [
                            {
                                "action": "c2pa.created",
                                "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/compositeSynthetic",
                                "softwareAgent": {"name": "Audact", "version": "1.1.0"},
                                "description": "Interaction between a human and an AI agent",
                            }
                        ]
                    },
                },
            ],
            "signature_algorithm": "ES256",
            "generated_at": NOW,
        }
        respx.post(f"{BASE}/v1/calls/{CALL_ID}/c2pa").mock(return_value=_json_response(payload))
        async with client as c:
            manifest = await c.generate_c2pa_manifest(CALL_ID)
        assert manifest.assertions[0].data.overall_compliance == "compliant"
        actions = manifest.assertions[1].data
        assert actions.actions[0].action == "c2pa.created"
        assert actions.actions[0].digitalSourceType.endswith("compositeSynthetic")

    @pytest.mark.asyncio
    @respx.mock
    async def test_generate_c2pa_manifest_es256_summary(self, client: AudactClient):
        mid = str(uuid4())
        payload = {
            "manifest_id": mid,
            "call_id": str(CALL_ID),
            "claim": {
                "claim_generator": "Audact/2.0.0",
                "claim_generator_info": [{"name": "Audact", "version": "2.0.0"}],
                "dc:format": "application/json",
                "dc:title": f"Call {CALL_ID}",
            },
            "assertions": [
                {
                    "label": "com.audact.compliance",
                    "data": {
                        "call_id": str(CALL_ID),
                        "tenant_id": str(TENANT_ID),
                        "overall_compliance": "compliant",
                    },
                },
                {"label": "c2pa.actions", "data": {"actions": [{"action": "c2pa.created"}]}},
                {
                    "label": "c2pa.hash.data",
                    "data": {"alg": "sha256", "hash": "ab" * 32, "name": "export.json"},
                },
            ],
            "signature_algorithm": "ES256",
            "asset": {
                "kind": "evidence_export",
                "media_type": "application/json",
                "sha256": "ab" * 32,
                "url": f"/v1/calls/{CALL_ID}/c2pa/{mid}/asset",
            },
            "manifest_store": {
                "media_type": "application/c2pa",
                "sha256": "cd" * 32,
                "url": f"/v1/calls/{CALL_ID}/c2pa/{mid}/manifest.c2pa",
            },
            "signing_credential": {
                "subject": "CN=Audact C2PA Claim Signer (staging),O=Audact,C=NL",
                "issuer": "CN=Audact C2PA Root CA (staging),O=Audact,C=NL",
                "serial": "1234",
                "not_before": NOW,
                "not_after": NOW,
                "fingerprint_sha256": "ef" * 32,
                "trust": "self_signed",
            },
            "generated_at": NOW,
        }
        respx.post(f"{BASE}/v1/calls/{CALL_ID}/c2pa").mock(return_value=_json_response(payload))
        # The REAL list shape (the manifest list item): no
        # claim, no assertions, signer subset only, no has_more.
        list_item = {
            "manifest_id": mid,
            "call_id": str(CALL_ID),
            "signature_algorithm": "ES256",
            "asset": payload["asset"],
            "manifest_store": payload["manifest_store"],
            "signing_credential": {"fingerprint_sha256": "ef" * 32, "trust": "self_signed"},
            "generated_at": NOW,
        }
        route = respx.get(f"{BASE}/v1/calls/{CALL_ID}/c2pa").mock(
            return_value=_json_response({"manifests": [list_item], "next_cursor": "c2"})
        )
        async with client as c:
            manifest = await c.generate_c2pa_manifest(CALL_ID)
            page = await c.list_c2pa_manifests(CALL_ID)
        assert manifest.manifest_id == mid
        assert manifest.signature_algorithm == "ES256"
        assert not hasattr(manifest, "signature")
        hash_data = manifest.assertions[2].data
        assert isinstance(hash_data, C2PAHashDataAssertionData)
        assert hash_data.alg == "sha256"
        assert manifest.asset is not None and manifest.asset.kind == "evidence_export"
        assert manifest.manifest_store is not None
        assert manifest.manifest_store.media_type == "application/c2pa"
        assert manifest.signing_credential is not None
        assert manifest.signing_credential.trust == "self_signed"
        assert route.called
        assert page.items[0].manifest_id == mid
        assert page.items[0].signing_credential.trust == "self_signed"
        assert page.has_more is True and page.next_cursor == "c2"

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_c2pa_manifest_store(self, client: AudactClient):
        data = b"\x00jumbf-bytes\xff"
        route = respx.get(f"{BASE}/v1/calls/{CALL_ID}/c2pa/m1/manifest.c2pa").mock(
            return_value=httpx.Response(
                200, content=data, headers={"Content-Type": "application/c2pa"}
            )
        )
        async with client as c:
            got = await c.download_c2pa_manifest_store(CALL_ID, "m1")
        assert route.called
        assert got == data

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_c2pa_asset_follows_redirect(self, client: AudactClient):
        data = b"OggS-recording"
        presigned = "https://s3.example.test/rec.ogg?X-Amz-Signature=abc"
        respx.get(f"{BASE}/v1/calls/{CALL_ID}/c2pa/m1/asset").mock(
            return_value=httpx.Response(302, headers={"Location": presigned})
        )
        target = respx.get(presigned).mock(return_value=httpx.Response(200, content=data))
        async with client as c:
            got = await c.download_c2pa_asset(CALL_ID, "m1")
        assert got == data
        assert "authorization" not in target.calls.last.request.headers

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_c2pa_trust_anchor(self, client: AudactClient):
        pem = "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n"
        route = respx.get(f"{BASE}/v1/c2pa/trust-anchor").mock(
            return_value=httpx.Response(
                200, text=pem, headers={"Content-Type": "application/x-pem-file"}
            )
        )
        async with client as c:
            got = await c.get_c2pa_trust_anchor()
        assert route.called
        assert got == pem

    @pytest.mark.asyncio
    @respx.mock
    async def test_generate_c2pa_manifest_unavailable(self, client: AudactClient):
        respx.post(f"{BASE}/v1/calls/{CALL_ID}/c2pa").mock(
            return_value=_error_response(503, "SIGNING_UNAVAILABLE", "manifest signing unavailable")
        )
        async with client as c:
            with pytest.raises(Exception) as exc_info:
                await c.generate_c2pa_manifest(CALL_ID)
        assert exc_info.value.status_code == 503  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────────
# get_receipt — GET /v1/receipts/{call_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestGetReceipt:
    def _receipt_payload(self, **overrides) -> dict:
        payload = {
            "receipt_format_version": "1.0.0",
            "call_id": str(CALL_ID),
            "timestamp": NOW,
            "input_hash": "a" * 64,
            "output_hash": "a" * 64,
            "verdict": "ALLOW",
            "config_version": 1,
            "config_seal_hash": "b" * 64,
            "policy_version": "DE_v1.1.0",
            "evidence_hash": "c" * 64,
            "auth_mechanism": "hmac-sha256",
            "signature": "d" * 64,
        }
        payload.update(overrides)
        return payload

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_receipt_verifiable(self, client: AudactClient):
        payload = {
            "receipt": self._receipt_payload(),
            "hmac_valid": True,
            "verifiability": "verifiable",
        }
        respx.get(f"{BASE}/v1/receipts/{CALL_ID}").mock(return_value=_json_response(payload))
        async with client as c:
            resp = await c.get_receipt(CALL_ID)
        assert isinstance(resp, GetReceiptResponse)
        assert resp.hmac_valid is True
        assert resp.verifiability == "verifiable"
        assert resp.receipt.call_id == CALL_ID

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_receipt_unverifiable_pre_horizon(self, client: AudactClient):
        """
        hmac_valid=False + verifiability="unverifiable_pre_horizon" must NOT
        be conflated with tampering.
        """
        payload = {
            "receipt": self._receipt_payload(),
            "hmac_valid": False,
            "verifiability": "unverifiable_pre_horizon",
        }
        respx.get(f"{BASE}/v1/receipts/{CALL_ID}").mock(return_value=_json_response(payload))
        async with client as c:
            resp = await c.get_receipt(CALL_ID)
        assert resp.hmac_valid is False
        assert resp.verifiability == "unverifiable_pre_horizon"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_receipt_not_found(self, client: AudactClient):
        respx.get(f"{BASE}/v1/receipts/{CALL_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "receipt not found")
        )
        async with client as c:
            with pytest.raises(AudactNotFoundError):
                await c.get_receipt(CALL_ID)


# ─────────────────────────────────────────────────────────────────────────────
# get_delivery_status / confirm_delivery
# ─────────────────────────────────────────────────────────────────────────────

class TestDelivery:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_delivery_status(self, client: AudactClient):
        payload = [
            {
                "turn_number": 1,
                "status": "confirmed",
                "mechanism": "webhook",
                "confirmation_grade": "independent",
                "content_match": True,
                "linking_hash": "a" * 64,
                "confirmed_at": NOW,
            }
        ]
        respx.get(f"{BASE}/v1/calls/{CALL_ID}/delivery").mock(return_value=_json_response(payload))
        async with client as c:
            statuses = await c.get_delivery_status(CALL_ID)
        assert len(statuses) == 1
        assert isinstance(statuses[0], TurnDeliveryStatus)
        assert statuses[0].status == "confirmed"
        assert statuses[0].content_match is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_delivery_status_empty(self, client: AudactClient):
        respx.get(f"{BASE}/v1/calls/{CALL_ID}/delivery").mock(return_value=_json_response([]))
        async with client as c:
            statuses = await c.get_delivery_status(CALL_ID)
        assert statuses == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_confirm_delivery(self, client: AudactClient):
        captured: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(json.loads(request.content))
            return httpx.Response(
                201,
                json={
                    "attestation_event_id": str(EVENT_ID),
                    "confirmation_grade": "independent",
                    "content_match": True,
                    "linking_hash": "a" * 64,
                },
            )

        respx.post(f"{BASE}/v1/delivery-confirmation").mock(side_effect=_handler)
        req = ConfirmDeliveryRequest(
            call_id=CALL_ID,
            turn_number=1,
            mechanism="webhook",
            delivered_text="Hello",
        )
        async with client as c:
            result = await c.confirm_delivery(req, idempotency_key="idem-1")
        assert isinstance(result, ProcessConfirmationResult)
        assert result.content_match is True
        assert result.attestation_event_id == EVENT_ID
        assert captured[0]["call_id"] == str(CALL_ID)
        assert captured[0]["mechanism"] == "webhook"

    @pytest.mark.asyncio
    @respx.mock
    async def test_confirm_delivery_sends_idempotency_key_header(self, client: AudactClient):
        captured_headers: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return httpx.Response(
                201,
                json={
                    "attestation_event_id": str(EVENT_ID),
                    "confirmation_grade": "independent",
                    "content_match": True,
                },
            )

        respx.post(f"{BASE}/v1/delivery-confirmation").mock(side_effect=_handler)
        req = ConfirmDeliveryRequest(call_id=CALL_ID, turn_number=1, mechanism="webhook")
        async with client as c:
            await c.confirm_delivery(req, idempotency_key="idem-2")
        assert captured_headers[0]["idempotency-key"] == "idem-2"


# ─────────────────────────────────────────────────────────────────────────────
# reconcile_transcript — POST /v1/transcript-reconciliation
# ─────────────────────────────────────────────────────────────────────────────

class TestReconcileTranscript:
    @pytest.mark.asyncio
    @respx.mock
    async def test_reconcile_transcript(self, client: AudactClient):
        captured: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(json.loads(request.content))
            return _json_response(
                {
                    "call_id": str(CALL_ID),
                    "total_segments": 2,
                    "matched_segments": 1,
                    "mismatched_segments": 1,
                    "unvalidated_segments": 0,
                    "segment_results": [
                        {"turn_number": 1, "matched": True, "reason": ""},
                        {"turn_number": 2, "matched": False, "reason": "content mismatch"},
                    ],
                }
            )

        respx.post(f"{BASE}/v1/transcript-reconciliation").mock(side_effect=_handler)
        req = ReconcileTranscriptRequest(
            call_id=CALL_ID,
            segments=[
                {"turn_number": 1, "text": "hello", "speaker": "agent"},
                {"turn_number": 2, "text": "world", "speaker": "human"},
            ],
            source="post_call_webhook",
        )
        async with client as c:
            result = await c.reconcile_transcript(req)
        assert isinstance(result, ReconcileTranscriptResponse)
        assert result.total_segments == 2
        assert result.mismatched_segments == 1
        assert result.segment_results[1].matched is False
        assert captured[0]["call_id"] == str(CALL_ID)
        assert captured[0]["source"] == "post_call_webhook"
        assert len(captured[0]["segments"]) == 2


# ─────────────────────────────────────────────────────────────────────────────
# get_article50_public_key — GET /v1/keys/{kid} (public, unauthenticated)
# ─────────────────────────────────────────────────────────────────────────────

class TestGetArticle50PublicKey:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_article50_public_key(self, client: AudactClient):
        pem = "-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQ==\n-----END PUBLIC KEY-----"
        respx.get(f"{BASE}/v1/keys/kid-1").mock(
            return_value=httpx.Response(
                200, text=pem, headers={"Content-Type": "application/x-pem-file"}
            )
        )
        async with client as c:
            result = await c.get_article50_public_key("kid-1")
        assert result == pem

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_article50_public_key_url_encodes_kid(self, client: AudactClient):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, text="PEM")

        respx.get(f"{BASE}/v1/keys/kid%2Fwith%2Fslashes").mock(side_effect=_handler)
        async with client as c:
            await c.get_article50_public_key("kid/with/slashes")
        assert captured[0].url.raw_path == b"/v1/keys/kid%2Fwith%2Fslashes"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_article50_public_key_not_found(self, client: AudactClient):
        respx.get(f"{BASE}/v1/keys/unknown-kid").mock(
            return_value=_error_response(404, "NOT_FOUND", "unknown key_id")
        )
        async with client as c:
            with pytest.raises(AudactNotFoundError):
                await c.get_article50_public_key("unknown-kid")


# ─── list_compliance_events ────────────────────────────────────────

def _compliance_event_payload() -> dict:
    return {
        "agent_id": "",
        "call_id": str(CALL_ID),
        "check_id": "chk_1",
        "compliance_score": 0.4,
        "detail": "blocked",
        "event_subtype": "violation_detected",
        "severity": "high",
        "timestamp": "2026-10-01T10:00:00Z",
        "turn_sequence": 3,
        "verdict": "BLOCK",
    }


class TestListComplianceEvents:
    @pytest.mark.asyncio
    @respx.mock
    async def test_filters_auth_and_decode(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/compliance/events").mock(
            return_value=_json_response(
                {
                    "events": [_compliance_event_payload()],
                    "has_more": True,
                    "next_cursor": "c2",
                    "total": 9,
                }
            )
        )
        async with client as c:
            out = await c.list_compliance_events(
                event_subtype="violation_detected",
                verdict="BLOCK",
                severity="high",
                call_id=str(CALL_ID),
                cursor="c1",
                limit=5,
            )
        req = route.calls.last.request
        assert req.method == "GET"
        assert dict(req.url.params) == {
            "event_subtype": "violation_detected",
            "verdict": "BLOCK",
            "severity": "high",
            "call_id": str(CALL_ID),
            "cursor": "c1",
            "limit": "5",
        }
        assert req.headers["Authorization"].startswith("Bearer ")
        assert out.total == 9 and out.next_cursor == "c2"
        assert out.events[0].verdict == "BLOCK" and out.events[0].turn_sequence == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_decodes_allow_event_with_omitted_fields(self, client: AudactClient):
        # An ALLOW turn as the server serialises it (omitempty): no check_id,
        # severity, detail or compliance_score; and one with no turn or call either.
        allow = {
            "agent_id": "",
            "call_id": str(CALL_ID),
            "event_subtype": "validation_completed",
            "timestamp": "2026-10-01T10:00:01Z",
            "turn_sequence": 2,
            "verdict": "ALLOW",
        }
        bare = {
            "agent_id": "",
            "event_subtype": "fail_open",
            "timestamp": "2026-10-01T10:00:02Z",
            "severity": "",
            "verdict": "",
        }
        respx.get(f"{BASE}/v1/compliance/events").mock(
            return_value=_json_response(
                {
                    "events": [allow, bare, _compliance_event_payload()],
                    "has_more": False,
                    "total": 3,
                }
            )
        )
        async with client as c:
            out = await c.list_compliance_events()
        ev_allow, ev_bare, ev_block = out.events
        assert ev_allow.verdict == "ALLOW" and ev_allow.turn_sequence == 2
        assert ev_allow.check_id is None and ev_allow.severity is None
        assert ev_allow.detail is None and ev_allow.compliance_score is None
        assert ev_bare.call_id is None and ev_bare.turn_sequence is None
        assert ev_bare.severity is None and ev_bare.verdict is None
        assert ev_block.severity == "high" and ev_block.compliance_score == 0.4

    @pytest.mark.asyncio
    @respx.mock
    async def test_omitted_filters_absent(self, client: AudactClient):
        route = respx.get(f"{BASE}/v1/compliance/events").mock(
            return_value=_json_response({"events": [], "has_more": False, "total": 0})
        )
        async with client as c:
            out = await c.list_compliance_events()
        assert route.calls.last.request.url.query == b""
        assert out.events == [] and out.next_cursor is None
