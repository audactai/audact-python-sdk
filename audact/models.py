"""
Audact SDK — Pydantic type definitions.

These models mirror the canonical wire format of every Audact API.  All
models use ``model_config = ConfigDict(extra="allow")`` so that new fields
introduced by future server versions are silently accepted rather than
raising validation errors.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

class _Base(BaseModel):
    """Root model with forward-compatible extras."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)



# ─────────────────────────────────────────────────────────────────────────────
# Spec enums — Literal aliases mirroring the documented Audact API
# ─────────────────────────────────────────────────────────────────────────────

def _blank_to_none(*names: str) -> Any:
    """``before`` validator: an unset enum string arrives as ``""``; model it as ``None``."""

    def _convert(cls: Any, value: Any) -> Any:
        return None if value == "" else value

    return field_validator(*names, mode="before")(classmethod(_convert))


C2PAAssertionLabel = Literal["com.audact.compliance", "c2pa.actions", "c2pa.hash.data"]
"""Label of a C2PA assertion; it determines the shape of ``data``."""

C2PAAssetKind = Literal["recording", "evidence_export"]
"""Kind of asset a C2PA credential is bound to."""

C2PATrust = Literal["self_signed", "ca_issued"]
"""Where the C2PA signing chain ends: the Audact root or a third-party CA."""

KBSourceType = Literal["url", "file", "text"]
"""Origin of a knowledge-base source (``kb.SourceType``)."""

KBSourceStatus = Literal["pending", "processing", "ready", "failed"]
"""Ingestion lifecycle state of a knowledge-base source (``kb.SourceStatus``)."""

KBRobotsPolicy = Literal["honor", "override"]
"""Crawler robots.txt handling of a knowledge base."""

KBRetrievalTurnRole = Literal["user", "assistant", "system"]
"""Speaker role of a retrieval-test conversation turn."""

TranscriptionStatus = Literal["transcribed", "no_speech"]
"""Whether ASR produced text for an audio segment (``audio.AudioSegmentResult``)."""

UsageRecordSource = Literal["stored", "live"]
"""Where a usage record's counts come from (``tenant.UsageRecord``)."""

AudioFormat = Literal["pcm_s16le_16000", "wav", "mp3"]
"""Audio encoding accepted by the audio validator."""

BundleKind = Literal["TenantBundle", "AgentBundle"]
"""Kind of an export/import bundle."""

PIIExemptType = Literal["email", "phone"]
"""Identifier type of a PII exemption."""

PIIIdentityType = Literal["name", "email", "phone", "call"]
"""Identity type of a linked PII identity."""

PIIIdentityRole = Literal["subject", "mentioned"]
"""Role of a linked PII identity within a call."""

PIIIdentitySource = Literal["call", "pstn", "call_init", "api", "detected"]
"""How a PII identity was linked to a call."""

PIILinkIdentityType = Literal["name", "email", "phone"]
"""Identifier type accepted when linking an identity."""

PIIShredScope = Literal["identity", "call", "tenant"]
"""Scope of a PII shred."""

OrgEntityType = Literal["individual", "company"]
"""Entity type at organisation signup."""

CallingHoursReason = Literal["quiet_hours", "holiday"]
"""Why a call is currently blocked by the calling-hours check."""

PolicyVerdict = Literal["ALLOW", "BLOCK"]
"""Verdict of a policy evaluation."""

WebhookScope = Literal["account", "agent", "compliance"]
"""Webhook endpoint scope. ``"agent"`` requires ``agent_id``."""

ReceiptVerdict = Literal["ALLOW", "BLOCK", "MODIFY"]
"""Verdict recorded on a compliance receipt."""

PromptScope = Literal["agent", "shared_union", "skipped"]
"""Which prompt set the prompt-confidentiality check covered."""

PromptDetectionLayer = Literal["canary", "ngram"]
"""Detection layer of the prompt-confidentiality check."""

ReconciliationSegmentStatus = Literal["matched", "mismatched", "unvalidated"]
"""Reconciliation outcome of one segment."""

CrossTurnConfidence = Literal["low", "medium", "high"]
"""Confidence of a cross-turn finding."""

CrossTurnStatus = Literal[
    "disabled", "skipped_insufficient_turns", "skipped_unknown_provider", "completed", "failed",
]
"""Whether the semantic cross-turn contradiction pass ran."""

CrossTurnKind = Literal[
    "opening_hours", "closing_hours", "price", "availability",
    "policy", "commitment", "fact", "other",
]
"""Kind of a cross-turn contradiction finding."""

VoicemailBranch = Literal["leave_message", "hangup"]
"""Voicemail handling branch."""

ExtractionFieldType = Literal["string", "boolean", "number", "enum"]
"""Value type of a post-call extraction field."""


def _key_id_from_api_key_id(data: Any) -> Any:
    """``before`` validator: the wire name is ``api_key_id``; mirror it into the legacy ``key_id``.
    """
    if isinstance(data, dict) and not data.get("key_id") and data.get("api_key_id"):
        data = {**data, "key_id": data["api_key_id"]}
    return data


CallDirection = Literal["inbound", "outbound"]
"""Direction of a call relative to the platform."""

TerminationClass = Literal[
    "answered",
    "no_answer",
    "busy",
    "rejected",
    "invalid_destination",
    "voicemail",
    "carrier_error",
]
"""How a call ended at the carrier level (``evidence.CallDetail.termination_class``)."""

PIIMode = Literal["encrypt", "redact"]
"""A call's PII mode, fixed at call start."""

TranscriptStatus = Literal["ok", "none", "unavailable", "erased"]
"""Why ``CallDetail.transcript`` is (or is not) populated."""

AnalysisStatus = Literal["ok", "none", "unavailable"]
"""Whether the post-call analysis on :class:`CallSummary` is available."""

SummaryStatus = Literal["ok", "degraded", "disabled"]
"""State of the post-call summary."""

IntegrationAuthMethod = Literal["api_key", "oauth"]
"""Credential type of an integration connection (``integrations.AuthMethod``)."""

IntegrationConnectionStatus = Literal["active", "revoked", "error"]
"""Lifecycle status of an integration connection."""

IntegrationConnectionHealth = Literal["connected", "token_expired", "revoked", "error", "unknown"]
"""Health of an integration connection (distinct from the BYO :data:`ConnectionHealth`)."""

StartSpeaker = Literal["agent", "caller"]
"""Who speaks first on a call."""

LLMProvider = Literal["mistral", "openai"]
"""Supported LLM providers."""

LLMModel = Literal["gpt-4.1-mini", "mistral-small-2603"]
"""Supported LLM models."""

STTProvider = Literal["deepgram"]
"""Supported speech-to-text providers."""

TTSProvider = Literal["elevenlabs", "voxtral"]
"""Supported text-to-speech providers. Voxtral (Mistral, EU) is the default;
ElevenLabs (US, global endpoint) is opt-in per agent."""

TTSModel = Literal[
    "",
    "eleven_flash_v2_5",
    "eleven_multilingual_v2",
    "eleven_turbo_v2_5",
    "eleven_v3_conversational",
    "eleven_v4_turbo",
    "voxtral-mini-tts-2603",
]
"""Provider-specific TTS models. ``""`` selects the provider default; the
allowed values depend on ``tts_provider`` (a mismatch is a 400 naming
``tts_model``)."""

AgentCreateStatus = Literal["draft", "published"]
"""Statuses an agent may be created with."""

AgentStatus = Literal["archived", "draft", "published"]
"""Agent lifecycle status accepted on update (adds ``archived``)."""

AgentCreateVoiceId = Literal[
    "en_paul_angry",
    "en_paul_cheerful",
    "en_paul_confident",
    "en_paul_excited",
    "en_paul_happy",
    "en_paul_neutral",
    "en_paul_sad",
    "fr_marie_angry",
    "fr_marie_excited",
    "fr_marie_happy",
    "fr_marie_neutral",
    "fr_marie_sad",
]
"""Built-in voice ids for ``POST /v1/agents``. ``voice_id`` also accepts any
tenant-cloned voice id (``POST /v1/voices``); the server has no closed list."""

AgentVoiceId = Literal[
    "en_paul_angry",
    "en_paul_cheerful",
    "en_paul_confident",
    "en_paul_excited",
    "en_paul_happy",
    "en_paul_neutral",
    "en_paul_sad",
    "fr_marie_angry",
    "fr_marie_excited",
    "fr_marie_happy",
    "fr_marie_neutral",
    "fr_marie_sad",
]
"""Built-in voice ids for ``PUT``/``PATCH /v1/agents/{id}``. ``voice_id`` also
accepts any tenant-cloned voice id; the server has no closed list."""

CallControlStatus = Literal["active", "terminated"]
"""Status of a live call as reported by the voice gateway."""

TrunkProvider = Literal["telnyx", "twilio"]
"""Telephony provider of a registered SIP trunk."""

HandoverReason = Literal["agent_requested", "escalation", "operator_requested", "caller_requested"]
"""Why a handover was initiated."""

WhisperMode = Literal["spoken", "portal", "both"]
"""How a handover whisper is delivered."""

KYCDocumentSetStatus = Literal["draft", "submitted", "approved", "rejected", "expired"]
"""Review status of a KYC document set."""

NumberOrderStatus = Literal[
    "pending", "requirement_review", "ordering", "success", "failure", "cancelled",
]
"""Status of a number order."""

RequestedOutcome = Literal[
    "answered", "no_answer", "busy", "rejected", "invalid_destination", "voicemail",
]
"""Simulated outcome for a sandbox outbound call."""

PhoneNumberStatus = Literal["available", "assigned", "suspended"]
"""Assignment status of a phone number."""

TransferOption = Literal["blind", "warm"]
"""Call-transfer mode."""

TransferSessionStatus = Literal["started", "bridged", "cancelled", "ended"]
"""State of a transfer session."""

WebhookDeliveryStatus = Literal["pending", "success", "failed", "dead_letter"]
"""Delivery state of a webhook attempt."""

WebhookEventType = Literal[
    "call_analyzed",
    "call_end_detected",
    "call_ended",
    "call_started",
    "call_summary",
    "chat_analyzed",
    "chat_ended",
    "chat_started",
    "compliance.byo_connection_created",
    "compliance.byo_connection_deleted",
    "compliance.byo_connection_health_changed",
    "compliance.byo_connection_verified",
    "compliance.byo_number_attached",
    "compliance.byo_number_detached",
    "compliance.call_blocked",
    "compliance.call_score_finalized",
    "compliance.chain_tampered",
    "compliance.chain_verified",
    "compliance.fail_open",
    "compliance.kyc_set_approved",
    "compliance.kyc_set_rejected",
    "compliance.kyc_set_submitted",
    "compliance.number_provisioning_approved",
    "compliance.number_provisioning_failed",
    "compliance.number_provisioning_requested",
    "compliance.policy_evaluated",
    "compliance.receipt_issued",
    "compliance.validation_completed",
    "compliance.violation_detected",
    "handover_completed",
    "handover_initiated",
    "handover_summary_ready",
    "transcript_updated",
    "transfer_bridged",
    "transfer_cancelled",
    "transfer_ended",
    "transfer_started",
    "voicemail_detected",
]
"""Event type a webhook endpoint can subscribe to."""

# ─────────────────────────────────────────────────────────────────────────────
# Validator — POST /v1/validate
# ─────────────────────────────────────────────────────────────────────────────

