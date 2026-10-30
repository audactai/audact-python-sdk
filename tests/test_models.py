"""
Tests for Audact SDK Pydantic type definitions (M4-011).

Exercises each model for:
- Required-field validation
- Default-value correctness
- ``extra="allow"`` forward-compatibility
- Round-trip serialisation / deserialisation via model_dump / model_validate
- Field types and constraints
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from audact.models import (
    ACVFContext,
    ACVFTurn,
    APIKey,
    APIKeyInfo,
    BlocklistPattern,
    CallState,
    CheckResult,
    CheckScoreEntry,
    ComplianceScore,
    Configuration,
    CreateConfigurationRequest,
    CreateTenantRequest,
    CreateTenantResponse,
    EvaluateRequest,
    EvaluateResponse,
    EvidenceEvent,
    FailOpenMeta,
    GenerateKeyRequest,
    GenerateKeyResponse,
    GetChainResponse,
    ListConfigurationsResponse,
    ListKeysResponse,
    PostEventRequest,
    PostEventResponse,
    Receipt,
    ReconstructResponse,
    Tenant,
    UpdateConfigurationRequest,
    UpdateTenantRequest,
    ValidateRequest,
    ValidateResponse,
    VerifyChainResponse,
)

# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

NOW = datetime.now(tz=UTC)
NOW_STR = NOW.isoformat()
TENANT_ID = uuid4()
CONFIG_ID = uuid4()
CALL_ID = uuid4()
EVENT_ID = uuid4()
KEY_ID = str(uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# CallState
# ─────────────────────────────────────────────────────────────────────────────

class TestCallState:
    def test_default_disclosure_delivered_is_false(self):
        cs = CallState()
        assert cs.disclosure_delivered is False

    def test_explicit_true(self):
        cs = CallState(disclosure_delivered=True)
        assert cs.disclosure_delivered is True

    def test_extra_fields_allowed(self):
        cs = CallState(disclosure_delivered=False, future_field="x")  # type: ignore[call-arg]
        assert cs.future_field == "x"  # type: ignore[attr-defined]

    def test_round_trip(self):
        cs = CallState(disclosure_delivered=True)
        dumped = cs.model_dump()
        assert CallState.model_validate(dumped).disclosure_delivered is True


# ─────────────────────────────────────────────────────────────────────────────
# ACVFTurn
# ─────────────────────────────────────────────────────────────────────────────

class TestACVFTurn:
    def _make(self, **kwargs) -> ACVFTurn:
        base = {"turn": 1, "content": "hello", "verdict": "ALLOW"}
        return ACVFTurn(**{**base, **kwargs})

    def test_required_fields(self):
        t = self._make()
        assert t.turn == 1
        assert t.content == "hello"
        assert t.verdict == "ALLOW"

    def test_missing_turn_raises(self):
        with pytest.raises(ValidationError):
            ACVFTurn(content="hi", verdict="ALLOW")  # type: ignore[call-arg]

    def test_missing_content_raises(self):
        with pytest.raises(ValidationError):
            ACVFTurn(turn=1, verdict="ALLOW")  # type: ignore[call-arg]

    def test_missing_verdict_raises(self):
        with pytest.raises(ValidationError):
            ACVFTurn(turn=1, content="hi")  # type: ignore[call-arg]

    def test_extra_allowed(self):
        t = self._make(extra_meta="value")
        assert t.extra_meta == "value"  # type: ignore[attr-defined]

    def test_round_trip(self):
        t = self._make(turn=3, verdict="BLOCK")
        assert ACVFTurn.model_validate(t.model_dump()).turn == 3


# ─────────────────────────────────────────────────────────────────────────────
# ACVFContext
# ─────────────────────────────────────────────────────────────────────────────

class TestACVFContext:
    def test_empty_defaults(self):
        ctx = ACVFContext()
        assert ctx.previous_turns == []
        assert ctx.call_state.disclosure_delivered is False

    def test_with_turns(self):
        turn = ACVFTurn(turn=1, content="hi", verdict="ALLOW")
        ctx = ACVFContext(previous_turns=[turn])
        assert len(ctx.previous_turns) == 1

    def test_with_call_state(self):
        cs = CallState(disclosure_delivered=True)
        ctx = ACVFContext(call_state=cs)
        assert ctx.call_state.disclosure_delivered is True

    def test_round_trip(self):
        turn = ACVFTurn(turn=1, content="test", verdict="MODIFY")
        ctx = ACVFContext(
            previous_turns=[turn],
            call_state=CallState(disclosure_delivered=True),
        )
        ctx2 = ACVFContext.model_validate(ctx.model_dump())
        assert len(ctx2.previous_turns) == 1
        assert ctx2.call_state.disclosure_delivered is True


# ─────────────────────────────────────────────────────────────────────────────
# ValidateRequest
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateRequest:
    def _make(self, **kwargs) -> ValidateRequest:
        base = {
            "call_id": CALL_ID,
            "tenant_id": TENANT_ID,
            "config_id": CONFIG_ID,
            "turn": 1,
            "content": "test content",
        }
        return ValidateRequest(**{**base, **kwargs})

    def test_required_fields(self):
        req = self._make()
        assert req.call_id == CALL_ID
        assert req.tenant_id == TENANT_ID
        assert req.turn == 1
        assert req.content == "test content"

    def test_default_context(self):
        req = self._make()
        assert isinstance(req.context, ACVFContext)
        assert req.context.previous_turns == []

    def test_uuid_from_string(self):
        req = self._make(call_id=str(CALL_ID))
        assert req.call_id == CALL_ID

    def test_missing_call_id_raises(self):
        with pytest.raises(ValidationError):
            ValidateRequest(  # type: ignore[call-arg]
                tenant_id=TENANT_ID,
                config_id=CONFIG_ID,
                turn=1,
                content="test",
            )

    def test_round_trip_json_mode(self):
        req = self._make()
        dumped = req.model_dump(mode="json")
        assert isinstance(dumped["call_id"], str)
        req2 = ValidateRequest.model_validate(dumped)
        assert req2.call_id == CALL_ID


# ─────────────────────────────────────────────────────────────────────────────
# CheckResult
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckResult:
    def test_required_fields(self):
        cr = CheckResult(check_id="disclosure_check", verdict="ALLOW")
        assert cr.check_id == "disclosure_check"
        assert cr.verdict == "ALLOW"

    def test_defaults(self):
        cr = CheckResult(check_id="x", verdict="BLOCK")
        assert cr.reason == ""
        assert cr.modified_content == ""
        assert cr.duration_ms == 0.0

    def test_extra_allowed(self):
        cr = CheckResult(check_id="x", verdict="ALLOW", future="field")  # type: ignore[call-arg]
        assert cr.future == "field"  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────────
# CheckScoreEntry & ComplianceScore
# ─────────────────────────────────────────────────────────────────────────────

class TestComplianceScore:
    def test_check_score_entry(self):
        entry = CheckScoreEntry(
            check_id="disclosure_check",
            verdict="ALLOW",
            weight=1.0,
            score=1.0,
        )
        assert entry.weight == 1.0
        assert entry.score == 1.0

    def test_compliance_score(self):
        score = ComplianceScore(
            composite=0.95,
            check_scores=[],
            total_weight=2.0,
        )
        assert score.composite == 0.95
        assert score.check_scores == []

    def test_compliance_score_defaults_check_scores(self):
        score = ComplianceScore(composite=1.0, total_weight=1.0)
        assert score.check_scores == []


# ─────────────────────────────────────────────────────────────────────────────
# FailOpenMeta
# ─────────────────────────────────────────────────────────────────────────────

class TestFailOpenMeta:
    def test_required_fields(self):
        meta = FailOpenMeta(
            reason="deadline_exceeded",
            deadline_ms=40.0,
            elapsed_ms=42.5,
            checks_completed=3,
        )
        assert meta.reason == "deadline_exceeded"
        assert meta.checks_completed == 3

    def test_missing_reason_raises(self):
        with pytest.raises(ValidationError):
            FailOpenMeta(deadline_ms=40.0, elapsed_ms=42.5, checks_completed=3)  # type: ignore[call-arg]


# ─────────────────────────────────────────────────────────────────────────────
# Receipt
# ─────────────────────────────────────────────────────────────────────────────

class TestReceipt:
    def _make(self, **kwargs) -> Receipt:
        base = {
            "receipt_format_version": "1",
            "call_id": CALL_ID,
            "timestamp": NOW_STR,
            "input_hash": "abc",
            "output_hash": "abc",
            "verdict": "ALLOW",
            "config_version": 1,
            "config_seal_hash": "seal",
            "policy_version": "NL_v1.1.0",
            "evidence_hash": "",
            "auth_mechanism": "hmac-sha256",
            "signature": "sig",
        }
        return Receipt(**{**base, **kwargs})

    def test_all_required_fields(self):
        r = self._make()
        assert r.auth_mechanism == "hmac-sha256"
        assert r.verdict == "ALLOW"
        assert isinstance(r.call_id, UUID)
        assert isinstance(r.timestamp, datetime)

    def test_timestamp_parsed_from_string(self):
        r = self._make()
        assert isinstance(r.timestamp, datetime)

    def test_extra_allowed(self):
        r = self._make(future_field="x")
        assert r.future_field == "x"  # type: ignore[attr-defined]

    def test_round_trip(self):
        r = self._make()
        r2 = Receipt.model_validate(r.model_dump(mode="json"))
        assert r2.signature == "sig"


# ─────────────────────────────────────────────────────────────────────────────
# ValidateResponse
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateResponse:
    def _minimal(self) -> dict:
        return {
            "call_id": str(CALL_ID),
            "turn": 1,
            "verdict": "ALLOW",
            "content": "hello",
        }

    def test_minimal_response(self):
        r = ValidateResponse.model_validate(self._minimal())
        assert r.verdict == "ALLOW"
        assert r.fail_open is False
        assert r.fail_open_meta is None
        assert r.receipt is None
        assert r.compliance_score is None
        assert r.checks == []

    def test_with_fail_open_meta(self):
        data = {
            **self._minimal(),
            "fail_open": True,
            "fail_open_meta": {
                "reason": "deadline_exceeded",
                "deadline_ms": 40.0,
                "elapsed_ms": 42.0,
                "checks_completed": 2,
            },
        }
        r = ValidateResponse.model_validate(data)
        assert r.fail_open is True
        assert r.fail_open_meta is not None
        assert r.fail_open_meta.checks_completed == 2

    def test_with_receipt(self):
        receipt = {
            "receipt_format_version": "1",
            "call_id": str(CALL_ID),
            "timestamp": NOW_STR,
            "input_hash": "in",
            "output_hash": "out",
            "verdict": "ALLOW",
            "config_version": 1,
            "config_seal_hash": "seal",
            "policy_version": "NL_v1.1.0",
            "evidence_hash": "",
            "auth_mechanism": "hmac-sha256",
            "signature": "sig",
        }
        data = {**self._minimal(), "receipt": receipt}
        r = ValidateResponse.model_validate(data)
        assert r.receipt is not None
        assert r.receipt.auth_mechanism == "hmac-sha256"

    def test_with_compliance_score(self):
        data = {
            **self._minimal(),
            "compliance_score": {
                "composite": 0.9,
                "total_weight": 2.0,
                "check_scores": [],
            },
        }
        r = ValidateResponse.model_validate(data)
        assert r.compliance_score is not None
        assert r.compliance_score.composite == 0.9

    def test_with_checks(self):
        data = {
            **self._minimal(),
            "checks": [
                {"check_id": "disclosure_check", "verdict": "ALLOW"},
                {"check_id": "blocklist_check", "verdict": "MODIFY", "reason": "redacted"},
            ],
        }
        r = ValidateResponse.model_validate(data)
        assert len(r.checks) == 2
        assert r.checks[1].reason == "redacted"

    def test_extra_fields_allowed(self):
        data = {**self._minimal(), "new_server_field": "value"}
        r = ValidateResponse.model_validate(data)
        assert r.new_server_field == "value"  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────────
# EvaluateRequest / EvaluateResponse
# ─────────────────────────────────────────────────────────────────────────────

class TestEvaluateModels:
    def test_evaluate_request(self):
        req = EvaluateRequest(country="NL", context={"dnc_registered": False})
        assert req.country == "NL"
        assert req.context["dnc_registered"] is False

    def test_evaluate_request_empty_context(self):
        req = EvaluateRequest(country="DE", context={})
        assert req.context == {}

    def test_evaluate_request_missing_country_raises(self):
        with pytest.raises(ValidationError):
            EvaluateRequest(context={})  # type: ignore[call-arg]

    def test_evaluate_response_allow(self):
        resp = EvaluateResponse.model_validate(
            {
                "verdict": "ALLOW",
                "reasons": [],
                "applicable_rules": [],
                "policy_version": "NL_v1.1.0",
            }
        )
        assert resp.verdict == "ALLOW"
        assert resp.policy_version == "NL_v1.1.0"

    def test_evaluate_response_block(self):
        resp = EvaluateResponse.model_validate(
            {
                "verdict": "BLOCK",
                "reasons": ["DNC registered"],
                "applicable_rules": ["dnc_check"],
                "policy_version": "NL_v1.1.0",
            }
        )
        assert resp.reasons == ["DNC registered"]

    def test_evaluate_response_default_lists(self):
        resp = EvaluateResponse.model_validate(
            {"verdict": "ALLOW", "policy_version": "NL_v1.1.0"}
        )
        assert resp.reasons == []
        assert resp.applicable_rules == []

    def test_evaluate_response_extra_allowed(self):
        resp = EvaluateResponse.model_validate(
            {
                "verdict": "ALLOW",
                "policy_version": "NL_v1.1.0",
                "future_field": True,
            }
        )
        assert resp.future_field is True  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────────
# Evidence Layer models
# ─────────────────────────────────────────────────────────────────────────────

class TestEvidenceModels:
    def _event_dict(self) -> dict:
        return {
            "event_id": str(EVENT_ID),
            "call_id": str(CALL_ID),
            "tenant_id": str(TENANT_ID),
            "event_type": "CALL_START",
            "sequence": 1,
            "hash": "abc123",
            "previous_hash": "0" * 64,
            "timestamp": NOW_STR,
        }

    def test_post_event_request(self):
        req = PostEventRequest(
            call_id=CALL_ID,
            tenant_id=TENANT_ID,
            event_type="CALL_START",
        )
        assert req.event_type == "CALL_START"
        assert req.data is None

    def test_post_event_request_with_data(self):
        req = PostEventRequest(
            call_id=CALL_ID,
            tenant_id=TENANT_ID,
            event_type="VALIDATION_RESULT",
            data={"verdict": "ALLOW"},
        )
        assert req.data == {"verdict": "ALLOW"}

    def test_post_event_response(self):
        resp = PostEventResponse.model_validate(self._event_dict())
        assert resp.sequence == 1
        assert resp.hash == "abc123"
        assert isinstance(resp.event_id, UUID)
        assert isinstance(resp.timestamp, datetime)

    def test_evidence_event(self):
        ev = EvidenceEvent.model_validate(self._event_dict())
        assert ev.event_type == "CALL_START"
        assert ev.data is None

    def test_evidence_event_with_data(self):
        d = {**self._event_dict(), "data": {"key": "value"}}
        ev = EvidenceEvent.model_validate(d)
        assert ev.data == {"key": "value"}

    def test_get_chain_response(self):
        resp = GetChainResponse.model_validate(
            {"call_id": str(CALL_ID), "events": [self._event_dict()]}
        )
        assert resp.call_id == CALL_ID
        assert len(resp.events) == 1

    def test_get_chain_response_empty_events(self):
        resp = GetChainResponse.model_validate({"call_id": str(CALL_ID)})
        assert resp.events == []

    def test_verify_chain_response(self):
        resp = VerifyChainResponse.model_validate(
            {
                "call_id": str(CALL_ID),
                "valid": True,
                "event_count": 5,
                "message": "",
            }
        )
        assert resp.valid is True
        assert resp.event_count == 5

    def test_verify_chain_response_default_message(self):
        resp = VerifyChainResponse.model_validate(
            {"call_id": str(CALL_ID), "valid": False, "event_count": 0}
        )
        assert resp.message == ""

    def test_reconstruct_response(self):
        resp = ReconstructResponse.model_validate(
            {"call_id": str(CALL_ID), "events": [self._event_dict(), self._event_dict()]}
        )
        assert len(resp.events) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Tenant Management models
# ─────────────────────────────────────────────────────────────────────────────

class TestTenantModels:
    def _tenant_dict(self) -> dict:
        return {
            "tenant_id": str(TENANT_ID),
            "name": "Acme Corp",
            "plan": "starter",
            "hmac_key_arn": "arn:aws:kms:eu-west-1:123:key/abc",
            "created_at": NOW_STR,
            "updated_at": NOW_STR,
        }

    def test_create_tenant_request_defaults(self):
        req = CreateTenantRequest(name="Acme")
        assert req.plan == "starter"
        assert req.key_name == "default"

    def test_create_tenant_request_custom(self):
        req = CreateTenantRequest(name="Acme", plan="enterprise", key_name="prod")
        assert req.plan == "enterprise"
        assert req.key_name == "prod"

    def test_tenant(self):
        t = Tenant.model_validate(self._tenant_dict())
        assert t.tenant_id == TENANT_ID
        assert t.name == "Acme Corp"
        assert t.plan == "starter"
        assert isinstance(t.created_at, datetime)

    def test_api_key_info(self):
        info = APIKeyInfo(
            key_id=KEY_ID,
            key="aud_live_xyz",
            key_prefix="aud_live",
            name="default",
            role="owner",
        )
        assert info.key == "aud_live_xyz"
        assert info.role == "owner"

    def test_create_tenant_response(self):
        data = {
            **self._tenant_dict(),
            "api_key": {
                "key_id": KEY_ID,
                "key": "aud_live_abc",
                "key_prefix": "aud_live",
                "name": "default",
                "role": "owner",
            },
        }
        resp = CreateTenantResponse.model_validate(data)
        assert resp.name == "Acme Corp"
        assert resp.api_key.key == "aud_live_abc"
        assert resp.api_key.role == "owner"

    def test_update_tenant_request_all_none(self):
        req = UpdateTenantRequest()
        assert req.name is None
        assert req.plan is None

    def test_update_tenant_request_partial(self):
        req = UpdateTenantRequest(plan="professional")
        assert req.plan == "professional"
        assert req.name is None


# ─────────────────────────────────────────────────────────────────────────────
# API Key models
# ─────────────────────────────────────────────────────────────────────────────

class TestAPIKeyModels:
    def test_generate_key_request_defaults(self):
        req = GenerateKeyRequest()
        assert req.name == "default"
        assert req.role == "developer"

    def test_generate_key_request_custom(self):
        req = GenerateKeyRequest(name="ci-key", role="viewer")
        assert req.name == "ci-key"
        assert req.role == "viewer"

    def test_generate_key_response(self):
        resp = GenerateKeyResponse.model_validate(
            {
                "key_id": KEY_ID,
                "key": "aud_live_newkey",
                "key_prefix": "aud_live",
                "name": "ci-key",
                "role": "developer",
                "created_at": NOW_STR,
            }
        )
        assert resp.key == "aud_live_newkey"
        assert resp.role == "developer"
        assert isinstance(resp.created_at, datetime)

    def test_api_key_no_revoked_at(self):
        key = APIKey.model_validate(
            {
                "key_id": KEY_ID,
                "key_prefix": "aud_live",
                "name": "default",
                "role": "owner",
                "created_at": NOW_STR,
                "revoked_at": None,
            }
        )
        assert key.revoked_at is None

    def test_api_key_with_revoked_at(self):
        key = APIKey.model_validate(
            {
                "key_id": KEY_ID,
                "key_prefix": "aud_live",
                "name": "default",
                "role": "owner",
                "created_at": NOW_STR,
                "revoked_at": NOW_STR,
            }
        )
        assert isinstance(key.revoked_at, datetime)

    def test_list_keys_response_empty(self):
        resp = ListKeysResponse.model_validate({"keys": []})
        assert resp.keys == []

    def test_list_keys_response_with_keys(self):
        data = {
            "keys": [
                {
                    "key_id": KEY_ID,
                    "key_prefix": "aud_live",
                    "name": "default",
                    "role": "owner",
                    "created_at": NOW_STR,
                    "revoked_at": None,
                }
            ]
        }
        resp = ListKeysResponse.model_validate(data)
        assert len(resp.keys) == 1
        assert resp.keys[0].role == "owner"


# ─────────────────────────────────────────────────────────────────────────────
# Configuration models
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigurationModels:
    def _config_dict(self) -> dict:
        return {
            "config_id": str(CONFIG_ID),
            "tenant_id": str(TENANT_ID),
            "name": "My Config",
            "version": 1,
            "countries": ["NL", "DE"],
            "created_at": NOW_STR,
            "updated_at": NOW_STR,
        }

    def test_blocklist_pattern(self):
        bp = BlocklistPattern(id="p1", terms=["bad word"], severity="block")
        assert bp.id == "p1"
        assert bp.terms == ["bad word"]
        assert bp.replacement_text == ""
        assert bp.category == ""

    def test_blocklist_pattern_full(self):
        bp = BlocklistPattern(
            id="p2",
            terms=["restricted"],
            severity="modify",
            replacement_text="[REDACTED]",
            category="pii",
        )
        assert bp.replacement_text == "[REDACTED]"
        assert bp.category == "pii"

    def test_create_configuration_request_minimal(self):
        req = CreateConfigurationRequest(name="cfg", countries=["NL"])
        assert req.name == "cfg"
        assert req.countries == ["NL"]
        assert req.validator_modes is None
        assert req.blocklist_patterns is None

    def test_secret_fields_hidden_from_repr(self):
        """Secrets must not leak into logs via repr()/print(), but must still
        reach the wire through model_dump()."""
        from audact.models import (
            CreateBYOConnectionRequest,
            OrgLoginRequest,
            UpdateConfigurationRequest,
        )

        cases = [
            CreateConfigurationRequest(
                name="cfg", countries=["NL"], upstream_llm_key="sk-SECRET-1"
            ),
            UpdateConfigurationRequest(upstream_llm_key="sk-SECRET-1"),
            OrgLoginRequest(email="a@b.c", password="sk-SECRET-1"),
        ]
        byo_fields = CreateBYOConnectionRequest.model_fields
        assert byo_fields["sip_password"].repr is False
        for req in cases:
            assert "sk-SECRET-1" not in repr(req), type(req).__name__
            assert "sk-SECRET-1" not in str(req), type(req).__name__
            assert "sk-SECRET-1" in req.model_dump_json(), type(req).__name__

    def test_create_configuration_request_with_patterns(self):
        bp = BlocklistPattern(id="p1", terms=["word"], severity="block")
        req = CreateConfigurationRequest(
            name="cfg",
            countries=["NL", "DE"],
            blocklist_patterns=[bp],
        )
        assert len(req.blocklist_patterns) == 1  # type: ignore[arg-type]

    def test_configuration(self):
        cfg = Configuration.model_validate(self._config_dict())
        assert cfg.config_id == CONFIG_ID
        assert cfg.tenant_id == TENANT_ID
        assert cfg.version == 1
        assert cfg.countries == ["NL", "DE"]
        assert cfg.config_seal_hash == ""
        assert isinstance(cfg.created_at, datetime)

    def test_configuration_optional_fields_none(self):
        cfg = Configuration.model_validate(self._config_dict())
        assert cfg.validator_modes is None
        assert cfg.blocklist_patterns is None
        assert cfg.pricing_bands is None
        assert cfg.disclosure_texts is None
        assert cfg.fallback_response is None

    def test_update_configuration_request_all_none(self):
        req = UpdateConfigurationRequest()
        assert req.name is None
        assert req.countries is None
        assert req.validator_modes is None

    def test_update_configuration_request_partial(self):
        req = UpdateConfigurationRequest(name="new name", countries=["NL"])
        assert req.name == "new name"
        assert req.countries == ["NL"]

    def test_list_configurations_response_empty(self):
        resp = ListConfigurationsResponse.model_validate({"configurations": []})
        assert resp.configurations == []

    def test_list_configurations_response_with_items(self):
        data = {"configurations": [self._config_dict(), self._config_dict()]}
        resp = ListConfigurationsResponse.model_validate(data)
        assert len(resp.configurations) == 2

    def test_configuration_request_llm_fields(self):
        """upstream_llm_url and upstream_llm_secret_arn are optional and default to None."""
        req = CreateConfigurationRequest(name="cfg", countries=["NL"])
        assert req.upstream_llm_url is None
        assert req.upstream_llm_secret_arn is None

    def test_configuration_request_llm_fields_serialized(self):
        """When set, LLM credential fields round-trip through model_dump."""
        req = CreateConfigurationRequest(
            name="cfg",
            countries=["NL"],
            upstream_llm_url="https://my-llm.example.com/v1",
            upstream_llm_secret_arn="arn:aws:secretsmanager:eu-west-1:123456789012:secret:my-key",
        )
        dumped = req.model_dump(mode="json", exclude_none=True)
        assert dumped["upstream_llm_url"] == "https://my-llm.example.com/v1"
        assert (
            dumped["upstream_llm_secret_arn"]
            == "arn:aws:secretsmanager:eu-west-1:123456789012:secret:my-key"
        )

    def test_configuration_response_llm_fields(self):
        """Configuration deserializes upstream_llm_url/secret_arn; absent fields default None."""
        cfg_without = Configuration.model_validate(self._config_dict())
        assert cfg_without.upstream_llm_url is None
        assert cfg_without.upstream_llm_secret_arn is None

        cfg_with = Configuration.model_validate({
            **self._config_dict(),
            "upstream_llm_url": "https://custom-llm.example.com/v1",
            "upstream_llm_secret_arn": "arn:aws:secretsmanager:eu-west-1:123:secret:key",
        })
        assert cfg_with.upstream_llm_url == "https://custom-llm.example.com/v1"
        assert cfg_with.upstream_llm_secret_arn == "arn:aws:secretsmanager:eu-west-1:123:secret:key"


# ─────────────────────────────────────────────────────────────────────────────
# Extra-field forward-compatibility (global smoke test)
# ─────────────────────────────────────────────────────────────────────────────

class TestForwardCompatibility:
    """All models use extra='allow'; verify that unknown fields never raise."""

    MODELS_AND_MINIMAL_DATA = [
        (CallState, {}),
        (ACVFContext, {}),
        (
            ValidateResponse,
            {"call_id": str(CALL_ID), "turn": 1, "verdict": "ALLOW", "content": "x"},
        ),
        (EvaluateResponse, {"verdict": "ALLOW", "policy_version": "v1"}),
        (PostEventResponse, {
            "event_id": str(EVENT_ID), "call_id": str(CALL_ID), "tenant_id": str(TENANT_ID),
            "event_type": "X", "sequence": 1, "hash": "h", "previous_hash": "p",
            "timestamp": NOW_STR,
        }),
        (GetChainResponse, {"call_id": str(CALL_ID)}),
        (VerifyChainResponse, {"call_id": str(CALL_ID), "valid": True, "event_count": 0}),
        (Tenant, {
            "tenant_id": str(TENANT_ID), "name": "T", "plan": "starter",
            "hmac_key_arn": "arn", "created_at": NOW_STR, "updated_at": NOW_STR,
        }),
        (Configuration, {
            "config_id": str(CONFIG_ID), "tenant_id": str(TENANT_ID), "name": "C",
            "version": 1, "countries": ["NL"], "created_at": NOW_STR, "updated_at": NOW_STR,
        }),
    ]

    @pytest.mark.parametrize("model_cls,data", MODELS_AND_MINIMAL_DATA)
    def test_unknown_field_does_not_raise(self, model_cls, data):
        enriched = {**data, "__future_field__": "should_be_ignored_or_stored"}
        instance = model_cls.model_validate(enriched)
        # Access via __pydantic_extra__ or direct attr — either way no exception
        assert instance is not None


def test_drift_fixed_enum_fields_and_blank_normalisation() -> None:
    """Literal-typed enum fields validate; ``""`` on a response enum becomes None."""
    import pytest
    from pydantic import ValidationError

    from audact import models as m

    detail = m.CallDetail.model_validate(
        {
            "call_id": "11111111-1111-1111-1111-111111111111",
            "tenant_id": "22222222-2222-2222-2222-222222222222",
            "direction": "inbound",
            "status": "completed",
            "termination_class": "",
            "started_at": "2026-01-01T00:00:00Z",
            "pii_mode": "encrypt",
            "transcript_status": "ok",
        }
    )
    assert detail.termination_class is None
    assert detail.pii_mode == "encrypt"
    with pytest.raises(ValidationError):
        m.CreateAgentRequest.model_validate({"name": "a", "llm_provider": "nope"})
    assert m.ToolConfig.model_validate(
        {"tool_id": "11111111-1111-1111-1111-111111111111", "destination_hint": "•••• 9354"}
    ).destination_hint == "•••• 9354"
