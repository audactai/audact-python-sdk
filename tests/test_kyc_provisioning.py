"""
Tests for the KYC document + number-provisioning surface.

Covers every KYC and number-provisioning method, with particular emphasis on the
**net-new multipart support**: ``upload_kyc_document`` and
``replace_kyc_document`` are the first SDK methods to send a
``multipart/form-data`` body, so their tests assert on the *recorded*
request's ``Content-Type`` and file part as a positive control that the
``files=`` wiring through ``_request`` actually works — not just that the
mocked response happens to parse.

Uses ``respx`` to mock the voice-gateway transport so no real network calls
are made.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
import respx

from audact import AudactClient
from audact.exceptions import AudactAPIError, AudactTimeoutError
from audact.models import (
    AvailableNumber,
    CreateKYCDocumentSetRequest,
    CreateNumberOrderRequest,
    KYCDocument,
    KYCDocumentSet,
    KYCDocumentSetItemRequest,
    KYCRequirement,
    NumberOrder,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures & helpers
# ─────────────────────────────────────────────────────────────────────────────

BASE = "http://localhost:8088"

DOC_ID = uuid4()
SET_ID = uuid4()
ORDER_ID = uuid4()
NOW = datetime.now(tz=UTC).isoformat()


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _error_response(
    status: int, code: str, message: str, details: dict | None = None
) -> httpx.Response:
    """
    Build a response with the server's REAL nested error envelope:
    ``{"error": {"code", "message", "details"}}``.
    The old fixture nested nothing, which does not match production — see
    ``tests/test_errors.py`` for the error-envelope positive control.
    """
    error: dict = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return httpx.Response(status, json={"error": error})


def _doc_payload(doc_id: UUID = DOC_ID, **overrides) -> dict:
    payload = {
        "id": str(doc_id),
        "doc_type": "passport",
        "filename": "passport.pdf",
        "content_type": "application/pdf",
        "size_bytes": 1234,
        "sha256": "a" * 64,
        "telnyx_document_id": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    payload.update(overrides)
    return payload


def _set_payload(set_id: UUID = SET_ID, **overrides) -> dict:
    payload = {
        "id": str(set_id),
        "name": "NL mobile KYC",
        "country_code": "NL",
        "number_type": "mobile",
        "action": "kyc_requirement_group_create",
        "telnyx_requirement_group_id": None,
        "status": "submitted",
        "status_detail": None,
        "items": [],
        "created_at": NOW,
        "updated_at": NOW,
    }
    payload.update(overrides)
    return payload


def _order_payload(order_id: UUID = ORDER_ID, **overrides) -> dict:
    payload = {
        "id": str(order_id),
        "country_code": "NL",
        "number_type": "mobile",
        "set_id": str(SET_ID),
        "phone_number": None,
        "telnyx_order_id": None,
        "status": "pending",
        "failure_reason": None,
        "phone_number_id": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def client() -> AudactClient:
    return AudactClient(api_key="aud_live_test123")


# ─────────────────────────────────────────────────────────────────────────────
# KYC documents — list / get / delete
# ─────────────────────────────────────────────────────────────────────────────

class TestKYCDocumentsReadDelete:
    @pytest.mark.asyncio
    @respx.mock
    async def test_list_kyc_documents(self):
        respx.get(f"{BASE}/v1/kyc/documents").mock(
            return_value=_json_response({"documents": [_doc_payload()]})
        )
        async with AudactClient(api_key="key") as c:
            docs = await c.list_kyc_documents()
        assert docs == [KYCDocument.model_validate(_doc_payload())]
        assert isinstance(docs[0], KYCDocument)
        assert docs[0].sha256 == "a" * 64

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_kyc_documents_empty(self):
        respx.get(f"{BASE}/v1/kyc/documents").mock(
            return_value=_json_response({"documents": []})
        )
        async with AudactClient(api_key="key") as c:
            docs = await c.list_kyc_documents()
        assert docs == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_kyc_document(self):
        respx.get(f"{BASE}/v1/kyc/documents/{DOC_ID}").mock(
            return_value=_json_response(_doc_payload())
        )
        async with AudactClient(api_key="key") as c:
            doc = await c.get_kyc_document(DOC_ID)
        assert isinstance(doc, KYCDocument)
        assert doc.id == DOC_ID
        assert doc.doc_type == "passport"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_kyc_document_not_found(self):
        respx.get(f"{BASE}/v1/kyc/documents/{DOC_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "document not found")
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.get_kyc_document(DOC_ID)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_kyc_document(self):
        respx.delete(f"{BASE}/v1/kyc/documents/{DOC_ID}").mock(
            return_value=httpx.Response(204)
        )
        async with AudactClient(api_key="key") as c:
            result = await c.delete_kyc_document(DOC_ID)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_kyc_document_in_use_conflict(self):
        """A document backing an in-flight order (or still set-referenced) surfaces 409."""
        respx.delete(f"{BASE}/v1/kyc/documents/{DOC_ID}").mock(
            return_value=_error_response(
                409, "document_in_use", "document is referenced by an in-flight number order"
            )
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.delete_kyc_document(DOC_ID)
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "document_in_use"


# ─────────────────────────────────────────────────────────────────────────────
# KYC documents — upload / replace (multipart — the net-new wiring)
# ─────────────────────────────────────────────────────────────────────────────

class TestKYCDocumentMultipartUpload:
    @pytest.mark.asyncio
    @respx.mock
    async def test_upload_kyc_document_sends_multipart(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_doc_payload())

        respx.post(f"{BASE}/v1/kyc/documents").mock(side_effect=_handler)

        async with AudactClient(api_key="key") as c:
            doc = await c.upload_kyc_document(
                b"%PDF-1.4 fake passport bytes",
                doc_type="passport",
                filename="passport.pdf",
                content_type="application/pdf",
            )

        assert isinstance(doc, KYCDocument)
        assert doc.id == DOC_ID

        request = captured[0]
        content_type = request.headers["content-type"]
        # Positive control: httpx must have written a real multipart boundary
        # header itself (never a manually-set application/json body).
        assert content_type.startswith("multipart/form-data")
        assert "boundary=" in content_type

        body = request.content
        assert b'name="file"' in body
        assert b'filename="passport.pdf"' in body
        assert b"application/pdf" in body
        assert b"%PDF-1.4 fake passport bytes" in body
        # The doc_type form field must ride alongside the file part.
        assert b'name="doc_type"' in body
        assert b"passport" in body

    @pytest.mark.asyncio
    @respx.mock
    async def test_upload_kyc_document_defaults_filename_and_content_type(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_doc_payload())

        respx.post(f"{BASE}/v1/kyc/documents").mock(side_effect=_handler)

        async with AudactClient(api_key="key") as c:
            await c.upload_kyc_document(b"raw bytes, no metadata", doc_type="proof_of_address")

        body = captured[0].content
        assert b'filename="upload"' in body
        assert b"application/octet-stream" in body

    @pytest.mark.asyncio
    @respx.mock
    async def test_upload_kyc_document_idempotency_key_header(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_doc_payload())

        respx.post(f"{BASE}/v1/kyc/documents").mock(side_effect=_handler)

        async with AudactClient(api_key="key") as c:
            await c.upload_kyc_document(
                b"bytes", doc_type="passport", idempotency_key="idem-kyc-1"
            )

        assert captured[0].headers["idempotency-key"] == "idem-kyc-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_replace_kyc_document_sends_multipart_put(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_doc_payload())

        respx.put(f"{BASE}/v1/kyc/documents/{DOC_ID}").mock(side_effect=_handler)

        async with AudactClient(api_key="key") as c:
            doc = await c.replace_kyc_document(
                DOC_ID,
                b"replacement bytes",
                filename="passport-v2.pdf",
                content_type="application/pdf",
            )

        assert isinstance(doc, KYCDocument)
        request = captured[0]
        assert request.method == "PUT"
        content_type = request.headers["content-type"]
        assert content_type.startswith("multipart/form-data")
        body = request.content
        assert b'name="file"' in body
        assert b'filename="passport-v2.pdf"' in body
        assert b"replacement bytes" in body

    @pytest.mark.asyncio
    @respx.mock
    async def test_replace_kyc_document_in_use_conflict(self):
        respx.put(f"{BASE}/v1/kyc/documents/{DOC_ID}").mock(
            return_value=_error_response(
                409, "document_in_use", "document backs an in-flight number order"
            )
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.replace_kyc_document(DOC_ID, b"bytes")
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "document_in_use"

    @pytest.mark.asyncio
    @respx.mock
    async def test_upload_kyc_document_uses_file_handle_name(self, tmp_path):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_doc_payload())

        respx.post(f"{BASE}/v1/kyc/documents").mock(side_effect=_handler)

        file_path = tmp_path / "id-card.jpg"
        file_path.write_bytes(b"fake image bytes")

        async with AudactClient(api_key="key") as c:
            with open(file_path, "rb") as fh:
                await c.upload_kyc_document(fh, doc_type="id_card")

        assert b'filename="id-card.jpg"' in captured[0].content


# ─────────────────────────────────────────────────────────────────────────────
# KYC requirements
# ─────────────────────────────────────────────────────────────────────────────

class TestKYCRequirements:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_kyc_requirements(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {
                    "requirements": [
                        {
                            "id": "req-1",
                            "requirement_type": "document",
                            "name": "Proof of ID",
                            "required": True,
                        }
                    ]
                }
            )

        respx.get(f"{BASE}/v1/kyc/requirements").mock(side_effect=_handler)

        async with AudactClient(api_key="key") as c:
            reqs = await c.get_kyc_requirements(country="NL", number_type="mobile")

        assert reqs == [
            KYCRequirement(
                id="req-1", requirement_type="document", name="Proof of ID", required=True
            )
        ]
        assert dict(captured[0].url.params) == {"country": "NL", "number_type": "mobile"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_kyc_requirements_legitimately_empty(self):
        """Zero requirements must round-trip as an explicit empty list, not an error."""
        respx.get(f"{BASE}/v1/kyc/requirements").mock(
            return_value=_json_response({"requirements": []})
        )
        async with AudactClient(api_key="key") as c:
            reqs = await c.get_kyc_requirements(country="US", number_type="toll_free")
        assert reqs == []


# ─────────────────────────────────────────────────────────────────────────────
# KYC document sets
# ─────────────────────────────────────────────────────────────────────────────

class TestKYCDocumentSets:
    @pytest.mark.asyncio
    @respx.mock
    async def test_list_kyc_document_sets(self):
        respx.get(f"{BASE}/v1/kyc/document-sets").mock(
            return_value=_json_response({"document_sets": [_set_payload()]})
        )
        async with AudactClient(api_key="key") as c:
            sets = await c.list_kyc_document_sets()
        assert isinstance(sets[0], KYCDocumentSet)
        assert sets[0].status == "submitted"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_kyc_document_set(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_set_payload())

        respx.post(f"{BASE}/v1/kyc/document-sets").mock(side_effect=_handler)

        req = CreateKYCDocumentSetRequest(
            name="NL mobile KYC",
            country_code="NL",
            number_type="mobile",
            items=[KYCDocumentSetItemRequest(requirement_id="req-1", document_id=DOC_ID)],
        )

        async with AudactClient(api_key="key") as c:
            doc_set = await c.create_kyc_document_set(req)

        assert isinstance(doc_set, KYCDocumentSet)
        assert doc_set.id == SET_ID
        assert doc_set.status == "submitted"

        sent = captured[0]
        assert sent.headers["content-type"] == "application/json"
        import json

        body = json.loads(sent.content)
        assert body["name"] == "NL mobile KYC"
        assert body["items"][0]["document_id"] == str(DOC_ID)

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_kyc_document_set_missing_requirement_422(self):
        """A missing REQUIRED requirement surfaces 422 with details.missing."""
        respx.post(f"{BASE}/v1/kyc/document-sets").mock(
            return_value=_error_response(
                422,
                "missing_requirement",
                "one or more required requirements are unsatisfied",
                details={"missing": ["req-2", "req-3"]},
            )
        )
        req = CreateKYCDocumentSetRequest(
            name="NL mobile KYC",
            country_code="NL",
            number_type="mobile",
            items=[KYCDocumentSetItemRequest(requirement_id="req-1", document_id=DOC_ID)],
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.create_kyc_document_set(req)

        assert exc_info.value.status_code == 422
        assert exc_info.value.code == "missing_requirement"
        assert exc_info.value.details["missing"] == ["req-2", "req-3"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_kyc_document_set(self):
        respx.get(f"{BASE}/v1/kyc/document-sets/{SET_ID}").mock(
            return_value=_json_response(
                _set_payload(
                    items=[
                        {
                            "requirement_id": "req-1",
                            "requirement_type": "document",
                            "document_id": str(DOC_ID),
                            "document_filename": "passport.pdf",
                            "doc_type": "passport",
                            "text_value": None,
                        }
                    ]
                )
            )
        )
        async with AudactClient(api_key="key") as c:
            doc_set = await c.get_kyc_document_set(SET_ID)
        assert doc_set.items[0].document_id == DOC_ID

    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_kyc_document_set(self):
        respx.delete(f"{BASE}/v1/kyc/document-sets/{SET_ID}").mock(
            return_value=httpx.Response(204)
        )
        async with AudactClient(api_key="key") as c:
            result = await c.delete_kyc_document_set(SET_ID)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_kyc_document_set_in_flight_conflict(self):
        respx.delete(f"{BASE}/v1/kyc/document-sets/{SET_ID}").mock(
            return_value=_error_response(
                409, "set_in_use", "set is referenced by an in-flight number order"
            )
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.delete_kyc_document_set(SET_ID)
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "set_in_use"

    @pytest.mark.asyncio
    @respx.mock
    async def test_rotate_kyc_dek(self):
        respx.post(f"{BASE}/v1/kyc/dek/rotate").mock(
            return_value=_json_response({"new_version": 3})
        )
        async with AudactClient(api_key="key") as c:
            new_version = await c.rotate_kyc_dek()
        assert new_version == 3


# ─────────────────────────────────────────────────────────────────────────────
# Number provisioning
# ─────────────────────────────────────────────────────────────────────────────

class TestNumberProvisioning:
    @pytest.mark.asyncio
    @respx.mock
    async def test_list_available_numbers(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(
                {
                    "numbers": [
                        {
                            "phone_number": "+31612345678",
                            "phone_number_type": "mobile",
                            "country_code": "NL",
                        }
                    ]
                }
            )

        respx.get(f"{BASE}/v1/numbers/available").mock(side_effect=_handler)

        async with AudactClient(api_key="key") as c:
            numbers = await c.list_available_numbers(country="NL", number_type="mobile")

        assert numbers == [
            AvailableNumber(
                phone_number="+31612345678", phone_number_type="mobile", country_code="NL"
            )
        ]
        assert dict(captured[0].url.params) == {"country": "NL", "number_type": "mobile"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_available_numbers_legitimately_empty(self):
        respx.get(f"{BASE}/v1/numbers/available").mock(
            return_value=_json_response({"numbers": []})
        )
        async with AudactClient(api_key="key") as c:
            numbers = await c.list_available_numbers(country="NL", number_type="mobile")
        assert numbers == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_number_order(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_order_payload())

        respx.post(f"{BASE}/v1/numbers/orders").mock(side_effect=_handler)

        req = CreateNumberOrderRequest(country_code="NL", number_type="mobile", set_id=SET_ID)
        async with AudactClient(api_key="key") as c:
            order = await c.create_number_order(req)

        assert isinstance(order, NumberOrder)
        assert order.status == "pending"
        assert order.set_id == SET_ID

        import json

        body = json.loads(captured[0].content)
        assert body["set_id"] == str(SET_ID)
        assert "phone_number" not in body  # exclude_none — omitted, not sent as null

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_number_order_idempotency_key_header(self):
        captured: list[httpx.Request] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(_order_payload())

        respx.post(f"{BASE}/v1/numbers/orders").mock(side_effect=_handler)

        req = CreateNumberOrderRequest(country_code="NL", number_type="mobile", set_id=SET_ID)
        async with AudactClient(api_key="key") as c:
            await c.create_number_order(req, idempotency_key="idem-order-1")

        assert captured[0].headers["idempotency-key"] == "idem-order-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_number_order_invalid_number_type_400(self):
        respx.post(f"{BASE}/v1/numbers/orders").mock(
            return_value=_error_response(
                400,
                "invalid_number_type",
                "number_type is not a recognized Telnyx phone_number_type",
            )
        )
        req = CreateNumberOrderRequest(
            country_code="NL", number_type="not_a_real_type", set_id=SET_ID
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.create_number_order(req)

        assert exc_info.value.status_code == 400
        assert exc_info.value.code == "invalid_number_type"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_number_order_set_in_use_409(self):
        """A set already backing another in-flight order is surfaced as 409."""
        respx.post(f"{BASE}/v1/numbers/orders").mock(
            return_value=_error_response(
                409, "set_in_use", "document set already backs an in-flight number order"
            )
        )
        req = CreateNumberOrderRequest(country_code="NL", number_type="mobile", set_id=SET_ID)
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.create_number_order(req)

        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "set_in_use"

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_number_orders(self):
        respx.get(f"{BASE}/v1/numbers/orders").mock(
            return_value=_json_response({"orders": [_order_payload()]})
        )
        async with AudactClient(api_key="key") as c:
            orders = await c.list_number_orders()
        assert isinstance(orders[0], NumberOrder)
        assert orders[0].id == ORDER_ID

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_number_order(self):
        respx.get(f"{BASE}/v1/numbers/orders/{ORDER_ID}").mock(
            return_value=_json_response(
                _order_payload(status="success", phone_number="+31612345678")
            )
        )
        async with AudactClient(api_key="key") as c:
            order = await c.get_number_order(ORDER_ID)
        assert order.status == "success"
        assert order.phone_number == "+31612345678"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_number_order_not_found(self):
        respx.get(f"{BASE}/v1/numbers/orders/{ORDER_ID}").mock(
            return_value=_error_response(404, "NOT_FOUND", "order not found")
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactAPIError) as exc_info:
                await c.get_number_order(ORDER_ID)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# wait_for_order polling
# ─────────────────────────────────────────────────────────────────────────────

class TestWaitForOrder:
    @pytest.mark.asyncio
    @respx.mock
    async def test_wait_for_order_polls_until_terminal(self):
        statuses = iter(["pending", "ordering", "success"])

        def _handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
            return _json_response(_order_payload(status=next(statuses)))

        respx.get(f"{BASE}/v1/numbers/orders/{ORDER_ID}").mock(side_effect=_handler)

        async with AudactClient(api_key="key") as c:
            order = await c.wait_for_order(ORDER_ID, timeout=5.0, poll_interval=0.0)

        assert order.status == "success"

    @pytest.mark.asyncio
    @respx.mock
    async def test_wait_for_order_returns_immediately_on_terminal_failure(self):
        respx.get(f"{BASE}/v1/numbers/orders/{ORDER_ID}").mock(
            return_value=_json_response(
                _order_payload(status="failure", failure_reason="telnyx_rejected")
            )
        )
        async with AudactClient(api_key="key") as c:
            order = await c.wait_for_order(ORDER_ID, timeout=5.0, poll_interval=0.0)
        assert order.status == "failure"
        assert order.failure_reason == "telnyx_rejected"

    @pytest.mark.asyncio
    @respx.mock
    async def test_wait_for_order_times_out(self):
        respx.get(f"{BASE}/v1/numbers/orders/{ORDER_ID}").mock(
            return_value=_json_response(_order_payload(status="pending"))
        )
        async with AudactClient(api_key="key") as c:
            with pytest.raises(AudactTimeoutError):
                await c.wait_for_order(ORDER_ID, timeout=0.05, poll_interval=0.01)