class CallState(BaseModel):
    """Mutable per-call state threaded through every validation check."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    disclosure_delivered: bool = False
    """``True`` when the AI disclosure has been delivered in a prior turn."""


class ACVFTurn(_Base):
    """A single historical conversation turn."""

    turn: int
    """1-based sequential turn number."""

    content: str
    """Text content of this turn."""

    verdict: str
    """Validation verdict applied to this turn (ALLOW, BLOCK, MODIFY)."""


class ACVFContext(_Base):
    """Conversation history and current call state."""

    previous_turns: list[ACVFTurn] = Field(default_factory=list)
    call_state: CallState = Field(default_factory=CallState)


class ValidateRequest(_Base):
    """
    Request body for ``POST /v1/validate``.

    All UUID fields must be non-zero.
    """

    call_id: UUID
    tenant_id: UUID
    config_id: UUID
    turn: int
    content: str
    context: ACVFContext = Field(default_factory=ACVFContext)
    config_seal_hash: str = ""
    """
    Config-identity seal (SHA-256 of RFC 8785 canonical JSON of the tenant
    configuration active for this call), pinned at call start and carried by
    the proxy so the Validator can stamp the real seal without a hot-path
    Redis read. Optional — empty when the caller does not have it.
    """

    agent_id: str | None = None
    """AgentID is optional: the UUID of the agent speaking, so prompt_confidentiality protects that
    agent's own prompt when the configuration is shared by several agents. Must be a UUID; any
    other value is ignored (never a 400, to keep the hot path fail-open) and the check falls
    back to the configuration's shared prompt set, visible as prompt_scope=shared_union in the
    response.
    """
    stream_segment: bool | None = None
    """StreamSegment is internal: set only by the LLM proxy for streamed segments (enables cross-
    segment matching). Direct callers should omit it.
    """


class CheckResult(_Base):
    """Outcome produced by a single compliance check."""

    check_id: str
    verdict: str
    reason: str = ""
    modified_content: str = ""
    duration_ms: float = 0.0
    mode: str = ""
    """
    Validator mode marker for this check: ``"enforce"``, ``"shadow"``, or
    ``"off"`` (``tenant.Configuration.validator_modes`` override). Empty
    when the server did not report a mode (older responses).
    """
    not_run: bool = False
    """``True`` when this check was skipped entirely (e.g. ``mode="off"``)."""
    not_evaluated: bool = False
    """``True`` when the check short-circuited without a full evaluation."""
    shadow_detection: bool = False
    """``True`` when a shadow-mode check would have fired (never affects the
    aggregated verdict — see ``shadow_verdict``)."""
    shadow_verdict: str = ""
    """The verdict a ``mode="shadow"`` check would have produced, for
    observability only; the aggregated ``ValidateResponse.verdict`` never
    reflects it."""
    shadow_findings: int = 0
    """Number of shadow-mode findings recorded for this check."""
    prompt_fingerprint: str | None = None
    """First 16 hex chars of ``sha256(prompt)`` (prompt-confidentiality check)."""
    layers: list[PromptDetectionLayer] | None = None
    """Detection layers that fired (prompt-confidentiality check)."""
    prompt_scope: PromptScope | None = None
    """``"agent"``, ``"shared_union"`` or ``"skipped"``."""

    detected_language: str | None = None
    """Detected language of the checked text (BCP-47-ish, e.g. ``"nl"``)."""
    negation_lexicon_version: str | None = None
    """Version of the negation lexicon used by the check (e.g. ``"v1"``)."""


class CheckScoreEntry(_Base):
    """Per-check compliance score contribution."""

    check_id: str
    verdict: str
    weight: float
    score: float


class ComplianceScore(_Base):
    """Weighted composite compliance score."""

    composite: float
    check_scores: list[CheckScoreEntry] = Field(default_factory=list)
    total_weight: float


class FailOpenMeta(_Base):
    """Diagnostic metadata included when ``fail_open`` is ``True``."""

    reason: str
    deadline_ms: float
    elapsed_ms: float
    checks_completed: int


class Receipt(_Base):
    """
    Compliance receipt providing cryptographic commitments to input/output.

    .. note::
        For MODIFY verdicts: ``input_hash`` is the original text hash;
        ``output_hash`` is the modified text hash.
    """

    receipt_format_version: str
    call_id: UUID
    timestamp: datetime
    input_hash: str
    output_hash: str
    verdict: ReceiptVerdict
    config_version: int
    config_seal_hash: str
    policy_version: str
    evidence_hash: str
    auth_mechanism: str
    signature: str

    # Populated only in later receipt-format versions (receipt.Receipt) —
    # zero-valued/empty when absent so existing v1.0.0-shaped callers are
    # unaffected.
    candidate_count: int = 0
    """Total candidates generated (v1.1.0+ multi-candidate path)."""
    candidate_set_hash: str = ""
    delivery_attestation_hash: str = ""
    """Hash of the DELIVERY_ATTESTATION evidence event; empty until confirmed (v1.2.0+)."""
    delivery_status: str = ""
    """``"confirmed"``, ``"unconfirmed"``, or ``"mismatch"``; empty pre-attestation."""
    confirmation_grade: str = ""
    """``"independent"``, ``"platform_sourced"``, or ``"unconfirmed"``."""
    early_terminated: bool = False
    selected_candidate_id: str = ""


class ValidateResponse(_Base):
    """Response body from ``POST /v1/validate``."""

    call_id: UUID
    turn: int
    verdict: str
    """One of ``ALLOW``, ``BLOCK``, ``MODIFY``."""

    content: str
    """Final text after all checks have been applied."""

    fail_open: bool = False
    fail_open_meta: FailOpenMeta | None = None
    receipt: Receipt | None = None
    compliance_score: ComplianceScore | None = None
    checks: list[CheckResult] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Policy Engine — POST /v1/evaluate
# ─────────────────────────────────────────────────────────────────────────────

class EvaluateRequest(_Base):
    """Request body for ``POST /v1/evaluate``."""

    country: str
    """ISO 3166-1 alpha-2 country code (case-insensitive)."""

    context: dict[str, Any]
    """Call-level fields referenced by rule conditions."""

    agent_id: str | None = None
    """AgentID is the voice/chat agent that triggered this evaluation. Optional; used for
    compliance.policy_evaluated event correlation.
    """
    call_id: str | None = None
    """CallID is the call session ID for this evaluation. Optional; used for
    compliance.policy_evaluated event correlation.
    """
    language: str | None = None
    """Language is the BCP-47 language code of the caller/agent voice (e.g. "de-DE" or "nl-NL").
    Optional; when absent, disclosure lookup is skipped. Caller language wins: this
    language is resolved against the language-indexed disclosure catalog first — independent of
    the jurisdiction being evaluated — and only falls back to the jurisdiction's own templates
    (then en-US) when the catalog has no entry for it at all. The response's DisclosureLanguage
    reports the language key actually matched, which may differ from this field on fallback.
    """
    tenant_id: str | None = None
    """TenantID is the Audact tenant that owns this evaluation. Optional; used for
    compliance.policy_evaluated event correlation.
    """


class EvaluateResponse(_Base):
    """Response body from ``POST /v1/evaluate``."""

    verdict: PolicyVerdict
    """``ALLOW`` or ``BLOCK``."""

    reasons: list[str] = Field(default_factory=list)
    applicable_rules: list[str] = Field(default_factory=list)
    policy_version: str

    disclosure_language: str | None = None
    """DisclosureLanguage is the BCP-47 language key that DisclosureText was actually resolved
    under — never the raw requested Language. Caller language wins: this is the caller-
    language catalog match when available, falling back to a jurisdiction template match (and
    finally en-US) only when the caller's language has no catalog entry at all. The pipeline
    records this value as the language honestly served to the caller, so it must never be
    assumed to equal the requested Language. Only set when RequireDisclosure is true.
    """
    disclosure_text: str | None = None
    """DisclosureText is the exact text to synthesize via TTS. Only set when RequireDisclosure is
    true.
    """
    next_permitted_at: datetime | None = None
    """NextPermittedAt is set only when Verdict is BLOCK and the block is time-bounded (i.e. caused
    by quiet hours / calling-hours restrictions, not a permanent reason such as a DNC
    registration or missing consent). It is the earliest UTC time at which the call would be
    permitted, so callers (e.g. the SIP gateway's pre-dial check) can surface a retry_after-
    style hint instead of a generic "try later". Omitted (nil) when the block is not time-
    bounded, or when Verdict is ALLOW.
    """
    require_disclosure: bool = False
    """RequireDisclosure is true when the jurisdiction requires a disclosure statement to be played
    at call start.
    """


# ─────────────────────────────────────────────────────────────────────────────
# Evidence Layer — POST /v1/events, GET /v1/chains, etc.
# ─────────────────────────────────────────────────────────────────────────────

class PostEventRequest(_Base):
    """Request body for ``POST /v1/events``."""

    call_id: UUID
    tenant_id: UUID
    event_type: str
    data: dict[str, Any] | None = None


class PostEventResponse(_Base):
    """Response body from ``POST /v1/events`` (hash receipt)."""

    event_id: UUID
    call_id: UUID
    tenant_id: UUID
    sequence: int
    hash: str
    previous_hash: str
    timestamp: datetime


class EvidenceEvent(_Base):
    """A single event in an evidence chain."""

    event_id: UUID
    call_id: UUID
    tenant_id: UUID
    event_type: str
    sequence: int
    hash: str
    previous_hash: str
    timestamp: datetime
    data: dict[str, Any] | None = None


class GetChainResponse(_Base):
    """Response body from ``GET /v1/chains/{call_id}``."""

    call_id: UUID
    events: list[EvidenceEvent] = Field(default_factory=list)

    has_more: bool = False
    """HasMore is true when there are additional events beyond this page."""
    next_cursor: int | None = None
    """NextCursor is the sequence number to pass as after_sequence in the next request to retrieve
    the next page. It equals the Sequence of the last event in Events. Omitted (zero-value) when
    HasMore is false.
    """


class VerifyChainResponse(_Base):
    """Response body from ``GET /v1/verify/{call_id}``."""

    call_id: UUID
    valid: bool = False
    """Derived from ``status == "VALID"`` when the server omits it."""
    event_count: int
    message: str = ""

    @model_validator(mode="before")
    @classmethod
    def _valid_from_status(cls, data: Any) -> Any:
        if isinstance(data, dict) and "valid" not in data and "status" in data:
            data = {**data, "valid": data["status"] == "VALID"}
        return data

    status: str | None = None
    """Status is "VALID" when all hash links are intact, "INVALID" when tamper is detected."""
    broken_at_sequence: int | None = None
    """BrokenAtSequence is -1 when Status is "VALID", or the 1-based sequence number of the first
    broken link when Status is "INVALID".
    """


class ReconstructResponse(_Base):
    """Response body from ``GET /v1/reconstruct/{call_id}``."""

    call_id: UUID
    events: list[EvidenceEvent] = Field(default_factory=list)

    chain_status: str | None = None
    """ChainStatus is "VALID" when all hash links are intact, "INVALID" when tamper is detected
    (real check implemented in M5-012).
    """
    event_count: int | None = None
    """EventCount is the total number of events in the reconstructed chain."""
    policy_version: str | None = None
    """PolicyVersion is the config_seal_hash of the most recent event in the chain. For calls where
    all events share the same config, this is the single policy version active throughout the
    call. When the configuration changed mid-call (e.g. a hot reload), individual event
    ConfigSealHash fields show exactly when each version was in effect.
    """
    config_versions: dict[str, ResolvedConfigVersion] = Field(default_factory=dict)
    """ConfigVersions maps each distinct config_seal_hash encountered in the evidence chain to its
    resolved configuration version. Keyed by the seal hash string so callers can look up per-
    event configurations in O(1). Entries are omitted for seal hashes that cannot be resolved
    (e.g. legacy events written before the configurations table existed). Soft-deleted
    configurations ARE included — this is the only endpoint that returns them.
    """


# ─────────────────────────────────────────────────────────────────────────────
# Evidence Layer completion — calls, violations, article50, c2pa,
# receipts, delivery, reconciliation, verification.
#
# These models mirror the Evidence Layer's JSON wire types (the documented
# API's evidence/article50/c2pa/receipts/delivery/reconciliation/verification
# tags).
# ─────────────────────────────────────────────────────────────────────────────

class CallRecord(_Base):
    """One row of :class:`ListCallsResponse` (``evidence.CallRecord``)."""

    call_id: UUID
    tenant_id: UUID
    direction: CallDirection
    """``"inbound"`` or ``"outbound"``."""

    status: str
    """One of: ``active``, ``completed``, ``failed``, ``abandoned``."""

    started_at: datetime
    ended_at: datetime | None = None
    channel: str | None = None
    """Media channel: ``"webrtc"`` (browser) or ``"pstn"``. ``None`` for
    historical calls recorded before the channel column existed."""

    metadata: dict[str, Any] | None = None
    """Arbitrary per-call metadata supplied when the call was created."""

    created_at: datetime


class ListCallsResponse(_Base):
    """
    Raw response body from ``GET /v1/calls`` (``evidence.GetCallsResponse``).

    :meth:`~audact.client.AudactClient.list_calls` returns this reshaped into
    the shared :class:`Page` convention.
    """

    calls: list[CallRecord] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: str | None = None


class TranscriptTurn(_Base):
    """A single decrypted transcript turn within :class:`CallDetail`."""

    role: str
    """``"agent"`` or ``"human"``."""

    content: str


class CallComplianceScore(_Base):
    """The finalized composite compliance score embedded in :class:`CallDetail`."""

    composite: float = 0.0
    total_turns: int = 0
    turns_with_violations: int = 0
    fail_open_count: int = 0


class CallDetail(_Base):
    """Response body from ``GET /v1/calls/{call_id}`` (``evidence.CallDetail``)."""

    call_id: UUID
    tenant_id: UUID
    agent_id: str = ""
    """
    Not currently populated server-side — always
    empty today.
    """

    direction: CallDirection
    status: str
    connected: bool | None = None
    termination_class: TerminationClass | None = None
    sip_response_code: int | None = None
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] | None = None
    """Arbitrary per-call metadata supplied when the call was created."""
    recording_available: bool = False
    recording_ref: str = ""
    transcript: list[TranscriptTurn] = Field(default_factory=list)
    compliance_score: CallComplianceScore | None = None
    """Not currently populated server-side."""

    evidence_link: str = ""
    """Not currently populated server-side."""

    pii_mode: PIIMode | None = None
    """The call's PII mode fixed at call start: ``"encrypt"`` or ``"redact"``;
    ``None`` when not recorded (calls recorded before PII identifiers existed)."""

    transcript_status: TranscriptStatus | None = None
    """Why ``transcript`` is (or is not) populated, so an empty list is never
    ambiguous: ``"ok"`` = decrypted (text carries PII tokens, returned as
    stored); ``"none"`` = no transcript stored yet; ``"unavailable"`` = a
    transcript exists but could not be decrypted; ``"erased"`` = the tenant's
    PII keyring was destroyed."""

    _blank_enums = _blank_to_none("termination_class")


class RecordingResponse(_Base):
    """Response body from ``GET /v1/calls/{call_id}/recording``."""

    call_id: UUID
    url: str
    """Short-lived (15-minute) signed download URL — never proxied through the evidence layer."""

    expires_at: datetime


class CallEndSummary(_Base):
    """End-of-call detection context embedded in :class:`CallSummary`."""

    termination_reason: str = ""
    termination_confidence: float | None = None
    termination_matched_phrase_key: str = ""
    voicemail_detected: bool = False
    voicemail_confidence: float | None = None
    voicemail_matched_phrase_key: str = ""
    voicemail_reason: str = ""
    disclosure_skipped_voicemail: bool = False
    disclosure_skip_reason: str = ""
    detected_at: datetime | None = None


class HandoverSummary(_Base):
    """Latest warm-handover context embedded in :class:`CallSummary`."""

    handover_id: str = ""
    handover_reason: str = ""
    whisper_mode: bool = False
    destination_hash: str = ""
    summary_text: str = ""
    summary_source: str = ""
    outcome: str = ""
    completed_at: datetime | None = None


class CallSummary(_Base):
    """Response body from ``GET /v1/calls/{call_id}/summary`` (``evidence.CallSummary``)."""

    call_id: UUID
    tenant_id: UUID
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    event_count: int = 0
    allow_count: int = 0
    modify_count: int = 0
    block_count: int = 0
    handover: HandoverSummary | None = None
    """``None`` when the call never triggered a handover."""

    call_end: CallEndSummary | None = None
    """``None`` when the call never recorded a ``CALL_END_DETECTED`` event."""

    analysis_status: AnalysisStatus | None = None
    """Whether the post-call analysis below is available: ``"ok"`` once the
    ``call_summary`` event was produced and stored, ``"none"`` before that,
    ``"unavailable"`` when the stored analysis could not be decrypted."""

    summary_status: SummaryStatus | None = None
    """Status of the post-call summary exactly as delivered in the
    ``call_summary`` webhook. Present only when ``analysis_status`` is
    ``"ok"``."""

    sentiment: str | None = None
    """Post-call sentiment (e.g. ``"positive"``), as in the ``call_summary`` webhook."""

    disposition: str | None = None
    """Post-call disposition (e.g. ``"callback_requested"``)."""

    key_facts: list[str] | None = None
    """Key facts extracted from the call."""

    extraction: dict[str, Any] | None = None
    """``{"values": {...}, "status": "ok"|"degraded"}``, or ``None`` when
    ``post_call_extraction`` is not enabled for the agent."""


class ViolationRecord(_Base):
    """One row of :class:`ListViolationsResponse` (``evidence.ViolationRecord``)."""

    event_id: UUID
    call_id: UUID
    tenant_id: UUID
    event_type: str
    """Always ``"CHECK_RESULT"`` for violation records."""

    sequence: int
    hash: str
    data: Any = None
    """Event payload; its shape depends on ``event_type``."""

    timestamp: datetime


class ListViolationsResponse(_Base):
    """
    Raw response body from ``GET /v1/violations`` (``evidence.GetViolationsResponse``).

    :meth:`~audact.client.AudactClient.list_violations` returns this reshaped
    into the shared :class:`Page` convention.
    """

    violations: list[ViolationRecord] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Article 50 evidence export (``GET /v1/calls/{call_id}/article50-report``,
# ``GET /v1/evidence-exports/{call_id}``)
# ─────────────────────────────────────────────────────────────────────────────

class Article50Acknowledgement(_Base):
    """Disclosure-delivered attestation (never a captured caller ack)."""

    type: str = ""
    basis: str = ""
    event_id: str = ""
    event_hash: str = ""


class Article50DisclosureLanguageFallback(_Base):
    """Set when the served disclosure language differs from the requested one."""

    from_: str = Field(default="", alias="from")
    to: str = ""


class Article50Disclosure(_Base):
    """The Article 50 disclosure + delivery attestation section."""

    status: str = ""
    """One of: ``delivered``, ``failed``, ``not_required``, ``incomplete``."""

    delivered: bool = False
    utterance: str = ""
    language: str = ""
    language_fallback: Article50DisclosureLanguageFallback | None = None
    duration_ms: int = 0
    played_at: datetime | None = None
    jurisdiction: str = ""
    config_seal_hash: str = ""
    acknowledgement: Article50Acknowledgement | None = None
    """``None`` when ``status == "not_required"``."""


class Article50EventIndexEntry(_Base):
    """A single compact, hash-only event index entry within :class:`Article50EvidenceChain`."""

    sequence: int
    event_type: str
    hash: str
    previous_hash: str
    timestamp: datetime


class Article50EvidenceChain(_Base):
    """The full hash-chain integrity section. Never includes raw event_data."""

    chain_status: str = ""
    """``"valid"`` or ``"invalid"`` (``hash.VerifyChain`` verdict)."""

    event_count: int = 0
    genesis_hash: str = ""
    head_hash: str = ""
    ordering: str = ""
    events: list[Article50EventIndexEntry] = Field(default_factory=list)


class Article50MerkleProofStep(_Base):
    """One step of a Merkle authentication path."""

    hash: str
    position: str
    """``"left"`` or ``"right"``."""


class Article50BranchProof(_Base):
    """A Merkle inclusion proof from a leaf up to a root."""

    leaf_hash: str = ""
    leaf_index: int = 0
    leaf_count: int = 0
    pad_count: int = 0
    tree_depth: int = 0
    root: str = ""
    steps: list[Article50MerkleProofStep] = Field(default_factory=list)


class Article50AnchoredEvent(_Base):
    """The terminal (chain-head) event a :class:`Article50MerkleProof` anchors."""

    hash: str = ""
    sequence: int = 0


class Article50MerkleProof(_Base):
    """The cross-tenant Merkle branch proof section."""

    status: str = ""
    """One of: ``available``, ``pending``, ``unavailable``."""

    window_id: str = ""
    """Empty while ``status == "pending"``."""

    merkle_root: str = ""
    tenant_leaf: str = ""
    anchored_event: Article50AnchoredEvent | None = None
    event_inclusion_proof: Article50BranchProof | None = None
    cross_tenant_proof: Article50BranchProof | None = None
    available_after: datetime | None = None
    """An estimate, not a guarantee — populated only while ``status == "pending"``."""

    retrieve_via: str = ""


class Article50ReceiptRef(_Base):
    """
    One compliance receipt reference within :class:`Article50Report`.

    Unlike ``turn`` (which may repeat across multi-sentence responses),
    ``sequence``/``event_id`` uniquely and monotonically identify a receipt.
    """

    event_id: str
    sequence: int
    turn: int
    verdict: str
    receipt_format_version: str = ""
    input_hash: str = ""
    output_hash: str = ""
    """Present on MODIFY events."""

    auth_mechanism: str = ""
    signature: str = ""
    verifiability: str = "unknown"
    """One of ``"verifiable"``, ``"unverifiable_pre_horizon"``, ``"unknown"``."""


class Article50ConfigurationSeal(_Base):
    """Binds the report to the exact tenant configuration in effect at CALL_START."""

    call_config_seal_hash: str = ""
    config_version: int = 0
    policy_version: str = ""
    seal_algorithm: str = ""


class Article50Signature(_Base):
    """The report-level ECDSA-P256 tamper seal."""

    auth_mechanism: str = ""
    key_id: str = ""
    public_key_url: str = ""
    scope: str = ""
    value: str = ""
    """Hex-encoded ASN.1 DER ECDSA(r,s) signature; empty until signed."""


class Article50TSATimestamp(_Base):
    """The RFC 3161 trusted-timestamp section."""

    status: str = ""
    covers: str = ""
    timestamp_time: datetime | None = None
    timestamp_token: str = ""
    """Base64-encoded DER ``TimeStampToken``; populated only when ``status == "available"``."""

    tsa_url: str = ""


class Article50Report(_Base):
    """
    Response body from ``GET /v1/calls/{call_id}/article50-report`` and
    ``GET /v1/evidence-exports/{call_id}`` when ``format=json`` (the default).

    Requesting ``format=pdf`` instead returns raw PDF bytes — see
    :meth:`~audact.client.AudactClient.get_article50_report`.
    """

    report_type: str = ""
    """Always ``"article_50_evidence_export"``."""

    report_format_version: str = ""
    call_id: UUID
    tenant_id: UUID
    direction: Literal["inbound", "outbound"] | None = None
    generated_at: datetime
    configuration_seal: Article50ConfigurationSeal | None = None
    disclosure: Article50Disclosure | None = None
    receipts: list[Article50ReceiptRef] = Field(default_factory=list)
    evidence_chain: Article50EvidenceChain | None = None
    merkle_proof: Article50MerkleProof | None = None
    tsa_timestamp: Article50TSATimestamp | None = None
    signature: Article50Signature | None = None

    _blank_enums = _blank_to_none("direction")

    channel: str | None = None
    """Channel is the call's transport axis — "webrtc" for browser-originated test calls, "pstn"
    otherwise — read from the signed CALL_START evidence event. This is a SEPARATE
    dimension from Direction: a browser test call reports Direction "inbound" and Channel
    "webrtc". Omitted for calls recorded before channel was added to CALL_START, whose evidence
    carries no such value — absence, never a guessed default.
    """


# ─────────────────────────────────────────────────────────────────────────────
# C2PA manifests (``POST /v1/calls/{call_id}/c2pa``)
# ─────────────────────────────────────────────────────────────────────────────

class C2PAMerkleProofReference(_Base):
    """
    A reference to (not the full steps of) a Merkle aggregation window
    covering this call. Fetch the full proof via ``GET /v1/proofs/{window_id}``.
    """

    window_id: str = ""
    merkle_root: str = ""
    leaf_hash: str = ""
    proof_available: bool = False


class C2PAReceiptReference(_Base):
    """A compliance receipt reference within :class:`C2PAComplianceAssertionData`."""

    event_id: str
    receipt_hash: str = ""
    verdict: str = ""


class C2PAComplianceAssertionData(_Base):
    """The compliance assertion payload for a C2PA manifest."""

    call_id: UUID
    tenant_id: UUID
    overall_compliance: str = ""
    """One of: ``compliant``, ``partial``, ``non_compliant``, ``unknown``."""

    segments_validated: int = 0
    segments_compliant: int = 0
    segments_modified: int = 0
    evidence_chain_verified: bool = False
    delivery_attestation_status: str = ""
    """One of: ``attested``, ``not_attested``, ``failed``."""

    receipt_references: list[C2PAReceiptReference] = Field(default_factory=list)
    merkle_proof_reference: C2PAMerkleProofReference | None = None
    """``None`` when no aggregation window covers this call."""


class C2PAClaimGeneratorInfo(_Base):
    """A single generator name/version pair."""

    name: str = ""
    version: str = ""


class C2PAAction(_Base):
    """One entry of a standard ``c2pa.actions`` assertion (C2PA 2.2 schema)."""

    action: str = ""
    """E.g. ``"c2pa.created"``."""

    digitalSourceType: str = ""
    """IPTC digital source type URI, e.g. ``…/compositeSynthetic``."""

    softwareAgent: C2PAClaimGeneratorInfo | None = None
    description: str = ""


class C2PAActionsAssertionData(_Base):
    """Payload of the ``c2pa.actions`` assertion declaring AI-generated content."""

    actions: list[C2PAAction]


class C2PAHashDataAssertionData(_Base):
    """Payload of the ``c2pa.hash.data`` assertion: the hard binding to the asset."""

    alg: str = ""
    """Hash algorithm, e.g. ``"sha256"``."""

    hash: str = ""
    """Hex-encoded digest of the bound asset bytes."""

    name: str = ""


class C2PAAssertion(_Base):
    """A single factual statement about the asset within a C2PA manifest.

    Audact manifests carry ``com.audact.compliance`` (always ``assertions[0]``,
    ``data`` is :class:`C2PAComplianceAssertionData`) and ``c2pa.actions``
    (``data`` is :class:`C2PAActionsAssertionData`) and ``c2pa.hash.data``
    (``data`` is :class:`C2PAHashDataAssertionData`).
    """

    label: C2PAAssertionLabel | None = None
    """``"com.audact.compliance"``, ``"c2pa.actions"`` or ``"c2pa.hash.data"``."""

    data: C2PAComplianceAssertionData | C2PAActionsAssertionData | C2PAHashDataAssertionData

    _blank_enums = _blank_to_none("label")


class C2PAClaim(_Base):
    """Describes the asset and the software that produced a C2PA manifest."""

    claim_generator: str = Field(default="", alias="claim_generator")
    claim_generator_info: list[C2PAClaimGeneratorInfo] = Field(default_factory=list)
    dc_format: str = Field(default="", alias="dc:format")
    dc_title: str = Field(default="", alias="dc:title")


class C2PAAssetRef(_Base):
    """The asset the manifest is hard-bound to (``asset`` in the summary)."""

    kind: C2PAAssetKind | None = None
    """``"recording"``, or ``"evidence_export"`` when the call has no recording."""

    media_type: str = ""
    sha256: str = ""
    url: str = ""
    """Relative API path; download with :meth:`AudactClient.download_c2pa_asset`."""

    _blank_enums = _blank_to_none("kind")


class C2PAManifestStoreRef(_Base):
    """The stored C2PA manifest store (JUMBF, ``application/c2pa``)."""

    media_type: str = ""
    sha256: str = ""
    url: str = ""
    """Relative API path; download with :meth:`AudactClient.download_c2pa_manifest_store`."""


class C2PASigningCredential(_Base):
    """Public details of the X.509 credential that signed the manifest (no key material)."""

    subject: str = ""
    issuer: str = ""
    serial: str = ""
    not_before: datetime | None = None
    not_after: datetime | None = None
    fingerprint_sha256: str = ""
    trust: C2PATrust | None = None
    """``"self_signed"`` (Audact root, not on the C2PA Trust List) or ``"ca_issued"``."""

    _blank_enums = _blank_to_none("trust")


class C2PAListSigner(_Base):
    """The stored subset of the signing credential carried by a list item."""

    fingerprint_sha256: str = ""
    trust: C2PATrust | None = None
    """``"self_signed"`` or ``"ca_issued"``."""

    _blank_enums = _blank_to_none("trust")


class C2PAManifestListItem(_Base):
    """
    One entry of ``GET /v1/calls/{call_id}/c2pa``.

    A SUBSET of :class:`C2PAManifest`: there is no ``claim`` and no
    ``assertions``, and ``signing_credential`` carries only the fingerprint and
    trust. Download the manifest store for the full content.
    """

    manifest_id: str
    call_id: UUID
    signature_algorithm: str = ""
    asset: C2PAAssetRef | None = None
    manifest_store: C2PAManifestStoreRef | None = None
    signing_credential: C2PAListSigner | None = None
    generated_at: datetime | None = None


class C2PAManifest(_Base):
    """
    C2PA content credential summary (``POST /v1/calls/{call_id}/c2pa``).

    **Breaking (generator 2.0.0):** the HMAC ``signature`` field was removed;
    the manifest is signed ES256 with an X.509 chain. Download the real
    manifest store and verify it independently with ``c2patool``.
    """

    manifest_id: str = ""
    call_id: UUID | None = None
    claim: C2PAClaim
    assertions: list[C2PAAssertion] = Field(default_factory=list)
    """``[0]`` compliance, then ``c2pa.actions`` and ``c2pa.hash.data``."""

    signature_algorithm: str = ""
    """``"ES256"``."""

    asset: C2PAAssetRef | None = None
    manifest_store: C2PAManifestStoreRef | None = None
    signing_credential: C2PASigningCredential | None = None
    generated_at: datetime


class C2PAManifestListResponse(_Base):
    """
    Raw response body from ``GET /v1/calls/{call_id}/c2pa``
    (``c2pa.ManifestListResponse``).

    :meth:`AudactClient.list_c2pa_manifests` reshapes this into the shared
    :class:`Page` convention; ``has_more`` is derived from ``next_cursor``.
    """

    manifests: list[C2PAManifestListItem] = Field(default_factory=list)
    next_cursor: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Compliance receipts (``GET /v1/receipts/{call_id}``)
# ─────────────────────────────────────────────────────────────────────────────

class GetReceiptResponse(_Base):
    """
    Response body from ``GET /v1/receipts/{call_id}``.

    ``verifiability`` distinguishes a receipt that predates
    ``RECEIPT_HMAC_KEY`` provisioning (``hmac_valid`` false but NOT
    tampering) from a genuinely invalid signature.
    """

    receipt: Receipt
    hmac_valid: bool
    verifiability: str = "unknown"
    """One of ``"verifiable"``, ``"unverifiable_pre_horizon"``, ``"unknown"``."""


# ─────────────────────────────────────────────────────────────────────────────
# Delivery attestation (``GET/POST .../delivery``, ``/v1/delivery-confirmation``)
# ─────────────────────────────────────────────────────────────────────────────

class TurnDeliveryStatus(_Base):
    """One element of the array returned by ``GET /v1/calls/{call_id}/delivery``."""

    turn_number: int
    status: str
    """One of: ``pending``, ``confirmed``, ``mismatch``, ``unconfirmed``."""

    mechanism: str = ""
    """One of: ``webhook``, ``api_query``, ``tts_completion``, ``audio_monitoring``."""

    confirmation_grade: str = ""
    """One of: ``independent``, ``platform_sourced``, ``unconfirmed``."""

    confirmation_count: int | None = None
    """How many delivery confirmations exist for the turn. When more than 1, the
    other fields describe the worst of them. ``None`` while pending."""

    content_match: bool | None = None
    """``None`` while pending."""

    mismatch_type: str = ""
    mismatch_severity: str = ""
    """``"benign"`` or ``"material"``; empty unless ``content_match`` is ``False``."""

    linking_hash: str = ""
    confirmed_at: datetime | None = None


class ConfirmDeliveryRequest(_Base):
    """Request body for ``POST /v1/delivery-confirmation``."""

    call_id: UUID
    turn_number: int
    mechanism: str
    """One of: ``webhook``, ``api_query``, ``tts_completion``, ``audio_monitoring``."""

    delivered_text: str | None = None
    audio_hash: str | None = None
    asr_transcription: str | None = None
    asr_confidence: float | None = None
    platform_timestamp: datetime | None = None

    validated_segments: list[str] | None = None
    """Optional. The texts the proxy streamed for this turn, one entry per proxy stream chunk,
    verbatim (including leading/trailing whitespace) and in the order they were streamed. Each
    entry is verified against its own per-segment validation receipt. Omit together with
    delivered_segments when the response was not streamed in segments.
    """
    delivered_segments: int | None = None
    """Optional. How many LEADING validated_segments entries were fully played to the caller
    (0..len(validated_segments)). Meaningful only together with validated_segments; must be 0 or
    omitted when validated_segments is absent. When validated_segments is sent, delivered_text
    must equal the first delivered_segments entries concatenated with no separator.
    """
    interrupted: bool | None = None
    """Whether playback of the turn was interrupted by the caller."""


class ProcessConfirmationResult(_Base):
    """Response body from ``POST /v1/delivery-confirmation``."""

    attestation_event_id: UUID
    confirmation_grade: str
    """One of: ``independent``, ``platform_sourced``. Always present."""

    content_match: bool
    mismatch_type: str = ""
    mismatch_severity: str = ""
    """Empty when ``content_match`` is ``True``."""

    linking_hash: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Post-call transcript reconciliation (``POST /v1/transcript-reconciliation``)
# ─────────────────────────────────────────────────────────────────────────────

class ReconcileTranscriptSegment(_Base):
    """One segment of a post-call transcript to reconcile against validated output."""

    turn_number: int | None = None
    text: str = ""
    speaker: str = ""


class ReconcileTranscriptRequest(_Base):
    """Request body for ``POST /v1/transcript-reconciliation``."""

    call_id: UUID
    segments: list[ReconcileTranscriptSegment] = Field(default_factory=list)
    source: str = ""
    """Identifies the provider/system that produced the transcript."""


class ReconciliationSegmentResult(_Base):
    """One row of :class:`ReconcileTranscriptResponse`'s ``segment_results``."""

    turn_number: int | None = None
    matched: bool = False
    reason: str = ""

    status: ReconciliationSegmentStatus | None = None
    """Status is one of "matched", "mismatched", or "unvalidated"."""
    sequence_number: int | None = None
    """SequenceNumber corresponds to the segment's turn_number."""
    mismatch_classification: str | None = None
    """MismatchClassification is populated only when Status == "mismatched"."""
    transcript_hash: str | None = None
    """TranscriptHash is the server-computed SHA-256 of the transcript segment text."""
    validated_hash: str | None = None
    """ValidatedHash is the SHA-256 stored in the validation event, if present."""
    _blank_enums = _blank_to_none("status")


class ReconcileTranscriptResponse(_Base):
    """Response body from ``POST /v1/transcript-reconciliation``."""

    call_id: UUID
    total_segments: int = 0
    matched_segments: int = 0
    mismatched_segments: int = 0
    unvalidated_segments: int = 0
    segment_results: list[ReconciliationSegmentResult] = Field(default_factory=list)

    cross_turn_status: CrossTurnStatus | None = None
    """CrossTurnStatus says whether the semantic cross-turn contradiction pass ran, so "no
    findings" can be told apart from "did not run". Always present. disabled: detector not
    configured on this deployment; skipped_insufficient_turns: fewer than two agent turns (or an
    empty transcript); skipped_unknown_provider: the call's LLM provider could not be resolved;
    completed: the pass ran (findings may be empty); failed: the detector errored or timed out,
    or no finding could be recorded.
    """
    cross_turn_finding_count: int = 0
    """CrossTurnFindingCount is the number of semantic cross-turn contradictions recorded. Zero
    unless cross_turn_status is "completed" and something was found.
    """
    cross_turn_findings: list[CrossTurnFinding] = Field(default_factory=list)
    """CrossTurnFindings holds the advisory semantic contradiction findings. Omitted when none were
    recorded.
    """
    cross_turn_model: str | None = None
    """CrossTurnModel is the LLM model that analysed the transcript. Present only when
    cross_turn_status is "completed".
    """
    cross_turn_provider: str | None = None
    """CrossTurnProvider is the LLM provider that analysed the transcript (the same provider the
    agent used on the call). Present only when cross_turn_status is "completed".
    """


# ─────────────────────────────────────────────────────────────────────────────
# Tenant Management — /v1/tenants
# ─────────────────────────────────────────────────────────────────────────────

class CreateTenantRequest(_Base):
    """Request body for ``POST /v1/tenants``."""

    name: str
    plan: str = "starter"
    """Billing tier: ``starter``, ``professional``, or ``enterprise``."""

    key_name: str = "default"
    """Human-readable label for the tenant's first API key."""


class APIKeyInfo(_Base):
    """API key data returned in the tenant creation response."""

    key_id: str
    key: str
    """Full plaintext key — returned ONCE at creation; store it immediately."""

    key_prefix: str
    name: str
    role: str


class Tenant(_Base):
    """A registered Audact tenant."""

    tenant_id: UUID
    name: str
    plan: str
    hmac_key_arn: str
    created_at: datetime
    updated_at: datetime


class CreateTenantResponse(_Base):
    """Response body from ``POST /v1/tenants``."""

    tenant_id: UUID
    name: str
    plan: str
    hmac_key_arn: str
    created_at: datetime
    updated_at: datetime
    api_key: APIKeyInfo


class UpdateTenantRequest(_Base):
    """Request body for ``PUT /v1/tenants/{tenant_id}``."""

    name: str | None = None
    plan: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Tenant Management — API keys
# ─────────────────────────────────────────────────────────────────────────────

class GenerateKeyRequest(_Base):
    """Request body for ``POST /v1/tenants/{tenant_id}/keys``."""

    name: str = "default"
    role: str = "developer"


class GenerateKeyResponse(_Base):
    """Response body from ``POST /v1/tenants/{tenant_id}/keys``."""

    key_id: str = ""
    """Legacy name of ``api_key_id`` (filled from it when absent)."""
    key: str
    """Full plaintext key — returned ONCE; store it immediately."""

    key_prefix: str
    name: str
    role: str
    created_at: datetime

    api_key_id: str | None = None
    """APIKeyID is the server-generated UUID primary key."""
    tenant_id: str | None = None
    """TenantID is the UUID of the tenant that owns this key."""
    scopes: list[str] = Field(default_factory=list)
    """Scopes is the set of authorised operations for this key. An empty slice means no scope
    restrictions are configured.
    """
    expires_at: datetime | None = None
    """ExpiresAt is the optional expiry timestamp. nil means never expires."""
    revoked_at: datetime | None = None
    """RevokedAt is set when the key has been revoked. nil means active."""

    @model_validator(mode="before")
    @classmethod
    def _key_id_compat(cls, data: Any) -> Any:
        return _key_id_from_api_key_id(data)


class APIKey(_Base):
    """A summarised API key record (key material NOT included)."""

    key_id: str = ""
    """Legacy name of ``api_key_id`` (filled from it when absent)."""
    key_prefix: str
    name: str
    role: str
    created_at: datetime
    revoked_at: datetime | None = None

    api_key_id: str | None = None
    """APIKeyID is the server-generated UUID primary key."""
    tenant_id: str | None = None
    """TenantID is the UUID of the tenant that owns this key."""
    scopes: list[str] = Field(default_factory=list)
    """Scopes is the set of authorised operations for this key. An empty slice means no scope
    restrictions are configured.
    """
    expires_at: datetime | None = None
    """ExpiresAt is the optional expiry timestamp. nil means never expires."""

    @model_validator(mode="before")
    @classmethod
    def _key_id_compat(cls, data: Any) -> Any:
        return _key_id_from_api_key_id(data)


class ListKeysResponse(_Base):
    """Response body from ``GET /v1/tenants/{tenant_id}/keys``."""

    keys: list[APIKey] = Field(default_factory=list)

    has_more: bool = False
    """HasMore is true when additional keys exist beyond this page."""
    next_cursor: str | None = None
    """NextCursor is the opaque cursor to pass as ?cursor= to fetch the next page. Empty when
    HasMore is false.
    """


# ─────────────────────────────────────────────────────────────────────────────
# Tenant Management — configurations
# ─────────────────────────────────────────────────────────────────────────────

class BlocklistPattern(_Base):
    """A single blocklist pattern entry within a configuration."""

    id: str
    terms: list[str]
    severity: str
    """``modify`` or ``block``."""

    replacement_text: str = ""
    category: str = ""


class PromptConfidentialityConfig(_Base):
    """Sealed prompt-confidentiality settings.

    All fields are optional; the server applies the defaults noted below.
    """

    hardening: bool | None = None
    """Default ``True``."""
    canary: bool | None = None
    """Default ``True``; requires ``hardening``."""
    ngram: bool | None = None
    """Default ``True``."""
    ngram_size: int | None = None
    """Default 5; range 4-8."""
    ngram_min_matches: int | None = None
    """Default 2; range 1-10."""
    allowlist_phrases: list[str] | None = None
    """Default ``[]``; at most 50 entries of 1-300 chars."""


class CreateConfigurationRequest(_Base):
    """Request body for ``POST /v1/configurations``."""

    name: str
    countries: list[str]
    """ISO 3166-1 alpha-2 country codes from the supported launch set."""

    validator_modes: dict[str, str] | None = None
    blocklist_patterns: list[BlocklistPattern] | None = None
    pricing_bands: dict[str, Any] | None = None
    disclosure_texts: dict[str, Any] | None = None
    fallback_response: dict[str, Any] | None = None
    prompt_confidentiality_config: PromptConfidentialityConfig | None = None
    # LLM credentials (optional — use operator defaults when absent)
    upstream_llm_url: str | None = None
    """Custom LLM endpoint URL for this configuration."""
    upstream_llm_secret_arn: str | None = None
    """AWS Secrets Manager ARN for the customer LLM API key."""

    asr_config: dict[str, Any] | None = None
    """ASRConfig is the optional ASR provider configuration (M9 BYOK)."""
    auto_handover_config: dict[str, Any] | None = None
    """AutoHandoverConfig is the optional auto-handover-on-escalation policy. Shape:
    {"enabled": bool, "escalation_threshold": float [0,1], "cooldown_seconds": int >= 0}. When
    omitted, defaults to '{}' (auto-handover disabled).
    """
    consent_config: dict[str, Any] | None = None
    """ConsentConfig is an optional JSONB object of consent_gating rules. Shape:
    {"rules":[{action_type, action_phrases, consent_type, consent_phrases}]}.
    """
    end_call: EndCallConfig | None = None
    """EndCall is the optional agent-initiated end-of-call policy. When omitted,
    defaults to the zero value (feature disabled — the agent never initiates call termination on
    its own).
    """
    multi_candidate: dict[str, Any] | None = None
    """MultiCandidate is the optional multi-candidate generation config (M7). JSON:
    MultiCandidateConfig. When omitted, defaults to '{}' (disabled).
    """
    output_constraint: dict[str, Any] | None = None
    """OutputConstraint is the optional output constraint enforcement config (M7). JSON:
    OutputConstraint. When omitted, defaults to '{}' (disabled).
    """
    record_calls: bool | None = None
    """RecordCalls opts this configuration into call recording.
    Optional; nil/omitted defaults to false (no recording — the privacy-preserving default).
    Scope is per-configuration. This is an OPERATIONAL toggle, NOT a compliance-sealed decision:
    it is deliberately excluded from config_seal_hash, so flipping recording on/off never
    invalidates the configuration seal.
    """
    recording_retention_days: int | None = None
    """RecordingRetentionDays optionally overrides the platform default recording retention
    window. When present, must be in [1, 3650] days — any other value is rejected with a 400.
    nil/omitted means "use the platform default".
    Like RecordCalls, this is NOT part of config_seal_hash.
    """
    tenant_id: str | None = None
    """TenantID is IGNORED — the owning tenant is always derived from the authenticated caller's
    identity (Security Fix M3-047), never from this field. Left in the request schema only for
    backwards-compatible clients; do not rely on it to target a specific tenant.
    """
    upstream_llm_key: str | None = Field(default=None, repr=False)
    """UpstreamLLMKey is the optional raw API key / bearer token for UpstreamLLMURL. When provided,
    the service stores the key in AWS Secrets Manager, saves the returned ARN in
    upstream_llm_secret_arn, and NEVER persists the raw value in the database.
    """
    voicemail: VoicemailConfig | None = None
    """Voicemail is the optional voicemail-detection handling policy. When omitted,
    defaults to the zero value (feature disabled). Branch must be "leave_message" or "hangup"
    when non-empty; any other value is rejected with a 400.
    """


class Configuration(_Base):
    """A persisted tenant configuration."""

    config_id: UUID
    tenant_id: UUID
    name: str
    version: int
    countries: list[str]
    validator_modes: dict[str, Any] | None = None
    blocklist_patterns: list[dict[str, Any]] | None = None
    pricing_bands: dict[str, Any] | None = None
    disclosure_texts: dict[str, Any] | None = None
    fallback_response: dict[str, Any] | None = None
    config_seal_hash: str = ""
    prompt_confidentiality_config: PromptConfidentialityConfig | None = None
    upstream_llm_url: str | None = None
    """Custom LLM endpoint URL for this configuration."""
    upstream_llm_secret_arn: str | None = None
    """AWS Secrets Manager ARN for the customer LLM API key."""
    created_at: datetime
    updated_at: datetime

    asr_config: dict[str, Any] | None = None
    """ASRConfig is the ASR provider configuration (M9 BYOK). Stored as JSONB. Keys are managed via
    Secrets Manager (same as multi_candidate).
    """
    auto_handover_config: dict[str, Any] | None = None
    """AutoHandoverConfig is the auto-handover-on-escalation policy. Stored as JSONB.
    Shape: {"enabled": bool, "escalation_threshold": float [0,1], "cooldown_seconds": int >= 0}.
    Empty object "{}" means disabled.
    """
    begin_message: str = ""
    """BeginMessage is the static agent greeting spoken verbatim via TTS at connect (tirza-support-
    spec A2). Stored as TEXT in the begin_message column. Empty string (the default) means no
    static greeting is configured.
    """
    consent_config: dict[str, Any] | None = None
    """ConsentConfig is a JSONB object of consent_gating rules: {"rules":[{action_type,
    action_phrases, consent_type, consent_phrases}]}.
    """
    deleted_at: datetime | None = None
    """DeletedAt is set when the configuration has been soft-deleted. nil means active; non-nil
    means logically deleted.
    """
    end_call: EndCallConfig | None = None
    """EndCall is the agent-initiated end-of-call policy. Stored as JSONB in the
    end_call column; decoded directly into EndCallConfig. The zero value (empty object "{}")
    means the feature is off.
    """
    llm_model: str = ""
    """LLMModel is the concrete LLM model this configuration is sealed to run under (denormalized
    from agents.llm_model). Empty string means not yet
    backfilled/provisioned; proxy enforcement fails closed on empty. The current allow-list
    is "gpt-4.1-mini", "mistral-small-2603".
    """
    llm_provider: str = ""
    """LLMProvider is the LLM provider for LLMModel (denormalized from agents.llm_provider).
    Empty string means not yet backfilled/provisioned.
    """
    multi_candidate: dict[str, Any] | None = None
    """MultiCandidate is the multi-candidate generation config (M7). Stored as JSONB in the DB.
    json.RawMessage defers parsing to the multi-candidate config type.
    """
    output_constraint: dict[str, Any] | None = None
    """OutputConstraint is the output constraint enforcement config (M7). Stored as JSONB in the
    DB. json.RawMessage defers parsing to the output-constraint type.
    """
    pii_encryption_enabled: bool | None = None
    """PIIEncryptionEnabled is the sealed copy of the tenant's PII encryption switch.
    Part of config_seal_hash. Read-only: written only at configuration creation (inherited
    from the tenant setting) and by the atomic re-seal on a switch flip.
    PUT /v1/configurations/{config_id} ignores it when it equals the stored value
    and rejects a different value (400 pii_encryption_read_only); change it tenant-wide via PUT
    /v1/pii/settings.
    """
    post_call_extraction: PostCallExtractionConfig | None = None
    """PostCallExtraction is the agency-configurable custom post-call extraction schema.
    Stored as JSONB in the post_call_extraction column; decoded directly into
    PostCallExtractionConfig. The zero
    value (Enabled: false) means the feature is off.
    """
    post_call_summary: PostCallSummaryConfig | None = None
    """PostCallSummary is the agency-configurable post-call summary policy.
    Stored as JSONB in the post_call_summary column; decoded directly into PostCallSummaryConfig.
    The zero value (Enabled: false) means the
    feature is off.
    """
    record_calls: bool | None = None
    """RecordCalls is the opt-in call-recording policy. Defaults to false
    (privacy-preserving: no recording) when never set. Scope is per-configuration. This is an
    OPERATIONAL toggle, NOT a compliance-sealed decision — it is deliberately excluded from
    config_seal_hash, so turning recording on/off never invalidates the configuration seal.
    """
    recording_retention_days: int | None = None
    """RecordingRetentionDays optionally overrides the platform default recording retention
    window. nil means "use the platform default (30/90 days)"; when set, it is always in
    [1, 3650]. Like RecordCalls, this is NOT part of config_seal_hash.
    """
    start_speaker: str = ""
    """StartSpeaker is the "who speaks first" policy. Stored as TEXT in the
    start_speaker column. Allowed values: "agent" (default), "caller".
    """
    voicemail: VoicemailConfig | None = None
    """Voicemail is the voicemail-detection handling policy. Stored as JSONB in the
    voicemail column; decoded directly into VoicemailConfig.
    The zero value (Enabled: false) means the
    feature is off.
    """


class UpdateConfigurationRequest(_Base):
    """Request body for ``PUT /v1/configurations/{config_id}``."""

    name: str | None = None
    countries: list[str] | None = None
    validator_modes: dict[str, str] | None = None
    blocklist_patterns: list[BlocklistPattern] | None = None
    pricing_bands: dict[str, Any] | None = None
    disclosure_texts: dict[str, Any] | None = None
    fallback_response: dict[str, Any] | None = None
    prompt_confidentiality_config: PromptConfidentialityConfig | None = None

    asr_config: dict[str, Any] | None = None
    """ASRConfig is the optional ASR provider configuration (M9 BYOK)."""
    auto_handover_config: dict[str, Any] | None = None
    """AutoHandoverConfig is the optional auto-handover-on-escalation policy. Shape:
    {"enabled": bool, "escalation_threshold": float [0,1], "cooldown_seconds": int >= 0}. When
    omitted, defaults to '{}' (auto-handover disabled).
    """
    consent_config: dict[str, Any] | None = None
    """ConsentConfig is an optional JSONB object of consent_gating rules."""
    end_call: EndCallConfig | None = None
    """EndCall is the optional agent-initiated end-of-call policy. When omitted,
    defaults to the zero value (feature disabled — the agent never initiates call termination on
    its own).
    """
    multi_candidate: dict[str, Any] | None = None
    """MultiCandidate is the optional multi-candidate generation config (M7). JSON:
    MultiCandidateConfig. When omitted, defaults to '{}' (disabled).
    """
    output_constraint: dict[str, Any] | None = None
    """OutputConstraint is the optional output constraint enforcement config (M7). JSON:
    OutputConstraint. When omitted, defaults to '{}' (disabled).
    """
    record_calls: bool | None = None
    """RecordCalls opts this configuration into call recording.
    nil/omitted means "leave the stored value unchanged" (patch semantics — distinguishing
    "omitted" from "false" is exactly why this is a pointer, per the same pattern as
    UpstreamLLMURL/ UpstreamLLMKey above). This is an OPERATIONAL toggle, NOT a compliance-
    sealed decision: it is deliberately excluded from config_seal_hash.
    """
    recording_retention_days: int | None = None
    """RecordingRetentionDays optionally overrides the platform default recording retention
    window. When present, must be in [1, 3650] days — any other value is rejected with a 400.
    nil/omitted means "leave the stored value unchanged" (patch semantics).
    Like RecordCalls, this is NOT part of config_seal_hash.
    """
    upstream_llm_key: str | None = Field(default=None, repr=False)
    """UpstreamLLMKey is the optional raw API key / bearer token for UpstreamLLMURL. When provided,
    the service updates (or creates) the AWS Secrets Manager secret associated with this
    configuration. The raw value is NEVER persisted in the database.
    """
    upstream_llm_secret_arn: str | None = None
    """UpstreamLLMSecretARN is captured from the request JSON solely to detect and reject client-
    supplied ARNs (M4-055 security fix). The field is server-managed: it is derived from
    upstream_llm_key provisioning and must NEVER be accepted from the client. Any non-nil value
    triggers a 400 response before any other processing.
    """
    upstream_llm_url: str | None = None
    """UpstreamLLMURL is the optional base URL of the tenant's upstream LLM endpoint. nil / omitted
    means this configuration has no upstream LLM endpoint and cannot serve proxied LLM
    completions (the proxy returns an error); there is NO platform-default fallback.
    """
    voicemail: VoicemailConfig | None = None
    """Voicemail is the optional voicemail-detection handling policy. When omitted,
    defaults to the zero value (feature disabled). Branch must be "leave_message" or "hangup"
    when non-empty; any other value is rejected with a 400.
    """


class ListConfigurationsResponse(_Base):
    """Response body from ``GET /v1/tenants/{tenant_id}/configurations``."""

    configurations: list[Configuration] = Field(default_factory=list)

    has_more: bool = False
    """HasMore is true when additional configurations exist beyond this page."""
    next_cursor: str | None = None
    """NextCursor is the opaque cursor to pass as ?cursor= to fetch the next page. Empty when
    HasMore is false.
    """


# ─────────────────────────────────────────────────────────────────────────────
# Platform admin — GET /v1/platform/export/{tenants,agents}/{id},
# POST /v1/platform/import/tenants/{target_tenant_id}
#
# These models mirror the platform export/import bundle (the export/import
# envelope, "Bundle" — always camelCase on the wire, both as YAML and JSON,
# since Marshal/Unmarshal share the same struct tags) and
# the import response and its per-entity results (the import
# result manifest — already snake_case on the wire, so no aliases are
# required there).
# ─────────────────────────────────────────────────────────────────────────────

class PlatformMetadata(_Base):
    """``Bundle.metadata``: human-readable, non-identifying export context."""

    name: str
    description: str = ""


class PlatformUpstreamLLMSpec(_Base):
    """``ConfigurationSpec.upstreamLLM``: redacted custom LLM routing target."""

    url: str = ""
    needs_secret: bool = Field(default=False, alias="needsSecret")


class PlatformConfigurationSpec(_Base):
    """Bundle-safe, copyable projection of a tenant Configuration."""

    ref: str
    name: str
    countries: list[str] = Field(default_factory=list)
    validator_modes: dict[str, Any] | None = Field(default=None, alias="validatorModes")
    blocklist_patterns: list[Any] | None = Field(default=None, alias="blocklistPatterns")
    pricing_bands: dict[str, Any] | None = Field(default=None, alias="pricingBands")
    disclosure_texts: dict[str, Any] | None = Field(default=None, alias="disclosureTexts")
    fallback_response: dict[str, Any] | None = Field(default=None, alias="fallbackResponse")
    multi_candidate: dict[str, Any] | None = Field(default=None, alias="multiCandidate")
    output_constraint: dict[str, Any] | None = Field(default=None, alias="outputConstraint")
    asr_config: dict[str, Any] | None = Field(default=None, alias="asrConfig")
    auto_handover_config: dict[str, Any] | None = Field(default=None, alias="autoHandoverConfig")
    upstream_llm: PlatformUpstreamLLMSpec | None = Field(default=None, alias="upstreamLLM")
    prompt_confidentiality_config: PromptConfidentialityConfig | None = Field(
        default=None, alias="promptConfidentialityConfig"
    )


class PlatformToolHeaderSpec(_Base):
    """Bundle-safe projection of a tool's static HTTP header."""

    key: str
    value: str = ""
    needs_secret: bool = Field(default=False, alias="needsSecret")


class PlatformToolQueryParamSpec(_Base):
    """Bundle-safe projection of a tool's query parameter."""

    key: str
    mode: str
    """Either ``"const"`` or ``"description"``."""

    value: str = ""


class PlatformToolResponseVarSpec(_Base):
    """Bundle-safe projection of a tool's dynamic response-variable extractor."""

    name: str
    json_path: str = Field(alias="jsonPath")


class PlatformSpeakDuringSpec(_Base):
    """Bundle-safe projection of a tool's in-flight hold-audio setting."""

    enabled: bool = False
    text: str = ""


class PlatformToolExecutionSpec(_Base):
    """Bundle-safe projection of a tool's runtime dispatch settings."""

    speak_during: PlatformSpeakDuringSpec = Field(
        default_factory=PlatformSpeakDuringSpec, alias="speakDuring"
    )
    timeout_ms: int = Field(default=0, alias="timeoutMs")
    model_override: str = Field(default="", alias="modelOverride")


class PlatformToolSpec(_Base):
    """Bundle-safe, copyable projection of a tenant Tool."""

    ref: str
    name: str
    description: str = ""
    method: str
    url: str
    headers: list[PlatformToolHeaderSpec] = Field(default_factory=list)
    query_params: list[PlatformToolQueryParamSpec] = Field(
        default_factory=list, alias="queryParams"
    )
    parameters: dict[str, Any] | None = None
    args_only: bool = Field(default=False, alias="argsOnly")
    response_vars: list[PlatformToolResponseVarSpec] = Field(
        default_factory=list, alias="responseVars"
    )
    execution: PlatformToolExecutionSpec = Field(default_factory=PlatformToolExecutionSpec)
    provider: str = ""
    provider_tool: str = Field(default="", alias="providerTool")
    connection_ref: str = Field(default="", alias="connectionRef")
    provider_config: dict[str, Any] | None = Field(default=None, alias="providerConfig")


class PlatformAgentSpec(_Base):
    """Bundle-safe, copyable projection of a tenant Agent."""

    ref: str
    name: str
    prompt: str = ""
    voice_id: str = Field(default="", alias="voiceId")
    llm_model: str = Field(default="", alias="llmModel")
    llm_provider: str = Field(default="", alias="llmProvider")
    stt_provider: str = Field(default="", alias="sttProvider")
    tts_provider: str = Field(default="", alias="ttsProvider")
    tts_model: str = Field(default="", alias="ttsModel")
    language: str = ""
    temperature: float = 0.0
    jurisdiction: str = ""
    config_ref: str = Field(default="", alias="configRef")
    tool_refs: list[str] = Field(default_factory=list, alias="toolRefs")


class PlatformBundleSpec(_Base):
    """``Bundle.spec``: the exported entities, grouped by kind."""

    configurations: list[PlatformConfigurationSpec] = Field(default_factory=list)
    tools: list[PlatformToolSpec] = Field(default_factory=list)
    agents: list[PlatformAgentSpec] = Field(default_factory=list)


class PlatformBundle(_Base):
    """
    The top-level export/import envelope (``apiVersion``/``kind``/``metadata``/``spec``).

    Returned by :meth:`~audact.client.AudactClient.export_tenant` and
    :meth:`~audact.client.AudactClient.export_agent`; accepted by
    :meth:`~audact.client.AudactClient.import_tenant`.
    """

    api_version: Literal["audact.ai/v1"] = Field(alias="apiVersion")
    """Must equal ``"audact.ai/v1"``."""

    kind: BundleKind
    """One of ``"TenantBundle"`` or ``"AgentBundle"``."""

    metadata: PlatformMetadata
    spec: PlatformBundleSpec = Field(default_factory=PlatformBundleSpec)


class PlatformImportEntityResult(_Base):
    """One row of :class:`PlatformImportResult`'s ``entities`` list."""

    ref: str
    kind: str
    """One of ``"configuration"``, ``"tool"``, ``"agent"``."""

    name: str
    status: str
    """``"created"`` in every response the server currently produces."""

    new_id: str = ""
    """Fresh target-tenant UUID (string). Empty when ``dry_run`` was ``True``."""

    needs_secret: bool = False


class PlatformImportResult(_Base):
    """Response body from ``POST /v1/platform/import/tenants/{target_tenant_id}``."""

    dry_run: bool = False
    mode: str = "create-only"
    bundle_sha256: str = ""
    counts: dict[str, int] = Field(default_factory=dict)
    entities: list[PlatformImportEntityResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Voice Gateway — KYC documents & number provisioning
#
# These models mirror the Voice Gateway's KYC and number-provisioning JSON wire
# types. Document
# bytes are NEVER part of any response — only metadata (Q8, "no-download").
# ─────────────────────────────────────────────────────────────────────────────

class KYCDocument(_Base):
    """
    Metadata for a single KYC document (``KYCDocumentResponse``).

    Returned by :meth:`~audact.client.AudactClient.upload_kyc_document`,
    :meth:`~audact.client.AudactClient.replace_kyc_document`,
    :meth:`~audact.client.AudactClient.get_kyc_document`, and as elements of
    :meth:`~audact.client.AudactClient.list_kyc_documents`. The plaintext file
    bytes are never returned by any endpoint.
    """

    id: UUID
    doc_type: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    """Hex-encoded SHA-256 digest of the plaintext file."""

    telnyx_document_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ListKYCDocumentsResponse(_Base):
    """Response body from ``GET /v1/kyc/documents``."""

    documents: list[KYCDocument] = Field(default_factory=list)


class KYCRequirement(_Base):
    """A single Telnyx regulatory requirement (``RegulatoryRequirement``)."""

    id: str
    requirement_type: str
    name: str
    required: bool


class ListKYCRequirementsResponse(_Base):
    """
    Response body from ``GET /v1/kyc/requirements``.

    ``requirements`` is explicitly empty (never omitted) when Telnyx
    legitimately requires nothing for the requested (country, number_type) —
    never inferred as an error.
    """

    requirements: list[KYCRequirement] = Field(default_factory=list)


class KYCDocumentSetItemRequest(_Base):
    """
    One requirement answer supplied when creating a KYC document set.

    Exactly one of ``document_id``/``text_value`` must be set — document-type
    requirements need ``document_id`` (from :meth:`upload_kyc_document`);
    free-text requirements (e.g. a tax ID) need ``text_value``.
    """

    requirement_id: str
    requirement_type: str = ""
    document_id: UUID | None = None
    text_value: str | None = None


class CreateKYCDocumentSetRequest(_Base):
    """Request body for ``POST /v1/kyc/document-sets``."""

    name: str
    country_code: str
    """ISO 3166-1 alpha-2 country code this set covers."""

    number_type: str
    """Telnyx's exact ``phone_number_type`` string, e.g. ``"mobile"``."""

    items: list[KYCDocumentSetItemRequest] = Field(default_factory=list)
    """Answers every Telnyx regulatory requirement for (country_code, number_type)."""


class KYCDocumentSetItem(_Base):
    """
    A single requirement slot within a KYC document set's detail view.

    ``document_filename``/``doc_type`` mirror the mapped document's metadata
    (never the bytes), so a mis-slotted upload can be spotted without a
    download.
    """

    requirement_id: str
    requirement_type: str
    document_id: UUID | None = None
    document_filename: str | None = None
    doc_type: str | None = None
    text_value: str | None = None


class KYCDocumentSet(_Base):
    """
    A ``kyc_document_sets`` row (``KYCDocumentSetResponse``).

    ``items`` is populated by :meth:`~audact.client.AudactClient.create_kyc_document_set`
    and :meth:`~audact.client.AudactClient.get_kyc_document_set`, but omitted by
    :meth:`~audact.client.AudactClient.list_kyc_document_sets` to keep the
    listing response small.
    """

    id: UUID
    name: str
    country_code: str
    number_type: str
    action: str
    telnyx_requirement_group_id: str | None = None
    status: KYCDocumentSetStatus
    """One of: draft, submitted, approved, rejected, expired."""

    status_detail: str | None = None
    items: list[KYCDocumentSetItem] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ListKYCDocumentSetsResponse(_Base):
    """Response body from ``GET /v1/kyc/document-sets``."""

    document_sets: list[KYCDocumentSet] = Field(default_factory=list)


class RotateDEKResponse(_Base):
    """Response body from ``POST /v1/kyc/dek/rotate``."""

    new_version: int
    """
    The tenant's new current Document Encryption Key version. Existing
    documents remain readable — decryption always uses the key_ref recorded
    on the document, never the tenant's current version.
    """


class AvailableNumber(_Base):
    """A single Telnyx available number, as returned by ``GET /v1/numbers/available``."""

    phone_number: str
    phone_number_type: str
    country_code: str


class ListAvailableNumbersResponse(_Base):
    """
    Response body from ``GET /v1/numbers/available``.

    ``numbers`` is explicitly empty (never an error) when Telnyx legitimately
    has no matching inventory.
    """

    numbers: list[AvailableNumber] = Field(default_factory=list)


class CreateNumberOrderRequest(_Base):
    """Request body for ``POST /v1/numbers/orders``."""

    country_code: str
    number_type: str
    set_id: UUID
    """The already-``approved`` KYC document set this order is placed against."""

    phone_number: str | None = None
    """Exact E.164 number to order. When omitted, Telnyx's first available match is used."""

    area_code: str | None = None
    """Narrows the available-number search when ``phone_number`` is omitted."""


class NumberOrder(_Base):
    """A ``number_orders`` row (``NumberOrderResponse``)."""

    id: UUID
    country_code: str
    number_type: str
    set_id: UUID
    phone_number: str | None = None
    telnyx_order_id: str | None = None
    status: NumberOrderStatus
    """One of: pending, requirement_review, ordering, success, failure, cancelled."""

    failure_reason: str | None = None
    phone_number_id: str | None = None
    """References the DID pool row created once the order succeeds. ``None`` until then."""

    created_at: datetime
    updated_at: datetime


class ListNumberOrdersResponse(_Base):
    """Response body from ``GET /v1/numbers/orders``."""

    orders: list[NumberOrder] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Voice Gateway — Bring-Your-Own (BYO) telephony
#
# These models mirror the Voice Gateway's BYO connection and phone-number JSON
# wire types (phone numbers are extended with the
# origin/byo_connection_id/provider/connection_health fields: a number is
# either Audact-provisioned or brought by the customer).
# SIP credentials (sip_username/sip_password) are write-only: stored in AWS
# Secrets Manager and NEVER echoed back on any response — has_credentials is
# a boolean flag only.
# ─────────────────────────────────────────────────────────────────────────────

NumberOrigin = Literal["audact", "byo"]
"""Discriminates who provisioned a DID: Audact's own Telnyx pool
(``"audact"``, the historical default) or a customer-owned SIP trunk
(``"byo"``)."""

SipProvider = Literal["twilio", "telnyx", "generic_sip"]
"""Telephony provider label for a BYO connection. Only selects
connect-instructions/default-allowlist copy — every provider takes the
identical SIP-only code path."""

SipTransport = Literal["udp", "tcp", "tls", "auto"]
"""SIP transport protocol for a BYO connection's outbound trunk."""

ConnectionHealth = Literal["unverified", "healthy", "unreachable", "auth_failed"]
"""Current health state of a BYO connection."""


class CreateBYOConnectionRequest(_Base):
    """
    Request body for ``POST /v1/byo/connections``, and the inline
    ``connection`` object accepted by :class:`CreateNumberRequest` for the
    one-step bring-your-own number add.

    Requires EITHER SIP credentials (``sip_username`` + ``sip_password``) OR
    an inbound IP allowlist (``inbound_allowed_ips``) — at least one is
    mandatory so inbound calls can be authenticated; a no-credential
    connection's allowlist may not be wider than a platform-configured floor
    (no accept-any trunks).
    """

    name: str | None = None
    """Display name for this connection. Required by the standalone create
    endpoint (server returns 400 when omitted); optional on the inline
    ``connection`` path, where the server synthesizes one when omitted."""

    provider: SipProvider
    sip_host: str
    """The customer's outbound SIP proxy host/domain."""

    sip_transport: SipTransport | None = None
    """Defaults to ``"auto"`` server-side when omitted."""

    sip_username: str | None = None
    sip_password: str | None = Field(default=None, repr=False)
    """Never echoed back by any response — stored only in Secrets Manager."""

    inbound_allowed_ips: list[str] | None = None
    """Inbound IP allowlist (CIDR or bare-IP strings)."""


class UpdateBYOConnectionRequest(_Base):
    """
    Request body for ``PUT /v1/byo/connections/{id}``.

    Every field is optional: an omitted field leaves the corresponding
    column unchanged. Supplying BOTH ``sip_username`` and ``sip_password``
    rotates the stored credential under the same Secrets Manager entry. To
    CLEAR ``inbound_allowed_ips`` explicitly, send an empty list (``[]``)
    rather than omitting the field.
    """

    name: str | None = None
    provider: SipProvider | None = None
    sip_host: str | None = None
    sip_transport: SipTransport | None = None
    sip_username: str | None = None
    sip_password: str | None = Field(default=None, repr=False)
    inbound_allowed_ips: list[str] | None = None


class BYOConnection(_Base):
    """
    A bring-your-own SIP trunk connection (``BYOConnectionResponse``).

    Credentials and Secrets Manager ARNs are NEVER included on the wire —
    only ``has_credentials`` reports whether a SIP username/password is
    currently stored.
    """

    id: UUID
    name: str
    provider: SipProvider
    sip_host: str
    sip_transport: SipTransport
    has_credentials: bool = False
    inbound_allowed_ips: list[str] = Field(default_factory=list)
    connection_health: ConnectionHealth
    health_detail: str = ""
    last_error_code: int | None = None
    last_error_at: datetime | None = None
    last_verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ListBYOConnectionsResponse(_Base):
    """Response body from ``GET /v1/byo/connections``."""

    connections: list[BYOConnection] = Field(default_factory=list)
    next_cursor: str | None = None


class ByoConfig(_Base):
    """
    Response body from ``GET /v1/byo/config`` — this deployment's SIP
    ingress configuration.

    Values are deployment-wide, not tenant-specific. Fetch this before
    creating any BYO connection to learn the host/signaling IPs to configure
    on your own SIP trunk's origination URI / allowed-callers list.
    """

    sip_ingress_host: str
    signaling_ips: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Numbers lifecycle completion: the pool management surface on top
# of the Telnyx order flow above — voice-gateway (8088).
# ─────────────────────────────────────────────────────────────────────────────

class PhoneNumber(_Base):
    """
    A DID phone-number pool row (``voice.PhoneNumberResponse``).

    ``origin`` discriminates Audact-provisioned numbers from bring-your-own
    numbers routed over a customer-owned SIP trunk. ``provider`` and
    ``connection_health`` are populated only for ``origin == "byo"``,
    surfacing the owning :class:`BYOConnection`'s provider label and current
    health for convenience.
    """

    id: UUID
    did: str
    """The DID in E.164 format, e.g. ``"+31201234567"``."""

    country_code: str
    """ISO 3166-1 alpha-2 country code, e.g. ``"NL"``."""

    trunk_provider: TrunkProvider | None = None
    """Telephony carrier for Audact-provisioned numbers: ``telnyx``
    (``twilio`` only on numbers registered before Audact numbers became
    Telnyx-only). Unset for ``origin == "byo"`` numbers — see ``provider``."""

    trunk_id: str | None = None
    """Provider-assigned trunk identifier, if any."""

    assigned_agent_id: UUID | None = None
    """UUID of the agent currently assigned to this DID. Only present when
    ``status`` is ``"assigned"``."""

    status: PhoneNumberStatus
    """One of: ``available``, ``assigned``, ``suspended``."""

    origin: NumberOrigin = "audact"
    """Discriminates Audact-provisioned numbers from bring-your-own numbers."""

    byo_connection_id: UUID | None = None
    """The owning :class:`BYOConnection`'s id. ``None`` for
    ``origin == "audact"`` numbers."""

    provider: SipProvider | None = None
    """The owning BYO connection's provider label. ``None`` for
    ``origin == "audact"`` numbers."""

    connection_health: ConnectionHealth | None = None
    """The owning BYO connection's current health. ``None`` for
    ``origin == "audact"`` numbers."""

    created_at: datetime
    updated_at: datetime

    _blank_enums = _blank_to_none("trunk_provider")


class ListNumbersResponse(_Base):
    """
    Raw response body from ``GET /v1/numbers`` (``voice.ListNumbersResponse``).

    :meth:`~audact.client.AudactClient.list_numbers` reshapes this into the
    shared :class:`Page` convention, while ALSO exposing ``numbers``/
    ``total_count`` directly on the returned :class:`Page` (via
    ``extra="allow"``) for callers that prefer the raw wire field names. This
    surface has no explicit ``has_more`` field on the wire — the presence of
    ``next_cursor`` is the signal that a further page exists.
    """

    numbers: list[PhoneNumber] = Field(default_factory=list)
    next_cursor: str | None = None
    total_count: int = 0


class CreateNumberRequest(_Base):
    """
    Request body for ``POST /v1/numbers`` — origin-aware DID creation.

    ``origin`` defaults to ``"audact"`` server-side when omitted (back-compat
    with the historical Telnyx-only flow). For ``origin == "byo"``, supply
    EITHER ``byo_connection_id`` (attach to an already-registered
    :class:`BYOConnection`) OR ``connection`` (inline connection details —
    create-or-reuse, dedup'd on (provider, sip_host, sip_username)) — never
    both.
    """

    did: str
    """E.164 phone number to add, e.g. ``"+442045136446"``. Must start with
    ``"+"`` and contain only digits after."""

    country_code: str
    """ISO 3166-1 alpha-2 code, e.g. ``"GB"``."""

    trunk_provider: Literal["telnyx"] | None = None
    """Telephony carrier for ``origin == "audact"``. Only ``telnyx`` is
    accepted (any other value is rejected with 400). A number you already own
    at Twilio is added with ``origin="byo"`` and ``connection`` whose
    ``provider`` is ``"twilio"``. Defaults to ``"telnyx"`` server-side if
    omitted."""

    origin: NumberOrigin | None = None
    """Defaults to ``"audact"`` server-side when omitted."""

    byo_connection_id: UUID | None = None
    """Attach to an already-registered :class:`BYOConnection`. Mutually
    exclusive with ``connection``."""

    connection: CreateBYOConnectionRequest | None = None
    """Inline connection details for a one-step bring-your-own number add.
    Mutually exclusive with ``byo_connection_id``."""


class AssignNumberRequest(_Base):
    """Request body for ``POST /v1/numbers/{id}/assign``."""

    agent_id: UUID
    """UUID of the agent to assign this DID to (same tenant)."""


class SetNumberTrunkRequest(_Base):
    """Request body for ``PUT /v1/numbers/{id}/trunk``."""

    trunk_id: str
    """The LiveKit outbound SIP trunk resource id (e.g. ``"ST_..."``) this
    number dials out on — obtain it from the ``sip_trunk_id`` field of an
    outbound trunk returned by :meth:`~audact.client.AudactClient.list_trunks`.
    An empty string clears the link."""


# ─────────────────────────────────────────────────────────────────────────────
# Completions: tenant usage, validator finalize-score,
# policy calling-hours, and the platform health check.
# ─────────────────────────────────────────────────────────────────────────────

class UsageRecord(_Base):
    """
    Response body from ``GET /v1/tenants/{tenant_id}/usage`` (mirrors
    ``tenant.UsageRecord``).

    An all-zero record (``tenant_id``/``period_*`` populated, counters at 0)
    is returned when no usage row exists yet for the requested period.
    """

    usage_id: UUID
    tenant_id: UUID
    period_start: datetime
    period_end: datetime
    calls_total: int = 0
    calls_inbound: int = 0
    calls_outbound: int = 0
    validator_checks: int = 0
    evidence_events_count: int = 0
    fail_open_count: int = 0
    llm_tokens_in: int = 0
    llm_tokens_out: int = 0
    created_at: datetime
    updated_at: datetime
    source: UsageRecordSource | None = None
    """Where the counts come from: ``"stored"`` for a persisted usage
    record, ``"live"`` when they were counted on request from the tenant's
    calls and evidence events for the period. A live record has a zero
    ``usage_id`` and ``created_at``/``updated_at`` set to the time it was
    computed."""


class FinalizeScoreRequest(_Base):
    """Request body for ``POST /v1/calls/{call_id}/finalize-score``."""

    agent_id: str = ""


class FinalizeScoreResponse(_Base):
    """
    Response body from ``POST /v1/calls/{call_id}/finalize-score``.

    ``composite_score``/``total_turns``/``turns_with_violations``/
    ``fail_open_count`` are only meaningful when ``status == "finalized"``;
    a ``"skipped"`` call (no turns recorded) leaves them at their zero value.
    """

    status: str
    """``"finalized"`` or ``"skipped"``."""

    composite_score: float | None = None
    total_turns: int = 0
    turns_with_violations: int = 0
    fail_open_count: int = 0


class CallingHoursCheckResponse(_Base):
    """Response body from ``GET /v1/calling-hours/check``."""

    allowed: bool
    """``True`` when an outbound call is permitted right now for the
    requested jurisdiction (not quiet hours, not a holiday)."""

    policy_version: str = ""
    """Formatted as ``"{COUNTRY}_v{semver}"``, e.g. ``"NL_v1.1.0"``."""

    reason: CallingHoursReason | None = None
    """``"quiet_hours"`` or ``"holiday"``; empty when ``allowed`` is ``True``."""

    next_permitted_at: datetime | None = None
    """Earliest UTC time an outbound call would be permitted; omitted when
    ``allowed`` is ``True``."""

    _blank_enums = _blank_to_none("reason")


class HealthComponentStatus(_Base):
    """Per-component status entry within :class:`HealthResponse`."""

    status: str = ""
    latency: str = ""
    error: str = ""


class HealthResponse(_Base):
    """Response body from ``GET /v1/health`` (mirrors ``health.Response``)."""

    status: str
    """Overall status, e.g. ``"ok"`` or ``"degraded"``."""

    timestamp: str = ""
    components: dict[str, HealthComponentStatus] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Pagination — cursor-based, manual (no auto async-iterator)
# ─────────────────────────────────────────────────────────────────────────────

_ItemT = TypeVar("_ItemT")


class Page(BaseModel, Generic[_ItemT]):
    """
    Generic cursor-paginated list response: ``{items, has_more, next_cursor}``.

    Mirrors the TS SDK's shipped pagination convention: list
    methods take an optional ``cursor`` parameter and return a ``Page``; the
    caller passes the returned ``next_cursor`` back as ``cursor`` to fetch
    the next page, and stops once ``has_more`` is ``False``. This is a
    **manual-cursor** convention — the SDK deliberately does NOT provide an
    automatic ``async for`` page-iterator, to keep the Python and TypeScript
    SDKs symmetric.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    items: list[_ItemT] = Field(default_factory=list)
    """The page's items, in server-defined order."""

    has_more: bool = False
    """``True`` when a subsequent page exists (fetch it with ``next_cursor``)."""

    next_cursor: str | None = None
    """Cursor for the next page (pass as ``cursor``); ``None`` when ``has_more`` is ``False``."""


# ─────────────────────────────────────────────────────────────────────────────
# Rate limits — X-RateLimit-* response headers
# ─────────────────────────────────────────────────────────────────────────────

class RateLimitInfo(_Base):
    """
    Snapshot of the ``X-RateLimit-Limit`` / ``X-RateLimit-Remaining`` /
    ``X-RateLimit-Reset`` response headers.

    Exposed both on :class:`~audact.exceptions.AudactRateLimitError`
    (``.rate_limit``) for a ``429`` and on
    :attr:`~audact.client.AudactClient.last_rate_limit` after *any* request
    (successful or not) that carried these headers — the ticket asks for
    both, going beyond the TS SDK, which surfaces only ``Retry-After``.
    """

    limit: int | None = None
    """Requests allowed per window (``X-RateLimit-Limit``)."""

    remaining: int | None = None
    """Requests remaining in the current window (``X-RateLimit-Remaining``)."""

    reset: int | None = None
    """Unix timestamp (seconds) when the window resets (``X-RateLimit-Reset``)."""


# ─────────────────────────────────────────────────────────────────────────────
# client.calls — SIP calls, handovers, transfers.
# voice-gateway (8088). Trunks/routes/ws-ticket/admission-url follow in
# the next section.
# ─────────────────────────────────────────────────────────────────────────────

class OutboundCallRequest(_Base):
    """Request body for ``POST /v1/sip/calls/outbound`` (``voice.OutboundCallRequest``)."""

    from_number: str
    """Caller ID to present on the outbound call, in strict E.164: a leading
    ``+``, the country code, then the subscriber number — digits only, 8 to 16
    characters in total, no spaces, dashes, dots or parentheses. Numbers are
    not normalised; ``"+31 20 123 4567"`` is rejected with 400
    ``INVALID_REQUEST``. Must also be one of your own numbers
    (``GET /v1/numbers``), otherwise 400 ``INVALID_REQUEST``."""

    destination_number: str
    """Phone number to call, in strict E.164: a leading ``+``, the country
    code, then the subscriber number — digits only, 8 to 16 characters in
    total, no spaces, dashes, dots or parentheses. Numbers are not
    normalised; ``"+44 20 7946 0958"`` is rejected with 400
    ``INVALID_REQUEST``. Example: ``"+442079460958"``."""

    agent_id: UUID | None = None
    """UUID of the voice agent to handle this call. When set, the
    agent-worker spawns an STT→LLM→TTS pipeline in the LiveKit room."""

    dynamic_variables: dict[str, str] | None = None
    """Per-call key/value pairs substituted into the agent prompt (``{{var}}``)
    and exposed to tools."""

    metadata: dict[str, Any] | None = None
    """Arbitrary per-call JSON persisted to ``calls.metadata`` and echoed on
    lifecycle webhook events. Never logged."""

    max_duration_seconds: int | None = None
    """Hard cap on this call's duration, in seconds, enforced server-side.
    Omit or ``0`` to fall back to the agent's configured default."""

    requested_outcome: RequestedOutcome | None = None
    """When set, synthesizes the outcome of this call instead of placing a
    real one — only accepted when sandbox mode is enabled. One of
    ``answered``, ``no_answer``, ``busy``, ``rejected``,
    ``invalid_destination``, ``voicemail``."""

    identifiers: list[CallIdentifier] | None = None
    """Tenant-supplied subject identifier hashes. Build with
    ``audact.pii.client_hash``; plaintext is never sent."""


class OutboundCallResponse(_Base):
    """Response body from ``POST /v1/sip/calls/outbound``."""

    call_id: UUID
    """Server-generated UUID for this call session."""

    room_name: str = ""
    """LiveKit room name created for this call."""

    participant_id: str = ""
    """LiveKit participant identity for the agent in this room."""

    sip_call_id: str = ""
    """SIP ``Call-ID`` header value assigned by the carrier."""


class InboundCallRequest(_Base):
    """Request body for ``POST /v1/sip/calls/inbound`` (``voice.InboundCallRequest``)."""

    caller_number: str
    """Originating phone number, in E.164 format."""

    called_did: str
    """Destination DID (E.164) that received the call."""

    dynamic_variables: dict[str, str] | None = None
    """Per-call key/value pairs substituted into the agent prompt (``{{var}}``)
    and exposed to tools."""

    metadata: dict[str, Any] | None = None
    """Arbitrary per-call JSON persisted to ``calls.metadata`` and echoed on
    lifecycle webhook events. Never logged."""

    identifiers: list[CallIdentifier] | None = None
    """Tenant-supplied subject identifier hashes. Build with
    ``audact.pii.client_hash``; plaintext is never sent."""


class InboundCallResponse(_Base):
    """Response body from ``POST /v1/sip/calls/inbound``."""

    call_id: UUID
    """Server-generated UUID for this call session."""

    room_name: str = ""
    """LiveKit room name created for this call."""

    trunk_id: str = ""
    """Identifier of the SIP trunk that received this call."""


class BrowserCallRequest(_Base):
    """Request body for ``POST /v1/sip/calls/browser`` (``voice.BrowserCallRequest``)."""

    agent_id: UUID
    """UUID of the agent to connect the browser test call to."""

    dynamic_variables: dict[str, str] | None = None
    """Per-call key/value pairs substituted into the agent prompt (``{{var}}``)
    and exposed to tools."""

    metadata: dict[str, Any] | None = None
    """Arbitrary per-call JSON persisted to ``calls.metadata`` and echoed on
    lifecycle webhook events. Never logged."""

    identifiers: list[CallIdentifier] | None = None
    """Tenant-supplied subject identifier hashes. Build with
    ``audact.pii.client_hash``; plaintext is never sent."""


class BrowserCallResponse(_Base):
    """
    Response body from ``POST /v1/sip/calls/browser``.

    ``livekit_token`` is a short-lived secret — never log it.
    """

    call_id: UUID
    """Server-generated UUID for this call session. Use it with
    ``GET /v1/sip/calls/{call_id}/status`` to poll the call's lifecycle state."""

    room_name: str = ""
    """LiveKit room name created for this call."""

    livekit_url: str = ""
    """Public WebSocket URL the browser client connects to (using
    ``livekit_token``) to join the room."""

    livekit_token: str = ""
    """Signed JWT the browser client presents to join the LiveKit room over
    WebRTC. Treat as a short-lived secret; do not log it."""


class HangupResponse(_Base):
    """Response body from ``POST /v1/sip/calls/{call_id}/hangup``."""

    call_id: UUID
    """UUID of the call that was terminated."""

    room_name: str = ""
    """LiveKit room that was deleted."""

    status: str = ""
    """Always ``"terminated"`` on success."""


class CallStatusResponse(_Base):
    """Response body from ``GET /v1/sip/calls/{call_id}/status``."""

    call_id: UUID
    """UUID of the call."""

    room_name: str = ""
    """LiveKit room backing this call."""

    status: CallControlStatus | None = None
    """Current call lifecycle state: ``"active"`` or ``"terminated"``."""

    started_at: datetime | None = None
    """Server-generated UTC timestamp when the call began. ``None`` if the
    call state does not carry a parsable ``started_at`` value."""

    _blank_enums = _blank_to_none("status")


class HandoverRequest(_Base):
    """Request body for ``POST /v1/sip/calls/{call_id}/handover``."""

    destination: str
    """E.164 phone number of the human supervisor to dial. Hashed
    immediately server-side — the raw number is never stored or logged."""

    handover_reason: HandoverReason
    """Why the handover was triggered. One of ``agent_requested``,
    ``escalation``, ``operator_requested``, ``caller_requested``."""

    caller_reason: str | None = None
    """Optional short code/enum describing why the caller asked for (or
    triggered) the handover."""

    whisper_mode: WhisperMode | None = None
    """How the human is briefed before the caller is bridged in:
    ``"spoken"``, ``"portal"``, or ``"both"``. Defaults to ``"spoken"`` when
    omitted."""


class HandoverResponse(_Base):
    """Response body from ``POST /v1/sip/calls/{call_id}/handover``."""

    call_id: UUID
    """UUID of the call being handed over."""

    handover_id: UUID
    """Server-generated UUID for this handover session. Use it to poll
    ``GET /v1/sip/handovers/{handover_id}``."""

    state: str = ""
    """Always ``"initiated"`` on success."""


class HandoverStateResponse(_Base):
    """
    Response body from ``GET /v1/sip/handovers/{handover_id}``.

    The destination phone number is never returned; only its SHA-256 hash
    (``destination_hash``).
    """

    handover_id: UUID
    """UUID of the handover session."""

    call_id: UUID
    """UUID of the caller's active call being handed over."""

    state: str = ""
    """Current handover lifecycle state: one of ``initiated``,
    ``summarizing``, ``dialing``, ``whispering``, ``bridged``, ``ended``,
    ``cancelled``, ``failed``."""

    handover_reason: str = ""
    """One of ``agent_requested``, ``escalation``, ``operator_requested``,
    ``caller_requested``."""

    whisper_mode: str = ""
    """One of ``spoken``, ``portal``, ``both``."""

    destination_hash: str = ""
    """SHA-256 hex digest of the human's E.164 number."""

    summary_source: str = ""
    """How the summary presented to the human was produced: ``"llm"``
    (normal path) or ``"template"`` (deadline fallback). Empty until the
    summarizing stage completes."""

    delivery_status: str = ""
    """Whisper/summary delivery outcome, e.g. ``"delivered"``, ``"pending"``,
    ``"failed"``. Empty until set by agent-worker."""

    initiated_at: datetime | None = None
    """Server-generated UTC timestamp when the handover was first requested."""

    completed_at: datetime | None = None
    """Server-generated UTC timestamp when the handover reached a terminal
    state (``ended`` or ``cancelled``). ``None`` while in flight."""


class TransferRequest(_Base):
    """Request body for ``POST /v1/sip/calls/{call_id}/transfer``."""

    destination: str
    """E.164 phone number to transfer the call to. Hashed immediately
    server-side — the raw number is never stored or logged."""

    transfer_option: TransferOption | None = None
    """Transfer type: ``"blind"`` (SIP REFER immediately, caller disconnected
    once picked up) or ``"warm"`` (caller held while the agent briefs the
    target). Defaults to ``"blind"`` when omitted."""


class TransferResponse(_Base):
    """Response body from ``POST /v1/sip/calls/{call_id}/transfer``."""

    call_id: UUID
    """UUID of the call being transferred."""

    transfer_id: UUID
    """Server-generated UUID for this transfer session. Use it to call the
    bridge/cancel/end endpoints."""

    status: str = ""
    """Always ``"started"`` on success."""

    transfer_option: str = ""
    """Resolved transfer type (``blind`` or ``warm``)."""


class TransferSessionResponse(_Base):
    """
    Response body from ``GET /v1/sip/transfers/{transfer_id}``.

    The destination phone number is never returned; only its SHA-256 hash
    (``destination_hash``).
    """

    transfer_id: UUID
    """UUID of the transfer session."""

    call_id: UUID
    """UUID of the call being transferred."""

    agent_id: UUID | None = None
    """UUID of the agent handling the call, if available."""

    status: TransferSessionStatus | None = None
    """Current transfer lifecycle state: ``"started"``, ``"bridged"``,
    ``"cancelled"``, or ``"ended"``."""

    transfer_option: TransferOption | None = None
    """Transfer type: ``"blind"`` or ``"warm"``."""

    destination_hash: str = ""
    """SHA-256 hex digest of the destination E.164 number."""

    initiated_at: datetime | None = None
    """Server-generated UTC timestamp when the transfer was first requested."""

    completed_at: datetime | None = None
    """Server-generated UTC timestamp when the transfer reached a terminal
    state (``bridged``, ``cancelled``, or ``ended``). ``None`` while the
    transfer is still ``"started"``."""

    _blank_enums = _blank_to_none("status", "transfer_option")


class TransferStateResponse(_Base):
    """
    Response body from ``POST /v1/sip/transfers/{transfer_id}/bridge``,
    ``/cancel``, and ``/end``.
    """

    transfer_id: UUID
    """UUID of the updated transfer session."""

    status: str = ""
    """New transfer status."""


# ─────────────────────────────────────────────────────────────────────────────
# Calls surface, part 2: SIP trunks, dispatch rules (routes), the
# pre-connect admission-url hook, and WebSocket tickets — voice-gateway (8088).
# ─────────────────────────────────────────────────────────────────────────────

class InboundTrunkSummary(_Base):
    """An inbound SIP trunk summary, as returned by ``GET /v1/sip/trunks``."""

    sip_trunk_id: str = ""
    """LiveKit-assigned SIP trunk ID, e.g. ``"ST_abc123"``."""

    provider: TrunkProvider | None = None
    """Telephony carrier. One of: ``telnyx``, ``twilio``."""

    did: str = ""
    """E.164 phone number associated with this trunk."""

    _blank_enums = _blank_to_none("provider")


class OutboundTrunkSummary(_Base):
    """An outbound SIP trunk summary, as returned by ``GET /v1/sip/trunks``."""

    sip_trunk_id: str = ""
    """LiveKit-assigned SIP trunk ID, e.g. ``"SOT_abc123"``."""

    provider: TrunkProvider | None = None
    """Telephony carrier. One of: ``telnyx``, ``twilio``."""

    address: str = ""
    """SIP proxy hostname for outbound calls."""

    _blank_enums = _blank_to_none("provider")


class ListTrunksResponse(_Base):
    """
    Response body from ``GET /v1/sip/trunks`` (``voice.ListTrunksResponse``).

    ``inbound_trunks`` is cursor-paginated (pass ``next_cursor`` back as
    ``cursor``); ``outbound_trunks`` is always returned in full (at most one
    trunk per tenant) and is never paginated. Returned as-is rather than
    reshaped into the generic :class:`Page` convention because it mixes a
    paginated and a non-paginated list in one body.
    """

    inbound_trunks: list[InboundTrunkSummary] = Field(default_factory=list)
    outbound_trunks: list[OutboundTrunkSummary] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: str | None = None


class CreateInboundTrunkRequest(_Base):
    """Request body for ``POST /v1/sip/trunks/inbound``."""

    provider: TrunkProvider
    """Telephony carrier. One of: ``"telnyx"``, ``"twilio"``. Required."""

    inbound_numbers: list[str] = Field(default_factory=list)
    """DID phone numbers (E.164) that belong to this inbound trunk. Required."""

    allowed_addresses: list[str] | None = None
    """Source IPs/CIDRs permitted to deliver inbound INVITEs to this trunk.
    Supply it (with no ``auth_*`` fields) to register a NO-AUTH,
    IP-authenticated inbound trunk — the mode Telnyx FQDN connections use
    (e.g. the Telnyx signaling range ``192.76.120.0/22``). Required when no
    credentials are given; optional as an extra restriction alongside
    credentials."""

    auth_user_arn: str | None = None
    """AWS Secrets Manager ARN for the SIP username credential. Mutually
    exclusive with ``auth_username`` — if both are set, this field (the ARN)
    takes precedence."""

    auth_pass_arn: str | None = None
    """AWS Secrets Manager ARN for the SIP password credential. Mutually
    exclusive with ``auth_password`` — if both are set, this field (the ARN)
    takes precedence."""

    auth_username: str | None = None
    """Plain-text SIP username. If provided (instead of ``auth_user_arn``),
    the server creates/updates a Secrets Manager secret and stores the
    resulting ARN — the plain value is never echoed back or logged."""

    auth_password: str | None = Field(default=None, repr=False)
    """Plain-text SIP password. If provided (instead of ``auth_pass_arn``),
    the server creates/updates a Secrets Manager secret and stores the
    resulting ARN — the plain value is never echoed back or logged."""


class CreateInboundTrunkResponse(_Base):
    """
    Response body from ``POST /v1/sip/trunks/inbound`` (200 idempotent
    replay or 201 created).
    """

    sip_trunk_id: str = ""
    """LiveKit-assigned SIP trunk identifier, e.g. ``"ST_abc123"``."""

    provider: TrunkProvider | None = None
    """Telephony carrier."""

    inbound_numbers: list[str] = Field(default_factory=list)
    """DID phone numbers registered to this trunk."""

    status: str = ""
    """Always ``"registered"`` on success."""

    _blank_enums = _blank_to_none("provider")


class CreateOutboundTrunkRequest(_Base):
    """Request body for ``POST /v1/sip/trunks/outbound``."""

    provider: TrunkProvider
    """Telephony carrier. One of: ``"telnyx"``, ``"twilio"``. Required."""

    address: str
    """SIP proxy hostname used for outbound calls, e.g. ``"sip.telnyx.com"``.
    Required."""

    numbers: list[str] = Field(default_factory=list)
    """DID phone numbers (E.164) that may be used as caller ID on outbound
    calls through this trunk. Required by LiveKit."""

    auth_user_arn: str | None = None
    """AWS Secrets Manager ARN for the SIP username credential."""

    auth_pass_arn: str | None = None
    """AWS Secrets Manager ARN for the SIP password credential."""

    transport: SipTransport | None = None
    """SIP transport protocol: ``"auto"``, ``"udp"``, ``"tcp"``, or
    ``"tls"``. Defaults to ``"auto"``. Use ``"tcp"`` for providers like
    Telnyx that require TCP."""


class CreateOutboundTrunkResponse(_Base):
    """
    Response body from ``POST /v1/sip/trunks/outbound`` (200 idempotent
    replay or 201 created).
    """

    sip_trunk_id: str = ""
    """LiveKit-assigned SIP trunk identifier, e.g. ``"SOT_abc123"``."""

    provider: TrunkProvider | None = None
    """Telephony carrier."""

    address: str = ""
    """SIP proxy hostname for outbound calls."""

    status: str = ""
    """Always ``"registered"`` on success."""

    _blank_enums = _blank_to_none("provider")


class RouteSummary(_Base):
    """A SIP dispatch rule (route), as returned by ``GET /v1/sip/routes``."""

    dispatch_rule_id: str = ""
    """LiveKit-assigned dispatch rule ID, e.g. ``"SDR_abc123"``."""

    did: str = ""
    """E.164 phone number this rule accepts calls on."""

    agent_id: UUID | None = None
    """UUID of the agent routed by this rule."""

    room_prefix: str = ""
    """LiveKit room prefix used by the dispatch rule."""


class ListRoutesResponse(_Base):
    """Response body from ``GET /v1/sip/routes`` (``voice.ListRoutesResponse``)."""

    routes: list[RouteSummary] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: str | None = None


class CreateDispatchRuleRequest(_Base):
    """Request body for ``POST /v1/sip/routes``."""

    did: str
    """E.164 phone number to route, e.g. ``"+31201234567"``. Required."""

    agent_id: UUID
    """UUID of the agent to dispatch calls to this DID. Obtain agent UUIDs
    from ``POST /v1/agents`` or ``GET /v1/agents``. Required."""


class CreateDispatchRuleResponse(_Base):
    """
    Response body from ``POST /v1/sip/routes`` (200 idempotent replay or
    201 created).
    """

    dispatch_rule_id: str = ""
    """LiveKit-assigned dispatch rule ID for this route, e.g.
    ``"dr-abc123"``. Use it to reference or delete the route later."""

    status: str = ""
    """Always ``"routed"`` on success."""


class AdmissionURLResponse(_Base):
    """Response body from ``GET``/``PUT /v1/sip/admission-url``."""

    admission_url: str = ""
    """The tenant's configured pre-connect admission hook URL, or ``""``
    when the hook is disabled."""


class SetAdmissionURLRequest(_Base):
    """Request body for ``PUT /v1/sip/admission-url``."""

    admission_url: str
    """The http(s) endpoint to POST inbound-call admission requests to. An
    empty string clears it (disables the hook)."""


class WsTicketResponse(_Base):
    """Response body from ``POST /v1/ws/ticket``."""

    ticket: str = ""
    """Single-use UUID valid for 30 seconds. Pass it as the ``?ticket=``
    query parameter when connecting to ``GET /v1/ws/calls``. Consumed on
    first use — request a new one if the upgrade attempt fails or the
    30-second window elapses."""


# ─────────────────────────────────────────────────────────────────────────────
# Webhooks — tenant-management (8085), ``client.webhooks.*``
# ─────────────────────────────────────────────────────────────────────────────

class WebhookEndpoint(_Base):
    """
    A configured webhook endpoint (``webhook.Endpoint``), as returned by
    ``GET``/``PUT /v1/webhooks/{id}`` and as an item of
    ``GET /v1/webhooks``.
    """

    id: str = ""
    """Unique endpoint identifier (uuid). Use this to address the endpoint
    in ``get_webhook``/``update_webhook``/``delete_webhook``/``test_webhook``."""

    tenant_id: str = ""
    """The owning tenant."""

    url: str = ""
    """The customer HTTPS endpoint that receives POST requests."""

    scope: WebhookScope | None = None
    """One of ``"account"`` (tenant-wide fallback), ``"agent"`` (overrides
    account for a specific agent), or ``"compliance"`` (overrides all
    others for ``compliance.*`` events)."""

    events: list[str] = Field(default_factory=list)
    """Subscribed event type strings. An empty list means "all events" (no
    filtering). Discover valid values via ``list_webhook_event_types``."""

    is_active: bool = True
    """Whether deliveries are attempted for this endpoint. Inactive
    endpoints are retained but silently skipped by the router."""

    agent_id: str | None = None
    """Set for agent-scoped endpoints (``scope == "agent"``); ``None`` for
    account/compliance endpoints. Obtain agent UUIDs from
    ``client.agents.list_agents``."""


class CreateWebhookRequest(_Base):
    """
    Request body for ``POST /v1/webhooks``.

    ``url`` must use the ``https`` scheme. ``events`` must be non-empty and
    each value must be a known event type (discover them via
    ``list_webhook_event_types``). ``agent_id`` is required when
    ``scope == "agent"``.
    """

    scope: WebhookScope
    """One of ``"account"``, ``"agent"``, or ``"compliance"``. Required."""

    url: str
    """Customer HTTPS endpoint, e.g. ``"https://example.com/webhooks"``.
    Required."""

    events: list[WebhookEventType]
    """Non-empty subscription list of event type strings. Required."""

    agent_id: str | None = None
    """Required when ``scope == "agent"``; ignored otherwise."""


class CreateWebhookResponse(WebhookEndpoint):
    """
    Response body from ``POST /v1/webhooks`` (200 idempotent replay or 201
    created).
    """

    signing_secret: str | None = Field(default=None, repr=False)
    """The plaintext HMAC-SHA256 signing secret (64 lowercase hex
    characters), present **only** on the single request that first
    provisions the tenant's webhook signing secret. Store it securely — no
    later call, including subsequent creations or
    ``get_webhook_secret_status``, will ever return it again. Use
    :meth:`~audact.client.WebhooksClient.rotate_webhook_secret` to obtain a
    replacement if it is lost. Use
    :func:`~audact.client.verify_webhook_signature` to verify inbound
    deliveries with it."""


class UpdateWebhookRequest(_Base):
    """
    Request body for ``PUT /v1/webhooks/{id}``. Only provided fields are
    changed (partial update, despite the ``PUT`` verb).
    """

    url: str | None = None
    """New HTTPS endpoint URL. Must use the ``https`` scheme when provided."""

    events: list[WebhookEventType] | None = None
    """Replacement subscription list. Must be non-empty and each value a
    known event type when provided."""

    is_active: bool | None = None
    """Enable or disable the endpoint."""


class ListWebhooksResponse(_Base):
    """Response body from ``GET /v1/webhooks`` (``webhook.listWebhooksResponse``)."""

    items: list[WebhookEndpoint] = Field(default_factory=list)
    """The current page of webhook endpoints."""

    has_more: bool = False
    """``True`` when there are additional pages after this one."""

    next_cursor: str | None = None
    """Opaque cursor to pass as ``cursor`` for the next page. ``None``/empty
    when ``has_more`` is ``False``."""


class WebhookTestPingResponse(_Base):
    """
    Response body from ``POST /v1/webhooks/{id}/test``
    (``webhook.testPingResponse``).
    """

    success: bool = False
    """``True`` when the endpoint returned a 2xx HTTP status code."""

    status_code: int | None = None
    """HTTP status code returned by the customer endpoint. ``None`` when a
    network-level error occurred before receiving a response."""

    latency_ms: float | None = None
    """Measured round-trip time in milliseconds. ``None`` when a
    network-level error prevented any response."""

    error: str | None = None
    """Human-readable failure reason. Populated only when ``success`` is
    ``False``."""


class WebhookDeliveryRecord(_Base):
    """
    A single delivery attempt record (``webhook.DeliveryRecord``), as
    returned by ``GET /v1/webhooks/{id}/deliveries``.
    """

    id: str = ""
    """Unique delivery identifier (``dlv_<uuid>``)."""

    endpoint_id: str = ""
    """The :class:`WebhookEndpoint` that received (or should receive) the
    delivery."""

    event_id: str = ""
    """The originating webhook event's ID."""

    event_type: str = ""
    """Mirrors the originating event's type, for fast querying without joins."""

    status: WebhookDeliveryStatus | None = None
    """Current delivery lifecycle state, e.g. ``"pending"``, ``"success"``,
    ``"failed"``, or ``"dead_letter"``."""

    attempt_count: int = 0
    """Total delivery attempts made so far, including the initial attempt
    (maximum 4: 1 initial + 3 retries)."""

    http_status: int | None = None
    """HTTP response code returned by the customer endpoint; ``None`` when
    the request never reached the server (network error, timeout)."""

    latency_ms: float | None = None
    """Round-trip time in milliseconds of the last successful HTTP request;
    ``None`` on failure or when no request was made."""

    last_error: str | None = None
    """Human-readable error message from the most recent failed attempt;
    ``None`` when ``status`` is ``"success"``. Never contains PII."""

    created_at: str = ""
    """UTC timestamp when the delivery record was first created."""

    completed_at: str | None = None
    """UTC timestamp when the delivery reached a terminal state; ``None``
    if still in-flight."""

    _blank_enums = _blank_to_none("status")


class ListWebhookDeliveriesResponse(_Base):
    """
    Response body from ``GET /v1/webhooks/{id}/deliveries``
    (``webhook.deliveryLogResponse``).

    Offset-paginated (``limit``/``offset`` query parameters), **not**
    cursor-paginated — this endpoint's wire shape carries no
    ``has_more``/``next_cursor`` fields, unlike ``list_webhooks``. ``total``
    is the full record count, for computing page counts.
    """

    deliveries: list[WebhookDeliveryRecord] = Field(default_factory=list)
    """The paginated slice of delivery records for the endpoint."""

    total: int = 0
    """Total number of delivery records for the endpoint."""


class ResendWebhookDeliveryResponse(_Base):
    """Response body from ``POST /v1/webhooks/deliveries/{id}/resend``."""

    delivery_id: str = ""
    """The ID of the re-queued delivery record."""

    requeued: bool = False
    """Whether the delivery was successfully re-queued."""


class WebhookEventTypeInfo(_Base):
    """One entry of ``GET /v1/webhooks/event-types`` (``webhook.EventTypeInfo``)."""

    name: str = ""
    """Event type string used in webhook subscriptions, e.g. ``"call_ended"``."""

    description: str = ""
    """Human-readable explanation of when this event fires."""

    category: str = ""
    """Groups related events, e.g. ``"voice"``, ``"chat"``, ``"compliance"``."""

    schema_url: str = ""
    """Path to the event-schema discovery endpoint for this event type,
    e.g. ``"/v1/webhooks/event-schemas?type=call_ended"``."""


class ListWebhookEventTypesResponse(_Base):
    """Response body from ``GET /v1/webhooks/event-types``."""

    event_types: list[WebhookEventTypeInfo] = Field(default_factory=list)


class WebhookEventSchema(_Base):
    """
    Response body from ``GET /v1/webhooks/event-schemas?type={type}``
    (``webhook.EventSchemaInfo``).
    """

    event_type: str = ""
    """The event type string this schema documents, e.g. ``"call_ended"``."""

    category: str = ""
    """Groups related events, e.g. ``"voice"``, ``"chat"``, ``"compliance"``."""

    description: str = ""
    """Human-readable explanation of when this event fires."""

    schema_version: str = ""
    """Version tag of this hand-maintained example catalogue. Bumped on any
    backwards-incompatible change to a payload's field set."""

    example_payload: dict[str, Any] = Field(default_factory=dict)
    """Fully-populated, illustrative example of the JSON envelope (``id``,
    ``tenant_id``, ``agent_id``, ``event_type``, ``created_at``, ``data``)
    delivered for this event type. Values are synthetic — never live data.
    (The spec mis-types this field as an integer array — a known swag
    artifact of the server's ``json.RawMessage`` field — the wire payload is
    actually a JSON object; this model reflects the real shape.)"""

    pii_handling_note: str | None = None
    """How sensitive fields are treated for this event category. Always
    non-empty for ``compliance.*`` events."""


class WebhookSecretStatus(_Base):
    """
    Response body from ``GET /v1/webhooks/secrets/status``
    (``webhook.secretStatusResponse``).
    """

    in_rotation: bool = False
    """``True`` while the 72-hour dual-signature grace period is active."""

    created_at: str = ""
    """UTC timestamp when the signing secret row was first provisioned for
    this tenant."""

    grace_period_ends: str | None = None
    """UTC timestamp when the rotation grace window closes. ``None`` when
    ``in_rotation`` is ``False``."""


class RotateWebhookSecretResponse(_Base):
    """
    Response body from ``POST /v1/webhooks/secrets/rotate``
    (``webhook.rotateSecretResponse``).
    """

    rotated: bool = True
    """Always ``True`` on a 200 response."""

    signing_secret: str = Field(default="", repr=False)
    """The newly generated plaintext HMAC-SHA256 signing secret (64
    lowercase hex characters), returned exactly once — store it securely.
    No later call will ever return this value again. Use
    :func:`~audact.client.verify_webhook_signature` to verify inbound
    deliveries with it."""

    grace_period_ends: str = ""
    """UTC timestamp when the old signing key expires. During this window
    both the old and new keys are valid for signature verification."""


# ─────────────────────────────────────────────────────────────────────────────
# Agents — agent-worker (8089), ``client.agents.*``
# ─────────────────────────────────────────────────────────────────────────────

class Agent(_Base):
    """
    A voice agent, as returned by the agent-worker CRUD API
    (``GET/PUT/PATCH/DELETE /v1/agents/{agent_id}``, ``main.Agent``).

    The full current ``AgentConfig``: a static greeting
    (``begin_message``), who speaks first (``start_speaker``,
    ``greet_on_connect``), a call-duration cap (``max_duration_seconds``),
    and four policy blocks — ``post_call_summary``, ``post_call_extraction``,
    ``voicemail``, ``end_call`` — that are sealed onto the agent's per-agent
    Configuration server-side (``tenant.EndCallConfig`` et al.) and are left
    as loosely-typed dicts here since the SDK only needs to pass them
    through, not validate their internals.
    """

    agent_id: UUID
    """Server-generated UUID primary key. Use this — not ``name`` — to
    address the agent in ``GET/PUT/PATCH/DELETE /v1/agents/{agent_id}``."""

    tenant_id: UUID
    """UUID of the tenant that owns this agent."""

    name: str = ""
    """Human-readable agent name."""

    prompt: str = ""
    """System prompt / instructions given to the LLM."""

    language: str = ""
    """BCP-47 language code the agent operates in."""

    voice_id: str = ""
    """TTS voice identifier used for this agent's spoken responses."""

    llm_provider: str = ""
    """LLM provider, e.g. ``"openai"`` or ``"mistral"``."""

    llm_model: str = ""
    """LLM model identifier, e.g. ``"gpt-4.1-mini"``."""

    stt_provider: str = ""
    """Speech-to-text provider, e.g. ``"deepgram"``."""

    tts_provider: str = ""
    """Text-to-speech provider: ``"voxtral"`` | ``"elevenlabs"``."""

    tts_model: str = ""
    """TTS model (``""`` = provider default)."""

    status: str = ""
    """Agent lifecycle state: ``"draft"`` | ``"published"`` | ``"archived"``."""

    version: int = 0
    """Server-managed optimistic-concurrency counter, incremented on every
    update."""

    jurisdiction: str | None = None
    """Compliance jurisdiction code (ISO 3166-1 alpha-2), e.g. ``"NL"``."""

    assigned_phone: str | None = None
    """E.164 DID phone number currently routed to this agent, when assigned."""

    configuration_id: UUID | None = None
    """UUID of the dedicated per-agent Configuration row; ``None`` for
    legacy agents."""

    tool_ids: list[str] = Field(default_factory=list)
    """Tool UUIDs currently attached to this agent."""

    temperature: float | None = None
    """LLM sampling temperature, in ``[0.0, 2.0]``."""

    max_duration_seconds: int | None = None
    """Caps a call's total duration in seconds; ``0``/``None`` means no cap."""

    greet_on_connect: bool | None = None
    """Whether the agent speaks first at connect."""

    begin_message: str | None = None
    """Static agent greeting spoken verbatim via TTS at connect."""

    start_speaker: StartSpeaker | None = None
    """Who speaks first at call connect: ``"agent"`` | ``"caller"``."""

    end_call: dict[str, Any] | None = None
    """End-call & voicemail-detection policy."""

    voicemail: dict[str, Any] | None = None
    """Voicemail-detection policy."""

    post_call_summary: dict[str, Any] | None = None
    """Agency-configurable post-call summary policy."""

    post_call_extraction: dict[str, Any] | None = None
    """Custom post-call extraction schema."""

    auto_handover_config: dict[str, Any] | None = None
    """Auto-handover-on-escalation policy."""

    created_at: datetime | None = None
    """Server-generated creation timestamp (UTC)."""

    updated_at: datetime | None = None
    """Server-generated last-update timestamp (UTC)."""

    deleted_at: datetime | None = None
    """Set when the agent has been soft-deleted; ``None`` for active agents."""


class ListAgentsResponse(_Base):
    """
    Raw response body from ``GET /v1/agents`` (``main.listAgentsResponse``).

    ``client.agents.list_agents`` returns this reshaped into the shared
    :class:`Page` convention.
    """

    agents: list[Agent] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: str | None = None


class CreateAgentRequest(_Base):
    """Request body for ``POST /v1/agents`` (``main.CreateAgentRequest``)."""

    name: str
    """Human-readable agent name. Required, non-empty."""

    language: str
    """BCP-47 language code the agent operates in. Required."""

    prompt: str | None = None
    """System prompt / instructions given to the LLM. Optional (a sample
    prompt is applied when omitted)."""

    voice_id: AgentCreateVoiceId | str | None = None
    """TTS voice identifier. See ``list_voices`` for valid values."""

    llm_provider: LLMProvider | None = None
    """LLM provider: ``"mistral"`` | ``"openai"``."""

    llm_model: LLMModel | None = None
    """LLM model identifier, e.g. ``"gpt-4.1-mini"`` | ``"mistral-small-2603"``."""

    stt_provider: STTProvider | None = None
    """Speech-to-text provider: ``"deepgram"``."""

    tts_provider: TTSProvider | None = None
    """Text-to-speech provider: ``"voxtral"`` | ``"elevenlabs"``."""

    tts_model: TTSModel | None = None
    """TTS model for the provider; ``None`` (omitted) = provider default."""

    status: AgentCreateStatus | None = None
    """Initial lifecycle state. Optional; defaults to ``"published"``. Only
    ``"draft"``/``"published"`` are valid at create time."""

    jurisdiction: str | None = None
    """Compliance jurisdiction code. Optional; defaults to ``"DE"``."""

    temperature: float | None = None
    """LLM sampling temperature, in ``[0.0, 2.0]``. Omit for the 0.7 default;
    an explicit ``0.0`` is honored verbatim."""

    max_duration_seconds: int | None = None
    """Caps a call's total duration in seconds; ``0`` (default) means no cap."""

    greet_on_connect: bool | None = None
    """Whether the agent speaks first at connect. Defaults to ``True`` when
    omitted."""

    begin_message: str | None = None
    """Static agent greeting spoken verbatim via TTS at connect."""

    start_speaker: StartSpeaker | None = None
    """Who speaks first at call connect. Defaults to ``"agent"``."""

    end_call: dict[str, Any] | None = None
    voicemail: dict[str, Any] | None = None
    post_call_summary: dict[str, Any] | None = None
    post_call_extraction: dict[str, Any] | None = None
    auto_handover_config: dict[str, Any] | None = None

    tool_ids: list[str] | None = None
    """UUIDs of tools to attach to the agent at creation time."""


class CreateAgentResponse(_Base):
    """
    Response body from ``POST /v1/agents`` (201 created,
    ``main.CreateAgentResponse``).
    """

    agent_id: UUID
    tenant_id: UUID
    name: str = ""
    prompt: str = ""
    language: str = ""
    voice_id: str = ""
    llm_provider: str = ""
    llm_model: str = ""
    stt_provider: str = ""
    tts_provider: str = ""
    tts_model: str = ""
    """TTS model (``""`` = provider default)."""
    status: str = ""
    """Agent lifecycle state as persisted (``"draft"`` or ``"published"``)."""

    temperature: float | None = None
    jurisdiction: str | None = None
    """Jurisdiction code applied, echoing the request (empty when unset)."""

    configuration_id: UUID | None = None
    """UUID of the provisioned per-agent Configuration; ``None`` when
    provisioning did not run."""

    tool_ids: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    """Server-generated creation timestamp (UTC, RFC 3339)."""


class UpdateAgentRequest(_Base):
    """
    Request body for ``PUT /v1/agents/{agent_id}`` — a full-replacement
    update (``main.UpdateAgentRequest``). All mutable fields are replaced;
    omitted fields are treated as their zero value (use
    :class:`PatchAgentRequest` for partial updates).
    """

    name: str
    language: str
    prompt: str
    voice_id: AgentVoiceId | str | None = None
    llm_provider: LLMProvider | None = None
    llm_model: LLMModel | None = None
    stt_provider: STTProvider | None = None
    tts_provider: TTSProvider | None = None
    tts_model: TTSModel | None = None
    """TTS model for the provider; ``None`` (omitted) = provider default."""
    status: AgentStatus | None = None
    """``"archived"`` | ``"draft"`` | ``"published"``."""

    jurisdiction: str | None = None
    temperature: float | None = None
    max_duration_seconds: int | None = None
    greet_on_connect: bool | None = None
    begin_message: str | None = None
    start_speaker: StartSpeaker | None = None
    end_call: dict[str, Any] | None = None
    voicemail: dict[str, Any] | None = None
    post_call_summary: dict[str, Any] | None = None
    post_call_extraction: dict[str, Any] | None = None
    auto_handover_config: dict[str, Any] | None = None
    tool_ids: list[str] | None = None


class PatchAgentRequest(_Base):
    """
    Request body for ``PATCH /v1/agents/{agent_id}`` — only the supplied
    fields change; omitted fields keep their current value
    (``main.PatchAgentRequest``). Server-managed fields (``tenant_id``,
    ``configuration_id``, ``version``) cannot be set.
    """

    name: str | None = None
    language: str | None = None
    prompt: str | None = None
    voice_id: AgentVoiceId | str | None = None
    llm_provider: LLMProvider | None = None
    llm_model: LLMModel | None = None
    stt_provider: STTProvider | None = None
    tts_provider: TTSProvider | None = None
    tts_model: TTSModel | None = None
    """TTS model for the provider; ``None`` (omitted) = provider default."""
    status: AgentStatus | None = None
    jurisdiction: str | None = None
    temperature: float | None = None
    max_duration_seconds: int | None = None
    greet_on_connect: bool | None = None
    begin_message: str | None = None
    start_speaker: StartSpeaker | None = None
    end_call: dict[str, Any] | None = None
    voicemail: dict[str, Any] | None = None
    post_call_summary: dict[str, Any] | None = None
    post_call_extraction: dict[str, Any] | None = None
    auto_handover_config: dict[str, Any] | None = None
    tool_ids: list[str] | None = None


class DeleteAgentResponse(_Base):
    """Response body from ``DELETE /v1/agents/{agent_id}`` (``main.deleteAgentResponse``)."""

    deleted: bool = True
    """Always ``True`` on success."""


class PipelineStatusResponse(_Base):
    """
    Response body from ``GET /v1/pipeline/status``
    (``main.PipelineStatusResponse``).
    """

    active_pipelines: int = 0
    """Number of voice pipeline instances currently running in the
    agent-worker process."""

    timestamp: str = ""
    """UTC instant this status snapshot was generated (RFC 3339)."""


class Voice(_Base):
    """
    A single TTS voice, as returned by ``GET /v1/voices/{voice_id}`` or
    within :class:`VoiceProvider` (``main.Voice``).
    """

    voice_id: str = ""
    """Stable identifier used in agent configuration (``Agent.voice_id``)."""

    name: str = ""
    """Human-readable display name for the voice."""

    language: str = ""
    """BCP-47 language code (e.g. ``"en"``, ``"de"``, ``"en-GB"``)."""

    gender: str = ""
    """``"male"`` or ``"female"``."""

    style: str | None = None
    """Speaking style (e.g. ``"neutral"``, ``"conversational"``, ``"professional"``)."""

    accent: str | None = None
    """Region/accent descriptor (e.g. ``"British"``, ``"French"``)."""

    preview_url: str | None = None
    """Short playable audio sample of this voice, if hosted."""

    languages: list[str] = Field(default_factory=list)
    """Language codes the voice can speak (``language`` is its native one).
    ElevenLabs voices are multilingual."""


class TTSModelInfo(_Base):
    """One TTS model of a provider and the languages it speaks (``main.TTSModelInfo``)."""

    id: str = ""
    """``tts_model`` value (``""`` on an agent selects the default)."""

    default: bool = False
    """Whether this model is used when an agent's ``tts_model`` is ``""``."""

    languages: list[str] = Field(default_factory=list)
    """Language codes the model speaks; empty when not published (Voxtral)."""


class VoiceProvider(_Base):
    """
    One TTS provider's catalogue entry, as returned within the
    ``GET /v1/voices`` response map (``main.VoiceProvider``).
    """

    display_name: str = ""
    """Human-readable provider label shown in the UI."""

    voices: list[Voice] = Field(default_factory=list)
    """Ordered list of voices offered by this provider."""

    models: list[TTSModelInfo] = Field(default_factory=list)
    """The provider's TTS models and the languages each speaks."""

    total: int = 0
    """How many voices matched before the per-provider limit."""

    truncated: bool = False
    """True when ``voices`` was cut to the limit; narrow with ``language`` or
    raise ``limit``."""


class CreateVoiceResponse(_Base):
    """
    Response body from ``POST /v1/voices`` (201 created,
    ``main.CreateVoiceResponse``).
    """

    voice_id: str = ""
    name: str = ""
    language: str = ""
    gender: str = ""
    style: str | None = None
    accent: str | None = None
    preview_url: str | None = None
    provider: str = ""


class CreateVoiceJSONRequest(_Base):
    """
    JSON request body for ``POST /v1/voices`` (``main.CreateVoiceJSONRequest``)
    — the alternative to the multipart form: the clip travels base64-encoded.
    """

    accent: str | None = None
    """Accent label, e.g. ``"British"``."""

    audio_base64: str | None = None
    """Base64 of a ~10s ``audio/mpeg`` or ``audio/wav`` clip."""

    consent_confirmed: bool | None = None
    """The caller confirms they hold the speaker's consent."""

    gender: str | None = None
    """e.g. ``"female"``."""

    language: str | None = None
    """BCP-47 tag, e.g. ``"en-GB"``."""

    name: str | None = None
    """Display name, e.g. ``"British Receptionist (female)"``."""

    style: str | None = None
    """e.g. ``"professional"``."""


# ─────────────────────────────────────────────────────────────────────────────
# client.tools — custom + platform-tool CRUD, agent-tool
# attach/detach/list. agent-worker (8089).
# ─────────────────────────────────────────────────────────────────────────────

class ToolHeader(_Base):
    """
    A single static HTTP header sent with every tool dispatch
    (``pipeline.ToolHeader``).
    """

    key: str = ""
    """HTTP header name (e.g. ``"Authorization"``, ``"X-Api-Key"``)."""

    value: str = ""
    """Header value, or a ``{{varName}}`` dynamic-variable template."""


class ToolQueryParam(_Base):
    """A single URL query parameter appended to a tool's dispatch URL
    (``pipeline.ToolQueryParam``)."""

    key: str = ""
    """Query parameter name (e.g. ``"format"``, ``"limit"``)."""

    mode: str = ""
    """Either ``"const"`` (fixed ``value``) or ``"description"`` (LLM-supplied,
    with ``value`` as the LLM-facing description)."""

    value: str = ""
    """The fixed value (``"const"``) or the LLM-facing description
    (``"description"``)."""


class ToolResponseVar(_Base):
    """
    A JSON path in a tool's HTTP response extracted into the pipeline's
    dynamic-variable store (``pipeline.ToolResponseVar``).
    """

    json_path: str = ""
    """Dot-separated key path into the response body (e.g.
    ``"data.user.id"``)."""

    name: str = ""
    """Variable name written to the dynamic variable store. Must match
    ``^[a-zA-Z0-9_-]+$``."""


class SpeakDuringExec(_Base):
    """In-flight hold-audio settings for a tool call
    (``pipeline.SpeakDuringExec``)."""

    enabled: bool = False
    """Activates speak-during behaviour for this tool."""

    text: str | None = None
    """Phrase spoken to the caller while the tool executes. Required when
    ``enabled`` is ``True``; ignored otherwise."""


class ToolExecution(_Base):
    """Runtime dispatch settings for a tool: timeout, speak-during, model
    override (``pipeline.ToolExecution``)."""

    timeout_ms: int | None = None
    """HTTP client timeout override for this tool, in ``[1, 300_000]`` ms
    when non-zero. ``None``/``0`` uses the server default (120 000 ms)."""

    speak_during: SpeakDuringExec | None = None
    """In-flight hold-audio behaviour while this tool executes."""

    model_override: str | None = None
    """Swaps the LLM model for the single turn that invokes this tool.
    Empty/``None`` uses the agent's default model."""


class ToolConfig(_Base):
    """
    A tool (custom HTTP function-calling tool, or platform-supplied tool
    such as Cal.com), as returned by the agent-worker's tool CRUD API
    (``pipeline.ToolConfig``).

    ``provider_config.destination`` on a ``warm_transfer`` tool is written
    as a plaintext E.164 number but is persisted (and hence returned here)
    as an opaque encrypted token — never the plaintext number. Re-saving
    the returned token unchanged is a safe no-op.
    """

    tool_id: UUID
    """Server-generated UUID primary key."""

    destination_hint: str | None = None
    """A ``warm_transfer`` tool's destination number with all but its last four
    digits masked (e.g. ``"•••• 9354"``). Response-only, never stored."""

    tenant_id: UUID | None = None
    """UUID of the owning tenant."""

    name: str = ""
    """Unique, machine-readable tool identifier within the tenant. Must
    match ``^[a-zA-Z0-9_-]+$``, at most 64 characters. Used as the function
    name sent to the LLM."""

    description: str = ""
    """Natural-language explanation of what the tool does, sent verbatim
    to the LLM as the function description."""

    method: str = ""
    """HTTP method for the tool endpoint: ``GET``, ``POST``, ``PUT``,
    ``PATCH``, or ``DELETE``."""

    url: str = ""
    """Absolute HTTP(S) endpoint the executor dispatches to. May contain
    ``{{varName}}`` placeholders resolved at execution time."""

    headers: list[ToolHeader] = Field(default_factory=list)
    """Ordered list of static HTTP headers included in every request."""

    query_params: list[ToolQueryParam] = Field(default_factory=list)
    """Ordered list of query parameters appended to the URL."""

    parameters: dict[str, Any] | None = None
    """JSON Schema (``type: object``) defining the arguments the LLM must
    supply when calling this tool. May be ``None`` for tools with no
    LLM-supplied arguments."""

    response_vars: list[ToolResponseVar] = Field(default_factory=list)
    """JSON paths in the tool response extracted into dynamic variables."""

    execution: ToolExecution | None = None
    """Runtime dispatch settings: timeout, speak-during, model override."""

    args_only: bool | None = None
    """When ``True``, no HTTP request is made — the (merged) arguments are
    marshalled to JSON and returned to the LLM as the tool result."""

    provider: str | None = None
    """Platform-tool provider (e.g. ``"cal_com"``). Empty/``None`` means an
    ordinary custom HTTP tool."""

    provider_tool: str | None = None
    """Specific operation exposed by ``provider`` (e.g.
    ``"book_appointment"``, ``"check_availability"``). Only meaningful when
    ``provider`` is set."""

    connection_id: UUID | None = None
    """UUID of the integration connection supplying credentials for a
    platform tool. Required when ``provider`` is set; unused otherwise."""

    provider_config: dict[str, Any] | None = None
    """Provider-specific configuration (event type, timezone, field
    mappings, etc.). Only meaningful when ``provider`` is set."""

    created_at: datetime | None = None
    """Server-generated UTC creation timestamp."""

    updated_at: datetime | None = None
    """Server-generated UTC last-modification timestamp."""

    deleted_at: datetime | None = None
    """Set on soft-delete. ``None`` means the tool is active."""


class ListToolsResponse(_Base):
    """
    Raw response body from ``GET /v1/tools`` (``main.listToolsResponse``).

    ``client.tools.list_tools`` returns this reshaped into the shared
    :class:`Page` convention.
    """

    tools: list[ToolConfig] = Field(default_factory=list)
    has_more: bool = False
    cursor: str | None = None


class CreateToolRequest(_Base):
    """Request body for ``POST /v1/tools`` and ``PUT /v1/tools/{tool_id}``
    (``main.CreateToolRequest``)."""

    name: str
    """Unique, machine-readable identifier for this tool within the
    tenant. Must match ``^[a-zA-Z0-9_-]+$``, at most 64 characters.
    Required."""

    description: str
    """Natural-language explanation sent to the LLM as the function
    description. Required, max 1024 chars."""

    method: str | None = None
    """HTTP method: ``GET``, ``POST``, ``PUT``, ``PATCH``, or ``DELETE``.
    Leave empty for a platform tool (``provider`` set)."""

    url: str | None = None
    """Absolute HTTP(S) endpoint. Leave empty for a platform tool
    (``provider`` set)."""

    headers: list[ToolHeader] | None = None
    """Static HTTP headers to include in every request."""

    query_params: list[ToolQueryParam] | None = None
    """Query parameters appended to the URL."""

    parameters: dict[str, Any] | None = None
    """JSON Schema (``type: object``) defining the LLM-supplied arguments.
    Only allowed for POST/PUT/PATCH methods. Leave empty for a platform
    tool (``provider`` set)."""

    response_vars: list[ToolResponseVar] | None = None
    """JSON paths in the tool response extracted into dynamic variables."""

    execution: ToolExecution | None = None
    """Runtime dispatch settings: timeout, speak-during, model override."""

    args_only: bool | None = None
    """``True``: no HTTP request is made — arguments are returned to the
    LLM as the tool result."""

    provider: str | None = None
    """Platform-tool provider (e.g. ``"cal_com"``). Leave empty for a
    custom HTTP tool. When set, ``method``/``url``/``parameters`` must be
    left empty and ``connection_id`` becomes required."""

    provider_tool: str | None = None
    """Specific operation exposed by ``provider`` (e.g.
    ``"book_appointment"``). Only meaningful when ``provider`` is set."""

    connection_id: UUID | None = None
    """UUID of an existing, active integration connection (see
    ``client.integrations``) supplying credentials this platform tool
    executes with. Required when ``provider`` is set."""

    provider_config: dict[str, Any] | None = None
    """Provider-specific configuration (event type, timezone, field
    mappings, etc.). Must contain ``event_type_id`` or
    (``event_type_slug`` and ``username``). Only meaningful when
    ``provider`` is set."""


class UpdateToolRequest(_Base):
    """Request body for ``PATCH /v1/tools/{tool_id}``
    (``main.UpdateToolRequest``). Only supplied fields are modified;
    omitted fields keep their current value (list fields are a full
    replacement when supplied, per the server's merge semantics)."""

    name: str | None = None
    description: str | None = None
    method: str | None = None
    url: str | None = None
    headers: list[ToolHeader] | None = None
    query_params: list[ToolQueryParam] | None = None
    parameters: dict[str, Any] | None = None
    response_vars: list[ToolResponseVar] | None = None
    execution: ToolExecution | None = None
    args_only: bool | None = None
    provider: str | None = None
    provider_tool: str | None = None
    connection_id: UUID | None = None
    provider_config: dict[str, Any] | None = None


class DeleteToolResponse(_Base):
    """Response body from ``DELETE /v1/tools/{tool_id}``
    (``main.deleteToolResponse``)."""

    deleted: bool = True
    """Always ``True`` on success."""


class TestToolResponse(_Base):
    """
    Response body from ``POST /v1/tools/{tool_id}/test``
    (``main.testToolResponse``).

    Validates a platform-supplied tool (Cal.com) without creating a real
    booking.
    """

    # Tells pytest not to try to collect this as a test class purely
    # because its name starts with "Test" (it mirrors the server's
    # ``main.testToolResponse`` type name) — silences a spurious
    # PytestCollectionWarning when this model is imported into test modules.
    __test__ = False

    tool_id: UUID | None = None
    """Echoes the tested tool's UUID."""

    healthy: bool = False
    """``True`` only when every check for this tool's kind passed."""

    checks_passed: list[str] = Field(default_factory=list)
    """Checks that succeeded before either ``healthy`` became ``True`` or a
    check failed. A subset of ``"connection_active"``,
    ``"event_type_resolved"``, ``"availability_probe"``,
    ``"field_mapping_coverage"``."""

    error: str | None = None
    """Stable, redacted failure code (e.g. ``"connection_revoked"``,
    ``"event_type_not_found"``, ``"field_mapping_error"``) — never a raw
    credential or provider error message. Empty when ``healthy`` is
    ``True``."""

    dynamic_var_fields: list[str] = Field(default_factory=list)
    """``book_appointment`` field_mappings entries sourced from a call
    dynamic variable, whose runtime value cannot be verified by a
    config-time test — informational only."""


class ListAgentToolsResponse(_Base):
    """
    Raw response body from ``GET /v1/agents/{agent_id}/tools``
    (``main.listAgentToolsResponse``).

    ``client.tools.list_agent_tools`` returns this reshaped into the
    shared :class:`Page` convention.
    """

    items: list[ToolConfig] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: str | None = None


class AttachToolRequest(_Base):
    """Request body for ``POST /v1/agents/{agent_id}/tools``
    (``main.AttachToolRequest``)."""

    tool_id: UUID
    """UUID of the tool to attach. Obtain from ``list_tools`` or
    ``create_tool``."""


class AttachToolResponse(_Base):
    """Response body from ``POST /v1/agents/{agent_id}/tools`` (201 created,
    ``main.attachToolResponse``)."""

    agent_id: UUID | None = None
    tool_id: UUID | None = None
    attached: bool = True


class DetachToolResponse(_Base):
    """Response body from ``DELETE /v1/agents/{agent_id}/tools/{tool_id}``
    (``main.detachToolResponse``)."""

    detached: bool = True
    """``True`` if the attachment existed and was removed; also ``True``
    (no-op) if it was not attached."""


# ─────────────────────────────────────────────────────────────────────────────
# Integrations — Cal.com connections — agent-worker
# ─────────────────────────────────────────────────────────────────────────────

class CalcomEventType(_Base):
    """
    A single Cal.com event type, as returned by
    ``client.integrations.list_connection_event_types`` (``calcom.EventType``).
    """

    id: int | None = None
    """Cal.com's numeric event-type ID."""

    title: str | None = None
    """Human-readable event type name."""

    slug: str | None = None
    """URL-safe event type identifier, usable in ``provider_config``
    (e.g. a Cal.com tool's ``event_type_slug``)."""

    length_in_minutes: int | None = Field(default=None, alias="lengthInMinutes")
    """Event duration in minutes."""

    hidden: bool | None = None
    """``True`` if the event type is hidden on the tenant's public booking
    page."""


class Connection(_Base):
    """
    A Cal.com integration connection (``integrations.Connection``).

    Credentials are always masked: only ``has_api_key``/``has_oauth_token``
    booleans are ever returned, never a raw API key, OAuth token, or Secrets
    Manager ARN.
    """

    connection_id: UUID | None = None
    """Server-generated UUID primary key."""

    tenant_id: UUID | None = None
    """UUID of the owning tenant."""

    provider: str | None = None
    """Upstream integration identifier. Only ``"cal_com"`` is currently
    supported."""

    name: str | None = None
    """Tenant-chosen, tenant-unique (among non-deleted rows) label."""

    auth_method: IntegrationAuthMethod | None = None
    """``"api_key"`` or ``"oauth"`` (``integrations.AuthMethod``)."""

    cal_username: str | None = None
    """Cal.com username associated with this connection, when known — used
    to disambiguate event types by slug."""

    has_api_key: bool | None = None
    """``True`` if API-key credential material is present. Exactly one of
    ``has_api_key``/``has_oauth_token`` is expected to be ``True``, matching
    ``auth_method``. Never exposes the key itself."""

    has_oauth_token: bool | None = None
    """``True`` if OAuth token material is present. Never exposes the
    token itself."""

    oauth_scope: str | None = None
    """Granted OAuth scope string, if any."""

    oauth_expires_at: str | None = None
    """Access token expiry (OAuth connections only). ``None`` for
    ``api_key`` connections or before the first token exchange."""

    status: IntegrationConnectionStatus | None = None
    """Connection lifecycle state: ``"active"``, ``"revoked"``, or
    ``"error"`` (``integrations.Status``)."""

    health: IntegrationConnectionHealth | None = None
    """Last-observed reachability/token state: ``"connected"``,
    ``"token_expired"``, ``"revoked"``, ``"error"``, or ``"unknown"``
    (``integrations.Health``)."""

    last_checked_at: str | None = None
    """When ``health`` was last (re)computed."""

    last_error: str | None = None
    """Redacted, human-readable description of the last failure. Never
    contains a secret or raw token."""

    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None


class ListConnectionsResponse(_Base):
    """Response body from ``GET /v1/integrations``
    (``main.listConnectionsResponse``)."""

    connections: list[Connection] = Field(default_factory=list)


class CreateConnectionRequest(_Base):
    """Request body for ``POST /v1/integrations``
    (``main.CreateConnectionRequest``).

    Creates a bring-your-own-account Cal.com connection using a pasted API
    key. Use :meth:`IntegrationsClient.calcom_oauth_start` for OAuth
    connections instead.
    """

    name: str
    """Tenant-chosen, tenant-unique label for this connection. Required,
    at most 120 characters."""

    api_key: str | None = Field(default=None, repr=False)
    """Raw Cal.com API key pasted from the user's own Cal.com dashboard
    (Settings → Developer → API Keys). Required when ``auth_method`` is
    ``"api_key"``. Write-only: never stored or echoed back — only its AWS
    Secrets Manager ARN is persisted."""

    auth_method: str | None = None
    """Credential method. Only ``"api_key"`` is accepted by this endpoint;
    empty defaults to ``"api_key"``."""

    provider: str | None = None
    """Upstream integration identifier. Only ``"cal_com"`` is currently
    supported; empty defaults to ``"cal_com"``."""

    cal_username: str | None = None
    """Cal.com username associated with this account, used to disambiguate
    event types by slug. Optional."""


class DeleteConnectionResponse(_Base):
    """Response body from ``DELETE /v1/integrations/{connection_id}``
    (``main.deleteConnectionResponse``)."""

    deleted: bool = True


class TestConnectionResponse(_Base):
    """
    Response body from ``POST /v1/integrations/{connection_id}/test``
    (``main.testConnectionResponse``).

    Always returns 200 with a distinguishable healthy/error outcome —
    never a raw credential or Cal.com error message.
    """

    # Tells pytest not to try to collect this as a test class purely because
    # its name starts with "Test" (it mirrors the server's
    # ``main.testConnectionResponse`` type name) — silences a spurious
    # PytestCollectionWarning when this model is imported into test modules.
    __test__ = False

    connection_id: UUID | None = None
    """Echoes the tested connection's UUID."""

    healthy: bool = False
    """``True`` only when credential resolution AND the live
    ``GET /v2/event-types`` probe both succeeded."""

    health: str | None = None
    """Mirrors ``integrations.Health`` — the same value just persisted
    (``"connected"``, ``"token_expired"``, ``"revoked"``, ``"error"``)."""

    error: str | None = None
    """Stable, redacted error code (e.g. ``"connection_revoked"``,
    ``"auth_failed"``, ``"rate_limited"``) — never a raw Cal.com error
    message or any credential material. Empty when ``healthy`` is
    ``True``."""

    event_type_count: int | None = None
    """Number of event types Cal.com returned. Only populated when
    ``healthy`` is ``True``."""


class ListEventTypesResponse(_Base):
    """Response body from
    ``GET /v1/integrations/{connection_id}/event-types``
    (``main.listEventTypesResponse``)."""

    event_types: list[CalcomEventType] = Field(default_factory=list)


class OAuthStartResponse(_Base):
    """Response body from ``GET /v1/integrations/cal_com/oauth/start``
    (``main.oauthStartResponse``)."""

    authorize_url: str | None = None
    """Cal.com-hosted consent screen the caller's frontend must redirect
    the user's browser to."""


# ─────────────────────────────────────────────────────────────────────────────
# Org self-service (client.org, OrgBearer) — org-management (8092)
# ─────────────────────────────────────────────────────────────────────────────

class Organization(_Base):
    """
    A registered organization (``org.Organization``).

    Timestamps are kept as server-emitted ISO-8601 strings (not
    ``datetime``) because reserved/not-yet-set fields such as
    ``verified_at`` may be absent or empty rather than a valid timestamp.
    """

    org_id: UUID
    """Server-generated UUID primary key."""

    name: str | None = None
    """Organization's display name."""

    legal_name: str | None = None
    """KYC legal/registered name (mandatory KYC minimum)."""

    entity_type: str | None = None
    """``"individual"`` or ``"company"`` (mandatory KYC minimum)."""

    country: str | None = None
    """ISO 3166-1 alpha-2 country code (mandatory KYC minimum)."""

    verification_status: str | None = None
    """One of ``"unverified"``, ``"verified"``, ``"rejected"``."""

    verified_at: str | None = None
    """Set once a platform admin verifies the organization."""

    verified_by_kid: str | None = None
    """The platform-admin key id that verified this org."""

    default_billing_ref: str | None = None
    """Reserved fallback billing — unused this phase."""

    created_at: str | None = None
    updated_at: str | None = None


class OrgAdmin(_Base):
    """An org_admin account (``org.OrgAdmin``)."""

    admin_id: UUID
    """Server-generated UUID primary key."""

    org_id: UUID | None = None
    """UUID of the owning organization."""

    email: str | None = None
    """Account's unique (case-insensitive) login email."""

    name: str | None = None
    """Admin's display name. Empty when unset."""

    role: str | None = None
    """Reserved for future RBAC; today always ``"org_admin"``."""

    last_login_at: str | None = None
    """Stamped on every successful login."""

    email_verified_at: str | None = None
    """Reserved (email-link verification deferred)."""

    disabled_at: str | None = None
    """Reserved."""

    created_at: str | None = None
    updated_at: str | None = None


class OrgKYC(_Base):
    """
    An organization's KYC record (``org.OrgKYC``).

    Superset of individual- and company-shaped fields; unused fields for a
    given ``entity_type`` are simply absent. ``additional`` is overflow
    JSONB for jurisdiction-specific extras — never national ID numbers
    (spec R6).
    """

    org_id: UUID | None = None
    legal_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    website: str | None = None

    # Address
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    address_country: str | None = None

    # Company
    registration_number: str | None = None
    incorporation_country: str | None = None
    incorporation_region: str | None = None
    incorporation_date: str | None = None
    lei: str | None = None
    representative_name: str | None = None
    representative_role: str | None = None

    # Individual
    date_of_birth: str | None = None
    nationality: str | None = None

    # Tax
    tax_id: str | None = None
    tax_residence_country: str | None = None
    vat_id: str | None = None

    additional: dict[str, Any] | None = None

    created_at: str | None = None
    updated_at: str | None = None


class OrgSignupRequest(_Base):
    """
    Request body for ``POST /v1/org/signup`` (``org.SignupRequest``).

    Open self-serve signup — no authentication required (IP-rate-limited).
    ``entity_type`` must be exactly ``"individual"`` or ``"company"``;
    ``country`` must be an ISO 3166-1 alpha-2 code.
    """

    org_name: str
    """Organization's display name."""

    email: str
    """First admin account's unique login email."""

    password: str = Field(repr=False)
    """Plaintext signup password (>= 12 chars). Never logged, never
    echoed back."""

    entity_type: OrgEntityType
    """Must be ``"individual"`` or ``"company"``."""

    legal_name: str
    """KYC legal/registered name."""

    country: str
    """ISO 3166-1 alpha-2 country code."""

    name: str | None = None
    """Admin's display name (optional)."""

    kyc: OrgKYC | None = None
    """Optional KYC superset captured at signup. Absent optional fields
    are never rejected — only a provided-but-malformed one is."""


class OrgSignupResponse(_Base):
    """Response body from ``POST /v1/org/signup``
    (``org.SignupResponse``)."""

    token: str | None = Field(default=None, repr=False)
    """Org access token (``Authorization: Bearer <token>``)."""

    expires_in: int | None = None
    org: Organization | None = None
    admin: OrgAdmin | None = None


class OrgLoginRequest(_Base):
    """Request body for ``POST /v1/org/login`` (``org.LoginRequest``)."""

    email: str
    password: str = Field(repr=False)


class OrgLoginResponse(_Base):
    """Response body from ``POST /v1/org/login`` (``org.LoginResponse``)."""

    token: str | None = Field(default=None, repr=False)
    """Org access token (``Authorization: Bearer <token>``)."""

    expires_in: int | None = None

    ver: bool | None = None
    """Mirrors the organization's CURRENT (DB-checked) verification_status
    at login time. A UX hint only — every route re-checks the database,
    never this field or the JWT ``ver`` claim it mirrors."""


class OrgRefreshResponse(_Base):
    """
    Response body from ``POST /v1/org/refresh``
    (``org.RefreshResponse``).

    The refresh token itself is never in the body — it is an httpOnly,
    ``SameSite=Strict`` cookie the underlying ``httpx.AsyncClient``'s
    cookie jar carries automatically across ``login()``/``refresh()``
    calls made on the same :class:`~audact.client.AudactClient` instance.
    """

    token: str | None = Field(default=None, repr=False)
    """Freshly minted org access token."""

    expires_in: int | None = None


class OrgProfileResponse(_Base):
    """Response body from ``GET``/``PATCH /v1/org/profile``
    (``org.OrgProfileResponse``)."""

    org: Organization | None = None
    admin: OrgAdmin | None = None


class OrgUpdateProfileRequest(_Base):
    """
    Request body for ``PATCH /v1/org/profile``
    (``org.UpdateProfileRequest``).

    Absent/empty fields are left unchanged.
    """

    org_name: str | None = None
    """When non-empty, replaces the organization's display name."""

    admin_name: str | None = None
    """When non-empty, replaces the calling admin's display name."""


class OrgKYCResponse(_Base):
    """Response body from ``GET``/``PATCH /v1/org/kyc``
    (``org.KYCResponse``)."""

    kyc: OrgKYC | None = None


class OrgKYCPatchRequest(_Base):
    """
    Request body for ``PATCH /v1/org/kyc`` (``org.KYCPatchRequest``).

    Merges the provided fields onto the organization's existing KYC
    record; absent fields are left unchanged. A provided-but-malformed
    field returns 422 ``kyc_invalid``.
    """

    legal_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    website: str | None = None

    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    address_country: str | None = None

    registration_number: str | None = None
    incorporation_country: str | None = None
    incorporation_region: str | None = None
    incorporation_date: str | None = None
    lei: str | None = None
    representative_name: str | None = None
    representative_role: str | None = None

    date_of_birth: str | None = None
    nationality: str | None = None

    tax_id: str | None = None
    tax_residence_country: str | None = None
    vat_id: str | None = None

    additional: dict[str, Any] | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Org-tenant lifecycle — org-management (8092), OrgBearer
# ─────────────────────────────────────────────────────────────────────────────

class OrgTenantSummary(_Base):
    """
    A tenant owned by the caller's organization (``org.TenantSummary``).

    Returned by every ``client.org.*`` tenant-lifecycle method.
    """

    tenant_id: UUID
    """Server-generated UUID primary key."""

    name: str
    """Human-readable tenant display name."""

    status: str
    """Tenant lifecycle status: ``"active"`` or ``"disabled"``."""

    created_at: datetime
    """Server-generated creation timestamp (UTC)."""

    deleted_at: datetime | None = None
    """Set when the tenant has been soft-deleted by its organization. ``None``
    for a live tenant."""

    initialized_at: datetime | None = None
    """Set once the tenant's default configuration and first owner key have
    been provisioned (:meth:`~audact.client.OrgClient.initialize_tenant`).
    ``None`` until then."""


class ListOrgTenantsResponse(_Base):
    """
    Raw response body from ``GET /v1/org/tenants`` (``org.ListTenantsResponse``).

    :meth:`~audact.client.OrgClient.list_tenants` reshapes this into the
    shared :class:`Page` convention. This surface has no explicit
    ``has_more`` field on the wire — the presence of ``next_cursor`` is the
    signal that a further page exists.
    """

    tenants: list[OrgTenantSummary] = Field(default_factory=list)
    next_cursor: str | None = None


class OrgCreateTenantRequest(_Base):
    """Request body for ``POST /v1/org/tenants`` (``org.CreateTenantRequest``)."""

    name: str
    """Human-readable tenant name. Required, non-empty."""


class OrgCreateTenantResponse(_Base):
    """Response body from ``POST /v1/org/tenants`` (``org.CreateTenantResponse``)."""

    tenant: OrgTenantSummary | None = None


class OrgGetTenantResponse(_Base):
    """Response body from ``GET /v1/org/tenants/{id}`` (``org.GetTenantResponse``)."""

    tenant: OrgTenantSummary | None = None


class OrgTenantActionResponse(_Base):
    """
    Response body shared by the org-tenant lifecycle actions that just
    return the updated tenant (``org.TenantActionResponse``): soft-delete,
    disable, enable, and restore.
    """

    tenant: OrgTenantSummary | None = None


class OrgImpersonateTenantResponse(_Base):
    """
    Response body from ``POST /v1/org/tenants/{id}/impersonate``
    (``org.ImpersonateTenantResponse``).
    """

    tenant_token: str | None = Field(default=None, repr=False)
    """Short-lived tenant JWT (``{tid, role:"owner", imp, oid}``) the caller
    can present to tenant-facing services to act as the tenant's owner.
    Returned exactly once — never stored server-side, never logged."""

    expires_in: int = 0
    """Token's remaining lifetime in seconds (~1200s / 20m)."""


class OrgInitializeAPIKeyView(_Base):
    """
    A newly-minted tenant API key, revealed exactly once
    (``org.InitializeAPIKeyView``).
    """

    api_key_id: UUID | None = None
    """Server-generated UUID of the newly-minted key."""

    key: str | None = None
    """Full raw API key value, returned ONCE. Never stored in plaintext and
    can never be retrieved again after this response."""

    key_prefix: str | None = None
    """First 8 characters of the random portion of ``key``, retained for
    display/lookup purposes (SEC-009)."""

    role: str | None = None
    """RBAC role assigned to this key — always ``"owner"`` for the key
    minted by :meth:`~audact.client.OrgClient.initialize_tenant`."""


class OrgInitializeTenantResponse(_Base):
    """
    Response body from ``POST /v1/org/tenants/{id}/initialize``
    (``org.InitializeTenantResponse``).
    """

    tenant: OrgTenantSummary | None = None
    api_key: OrgInitializeAPIKeyView | None = None


class OrgIssueKeyRequest(_Base):
    """
    Request body for ``POST /v1/org/tenants/{id}/keys`` (``org.IssueKeyRequest``).
    """

    name: str | None = None
    """Human-readable label for the new key. Optional, defaults to
    ``"owner"`` when empty."""


class OrgIssueKeyResponse(_Base):
    """
    Response body from ``POST /v1/org/tenants/{id}/keys`` (``org.IssueKeyResponse``).
    """

    api_key: OrgInitializeAPIKeyView | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Platform-admin org-management surface (``client.platform.orgs``, PlatformBearer).
# Reuses :class:`Organization`/:class:`OrgAdmin` (defined above for
# the org self-service surface) since the wire shapes are identical
# — only the auth scheme (PlatformBearer, not OrgBearer) and the caller
# (platform superadmin, not the org itself) differ.
# ─────────────────────────────────────────────────────────────────────────────


class PlatformListOrganizationsResponse(_Base):
    """
    Raw response body from ``GET /v1/platform/organizations``
    (``org.listOrganizationsResponse``).

    :meth:`~audact.client.PlatformOrgsClient.list_organizations` reshapes
    this into the shared :class:`Page` convention. This surface has no
    explicit ``has_more`` field on the wire — the presence of a non-empty
    ``next_cursor`` is the signal that a further page exists.
    """

    organizations: list[Organization] = Field(default_factory=list)
    next_cursor: str | None = None


class PlatformOrganizationResponse(_Base):
    """
    Response body shared by
    :meth:`~audact.client.PlatformOrgsClient.verify_organization` and
    :meth:`~audact.client.PlatformOrgsClient.reject_organization`
    (``org.organizationResponse``).
    """

    organization: Organization | None = None


class PlatformRejectOrganizationRequest(_Base):
    """
    Request body for ``POST /v1/platform/organizations/{org_id}/reject``
    (``org.rejectOrganizationRequest``).

    ``reason`` is required — persisted only in the ``org_audit_log``
    ``"org.reject"`` row's metadata, never on the organization record
    itself.
    """

    reason: str
    """Rejection reason. Required; a 422 ``reason_required`` is returned
    when empty."""


class PlatformFindOrgAdminsResponse(_Base):
    """
    Response body from ``GET /v1/platform/org-admins``
    (``org.findOrgAdminsResponse``). Never includes ``password_hash``.
    """

    org_admins: list[OrgAdmin] = Field(default_factory=list)


class PlatformOrgAdminResponse(_Base):
    """
    Response body from ``PATCH /v1/platform/org-admins/{admin_id}``
    (``org.orgAdminResponse``).
    """

    org_admin: OrgAdmin | None = None


class PlatformChangeOrgAdminEmailRequest(_Base):
    """
    Request body for ``PATCH /v1/platform/org-admins/{admin_id}``
    (``org.changeOrgAdminEmailRequest``).
    """

    email: str
    """New login email."""


class PlatformResetOrgAdminPasswordRequest(_Base):
    """
    Request body for ``POST /v1/platform/org-admins/{admin_id}/reset-password``
    (``org.resetOrgAdminPasswordRequest``).

    Omit or leave ``new_password`` empty to mint a one-time reset token
    instead of setting a password directly.
    """

    new_password: str | None = Field(default=None, repr=False)
    """When non-empty (>= 12 chars), bcrypt-hashed and set directly. Never
    echoed back or logged."""


class PlatformResetOrgAdminPasswordResponse(_Base):
    """
    Response body from ``POST /v1/platform/org-admins/{admin_id}/reset-password``
    (``org.resetOrgAdminPasswordResponse``).
    """

    reset: str
    """``"password_set"`` (``new_password`` mode) or ``"token"`` (one-time
    reset-token mode)."""

    token: str | None = Field(default=None, repr=False)
    """Present ONLY in ``"token"`` mode. Returned exactly once — the server
    does not store it in plaintext beyond a short Redis TTL, and never logs
    it."""

    expires_in: int | None = None
    """Present ONLY in ``"token"`` mode: the token's remaining lifetime in
    seconds."""


# ─────────────────────────────────────────────────────────────────────────────
# Aggregation — aggregator (8087)
# ─────────────────────────────────────────────────────────────────────────────

class ProofStep(_Base):
    """
    A single step of a Merkle authentication path
    (``aggregation.ProofStepResponse`` / ``aggregation.VerifyInclusionProofStep``).

    Shared shape used both in :class:`BranchProof` (a server-issued proof,
    from :meth:`~audact.client.AggregationClient.get_proof`) and in
    :class:`VerifyInclusionRequest` (a caller-supplied proof to verify).
    """

    hash: str
    """Hex-encoded SHA-256 sibling hash at this level."""

    position: str
    """Sibling's position relative to the current node: ``"left"``
    (combine as ``SHA256(sibling || current)``) or ``"right"`` (combine as
    ``SHA256(current || sibling)``)."""


class BranchProof(_Base):
    """
    Merkle authentication path proving a tenant's aggregate hash is
    included in a window's Merkle root (``aggregation.BranchProofResponse``).

    Embedded in :class:`ProofResponse` (``branch_proof``).
    """

    root: str
    """Hex-encoded SHA-256 Merkle root. Equals ``merkle_root`` on the
    parent :class:`ProofResponse`."""

    leaf_hash: str
    """Hex-encoded SHA-256 of the tenant's aggregate hash leaf."""

    leaf_index: int
    """0-based position of this leaf in the padded tree."""

    leaf_count: int
    """Total number of leaf positions (real + padding)."""

    pad_count: int
    """Number of padding leaves added to reach the minimum of 16."""

    tree_depth: int
    """Number of levels above the leaf level."""

    steps: list[ProofStep] = Field(default_factory=list)
    """Ordered Merkle authentication path from leaf to root."""


class ProofResponse(_Base):
    """
    Response body from ``GET /v1/proofs/{window_id}``
    (``aggregation.ProofResponse``) — a per-tenant branch proof plus the
    RFC 3161 timestamp token attesting the window's Merkle root.
    """

    window_id: str
    """Canonical RFC 3339 string identifying the aggregation window
    (equals ``window_start`` in UTC)."""

    aggregation_id: str
    """Server-generated UUID of the ``aggregation_results`` row."""

    batch_number: int
    """Monotonically increasing batch sequence number."""

    merkle_root: str
    """Hex-encoded SHA-256 Merkle root of the padded tree."""

    tenant_aggregate_hash: str
    """Hex-encoded per-tenant aggregate hash forming this tenant's leaf."""

    branch_proof: BranchProof
    """Merkle authentication path from this tenant's leaf to ``merkle_root``."""

    timestamp_token: str | None = None
    """Base64-encoded DER RFC 3161 ``TimeStampToken``. Decode with
    ``base64.b64decode`` before parsing (e.g. with ``asn1crypto`` or
    ``openssl ts -verify``)."""

    timestamp_time: str | None = None
    """Time attested by the RFC 3161 TSA."""

    tsa_url: str | None = None
    """URL of the Time-Stamp Authority endpoint that issued the token."""


class ProofSummary(_Base):
    """
    One entry of :attr:`ProofListResponse.proofs`
    (``aggregation.ProofSummary``) — an aggregation window the tenant
    participated in, without the full branch proof.
    """

    window_id: str
    """Canonical RFC 3339 string identifying the aggregation window."""

    window_start: str | None = None
    """Inclusive start of the aggregation window (UTC)."""

    window_end: str | None = None
    """Exclusive end of the aggregation window (UTC)."""

    aggregation_id: str
    """Server-generated UUID of the ``aggregation_results`` row."""

    batch_number: int
    """Monotonically increasing batch sequence number."""

    merkle_root: str
    """Hex-encoded SHA-256 Merkle root of the padded tree."""

    tenant_aggregate_hash: str
    """Hex-encoded per-tenant aggregate hash for this window."""

    status: str
    """Lifecycle state of this aggregation batch: one of ``"pending"``,
    ``"timestamped"``, ``"attested"``, ``"complete"``, ``"failed"``."""

    timestamp_time: str | None = None
    """Time attested by the RFC 3161 TSA. ``None`` when no RFC 3161 proof
    exists yet for this window."""

    tsa_url: str | None = None
    """URL of the Time-Stamp Authority endpoint. Empty/``None`` when no
    RFC 3161 proof exists yet for this window."""

    created_at: str | None = None
    """Server-generated timestamp of the ``aggregation_results`` row."""


class ProofListResponse(_Base):
    """
    Raw response body from ``GET /v1/proofs``
    (``aggregation.ProofListResponse``).

    :meth:`~audact.client.AggregationClient.list_proofs` reshapes this
    into the shared :class:`Page` convention.
    """

    proofs: list[ProofSummary] = Field(default_factory=list)
    count: int = 0
    has_more: bool = False
    next_cursor: str | None = None

    total: int | None = None
    """Total is the number of aggregation windows the tenant participated in, across all
    pages. Omitted only if the store cannot count.
    """


class MetaChainEntry(_Base):
    """
    One entry of the public meta-chain (chain-of-chains)
    (``aggregation.MetaChainEntry``) — a single window's aggregation batch,
    chained to the previous one. Contains only root hashes and integrity
    fields, never tenant-specific data.
    """

    meta_id: str
    """Server-generated identifier of this meta-chain link."""

    sequence: int
    """Monotonically increasing meta-chain sequence number."""

    aggregation_id: str
    """UUID of the underlying ``aggregation_results`` row."""

    merkle_root: str
    """Hex-encoded SHA-256 Merkle root of this window's batch."""

    previous_hash: str | None = None
    """Hex-encoded hash of the previous meta-chain link (chains the
    meta-chain itself)."""

    chain_hash: str | None = None
    """Hex-encoded hash of this meta-chain link (``previous_hash`` +
    this entry's own fields)."""


class MetaChainResponse(_Base):
    """
    Raw response body from ``GET /v1/metachain``
    (``aggregation.MetaChainResponse``) — public, no authentication
    required.

    :meth:`~audact.client.AggregationClient.get_metachain` reshapes this
    into the shared :class:`Page` convention.
    """

    entries: list[MetaChainEntry] = Field(default_factory=list)
    count: int = 0
    has_more: bool = False
    next_cursor: str | None = None

    total: int | None = None
    """Total is the number of entries in the whole meta-chain. Omitted only if the
    backing store cannot count.
    """


class VerifyInclusionRequest(_Base):
    """
    Request body for ``POST /v1/verify-inclusion``
    (``aggregation.VerifyInclusionRequest``) — public, no authentication or
    database access required server-side; verification is computed
    entirely from this body.
    """

    leaf_hash: str
    """Hex-encoded SHA-256 hash of the leaf being proven."""

    root: str
    """Hex-encoded SHA-256 Merkle root to verify against."""

    steps: list[ProofStep] = Field(default_factory=list)
    """Ordered Merkle authentication path from leaf to root."""

    leaf_index: int | None = None
    """0-based position of the leaf in the padded tree. Informational
    only — not used in the verification computation."""

    leaf_count: int | None = None
    """Total number of leaf positions (real + padding). Informational
    only — not used in the verification computation."""

    pad_count: int | None = None
    """Number of padding leaves added to reach the minimum of 16.
    Informational only — not used in the verification computation."""

    tree_depth: int | None = None
    """Number of levels above the leaf level. Informational only — not
    used in the verification computation."""


class VerifyInclusionResponse(_Base):
    """
    Response body from ``POST /v1/verify-inclusion``
    (``aggregation.VerifyInclusionResponse``).
    """

    valid: bool
    """``True`` iff the supplied proof cryptographically demonstrates that
    ``leaf_hash`` is included in ``root`` via the given ``steps``."""


class AdminAggregateRequest(_Base):
    """
    Request body for ``POST /v1/admin/aggregate``
    (``aggregation.AdminAggregateRequest``). Owner role required.

    Both fields are optional but must be supplied together — omit both to
    let the server compute the window.
    """

    window_start: str | None = None
    """Inclusive start of the evidence collection window (RFC 3339 UTC).
    Required if ``window_end`` is set."""

    window_end: str | None = None
    """Exclusive end of the evidence collection window (RFC 3339 UTC).
    Required if ``window_start`` is set."""


class AdminAggregateResponse(_Base):
    """
    Response body from ``POST /v1/admin/aggregate``
    (``aggregation.AdminAggregateResponse``) — the resulting aggregation
    batch.
    """

    aggregation_id: str
    """Server-generated UUID of the ``aggregation_results`` row."""

    batch_number: int
    """Monotonically increasing sequence number for this batch."""

    window_start: str | None = None
    """Inclusive start of the aggregated window (UTC)."""

    window_end: str | None = None
    """Exclusive end of the aggregated window (UTC)."""

    merkle_root: str
    """Hex-encoded SHA-256 Merkle root of the padded tree."""

    leaf_count: int
    """Total number of leaves (real + padding) in the tree."""

    tenant_count: int
    """Number of distinct tenants with evidence in the window."""

    ts_timestamp: str | None = None
    """Time attested by the RFC 3161 TSA."""

    tsa_name: str | None = None
    """Common Name / Organisation of the TSA signing certificate."""


# ─────────────────────────────────────────────────────────────────────────────
# Audio Validator — POST /v1/validate-audio, POST /v1/audio-reconciliation
# ─────────────────────────────────────────────────────────────────────────────

class AudioCallContext(_Base):
    """Per-call metadata for :class:`ValidateAudioRequest` (``audio.CallContext``)."""

    language: str | None = None
    """BCP-47 language tag of the call (e.g. ``"nl"``, ``"de"``)."""

    disclosure_delivered: bool = False
    """``True`` when the AI disclosure has already been delivered to the
    called party."""


class ValidateAudioRequest(_Base):
    """
    Request body for ``POST /v1/validate-audio``
    (``audio.ValidateAudioRequest``).
    """

    call_id: str
    """Uniquely identifies the call/session."""

    turn_number: int
    """1-based turn number within this call."""

    audio_data: str
    """Base64-encoded raw PCM audio bytes."""

    audio_format: AudioFormat = "pcm_s16le_16000"
    """Encoding of ``audio_data``: ``"pcm_s16le_16000"``, ``"wav"``, or
    ``"mp3"``."""

    configuration_id: UUID | None = None
    """Tenant configuration to apply."""

    config_seal_hash: str | None = None
    """The call's config seal. Optional: when omitted the call's pinned seal is
    used; required only for speech in a call with no pinned seal."""

    asr_provider: str | None = None
    """Overrides the default ASR provider for this request."""

    segmentation_method: str | None = None
    """Segmentation strategy: ``"asr_first"`` (default) or
    ``"prosodic_first"``."""

    parallel_asr: bool | None = None
    """Enables multi-model ASR for this request."""

    call_context: AudioCallContext | None = None
    """Per-call metadata (language, disclosure state)."""


class AudioParallelASRSummary(_Base):
    """Multi-model ASR agreement summary (``audio.ParallelASRSummary``),
    present on a segment only when ``parallel_asr`` was requested."""

    model_count: int = 0
    """Number of ASR models that responded."""

    converged: bool = False
    """``True`` when every model produced the same transcription text."""

    confidence_spread: float = 0.0
    """Difference between the highest and lowest model confidence scores."""


class AudioTextCheckResult(_Base):
    """Per-check compliance detail for one audio segment (``audio.TextCheckResult``)."""

    check_id: str = ""
    """Stable identifier of the check (e.g. ``"blocklist_scan"``)."""

    verdict: str = ""
    """``ALLOW``, ``MODIFY``, or ``BLOCK``."""

    reason: str = ""
    """Short, PII-free explanation of the verdict."""


class AudioSegmentResult(_Base):
    """One element of :class:`ValidateAudioResponse`'s ``segments``
    (``audio.AudioSegmentResult``)."""

    segment_index: int = 0
    """0-based position of this segment in the call turn."""

    verdict: str = ""
    """Compliance verdict: ``ALLOW``, ``MODIFY``, or ``BLOCK``."""

    action: str = ""
    """Audio routing decision: ``"forward"``, ``"substitute"``, or ``"block"``."""

    audio_hash: str = ""
    """SHA-256 hex digest of the raw audio segment bytes."""

    text_hash: str = ""
    """SHA-256 hex digest of ``transcribed_text``."""

    transcribed_text: str = ""
    """ASR output for operator visibility. **Never** stored in evidence
    events — only ``text_hash`` travels the chain (SEC-031)."""

    asr_confidence: float = 0.0
    """ASR model's confidence score for this segment."""

    asr_model_id: str = ""
    """Identifies which ASR model produced the transcription."""

    segmentation_method: str = ""
    """Segmentation strategy used for this segment."""

    check_results: list[AudioTextCheckResult] = Field(default_factory=list)
    """Per-check compliance detail."""

    parallel_asr_result: AudioParallelASRSummary | None = None
    """Populated only when parallel ASR was used for this segment."""

    transcription_status: TranscriptionStatus | None = None
    """``"transcribed"``, or ``"no_speech"`` when the ASR produced no text
    (the segment is ALLOW but nothing was checked)."""


class AudioComplianceReceipt(_Base):
    """Compliance receipt for an audio validation call
    (``audio.ComplianceReceipt``)."""

    verdict: str = ""
    """Aggregated compliance verdict."""

    input_hash: str = ""
    """SHA-256 of the original audio bytes."""

    output_hash: str = ""
    """SHA-256 of the forwarded or substituted audio bytes."""

    text_hash: str = ""
    """SHA-256 of the ASR transcription."""

    evidence_hash: str = ""
    """Last evidence chain hash for this call."""

    asr_confidence: float = 0.0
    """Confidence score from the first (or primary) segment."""

    config_version: int = 0
    """Version of the tenant configuration applied."""

    policy_version: str = ""
    """Policy schema version."""

    segmentation_method: str = ""
    """Segmentation strategy used."""

    signature: str = ""
    """HMAC-SHA256 of all above fields."""

    call_id: str = ""
    """The call this receipt belongs to."""

    turn_number: int = 0
    """The turn this audio segment was validated for."""

    timestamp: str = ""
    """Server time of the validation (RFC 3339, UTC)."""

    config_seal_hash: str = ""
    """Config seal pinned to the call."""

    auth_mechanism: str = ""
    """Integrity-tag mechanism (e.g. ``"hmac-sha256"``)."""

    receipt_format_version: str | None = None
    """Audio receipt format version; absent on receipts issued before the
    format was versioned."""


class ValidateAudioResponse(_Base):
    """
    Response body from ``POST /v1/validate-audio``
    (``audio.ValidateAudioResponse``).
    """

    verdict: str = ""
    """Aggregated verdict across all segments."""

    segments: list[AudioSegmentResult] = Field(default_factory=list)
    """Per-segment validation results."""

    receipt: AudioComplianceReceipt | None = None
    """Compliance receipt for this validation."""

    fail_open: bool = False
    """``True`` when the validator timed out for any segment."""

    evidence_event_id: str = ""
    """UUID of the evidence event written for this request."""

    evidence_hash: str = ""
    """SHA-256 hex digest of the evidence event."""

    evidence_write_status: str = ""
    """Whether the evidence chain write succeeded: ``"success"``,
    ``"failed"``, or ``"skipped"``."""


class AudioReconciliationRequest(_Base):
    """
    Request body for ``POST /v1/audio-reconciliation``
    (``audio.AudioReconciliationRequest``).
    """

    call_id: UUID
    """Uniquely identifies the completed call to reconcile. Obtain this
    from ``GET /v1/calls`` (:meth:`AudactClient.list_calls`)."""

    audio_data: str
    """Base64-encoded audio bytes (PCM, WAV, or MP3)."""

    audio_format: AudioFormat = "wav"
    """Encoding of ``audio_data``: ``"pcm_s16le_16000"``, ``"wav"``, or
    ``"mp3"``."""

    configuration_id: UUID | None = None
    """Optional UUID of the agent configuration whose ``asr_config``
    should be used for ASR key resolution. When absent, falls back to the
    tenant's first active configuration with an ``asr_config`` entry, or
    the global ASR client when none is configured. Obtain this from
    ``GET /v1/configurations`` (:meth:`AudactClient.list_configurations`)."""

    asr_provider: str | None = None
    """Overrides the default ASR provider for this request."""

    language: str | None = None
    """BCP-47 language tag (e.g. ``"nl"``, ``"de"``, ``"es"``)."""


class AudioSegmentReconciliationResult(_Base):
    """One element of :class:`AudioReconciliationResponse`'s
    ``segment_results`` (``reconciliation.SegmentReconciliationResult``)."""

    sequence_number: int = 0
    """Corresponds to the segment's ``turn_number``."""

    status: str = ""
    """One of ``"matched"``, ``"mismatched"``, or ``"unvalidated"``."""

    mismatch_classification: str | None = None
    """Populated only when ``status == "mismatched"``."""

    transcript_hash: str = ""
    """Server-computed SHA-256 of the transcript segment text."""

    validated_hash: str = ""
    """SHA-256 stored in the validation event, if present."""


class AudioReconciliationResponse(_Base):
    """
    Response body from ``POST /v1/audio-reconciliation``
    (``audio.AudioReconciliationResponse``).
    """

    call_id: str = ""
    """UUID of the reconciled call."""

    total_segments: int = 0
    """Number of agent segments processed (unaffected by
    ``segment_results`` pagination — always the full count)."""

    matched_segments: int = 0
    """Count of segments with status ``"matched"`` (always the full count)."""

    mismatched_segments: int = 0
    """Count of segments with status ``"mismatched"`` (always the full count)."""

    unvalidated_segments: int = 0
    """Count of segments with status ``"unvalidated"`` (always the full count)."""

    has_more: bool = False
    """``True`` when additional ``segment_results`` exist beyond this page.
    Fetch the next page with ``after_sequence=<sequence_number of the last
    entry in segment_results>``."""

    asr_confidence: float = 0.0
    """Overall ASR confidence score."""

    asr_model_id: str = ""
    """Identifies which ASR model produced the transcription."""

    segment_results: list[AudioSegmentReconciliationResult] = Field(default_factory=list)
    """Per-segment outcomes ordered by ``sequence_number``. Paginated —
    see ``limit``/``after_sequence``."""


# ─────────────────────────────────────────────────────────────────────────────
# Auth — POST /v1/auth/exchange-key, POST /v1/auth/refresh
# ─────────────────────────────────────────────────────────────────────────────

class ExchangeKeyResponse(_Base):
    """
    Response body from ``POST /v1/auth/exchange-key``
    (``tenant.ExchangeKeyResponse``).

    The server also sets a long-lived refresh token as an httpOnly,
    ``SameSite=Strict`` cookie scoped to ``/v1/auth`` — never present in
    this body. ``AudactClient`` retains cookies across requests on its
    underlying ``httpx.AsyncClient`` instance, so a subsequent
    ``client.auth.refresh_token()`` call on the *same* client instance
    automatically presents that cookie.
    """

    access_token: str
    """Short-lived JWT (15 min) for dashboard API calls. Send it as
    ``Authorization: Bearer <access_token>``."""

    token_type: str = "Bearer"
    """Always ``"Bearer"``."""

    expires_in: int = 900
    """Access token lifetime in seconds (900 = 15 min)."""


class RefreshTokenResponse(_Base):
    """
    Response body from ``POST /v1/auth/refresh``
    (``tenant.RefreshResponse``). Rotates both the access token (returned
    here) and the refresh-token cookie (single-use rotation).
    """

    access_token: str
    """New short-lived JWT (15 min)."""

    token_type: str = "Bearer"
    """Always ``"Bearer"``."""

    expires_in: int = 900
    """Access token lifetime in seconds (900 = 15 min)."""


# ─────────────────────────────────────────────────────────────────────────────
# PII vault — identifiers on call create, shred/decrypt/identities.
# ─────────────────────────────────────────────────────────────────────────────

class CallIdentifier(_Base):
    """A tenant-supplied subject identifier on call create.

    ``hash`` is ``audact.pii.client_hash(type, value)``; never send plaintext."""

    type: Literal["name", "email", "phone"]
    hash: str


class PIIShredRequest(_Base):
    """Body for ``POST /v1/pii/shred``."""

    identifier_type: Literal["name", "email", "phone"]
    identifier_hash: str


class PIIShredResponse(_Base):
    """Response of the shred endpoints."""

    shred_id: UUID | None = None
    identities_shredded: int = 0
    calls_affected: int = 0
    shredded_at: datetime | None = None


class PIIIdentity(_Base):
    """One identity linked to a call."""

    identity_id: UUID
    type: PIIIdentityType | None = None
    role: PIIIdentityRole | None = None
    source: PIIIdentitySource | None = None
    linked_at: datetime | None = None
    shredded_at: datetime | None = None

    _blank_enums = _blank_to_none("type", "role", "source")


class PIIIdentitiesResponse(_Base):
    """Response of ``GET /v1/calls/{call_id}/pii/identities``."""

    identities: list[PIIIdentity] = Field(default_factory=list)


class PIILinkIdentityResponse(_Base):
    """Response of ``POST /v1/calls/{call_id}/pii/identities``."""

    identity_id: UUID


class PIIDecryptResponse(_Base):
    """Response of ``POST /v1/calls/{call_id}/pii/decrypt``."""

    text: str | None = None
    texts: list[str] | None = None
    decrypted: int = 0
    erased: int = 0


class PIIShredRecord(_Base):
    """One row of the erasure log (``GET /v1/pii/shreds``). Contains no PII."""

    shred_id: UUID
    scope: PIIShredScope | None = None
    """``identity`` (one identity everywhere), ``call`` (one call) or ``tenant``."""
    identity_type: PIIIdentityType | None = None
    """``name``/``email``/``phone``/``call``; set for ``identity`` scope."""
    call_id: UUID | None = None
    """Set for ``call`` scope."""
    identities_shredded: int = 0
    calls_affected: int = 0
    actor_key_id: str = ""
    """API key that requested the erasure."""
    impersonator_id: str | None = None
    """Org user who acted on the tenant's behalf, if any."""
    impersonator_org_id: str | None = None
    """That user's organisation."""
    shredded_at: datetime | None = None

    _blank_enums = _blank_to_none("identity_type", "scope")


class PIIShredsResponse(_Base):
    """Response of ``GET /v1/pii/shreds``."""

    shreds: list[PIIShredRecord] = Field(default_factory=list)
    next_cursor: str | None = None


class PIISettingsHistoryEntry(_Base):
    """One change of the tenant's PII encryption switch."""

    encryption_enabled: bool = False
    """The value the switch was set to."""
    actor_key_id: str = ""
    """API key that made the change."""
    impersonator_id: str | None = None
    """Org user who acted on the tenant's behalf, if any."""
    impersonator_org_id: str | None = None
    """That user's organisation."""
    configurations_resealed: int = 0
    """Configurations re-sealed because the switch is part of the seal."""
    changed_at: datetime | None = None


class PIISettingsResponse(_Base):
    """Response of ``GET``/``PUT /v1/pii/settings`` (tenant-management)."""

    encryption_enabled: bool = False
    changed_at: datetime | None = None
    changed_by: str | None = None
    history: list[PIISettingsHistoryEntry] = Field(default_factory=list)
    configurations_resealed: int | None = None


class PIIExemption(_Base):
    """An exemption entry; the value is never stored, only a lookup prefix."""

    exempt_type: PIIExemptType | None = None
    lookup_prefix: str = ""
    created_at: datetime | None = None

    _blank_enums = _blank_to_none("exempt_type")


class PIIExemptionsResponse(_Base):
    """Response of ``GET /v1/pii/exemptions``."""

    exemptions: list[PIIExemption] = Field(default_factory=list)
    auto_exempt_dids: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Drift-fix models — definitions that had no named SDK model
# ─────────────────────────────────────────────────────────────────────────────


class EventComplianceReceipt(_Base):
    """Compliance receipt summary attached to a reconstructed evidence event."""

    config_seal_hash: str | None = None
    event_id: str | None = None
    issued_at: str | None = None
    verdict: str | None = None


class ReconstructedEvent(_Base):
    """One event of a ``GET /v1/reconstruct/{call_id}`` response."""

    call_id: str | None = None
    compliance_receipt: EventComplianceReceipt | None = None
    config_seal_hash: str | None = None
    data: Any = None
    """Event payload (the spec types it as a JSON string; objects are accepted)."""
    event_id: str | None = None
    event_type: str | None = None
    hash: str | None = None
    previous_hash: str | None = None
    sequence: int | None = None
    tenant_id: str | None = None
    timestamp: str | None = None


class ResolvedConfigVersion(_Base):
    """Configuration version resolved from a ``config_seal_hash``.

    Carries the settings the version ran with, read from the immutable
    configuration version: what a call pinned to this version was judged
    by, even after the configuration has been edited. The same version is
    returned by :meth:`AudactClient.get_configuration_version`. Key and
    secret references (multi-candidate, ASR, upstream LLM) are not included.
    """

    auto_handover_config: dict[str, Any] | None = None
    config_id: str | None = None
    config_seal_hash: str | None = None
    created_at: str | None = None
    deleted_at: str | None = None
    name: str | None = None
    pii_encryption: bool | None = None
    tenant_id: str | None = None
    updated_at: str | None = None
    version: int | None = None

    countries: list[str] | None = None
    """ISO 3166-1 alpha-2 codes the version applied to."""
    validator_modes: dict[str, Any] | None = None
    """Per-check mode map (``"enforce"`` | ``"shadow"`` | ``"off"``)."""
    blocklist_patterns: list[dict[str, Any]] | None = None
    """Blocklist patterns (terms, severity)."""
    pricing_bands: dict[str, Any] | None = None
    """Permitted price ranges per category."""
    consent_config: dict[str, Any] | None = None
    """Consent-gating rules."""
    prompt_confidentiality_config: PromptConfidentialityConfig | None = None
    """Prompt-confidentiality configuration."""
    disclosure_texts: dict[str, Any] | None = None
    """AI-disclosure texts per language."""
    fallback_response: dict[str, Any] | None = None
    """Line spoken in place of a blocked turn."""
    output_constraint: dict[str, Any] | None = None
    """Output length/truncation policy."""
    end_call: EndCallConfig | None = None
    """End-call policy."""
    voicemail: VoicemailConfig | None = None
    """Voicemail policy."""
    begin_message: str | None = None
    """The agent's opening line."""
    llm_provider: str | None = None
    """Provider of the sealed agent LLM."""
    llm_model: str | None = None
    """Model of the sealed agent LLM."""


class PIICallShredRequest(_Base):
    """Request body for shredding the identities of a call."""

    identity_ids: list[str] | None = None


class PIIDecryptRequest(_Base):
    """Request body for ``POST /v1/pii/decrypt`` (``text`` or ``texts``)."""

    text: str | None = None
    texts: list[str] | None = None


class PIIExemptionRequest(_Base):
    """Request body for creating a PII exemption."""

    exempt_type: PIIExemptType
    identifier_hash: str


class PIILinkIdentityRequest(_Base):
    """Request body for linking an identity to a call."""

    identifier_hash: str
    identifier_type: PIILinkIdentityType


class EvaluationContext(_Base):
    """Evaluation context echoed by the policy engine."""

    call_time: str | None = None
    call_within_permitted_hours: bool | None = None
    consent_status: str | None = None
    contact_type: str | None = None
    direction: CallDirection | None = None
    dnc_registered: bool | None = None
    existing_relationship: bool | None = None

    _blank_enums = _blank_to_none("direction")


class PolicyDNCAdapterDoc(_Base):
    """A do-not-call adapter entry of a policy file."""

    description: str | None = None
    id: str | None = None
    required: bool | None = None
    type: str | None = None


class PolicyHolidayDoc(_Base):
    """A holiday entry of a policy file."""

    date: str | None = None
    name: str | None = None


class PolicyJurisdictionCascadeDoc(_Base):
    """A jurisdiction parent/children cascade entry."""

    children: list[str] | None = None
    parent: str | None = None


class PolicyQuietWindowDoc(_Base):
    """A quiet-hours window of a policy file."""

    days: list[str] | None = None
    end: str | None = None
    label: str | None = None
    start: str | None = None
    timezone: str | None = None


class PolicyRuleConditionDoc(_Base):
    """A rule condition of a use case."""

    field: str | None = None
    operator: str | None = None
    value: Any = None
    """Comparison value: a ``str``, an ``int``/``float``, a ``bool`` or a ``list[str]``."""


class PolicyUseCaseDoc(_Base):
    """A use-case entry of a policy file."""

    block_reasons: list[str] | None = None
    conditions: list[PolicyRuleConditionDoc] | None = None
    default_verdict: str | None = None
    description: str | None = None
    id: str | None = None


class PolicyFileResponse(_Base):
    """Response of the policy-file endpoint for one country."""

    country: str | None = None
    dnc_adapters: list[PolicyDNCAdapterDoc] | None = None
    holidays: list[PolicyHolidayDoc] | None = None
    jurisdiction_cascade: list[PolicyJurisdictionCascadeDoc] | None = None
    quiet_hours: list[PolicyQuietWindowDoc] | None = None
    updated_at: str | None = None
    use_cases: list[PolicyUseCaseDoc] | None = None
    version: str | None = None


class AudactValidationMeta(_Base):
    """``audact_validation`` block of a chat-completion response."""

    call_id: str | None = None
    fail_open: bool | None = None
    modified: bool | None = None
    verdict: str | None = None


class ToolCallFunction(_Base):
    """Function part of a chat tool call."""

    arguments: str | None = None
    name: str | None = None


class ChatToolCall(_Base):
    """A tool call inside a chat message."""

    function: ToolCallFunction | None = None
    id: str | None = None
    index: int | None = None
    type: str | None = None


class ToolFunctionSchema(_Base):
    """Function schema of a chat tool definition."""

    description: str | None = None
    name: str | None = None
    parameters: Any = None
    """JSON-schema object (the spec types it as raw JSON)."""


class ChatToolDefinition(_Base):
    """A tool offered to the model in a chat-completion request."""

    function: ToolFunctionSchema | None = None
    type: str | None = None


class ChatMessage(_Base):
    """A chat message."""

    content: str | None = None
    name: str | None = None
    role: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ChatToolCall] | None = None


class ChatCompletionChoice(_Base):
    """One choice of a chat-completion response."""

    finish_reason: str | None = None
    index: int | None = None
    message: ChatMessage | None = None


class UsageStats(_Base):
    """Token usage of a chat completion."""

    completion_tokens: int | None = None
    prompt_tokens: int | None = None
    total_tokens: int | None = None


class ChatCompletionRequest(_Base):
    """Request body of the LLM proxy chat-completions endpoint."""

    max_completion_tokens: int | None = None
    max_tokens: int | None = None
    messages: list[ChatMessage] | None = None
    model: str | None = None
    parallel_tool_calls: bool | None = None
    reasoning_effort: str | None = None
    stream: bool | None = None
    temperature: float | None = None
    tool_choice: Any = None
    tools: list[ChatToolDefinition] | None = None


class ChatCompletionResponse(_Base):
    """Response of the LLM proxy chat-completions endpoint."""

    audact_validation: AudactValidationMeta | None = None
    choices: list[ChatCompletionChoice] | None = None
    created: int | None = None
    id: str | None = None
    model: str | None = None
    object: str | None = None
    usage: UsageStats | None = None


class CrossTurnFinding(_Base):
    """An advisory semantic cross-turn contradiction finding."""

    confidence: CrossTurnConfidence | None = None
    kind: CrossTurnKind | None = None
    summary: str | None = None
    turn_a: int | None = None
    turn_b: int | None = None


class EndCallSilenceConfig(_Base):
    """Silence trigger of the end-call policy."""

    max_reprompts: int | None = None
    reprompt_text: dict[str, str] | None = None
    window_ms: int | None = None


class EndCallConfig(_Base):
    """Agent-initiated end-of-call policy (an empty object means off)."""

    closing_line: dict[str, str] | None = None
    silence: EndCallSilenceConfig | None = None
    trigger_phrases: dict[str, list[str]] | None = None


class ExtractionField(_Base):
    """One field of a post-call extraction schema."""

    description: str | None = None
    format: Literal["date-time"] | None = None
    name: str | None = None
    type: ExtractionFieldType | None = None
    values: list[str] | None = None


class PostCallExtractionConfig(_Base):
    """Custom post-call extraction schema."""

    enabled: bool | None = None
    fields: list[ExtractionField] | None = None


class PostCallSummaryConfig(_Base):
    """Post-call summary policy."""

    dispositions: list[str] | None = None
    enabled: bool | None = None


class VoicemailConfig(_Base):
    """Voicemail-detection handling policy."""

    beep_hz: int | None = None
    branch: VoicemailBranch | None = None
    decision_window_ms: int | None = None
    enabled: bool | None = None
    message: dict[str, str] | None = None

    _blank_enums = _blank_to_none("branch")


class PIISettingsPutRequest(_Base):
    """Request body for ``PUT /v1/tenants/{tenant_id}/pii-settings``."""

    encryption_enabled: bool


# ─────────────────────────────────────────────────────────────────────────────
# Compliance events, erased keysets and platform admin keys
# ─────────────────────────────────────────────────────────────────────────────

ComplianceEventSubtype = Literal[
    "validation_completed",
    "violation_detected",
    "fail_open",
    "policy_triggered",
    "audit_logged",
    "receipt_issued",
]
"""``event_subtype`` filter of ``GET /v1/compliance/events``. ``policy_triggered``,
``audit_logged`` and ``receipt_issued`` are webhook-only and always yield an empty page."""

ComplianceEventLogSubtype = Literal["validation_completed", "violation_detected", "fail_open"]
"""``event_subtype`` of a returned compliance event: the only three the event log projects."""

ComplianceVerdict = Literal["ALLOW", "MODIFY", "BLOCK"]
"""Aggregate pipeline verdict of a compliance event."""

ComplianceSeverity = Literal["critical", "high", "medium", "low"]
"""Severity band of a compliance event's check."""


class PIIErasedKeysetsResponse(_Base):
    """Response of ``GET /v1/calls/{call_id}/pii/erased-keysets``."""

    erased_keyset_ids: list[str]
    """Subset of the requested keyset ids that include a crypto-shredded identity. Tokens sealed
    under these keysets can never be decrypted again (they decrypt to ``[ERASED_<TYPE>]``)."""


class ComplianceEvent(_Base):
    """One entry of the compliance event log: every validation result, ALLOW included.

    Only ``agent_id``, ``event_subtype`` and ``timestamp`` are always present; the server omits
    the other fields when empty or unrecorded (an ALLOW turn has no check, severity or detail).
    """

    _blank_enums = _blank_to_none("severity", "verdict")

    agent_id: str
    """Not yet populated; resolve the agent via ``GET /v1/calls/{call_id}``."""
    call_id: str | None = None
    """The call this event belongs to."""
    check_id: str | None = None
    """Highest-severity non-ALLOW check for a violation; absent otherwise."""
    compliance_score: float | None = None
    """Composite compliance score in [0, 1] when recorded."""
    detail: str | None = None
    """The check's structural reason (no PII); absent for non-violations."""
    event_subtype: ComplianceEventLogSubtype
    """Event subtype."""
    severity: ComplianceSeverity | None = None
    """Severity band of ``check_id``; absent for non-violations."""
    timestamp: str
    """Server-generated UTC time of the event (RFC 3339)."""
    turn_sequence: int | None = None
    """Turn number within the call, when recorded."""
    verdict: ComplianceVerdict | None = None
    """Aggregate pipeline verdict: ALLOW, MODIFY, or BLOCK."""


class ListComplianceEventsResponse(_Base):
    """Response of ``GET /v1/compliance/events``."""

    events: list[ComplianceEvent]
    """Page of events ordered by timestamp DESC; empty when nothing matches."""
    has_more: bool
    """True when further pages exist."""
    next_cursor: str | None = None
    """Opaque cursor for the next page; omitted when ``has_more`` is false."""
    total: int
    """Number of events matching the filters across all pages."""


class AdminKey(_Base):
    """A platform admin signing key (public half only)."""

    active: bool
    added_at: str
    disabled_at: str | None = None
    kid: str
    operator: str


class AddAdminKeyRequest(_Base):
    """Request body for ``POST /v1/platform/admin-keys``."""

    kid: str
    """Identifies the key; tokens signed with it carry this kid."""
    public_key_pem: str
    """PEM-wrapped PKIX Ed25519 PUBLIC key."""
    operator: str | None = None
    """Who the key belongs to. Defaults to the calling token's actor."""


class ListAdminKeysResponse(_Base):
    """Response of ``GET /v1/platform/admin-keys``."""

    admin_keys: list[AdminKey]


class AdminKeyResponse(_Base):
    """Response of the add / disable admin-key operations."""

    admin_key: AdminKey


class PlatformTenant(_Base):
    """A tenant as seen by a platform admin (``org.PlatformTenantSummary``)."""

    created_at: str | None = None
    deleted_at: str | None = None
    """Set when the tenant is soft-deleted; ``None`` for a live tenant."""
    initialized_at: str | None = None
    name: str | None = None
    organization_id: str | None = None
    """``None`` for a tenant that belongs to no organization."""
    plan: str | None = None
    status: str | None = None
    """``"active"`` or ``"disabled"``."""
    tenant_id: str | None = None


class PlatformListTenantsResponse(_Base):
    """Response of ``GET /v1/platform/tenants`` (``org.platformTenantListResponse``)."""

    tenants: list[PlatformTenant] = Field(default_factory=list)
    next_cursor: str | None = None
    """Empty or absent on the last page."""


class PlatformTenantResponse(_Base):
    """Response of the get / soft-delete / restore tenant operations."""

    tenant: PlatformTenant | None = None


class PlatformSoftDeleteTenantRequest(_Base):
    """Request body for ``POST /v1/platform/tenants/{tenant_id}/soft-delete``."""

    reason: str
    """Audit-log reason, 1-500 characters after trimming. Do not put PII in it."""


class PlatformRestoreTenantRequest(_Base):
    """Request body for ``POST /v1/platform/tenants/{tenant_id}/restore``."""

    reason: str | None = None
    """Optional audit-log reason, at most 500 characters."""


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge bases (RAG) — ``client.knowledge_bases`` — tenant-management (8085)
# ─────────────────────────────────────────────────────────────────────────────

class KnowledgeBase(_Base):
    """A knowledge base (``kb.KBResponse``)."""

    kb_id: UUID
    """Server-generated UUID primary key."""

    tenant_id: UUID | None = None
    """The owning tenant's UUID."""

    name: str = ""
    """Human-readable label."""

    auto_refresh: bool = False
    """When ``True``, sources are re-ingested on a 24h schedule."""

    robots_policy: KBRobotsPolicy | None = None
    """Crawler robots.txt handling: ``"honor"`` or ``"override"``."""

    created_at: datetime | None = None
    """Server-generated UTC creation timestamp."""

    updated_at: datetime | None = None
    """Server-generated UTC last-mutation timestamp."""


class ListKnowledgeBasesResponse(_Base):
    """
    Raw response body from ``GET /v1/knowledge-bases`` (``kb.ListKBsResponse``).

    :meth:`KnowledgeBasesClient.list_knowledge_bases` reshapes this into the
    shared :class:`Page` convention.
    """

    items: list[KnowledgeBase] = Field(default_factory=list)
    """The current page, ordered by ``kb_id`` ascending."""

    has_more: bool = False
    """``True`` when additional pages exist."""

    next_cursor: str | None = None
    """Cursor to pass as ``cursor`` for the next page; empty when ``has_more`` is ``False``."""


class CreateKnowledgeBaseRequest(_Base):
    """Request body for ``POST /v1/knowledge-bases`` (``kb.CreateKBRequest``)."""

    name: str
    """Human-readable label. Required, 1–200 characters."""

    auto_refresh: bool | None = None
    """Enable scheduled 24h re-ingestion. Server default ``False``."""

    robots_policy: KBRobotsPolicy | None = None
    """``"honor"`` (server default) or ``"override"``; any other value is rejected."""


class PatchKnowledgeBaseRequest(_Base):
    """Request body for ``PATCH /v1/knowledge-bases/{kb_id}`` (``kb.PatchKBRequest``).
    Only supplied fields change."""

    name: str | None = None
    """New display name, 1–200 characters. Display-only; retrieval is unaffected."""

    auto_refresh: bool | None = None
    """Enable or disable scheduled 24h re-ingestion."""


class KBCrawlCoverage(_Base):
    """Page coverage of a source's latest successful ingestion
    (``kb.CrawlCoverageResponse``). A single page, file or text source
    reports 1 discovered / 1 stored."""

    discovered: int = 0
    """Pages found."""

    stored: int = 0
    """Pages whose content was stored."""

    excluded: int = 0
    """Pages skipped by the knowledge base's exclusion list."""

    failed: int = 0
    """Pages that could not be fetched or ingested."""


class KBSource(_Base):
    """A source (URL, file or text) of a knowledge base (``kb.SourceResponse``)."""

    source_id: UUID
    """Stable UUID primary key."""

    tenant_id: UUID | None = None
    """The owning tenant's UUID."""

    kb_id: UUID | None = None
    """The parent knowledge base's UUID."""

    type: KBSourceType | None = None
    """``"url"``, ``"file"`` or ``"text"``."""

    uri: str = ""
    """The URL (url sources), the original filename (file sources), or empty (text)."""

    title: str = ""
    """Optional human-readable name; empty when unset."""

    content_preview: str = ""
    """Short server-truncated snippet of a text source's content; never the full content."""

    status: KBSourceStatus | None = None
    """``"pending"``, ``"processing"``, ``"ready"`` or ``"failed"``."""

    error: str = ""
    """The most recent ingest error, or empty on success."""

    ingest_version: int = 0
    """Current ingest version; incremented on each re-ingest."""

    config: dict[str, Any] | None = None
    """Per-source configuration (crawl flags, etc.)."""

    chunk_count: int | None = None
    """Chunks stored by the latest successful ingestion; ``None`` until a
    first ingestion has finished."""

    crawl_coverage: KBCrawlCoverage | None = None
    """Page coverage of the latest successful ingestion; ``None`` until
    a first ingestion has finished."""

    last_ingested_at: datetime | None = None
    """When the latest successful ingestion finished; ``None`` until a
    first ingestion has finished."""

    created_at: datetime | None = None
    """Server-generated UTC creation timestamp."""

    updated_at: datetime | None = None
    """Server-generated UTC last-mutation timestamp."""

    _blank_enums = _blank_to_none("type", "status")


class ListKBSourcesResponse(_Base):
    """Response body from ``GET /v1/knowledge-bases/{kb_id}/sources``
    (``kb.ListSourcesResponse``)."""

    items: list[KBSource] = Field(default_factory=list)
    """All sources of the knowledge base, ordered by ``created_at`` ascending."""

    total: int = 0
    """Number of items returned."""


class AddKBSourceRequest(_Base):
    """
    JSON request body for ``POST /v1/knowledge-bases/{kb_id}/sources``
    (``kb.AddSourceRequest``) — url and text sources.

    File sources are uploaded as multipart with
    :meth:`KnowledgeBasesClient.upload_kb_source_file`; the server rejects
    ``type="file"`` in a JSON body.
    """

    type: Literal["url", "text"]
    """``"url"`` or ``"text"``. Required. Upload files with
    :meth:`KnowledgeBasesClient.upload_kb_source_file`."""

    url: str | None = None
    """http(s) URL to crawl. Required when ``type`` is ``"url"``."""

    content: str | None = None
    """Raw text content. Required when ``type`` is ``"text"``."""

    title: str | None = None
    """Optional human-readable name, at most 200 characters."""

    config: dict[str, Any] | None = None
    """Optional per-source flags, e.g. ``{"auto_crawl": True, "depth": 2}`` for url sources."""


class PatchKBSourceRequest(_Base):
    """Request body for ``PATCH /v1/knowledge-bases/{kb_id}/sources/{source_id}``
    (``kb.PatchSourceRequest``). At least one field is required."""

    title: str | None = None
    """New human-readable name, 1–200 characters."""

    content: str | None = None
    """Replacement text (text sources only, up to 1 MiB); triggers a re-ingest."""


class KBAgentLink(_Base):
    """A link between a knowledge base and an agent, with its retrieval tuning
    (``kb.AgentLinkResponse``)."""

    kb_id: UUID
    """The knowledge base's UUID."""

    agent_id: UUID
    """The linked agent's UUID."""

    tenant_id: UUID | None = None
    """The owning tenant's UUID."""

    top_k: int | None = None
    """Maximum chunks returned per retrieval query (1–10)."""

    similarity_threshold: float | None = None
    """Minimum cosine similarity score (0.0–1.0)."""

    retrieval_instruction: str = ""
    """Optional system-prompt fragment injected before retrieved passages."""

    created_at: datetime | None = None
    """Server-generated UTC creation timestamp."""


class ListKBAgentLinksResponse(_Base):
    """Response body from ``GET /v1/knowledge-bases/{kb_id}/agents`` and
    ``GET /v1/knowledge-bases/agent-links`` (``kb.ListLinksResponse``)."""

    items: list[KBAgentLink] = Field(default_factory=list)
    """The links, ordered by ``created_at`` ascending."""

    total: int = 0
    """Number of links returned."""


class PutKBAgentLinkRequest(_Base):
    """Request body for ``PUT /v1/knowledge-bases/{kb_id}/agents/{agent_id}``
    (``kb.PutLinkRequest``). Omitted fields take the server defaults."""

    top_k: int | None = None
    """1–10; server default 3."""

    similarity_threshold: float | None = None
    """0.0–1.0; server default 0.6."""

    retrieval_instruction: str | None = None
    """At most 500 characters; server default ``""``."""


class PatchKBAgentLinkRequest(_Base):
    """Request body for ``PATCH /v1/knowledge-bases/{kb_id}/agents/{agent_id}``
    (``kb.PatchLinkRequest``). Only supplied fields change."""

    top_k: int | None = None
    """1–10."""

    similarity_threshold: float | None = None
    """0.0–1.0."""

    retrieval_instruction: str | None = None
    """At most 500 characters."""


class KBCrawlExclusion(_Base):
    """A crawl exclusion rule of a knowledge base (``kb.CrawlExclusionResponse``)."""

    id: UUID
    """Stable UUID primary key."""

    kb_id: UUID | None = None
    """The knowledge base the rule belongs to."""

    tenant_id: UUID | None = None
    """The owning tenant's UUID."""

    crawl_path: str | None = None
    """Path-prefix exclusion, or ``None`` for an exact-URL rule."""

    url: str | None = None
    """Exact URL excluded, or ``None`` for a path-prefix rule."""

    created_at: datetime | None = None
    """Server-generated UTC creation timestamp."""


class ListKBExclusionsResponse(_Base):
    """Response body from ``GET /v1/knowledge-bases/{kb_id}/exclusions``
    (``kb.ListExclusionsResponse``)."""

    items: list[KBCrawlExclusion] = Field(default_factory=list)
    """All rules of the knowledge base, ordered by ``created_at`` ascending."""

    total: int = 0
    """Number of rules returned."""


class AddKBExclusionRequest(_Base):
    """Request body for ``POST /v1/knowledge-bases/{kb_id}/exclusions``
    (``kb.AddExclusionRequest``). Set exactly one of the two fields."""

    crawl_path: str | None = None
    """Path prefix to skip (e.g. ``"/admin"``), at most 200 characters."""

    url: str | None = None
    """Exact URL to skip, at most 200 characters."""


class KBTestHarnessTurn(_Base):
    """One conversation turn of a retrieval test (``kb.TestHarnessTurn``)."""

    role: KBRetrievalTurnRole
    """One of ``"user"``, ``"assistant"`` or ``"system"``; any other value is rejected."""

    content: str
    """Text content of the turn."""


class KBTestRetrievalRequest(_Base):
    """Request body for ``POST /v1/knowledge-bases/{kb_id}/test-retrieval``
    (``kb.TestRetrievalRequest``). Set exactly one of ``question`` and ``turns``."""

    question: str | None = None
    """Shorthand for a single user turn."""

    turns: list[KBTestHarnessTurn] | None = None
    """Multi-turn conversation history."""

    top_k: int | None = None
    """Ad-hoc override of the chunk count, 1–10; server default 3."""

    threshold: float | None = None
    """Ad-hoc similarity threshold override, 0.0–1.0; server default 0.0 (return all)."""


class KBTestHarnessHit(_Base):
    """One retrieved chunk of a retrieval test (``kb.TestHarnessHit``)."""

    text: str = ""
    """The raw chunk content."""

    source_id: UUID | None = None
    """The source that produced the chunk."""

    kb_id: UUID | None = None
    """The knowledge base the chunk belongs to."""

    similarity: float = 0.0
    """Cosine similarity score in ``[0, 1]``."""


class KBTestRetrievalResponse(_Base):
    """Response body from ``POST /v1/knowledge-bases/{kb_id}/test-retrieval``
    (``kb.TestRetrievalResponse``)."""

    condensed_query: str = ""
    """The search query produced by the condensation stage; may be empty."""

    hits: list[KBTestHarnessHit] = Field(default_factory=list)
    """Chunks that passed the threshold, sorted by similarity descending."""

    empty: bool = False
    """``True`` when nothing met the threshold — a 200, not an error."""
