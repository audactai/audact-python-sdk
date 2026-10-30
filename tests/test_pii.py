"""client_hash/normalize parity with Go, PII methods, call identifiers."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import respx

from audact import AudactClient
from audact.models import (
    BrowserCallRequest,
    CallIdentifier,
    OutboundCallRequest,
    PIIExemption,
    PIISettingsHistoryEntry,
    PIIShredRecord,
)
from audact.pii import client_hash, normalize_identifier

VECTORS_PATH = Path(__file__).resolve().parent / "testdata" / "pii_normalize_vectors.json"
VECTORS = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
H = "a" * 64


def _check(v: dict) -> None:
    if v.get("error"):
        with pytest.raises(ValueError):
            client_hash(v["type"], v["input"])
        return
    assert normalize_identifier(v["type"], v["input"]) == v["normalized"]
    assert client_hash(v["type"], v["input"]) == v["client_hash"]


def test_vectors_file_nonempty() -> None:
    assert len(VECTORS) >= 19


@pytest.mark.parametrize("v", VECTORS, ids=lambda v: f"{v['type']}:{v['input']!r}")
def test_shared_vectors(v: dict) -> None:
    _check(v)


def test_positive_control_mutated_vector_fails() -> None:
    good = next(v for v in VECTORS if not v.get("error"))
    mutated = dict(
        good, client_hash=("0" if good["client_hash"][0] != "0" else "1") + good["client_hash"][1:]
    )
    with pytest.raises(AssertionError):
        _check(mutated)
    mutated_err = dict(good, error=True)
    with pytest.raises(pytest.fail.Exception):
        _check(mutated_err)


def test_unsupported_type() -> None:
    with pytest.raises(ValueError):
        normalize_identifier("call", "x")


def test_go_lowercase_edge_cases() -> None:
    # str.lower() would give a final "ς" and "i" + U+0307; Go maps per code point.
    assert normalize_identifier("name", "ΟΔΥΣΣΕΥΣ") == "οδυσσευσ"
    assert normalize_identifier("name", "İstanbul") == "istanbul"
    assert normalize_identifier("email", "İlker@Example.com.tr") == "ilker@example.com.tr"
    # Unicode 16 letters (absent from Go 1.25's Unicode 15 tables) stay unchanged.
    assert normalize_identifier("name", "\U00010d50") == "\U00010d50"


def test_nfd_equals_nfc() -> None:
    assert client_hash("name", "Émile") == client_hash("name", "Émile")


def test_call_identifiers_serialised() -> None:
    ident = CallIdentifier(type="phone", hash=H)
    for req in (
        OutboundCallRequest(
            from_number="+31600000000", destination_number="+31611111111", identifiers=[ident]
        ),
        BrowserCallRequest(agent_id=uuid4(), identifiers=[ident]),
    ):
        assert req.model_dump(mode="json", exclude_none=True)["identifiers"] == [
            {"type": "phone", "hash": H}
        ]
    assert "identifiers" not in BrowserCallRequest(agent_id=uuid4()).model_dump(exclude_none=True)


@pytest.mark.asyncio
@respx.mock
async def test_pii_methods() -> None:
    cid, iid, sid = uuid4(), uuid4(), uuid4()
    ev, tm = "http://ev.test", "http://tm.test"
    shred = {"shred_id": str(uuid4()), "identities_shredded": 1, "calls_affected": 2}
    routes = {
        "shred": respx.post(f"{ev}/v1/pii/shred").mock(
            return_value=httpx.Response(202, json=shred)
        ),
        "list": respx.get(f"{ev}/v1/calls/{cid}/pii/identities").mock(
            return_value=httpx.Response(
                200, json={"identities": [{"identity_id": str(iid), "type": "call"}]}
            )
        ),
        "link": respx.post(f"{ev}/v1/calls/{cid}/pii/identities").mock(
            return_value=httpx.Response(201, json={"identity_id": str(iid)})
        ),
        "cshred": respx.post(f"{ev}/v1/calls/{cid}/pii/shred").mock(
            return_value=httpx.Response(202, json=shred)
        ),
        "decrypt": respx.post(f"{ev}/v1/calls/{cid}/pii/decrypt").mock(
            return_value=httpx.Response(200, json={"text": "hi", "decrypted": 1, "erased": 0})
        ),
        "shreds2": respx.get(f"{ev}/v1/pii/shreds", params={"limit": "1"}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "shreds": [
                        {
                            "shred_id": str(sid),
                            "scope": "call",
                            "call_id": str(cid),
                            "identities_shredded": 2,
                            "calls_affected": 1,
                            "actor_key_id": "key-1",
                            "shredded_at": "2026-06-04T09:30:00Z",
                        }
                    ],
                    "next_cursor": "c2",
                },
            )
        ),
        "shreds": respx.get(f"{ev}/v1/pii/shreds").mock(
            return_value=httpx.Response(200, json={"shreds": [], "next_cursor": None})
        ),
        "get": respx.get(f"{tm}/v1/pii/settings").mock(
            return_value=httpx.Response(
                200,
                json={
                    "encryption_enabled": True,
                    "history": [
                        {
                            "encryption_enabled": False,
                            "actor_key_id": "key-1",
                            "configurations_resealed": 4,
                            "changed_at": "2026-10-05T09:30:00Z",
                        }
                    ],
                },
            )
        ),
        "put": respx.put(f"{tm}/v1/pii/settings").mock(
            return_value=httpx.Response(
                200, json={"encryption_enabled": False, "configurations_resealed": 3}
            )
        ),
        "exl": respx.get(f"{ev}/v1/pii/exemptions").mock(
            return_value=httpx.Response(200, json={"exemptions": [], "auto_exempt_dids": 4})
        ),
        "exa": respx.post(f"{ev}/v1/pii/exemptions").mock(
            return_value=httpx.Response(
                201,
                json={
                    "exempt_type": "phone",
                    "lookup_prefix": "a1b2c3d4",
                    "created_at": "2026-06-03T12:00:00Z",
                },
            )
        ),
        "exd": respx.delete(f"{ev}/v1/pii/exemptions/phone/{H}").mock(
            return_value=httpx.Response(204)
        ),
    }
    async with AudactClient(api_key="k", evidence_layer_url=ev, tenant_management_url=tm) as c:
        assert (await c.pii.shred("phone", H)).calls_affected == 2
        assert json.loads(routes["shred"].calls[0].request.content) == {
            "identifier_type": "phone",
            "identifier_hash": H,
        }
        assert "Idempotency-Key" not in routes["shred"].calls[0].request.headers
        await c.pii.shred("phone", H, idempotency_key="idem-shred-1")
        assert routes["shred"].calls[1].request.headers["Idempotency-Key"] == "idem-shred-1"
        assert (await c.pii.list_call_identities(cid)).identities[0].identity_id == iid
        assert (await c.pii.link_call_identity(cid, "email", H)).identity_id == iid
        await c.pii.shred_call(cid)
        assert json.loads(routes["cshred"].calls[0].request.content) == {}
        await c.pii.shred_call(cid, [iid])
        assert json.loads(routes["cshred"].calls[1].request.content) == {"identity_ids": [str(iid)]}
        assert "Idempotency-Key" not in routes["cshred"].calls[1].request.headers
        await c.pii.shred_call(cid, idempotency_key="idem-cshred-1")
        assert routes["cshred"].calls[2].request.headers["Idempotency-Key"] == "idem-cshred-1"
        assert (await c.pii.decrypt(cid, text="x")).decrypted == 1
        # Decrypt never carries an idempotency key (no plaintext in a replay cache).
        assert "Idempotency-Key" not in routes["decrypt"].calls[0].request.headers
        assert (await c.pii.list_shreds()).shreds == []
        page = await c.pii.list_shreds(limit=1)
        assert isinstance(page.shreds[0], PIIShredRecord)
        assert page.shreds[0].shred_id == sid and page.shreds[0].call_id == cid
        assert page.shreds[0].scope == "call" and page.next_cursor == "c2"
        settings = await c.pii.get_settings()
        assert settings.encryption_enabled is True
        assert isinstance(settings.history[0], PIISettingsHistoryEntry)
        assert settings.history[0].configurations_resealed == 4
        assert (await c.pii.update_settings(False)).configurations_resealed == 3
        assert "Idempotency-Key" not in routes["put"].calls[0].request.headers
        await c.pii.update_settings(True, idempotency_key="idem-put-1")
        assert routes["put"].calls[1].request.headers["Idempotency-Key"] == "idem-put-1"
        assert (await c.pii.list_exemptions()).auto_exempt_dids == 4
        ex = await c.pii.add_exemption("phone", H)
        assert isinstance(ex, PIIExemption) and ex.lookup_prefix == "a1b2c3d4"
        await c.pii.remove_exemption("phone", H)
    assert all(r.called for r in routes.values())


@pytest.mark.asyncio
async def test_pii_validation_errors() -> None:
    async with AudactClient(api_key="k") as c:
        with pytest.raises(ValueError):
            await c.pii.shred("call", H)
        with pytest.raises(ValueError):
            await c.pii.shred("phone", "NOTHEX")
        with pytest.raises(ValueError):
            await c.pii.decrypt(uuid4())
        with pytest.raises(ValueError):
            await c.pii.decrypt(uuid4(), text="a", texts=["b"])


@pytest.mark.asyncio
@respx.mock
async def test_remove_exemption_with_body_uses_legacy_route() -> None:
    ev = "http://localhost:8083"
    route = respx.delete(f"{ev}/v1/pii/exemptions").mock(return_value=httpx.Response(204))
    async with AudactClient(api_key="k", evidence_layer_url=ev) as c:
        await c.pii.remove_exemption_with_body("phone", "a" * 64)
    assert route.called
    assert json.loads(route.calls[0].request.content) == {
        "exempt_type": "phone",
        "identifier_hash": "a" * 64,
    }


# ─── list_erased_keysets ───────────────────────────────────────────

_EV = "http://localhost:8083"


@pytest.mark.asyncio
@respx.mock
async def test_list_erased_keysets_repeats_param_and_decodes() -> None:
    cid, k1, k2 = uuid4(), str(uuid4()), str(uuid4())
    route = respx.get(f"{_EV}/v1/calls/{cid}/pii/erased-keysets").mock(
        return_value=httpx.Response(200, json={"erased_keyset_ids": [k1]})
    )
    async with AudactClient(api_key="k-test") as c:
        out = await c.pii.list_erased_keysets(cid, [k1, k2])
    req = route.calls.last.request
    assert req.method == "GET"
    assert req.url.params.get_list("keyset_id") == [k1, k2]
    assert req.headers["Authorization"] == "Bearer k-test"
    assert out.erased_keyset_ids == [k1]


@pytest.mark.asyncio
@respx.mock
async def test_list_erased_keysets_empty_raises_without_request() -> None:
    route = respx.route().mock(return_value=httpx.Response(200, json={}))
    async with AudactClient(api_key="k") as c:
        with pytest.raises(ValueError):
            await c.pii.list_erased_keysets(uuid4(), [])
    assert not route.called


@pytest.mark.asyncio
@respx.mock
async def test_list_erased_keysets_bare_string_raises_type_error() -> None:
    route = respx.route().mock(return_value=httpx.Response(200, json={}))
    async with AudactClient(api_key="k") as c:
        with pytest.raises(TypeError):
            await c.pii.list_erased_keysets(uuid4(), str(uuid4()))  # type: ignore[arg-type]
    assert not route.called
