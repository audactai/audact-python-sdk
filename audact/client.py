"""
Audact SDK — async Python client.

``AudactClient`` is the single entry-point for all Audact service APIs.
It is designed to be used as an async context manager so that the
underlying httpx connection pool is closed cleanly on exit.

Usage example::

    async with AudactClient(api_key="aud_live_...") as client:
        result = await client.validate(
            call_id=uuid.uuid4(),
            tenant_id=my_tenant_id,
            config_id=my_config_id,
            turn=1,
            content="Hello, this is an automated message.",
        )
        print(result.verdict)  # "ALLOW" | "BLOCK" | "MODIFY"

All service base URLs default to ``http://localhost:<port>`` for local
development.  Override them via constructor keyword arguments or
environment variables when running against a real deployment.

Environment variable overrides
-------------------------------
``AUDACT_API_KEY``              – API key (``Authorization: Bearer …``).
``AUDACT_BASE_URL``             – One host for every service (e.g.
                                   ``https://api.audact.ai``); a trailing
                                   ``/v1`` is stripped. Per-service URLs
                                   (kwarg or env) take precedence.
``AUDACT_POLICY_ENGINE_URL``    – Policy Engine base URL (default :8081).
``AUDACT_VALIDATOR_URL``        – Validator base URL (default :8082).
``AUDACT_EVIDENCE_LAYER_URL``   – Evidence Layer base URL (default :8083).
``AUDACT_LLM_PROXY_URL``        – LLM Proxy base URL (default :8084).
``AUDACT_TENANT_MANAGEMENT_URL``– Tenant Management base URL (default :8085).
``AUDACT_AUDIO_VALIDATOR_URL``  – Audio Validator base URL (default :8086).
``AUDACT_AGGREGATOR_URL``       – Aggregator base URL (default :8087).
``AUDACT_VOICE_GATEWAY_URL``    – Voice Gateway base URL (default :8088).
``AUDACT_AGENT_WORKER_URL``     – Agent Worker base URL (default :8089).
``AUDACT_ORG_MANAGEMENT_URL``   – Org Management base URL (default :8092).
``AUDACT_ORG_TOKEN``            – OrgBearer JWT for ``client.org.*`` calls.
``AUDACT_PLATFORM_TOKEN``       – PlatformBearer token for
                                   ``client.platform.orgs.*`` calls (the SDK
                                   never mints this token itself).
"""

from __future__ import annotations

import asyncio
import json as _json
import os
import warnings
from collections.abc import AsyncGenerator, Mapping, Sequence
from typing import IO, Any, cast
from urllib.parse import quote
from uuid import UUID

import httpx
import yaml

from .exceptions import (
    AudactAPIError,
    AudactAuthError,
    AudactConnectionError,
    AudactForbiddenError,
    AudactNotFoundError,
    AudactRateLimitError,
    AudactTimeoutError,
)
from .models import (
    AddAdminKeyRequest,
    AddKBExclusionRequest,
    AddKBSourceRequest,
    AdminAggregateRequest,
    AdminAggregateResponse,
    AdminKeyResponse,
    AdmissionURLResponse,
    Agent,
    APIKey,
    Article50Report,
    AssignNumberRequest,
    AttachToolRequest,
    AttachToolResponse,
    AudioReconciliationRequest,
    AudioReconciliationResponse,
    AvailableNumber,
    BrowserCallRequest,
    BrowserCallResponse,
    ByoConfig,
    BYOConnection,
    C2PAManifest,
    C2PAManifestListItem,
    C2PAManifestListResponse,
    CalcomEventType,
    CallDetail,
    CallingHoursCheckResponse,
    CallRecord,
    CallStatusResponse,
    CallSummary,
    ComplianceEventSubtype,
    ComplianceSeverity,
    ComplianceVerdict,
    Configuration,
    ConfirmDeliveryRequest,
    Connection,
    CreateAgentRequest,
    CreateAgentResponse,
    CreateBYOConnectionRequest,
    CreateConfigurationRequest,
    CreateConnectionRequest,
    CreateDispatchRuleRequest,
    CreateDispatchRuleResponse,
    CreateInboundTrunkRequest,
    CreateInboundTrunkResponse,
    CreateKnowledgeBaseRequest,
    CreateKYCDocumentSetRequest,
    CreateNumberOrderRequest,
    CreateNumberRequest,
    CreateOutboundTrunkRequest,
    CreateOutboundTrunkResponse,
    CreateTenantRequest,
    CreateTenantResponse,
    CreateToolRequest,
    CreateVoiceResponse,
    CreateWebhookRequest,
    CreateWebhookResponse,
    DeleteAgentResponse,
    DeleteConnectionResponse,
    DeleteToolResponse,
    DetachToolResponse,
    EvaluateRequest,
    EvaluateResponse,
    ExchangeKeyResponse,
    FinalizeScoreRequest,
    FinalizeScoreResponse,
    GenerateKeyRequest,
    GenerateKeyResponse,
    GetChainResponse,
    GetReceiptResponse,
    HandoverRequest,
    HandoverResponse,
    HandoverStateResponse,
    HangupResponse,
    HealthResponse,
    InboundCallRequest,
    InboundCallResponse,
    KBAgentLink,
    KBCrawlExclusion,
    KBSource,
    KBTestRetrievalRequest,
    KBTestRetrievalResponse,
    KnowledgeBase,
    KYCDocument,
    KYCDocumentSet,
    KYCRequirement,
    ListAdminKeysResponse,
    ListAgentsResponse,
    ListAgentToolsResponse,
    ListAvailableNumbersResponse,
    ListBYOConnectionsResponse,
    ListCallsResponse,
    ListComplianceEventsResponse,
    ListConfigurationsResponse,
    ListConnectionsResponse,
    ListEventTypesResponse,
    ListKBAgentLinksResponse,
    ListKBExclusionsResponse,
    ListKBSourcesResponse,
    ListKeysResponse,
    ListKnowledgeBasesResponse,
    ListKYCDocumentSetsResponse,
    ListKYCDocumentsResponse,
    ListKYCRequirementsResponse,
    ListNumberOrdersResponse,
    ListNumbersResponse,
    ListOrgTenantsResponse,
    ListRoutesResponse,
    ListToolsResponse,
    ListTrunksResponse,
    ListViolationsResponse,
    ListWebhookDeliveriesResponse,
    ListWebhookEventTypesResponse,
    ListWebhooksResponse,
    MetaChainEntry,
    MetaChainResponse,
    NumberOrder,
    OAuthStartResponse,
    Organization,
    OrgCreateTenantRequest,
    OrgCreateTenantResponse,
    OrgGetTenantResponse,
    OrgImpersonateTenantResponse,
    OrgInitializeTenantResponse,
    OrgIssueKeyRequest,
    OrgIssueKeyResponse,
    OrgKYCPatchRequest,
    OrgKYCResponse,
    OrgLoginRequest,
    OrgLoginResponse,
    OrgProfileResponse,
    OrgRefreshResponse,
    OrgSignupRequest,
    OrgSignupResponse,
    OrgTenantActionResponse,
    OrgTenantSummary,
    OrgUpdateProfileRequest,
    OutboundCallRequest,
    OutboundCallResponse,
    Page,
    PatchAgentRequest,
    PatchKBAgentLinkRequest,
    PatchKBSourceRequest,
    PatchKnowledgeBaseRequest,
    PhoneNumber,
    PIIDecryptResponse,
    PIIErasedKeysetsResponse,
    PIIExemption,
    PIIExemptionsResponse,
    PIIIdentitiesResponse,
    PIILinkIdentityResponse,
    PIISettingsResponse,
    PIIShredRequest,
    PIIShredResponse,
    PIIShredsResponse,
    PipelineStatusResponse,
    PlatformBundle,
    PlatformChangeOrgAdminEmailRequest,
    PlatformFindOrgAdminsResponse,
    PlatformImportResult,
    PlatformListOrganizationsResponse,
    PlatformListTenantsResponse,
    PlatformOrgAdminResponse,
    PlatformOrganizationResponse,
    PlatformRejectOrganizationRequest,
    PlatformResetOrgAdminPasswordRequest,
    PlatformResetOrgAdminPasswordResponse,
    PlatformRestoreTenantRequest,
    PlatformSoftDeleteTenantRequest,
    PlatformTenantResponse,
    PostEventRequest,
    PostEventResponse,
    ProcessConfirmationResult,
    ProofListResponse,
    ProofResponse,
    ProofSummary,
    PutKBAgentLinkRequest,
    RateLimitInfo,
    ReconcileTranscriptRequest,
    ReconcileTranscriptResponse,
    ReconstructResponse,
    RecordingResponse,
    RefreshTokenResponse,
    ResendWebhookDeliveryResponse,
    RotateDEKResponse,
    RotateWebhookSecretResponse,
    SetAdmissionURLRequest,
    SetNumberTrunkRequest,
    Tenant,
    TestConnectionResponse,
    TestToolResponse,
    ToolConfig,
    TransferRequest,
    TransferResponse,
    TransferSessionResponse,
    TransferStateResponse,
    TTSProvider,
    TurnDeliveryStatus,
    UpdateAgentRequest,
    UpdateBYOConnectionRequest,
    UpdateConfigurationRequest,
    UpdateTenantRequest,
    UpdateToolRequest,
    UpdateWebhookRequest,
    UsageRecord,
    ValidateAudioRequest,
    ValidateAudioResponse,
    ValidateRequest,
    ValidateResponse,
    VerifyChainResponse,
    VerifyInclusionRequest,
    VerifyInclusionResponse,
    ViolationRecord,
    Voice,
    VoiceProvider,
    WebhookEndpoint,
    WebhookEventSchema,
    WebhookSecretStatus,
    WebhookTestPingResponse,
    WsTicketResponse,
)

# A bundle may be supplied to import_tenant() as an already-typed PlatformBundle,
# a plain mapping (e.g. loaded from a hand-edited YAML file with PyYAML), raw
# text/bytes (e.g. the exact output of export_tenant()/export_agent()), or an
# open, readable binary file handle so large bundles can be streamed to the
# server without ever being fully buffered in SDK memory.
BundleInput = PlatformBundle | Mapping[str, Any] | str | bytes | IO[bytes]

__all__ = [
    "AudactClient",
    "AggregationClient",
    "AgentsClient",
    "CallsClient",
    "IntegrationsClient",
    "OrgClient",
    "ToolsClient",
    "WebhooksClient",
    "verify_webhook_signature",
]

# ─────────────────────────────────────────────────────────────────────────────
# Default service base URLs (can be overridden)
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_POLICY_ENGINE_URL = "http://localhost:8081"
_DEFAULT_VALIDATOR_URL = "http://localhost:8082"
_DEFAULT_EVIDENCE_LAYER_URL = "http://localhost:8083"
_DEFAULT_LLM_PROXY_URL = "http://localhost:8084"
_DEFAULT_TENANT_MANAGEMENT_URL = "http://localhost:8085"
_DEFAULT_AUDIO_VALIDATOR_URL = "http://localhost:8086"
_DEFAULT_AGGREGATOR_URL = "http://localhost:8087"
_DEFAULT_VOICE_GATEWAY_URL = "http://localhost:8088"
_DEFAULT_AGENT_WORKER_URL = "http://localhost:8089"
_DEFAULT_ORG_MANAGEMENT_URL = "http://localhost:8092"

# Default request timeout in seconds.
_DEFAULT_TIMEOUT = 30.0

# Opt-in retry backoff bounds — used only when
# Retry-After is absent from the response.
_RETRY_BACKOFF_BASE = 0.5  # seconds
_RETRY_BACKOFF_MAX = 8.0  # seconds

# Number order statuses that will never transition further — used by
# wait_for_order() to know when to stop polling.
_TERMINAL_ORDER_STATUSES = frozenset({"success", "failure", "cancelled"})


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _resolve_service_url(
    kwarg: str | None, env_key: str, default: str, base_url: str | None
) -> str:
    """Resolve one service URL.

    Order: ``x_url=`` kwarg, ``AUDACT_X_URL``, ``base_url=`` kwarg,
    ``AUDACT_BASE_URL``, then the localhost default.
    """
    explicit = kwarg or os.environ.get(env_key)
    if explicit:
        return explicit.rstrip("/")
    shared = base_url or os.environ.get("AUDACT_BASE_URL")
    if shared:
        return _normalize_base_url(shared)
    return default


def _normalize_base_url(url: str) -> str:
    """Strip a trailing ``/``, then a trailing ``/v1``, then ``/``."""
    url = url.rstrip("/")
    if url.endswith("/v1"):
        url = url[: -len("/v1")]
    return url.rstrip("/")


# ─────────────────────────────────────────────────────────────────────────────
# HTTP error mapping
# ─────────────────────────────────────────────────────────────────────────────

# Response headers read alongside/at parity with the server: the API sets
# Retry-After on errors and the X-RateLimit-* triplet on rate-limited routes.
# Header names are case-insensitive on the wire — httpx.Headers already
# normalizes lookups — but the literal casing here matches what the API
# actually writes.
_REQUEST_ID_HEADER = "X-Request-ID"
_RETRY_AFTER_HEADER = "Retry-After"
_RATE_LIMIT_LIMIT_HEADER = "X-RateLimit-Limit"
_RATE_LIMIT_REMAINING_HEADER = "X-RateLimit-Remaining"
_RATE_LIMIT_RESET_HEADER = "X-RateLimit-Reset"


def _parse_int_header(value: str | None) -> int | None:
    """Parse an integer header value, tolerating absence or non-numeric junk."""
    if value is None:
        return None
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return None


def _parse_rate_limit_headers(headers: httpx.Headers) -> RateLimitInfo | None:
    """
    Extract the ``X-RateLimit-Limit``/``-Remaining``/``-Reset`` triplet from
    a response's headers.

    Returns ``None`` when none of the three headers are present, so callers
    can distinguish "server didn't send rate-limit info" from "sent zeros".
    """
    limit = headers.get(_RATE_LIMIT_LIMIT_HEADER)
    remaining = headers.get(_RATE_LIMIT_REMAINING_HEADER)
    reset = headers.get(_RATE_LIMIT_RESET_HEADER)
    if limit is None and remaining is None and reset is None:
        return None
    return RateLimitInfo(
        limit=_parse_int_header(limit),
        remaining=_parse_int_header(remaining),
        reset=_parse_int_header(reset),
    )


def _raise_for_status(response: httpx.Response) -> None:
    """
    Raise an appropriate :class:`~audact.exceptions.AudactAPIError` subclass
    for any non-2xx response.

    The server writes every error as a **nested**
    envelope, ``{"error": {"code", "message", "hint", "details",
    "request_id"}}`` — this is parsed first; a flat top-level
    ``{"code": ..., "message": ...}`` body is accepted as a forward-compat
    fallback only when no ``error`` object is present. ``request_id`` is
    also read from the ``X-Request-ID`` response header when the body omits
    it (mirrors the TS SDK's ``base.ts``). On a ``429``, ``Retry-After`` and
    the ``X-RateLimit-*`` triplet are attached to
    the raised :class:`~audact.exceptions.AudactRateLimitError`.
    """
    if response.is_success:
        return

    # Try to extract the structured error body — nested {"error": {...}}
    # first (the real wire shape), flat top-level as a fallback.
    code = "UNKNOWN"
    message = response.text or f"HTTP {response.status_code}"
    details: dict[str, Any] = {}
    hint: str | None = None
    request_id: str | None = response.headers.get(_REQUEST_ID_HEADER)

    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        body = None

    if isinstance(body, dict):
        error_obj = body.get("error")
        source = error_obj if isinstance(error_obj, dict) else body
        code = source.get("code", code)
        message = source.get("message", message)
        details = source.get("details") or {}
        hint = source.get("hint") or hint
        request_id = source.get("request_id") or request_id

    status = response.status_code
    kwargs: dict[str, Any] = dict(
        status_code=status,
        code=code,
        details=details,
        hint=hint,
        request_id=request_id,
    )

    if status == 401:
        raise AudactAuthError(message, **kwargs)
    if status == 403:
        raise AudactForbiddenError(message, **kwargs)
    if status == 404:
        raise AudactNotFoundError(message, **kwargs)
    if status == 429:
        raise AudactRateLimitError(
            message,
            retry_after=_parse_int_header(response.headers.get(_RETRY_AFTER_HEADER)),
            rate_limit=_parse_rate_limit_headers(response.headers),
            **kwargs,
        )

    raise AudactAPIError(message, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# AudactClient
# ─────────────────────────────────────────────────────────────────────────────

class AudactClient:
    """
    Async client for all Audact service APIs.

    Parameters
    ----------
    api_key:
        Bearer token used for authenticated endpoints.  Falls back to
        the ``AUDACT_API_KEY`` environment variable when not supplied.
    base_url:
        One host for every service (e.g. ``https://api.audact.ai``). A
        trailing ``/`` and ``/v1`` are stripped. Falls back to
        ``AUDACT_BASE_URL``. Precedence per service: ``x_url=`` kwarg,
        ``AUDACT_X_URL`` env, ``base_url``, ``AUDACT_BASE_URL``, then the
        localhost default.
    policy_engine_url:
        Base URL for the Policy Engine service.
    validator_url:
        Base URL for the Validator service.
    evidence_layer_url:
        Base URL for the Evidence Layer service.
    llm_proxy_url:
        Base URL for the LLM Proxy service.
    tenant_management_url:
        Base URL for the Tenant Management service.
    voice_gateway_url:
        Base URL for the Voice Gateway service (KYC documents & number
        provisioning).
    audio_validator_url:
        Base URL for the Audio Validator service.
    aggregator_url:
        Base URL for the Aggregator service.
    agent_worker_url:
        Base URL for the Agent Worker service (agents/voices/tools/
        integrations).
    org_management_url:
        Base URL for the Org Management service (``client.org.*`` /
        ``client.platform.orgs.*``).
    org_token:
        Optional OrgBearer JWT used instead of ``api_key`` for
        ``client.org.*`` calls.  Falls back to the ``AUDACT_ORG_TOKEN``
        environment variable.  Obtained from an org ``login()`` response (or
        supplied directly) and held in-memory only — never written to disk.
    platform_token:
        Optional pre-minted Ed25519 PlatformBearer token used instead of
        ``api_key`` for ``client.platform.orgs.*`` calls.  Falls back to the
        ``AUDACT_PLATFORM_TOKEN`` environment variable.  The SDK never mints
        this token itself; the caller must supply one obtained out of band.
    timeout:
        Default request timeout in seconds.
    max_retries:
        Maximum number of **opt-in** retry attempts for idempotent ``GET``
        requests that fail with ``429``/``5xx``.
        Defaults to ``0`` (off) — retries are never performed unless the
        caller explicitly raises this. Retries honor the ``Retry-After``
        response header when present, fall back to a small capped
        exponential backoff otherwise, and are **never** attempted against
        the Validator (any URL under ``validator_url``, e.g.
        ``/v1/validate``) regardless of method or status code.
    httpx_client:
        Optional pre-configured :class:`httpx.AsyncClient` to use instead of
        creating a new one.  Useful for testing with ``respx`` or for sharing
        a client across multiple ``AudactClient`` instances.

    Attributes
    ----------
    calls:
        :class:`CallsClient` sub-client exposing the SIP calls surface
        (``client.calls.*`` — outbound/inbound/browser calls, hangup,
        status, handovers, transfers; voice-gateway 8088).
    webhooks:
        :class:`WebhooksClient` sub-client exposing the webhook
        subscriptions surface (``client.webhooks.*`` — CRUD, test,
        deliveries, resend, event-types/schemas, secret status/rotate;
        tenant-management 8085).
    agents:
        :class:`AgentsClient` sub-client exposing the agent-worker voice
        agent management surface (``client.agents.*`` — agent CRUD +
        duplicate, TTS voice catalog CRUD, pipeline-load status;
        agent-worker 8089). More attribute sub-clients (``client.tools``,
        etc.) land in later tasks.
    knowledge_bases:
        :class:`KnowledgeBasesClient` sub-client exposing the knowledge-base
        (RAG) surface (``client.knowledge_bases.*`` — KB CRUD, sources incl.
        file upload and re-ingest, agent links + retrieval tuning, crawl
        exclusions, retrieval test harness; tenant-management 8085).
    org:
        :class:`OrgClient` sub-client exposing the org self-service
        surface (``client.org.*`` — signup/login/refresh/logout, profile,
        KYC, and the org-tenant lifecycle; org-management 8092,
        **OrgBearer**). Unlike every other sub-client, this one
        authenticates with the in-memory ``org_token`` (set at
        construction, via ``AUDACT_ORG_TOKEN``, or by
        ``login()``/``signup()``/``refresh()``) instead of the tenant
        ``api_key``; falls back to ``api_key`` when unset.
    platform:
        :class:`PlatformClient` sub-client. ``client.platform.orgs``
        exposes the platform-admin org-management surface
        (``client.platform.orgs.*`` — organizations list/verify/reject,
        org_admin find/change-email/reset-password; org-management 8092,
        **PlatformBearer**). Authenticates with the in-memory
        ``platform_token`` (set at construction, via
        ``AUDACT_PLATFORM_TOKEN``, or ``set_platform_token()``); falls back
        to ``api_key`` when unset. The SDK never mints this token — the
        caller must supply one obtained out of band. The pre-existing
        cross-tenant YAML export/import methods
        (:meth:`export_tenant`/:meth:`export_agent`/:meth:`import_tenant`)
        remain flat methods on :class:`AudactClient` taking an explicit
        ``platform_token`` argument per call — a distinct surface
        (Tenant Management 8085) predating this sub-client.
    aggregation:
        :class:`AggregationClient` sub-client exposing the Merkle
        aggregation surface (``client.aggregation.*`` — per-tenant proof
        list/get, the public meta-chain, public inclusion verification, and
        the owner-only manual aggregation trigger; aggregator 8087).
        ``get_metachain``/``verify_inclusion`` are public endpoints (no
        authentication required by the server).
    audio:
        :class:`AudioClient` sub-client exposing the Audio Validator
        surface (``client.audio.*`` — per-turn audio compliance
        validation and post-call audio-to-transcript reconciliation;
        audio-validator 8086).
    auth:
        :class:`AuthClient` sub-client exposing the Tenant Management
        API-key ↔ JWT session bridge (``client.auth.*`` —
        ``exchange_key``/``refresh_token``; tenant-management 8085,
        ``/v1/auth/*``). Built for dashboard-style UIs that want a
        short-lived JWT instead of sending the raw tenant ``api_key`` on
        every request. The refresh token is an httpOnly cookie the
        underlying ``httpx.AsyncClient`` retains automatically across
        calls on the same client instance.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        policy_engine_url: str | None = None,
        validator_url: str | None = None,
        evidence_layer_url: str | None = None,
        llm_proxy_url: str | None = None,
        tenant_management_url: str | None = None,
        voice_gateway_url: str | None = None,
        audio_validator_url: str | None = None,
        aggregator_url: str | None = None,
        agent_worker_url: str | None = None,
        org_management_url: str | None = None,
        org_token: str | None = None,
        platform_token: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = 0,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key: str = (
            api_key
            or _env("AUDACT_API_KEY", "")
        )

        self._policy_engine_url: str = _resolve_service_url(
            policy_engine_url, "AUDACT_POLICY_ENGINE_URL", _DEFAULT_POLICY_ENGINE_URL, base_url
        )

        self._validator_url: str = _resolve_service_url(
            validator_url, "AUDACT_VALIDATOR_URL", _DEFAULT_VALIDATOR_URL, base_url
        )

        self._evidence_layer_url: str = _resolve_service_url(
            evidence_layer_url, "AUDACT_EVIDENCE_LAYER_URL", _DEFAULT_EVIDENCE_LAYER_URL, base_url
        )

        self._llm_proxy_url: str = _resolve_service_url(
            llm_proxy_url, "AUDACT_LLM_PROXY_URL", _DEFAULT_LLM_PROXY_URL, base_url
        )

        self._tenant_management_url: str = _resolve_service_url(
            tenant_management_url,
            "AUDACT_TENANT_MANAGEMENT_URL",
            _DEFAULT_TENANT_MANAGEMENT_URL,
            base_url,
        )

        self._voice_gateway_url: str = _resolve_service_url(
            voice_gateway_url, "AUDACT_VOICE_GATEWAY_URL", _DEFAULT_VOICE_GATEWAY_URL, base_url
        )

        self._audio_validator_url: str = _resolve_service_url(
            audio_validator_url,
            "AUDACT_AUDIO_VALIDATOR_URL",
            _DEFAULT_AUDIO_VALIDATOR_URL,
            base_url,
        )

        self._aggregator_url: str = _resolve_service_url(
            aggregator_url, "AUDACT_AGGREGATOR_URL", _DEFAULT_AGGREGATOR_URL, base_url
        )

        self._agent_worker_url: str = _resolve_service_url(
            agent_worker_url, "AUDACT_AGENT_WORKER_URL", _DEFAULT_AGENT_WORKER_URL, base_url
        )

        self._org_management_url: str = _resolve_service_url(
            org_management_url, "AUDACT_ORG_MANAGEMENT_URL", _DEFAULT_ORG_MANAGEMENT_URL, base_url
        )

        # OrgBearer / PlatformBearer tokens: in-memory only, never
        # persisted to disk. Stored as "" (not None) internally so the
        # env-fallback chain mirrors api_key's; exposed publicly as None
        # when unset via the org_token/platform_token properties below.
        self._org_token: str = org_token or _env("AUDACT_ORG_TOKEN", "")
        self._platform_token: str = platform_token or _env("AUDACT_PLATFORM_TOKEN", "")

        self._timeout = timeout

        # Opt-in retry-with-backoff: off by default.
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self._max_retries = max_retries

        # Most recent X-RateLimit-* snapshot seen on any response (success or
        # error) — the ticket asks that these be readable on successful
        # responses too, not just on a 429 error object.
        self._last_rate_limit: RateLimitInfo | None = None

        self._owned_client = httpx_client is None

        if httpx_client is not None:
            self._http = httpx_client
        else:
            self._http = httpx.AsyncClient(timeout=self._timeout)

        # Attribute sub-clients: each holds a reference back to this client
        # so it reuses `_request`, auth headers, and base URLs rather than
        # duplicating transport logic.
        self.calls = CallsClient(self)
        self.webhooks = WebhooksClient(self)
        self.agents = AgentsClient(self)
        self.tools = ToolsClient(self)
        self.knowledge_bases = KnowledgeBasesClient(self)
        self.integrations = IntegrationsClient(self)
        self.org = OrgClient(self)
        self.pii = PIIClient(self)
        self.platform = PlatformClient(self)
        self.aggregation = AggregationClient(self)
        self.audio = AudioClient(self)
        self.auth = AuthClient(self)

    # ── Context-manager protocol ──────────────────────────────────────────────

    async def __aenter__(self) -> AudactClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client and release connection resources."""
        if self._owned_client:
            await self._http.aclose()

    # ── OrgBearer / PlatformBearer token state ──────────────────────────

    @property
    def org_token(self) -> str | None:
        """The in-memory OrgBearer JWT used by ``client.org.*`` calls, or ``None`` if unset."""
        return self._org_token or None

    def set_org_token(self, token: str | None) -> None:
        """
        Set (or, with ``None``, clear) the in-memory OrgBearer token.

        Called by ``client.org.login()``/``client.org.refresh()`` once they
        exist; may also be called directly. Never written to disk.
        """
        self._org_token = token or ""

    @property
    def platform_token(self) -> str | None:
        """The in-memory PlatformBearer token for ``client.platform.orgs.*``; ``None`` if unset."""
        return self._platform_token or None

    def set_platform_token(self, token: str | None) -> None:
        """
        Set (or, with ``None``, clear) the in-memory PlatformBearer token.

        The SDK never mints this Ed25519 token itself — the caller must
        supply one obtained out of band (e.g. ``audact-admin auth --action
        org``).
        """
        self._platform_token = token or ""

    # ── Rate-limit snapshot ──────────────────────────────────────────────

    @property
    def last_rate_limit(self) -> RateLimitInfo | None:
        """
        The ``X-RateLimit-Limit``/``-Remaining``/``-Reset`` triplet from the
        most recently completed request, or ``None`` if no response has
        carried these headers yet. Updated on every ``_request()`` call —
        successful or not — so callers can inspect their remaining quota
        after an ordinary 2xx response, not only on a ``429`` error.
        """
        return self._last_rate_limit

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _auth_headers(self, *, auth_token: str | None = None) -> dict[str, str]:
        """
        Return the ``Authorization`` header dict for a request.

        ``auth_token``, when supplied (even as an empty string), is used
        verbatim instead of the client's default API key — this is how an
        OrgBearer/PlatformBearer-scoped sub-client sends its own bearer
        token (``self.org_token`` / ``self.platform_token``) rather than the
        tenant ``api_key``. When omitted (``None``), falls back to the API
        key configured on this client (``api_key=``/``AUDACT_API_KEY``).
        """
        token = auth_token if auth_token is not None else self._api_key
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    def _is_validator_request(self, url: str) -> bool:
        """
        ``True`` when ``url`` targets the Validator (e.g. ``/v1/validate``).

        Retries are never attempted against the Validator regardless of
        method or status code (40ms hard-deadline invariant) — this check is
        belt-and-suspenders since retries are already restricted to ``GET``
        and the Validator only exposes ``POST /v1/validate``.
        """
        return url.startswith(self._validator_url)

    def _should_retry(
        self, method: str, url: str, response: httpx.Response, attempt: int
    ) -> bool:
        """
        Decide whether a failed response should be retried: opt-in
        (``max_retries > 0``), only for idempotent
        ``GET`` requests, only on ``429``/``5xx``, and never against the
        Validator.
        """
        if self._max_retries <= 0 or attempt >= self._max_retries:
            return False
        if method.upper() != "GET":
            return False
        if self._is_validator_request(url):
            return False
        return response.status_code == 429 or response.status_code >= 500

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        """
        Compute the backoff delay before the next retry attempt.

        Honors the ``Retry-After`` response header (seconds) when present;
        otherwise falls back to a small capped exponential backoff.
        """
        retry_after = _parse_int_header(response.headers.get(_RETRY_AFTER_HEADER))
        if retry_after is not None:
            return max(float(retry_after), 0.0)
        backoff = _RETRY_BACKOFF_BASE * (2**attempt)
        return float(min(backoff, _RETRY_BACKOFF_MAX))

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: Any = None,
        content: bytes | AsyncGenerator[bytes, None] | None = None,
        files: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        params: Mapping[str, str | list[str]] | None = None,
        extra_headers: dict[str, str] | None = None,
        repeated_headers: Sequence[tuple[str, str]] | None = None,
        timeout: float | None = None,
        auth_token: str | None = None,
        idempotency_key: str | None = None,
    ) -> httpx.Response:
        """
        Execute an HTTP request, raise on non-2xx, and return the response.

        ``content`` (raw bytes or an open, readable binary file handle) and
        ``json`` are mutually exclusive, mirroring :meth:`httpx.AsyncClient.request`;
        pass ``content`` for a pre-serialized/streamed body (e.g. a platform
        bundle upload) instead of a JSON-serializable object.

        ``files`` (a mapping to the ``(filename, file_or_bytes, content_type)``
        tuples httpx expects) requests a ``multipart/form-data`` body — used by
        the KYC document upload/replace endpoints. ``data`` supplies the
        accompanying plain form fields (e.g. ``doc_type``). Neither is ever
        combined with ``json``/``content`` by any caller in this SDK. Callers
        must NOT set a ``Content-Type`` header themselves when passing
        ``files`` — httpx computes the multipart boundary and writes the
        header itself; setting it manually would produce a malformed body the
        server cannot parse.

        ``auth_token``, when supplied, is sent as the ``Authorization``
        bearer instead of the client's default ``api_key`` — this is how an
        OrgBearer/PlatformBearer-scoped sub-client authenticates (see
        :meth:`_auth_headers`). ``idempotency_key``, when supplied, is sent
        as the ``Idempotency-Key`` header — the single, uniform mechanism
        every POST-mutation method should use instead of building its own
        ad-hoc header dict.

        When ``max_retries`` (constructor kwarg, default ``0``/off) is
        positive, idempotent ``GET`` requests that fail with ``429``/``5xx``
        are retried with backoff (honoring ``Retry-After``) up to that many
        times — never against the Validator. See :meth:`_should_retry`.

        The ``X-RateLimit-*`` response headers, when present, are recorded
        on :attr:`last_rate_limit` after every attempt.

        All :class:`httpx.TimeoutException` and
        :class:`httpx.ConnectError` instances are wrapped in SDK-specific
        exception types so callers do not need to import httpx directly.
        """
        merged = {**self._auth_headers(auth_token=auth_token), **(extra_headers or {})}
        if idempotency_key:
            merged["Idempotency-Key"] = idempotency_key
        # repeated_headers carries headers that may legitimately appear more than
        # once on the wire (e.g. X-Audact-Set-Secret). httpx sends a list of
        # (name, value) tuples as repeated header LINES — which is what the
        # server reads via r.Header.Values(...). A plain dict cannot represent
        # duplicates, so when repeated headers are present we pass the whole set
        # as a tuple list instead.
        headers: dict[str, str] | list[tuple[str, str]]
        if repeated_headers:
            headers = [*merged.items(), *repeated_headers]
        else:
            headers = merged

        attempt = 0
        while True:
            try:
                response = await self._http.request(
                    method,
                    url,
                    json=json,
                    content=content,
                    files=files,
                    data=data,
                    params=params,
                    headers=headers,
                    timeout=timeout or self._timeout,
                )
            except httpx.TimeoutException as exc:
                raise AudactTimeoutError(
                    f"Request to {url} timed out after {timeout or self._timeout}s"
                ) from exc
            except httpx.ConnectError as exc:
                raise AudactConnectionError(f"Cannot connect to {url}: {exc}") from exc

            rate_limit = _parse_rate_limit_headers(response.headers)
            if rate_limit is not None:
                self._last_rate_limit = rate_limit

            if response.is_success:
                return response

            if self._should_retry(method, url, response, attempt):
                await asyncio.sleep(self._retry_delay(response, attempt))
                attempt += 1
                continue

            _raise_for_status(response)
            return response  # pragma: no cover - _raise_for_status always raises

    # ─────────────────────────────────────────────────────────────────────────
    # Policy Engine — POST /v1/evaluate, GET /v1/policies/{country}
    # ─────────────────────────────────────────────────────────────────────────

    async def evaluate(
        self,
        country: str,
        context: dict[str, Any],
    ) -> EvaluateResponse:
        """
        Evaluate a call against the country-specific compliance policy.

        This is a **stateless** call — no evidence events are written.

        Parameters
        ----------
        country:
            ISO 3166-1 alpha-2 country code (e.g. ``"NL"``).
        context:
            Mapping of call-level fields referenced by policy rules
            (e.g. ``{"dnc_registered": False, "consent_status": "granted"}``).

        Returns
        -------
        EvaluateResponse
            Contains ``verdict`` (``ALLOW`` or ``BLOCK``), ``reasons``,
            ``applicable_rules``, and ``policy_version``.
        """
        req = EvaluateRequest(country=country, context=context)
        url = f"{self._policy_engine_url}/v1/evaluate"
        response = await self._request(
            "POST",
            url,
            json=req.model_dump(),
        )
        return EvaluateResponse.model_validate(response.json())

    async def get_policy(self, country: str) -> dict[str, Any]:
        """
        Fetch the full policy document for a country.

        Parameters
        ----------
        country:
            ISO 3166-1 alpha-2 country code.

        Returns
        -------
        dict
            Raw policy document as returned by the server.
        """
        url = f"{self._policy_engine_url}/v1/policies/{country.upper()}"
        response = await self._request("GET", url)
        return cast(dict[str, Any], response.json())

    async def check_calling_hours(
        self,
        country: str,
        *,
        call_time: str | None = None,
    ) -> CallingHoursCheckResponse:
        """
        Check whether an outbound call is currently permitted for a
        jurisdiction under its quiet-hours/holiday rules.

        Calls ``GET /v1/calling-hours/check``. Task-oriented convenience
        endpoint so MCP/LLM callers can "check then act" instead of
        attempting a call and parsing a 403. Only reflects quiet-hours/
        holiday timing — it does **not** evaluate consent, DNC, or other
        per-call conditions; use :meth:`evaluate` for the full compliance
        verdict.

        Parameters
        ----------
        country:
            ISO 3166-1 alpha-2 country code (e.g. ``"NL"``).
        call_time:
            Optional RFC 3339 timestamp to check; defaults to the current
            server time (UTC) when omitted.

        Returns
        -------
        CallingHoursCheckResponse
            ``allowed`` plus, when blocked, ``reason``
            (``"quiet_hours"``/``"holiday"``) and ``next_permitted_at``.
        """
        params: dict[str, str] = {"country": country}
        if call_time is not None:
            params["call_time"] = call_time
        url = f"{self._policy_engine_url}/v1/calling-hours/check"
        response = await self._request("GET", url, params=params)
        return CallingHoursCheckResponse.model_validate(response.json())

    # ─────────────────────────────────────────────────────────────────────────
    # Validator — POST /v1/validate
    # ─────────────────────────────────────────────────────────────────────────

    async def validate(
        self,
        call_id: UUID,
        tenant_id: UUID,
        config_id: UUID,
        turn: int,
        content: str,
        *,
        previous_turns: list[dict[str, Any]] | None = None,
        disclosure_delivered: bool = False,
        config_seal_hash: str = "",
    ) -> ValidateResponse:
        """
        Validate a single conversation turn through the 7-check ACVF pipeline.

        The validator enforces a 40 ms hard deadline and will return
        ``fail_open=True`` if the pipeline cannot complete in time.

        Parameters
        ----------
        call_id:
            UUID identifying the call/session.
        tenant_id:
            UUID of the owning Audact tenant.
        config_id:
            UUID of the tenant configuration version to apply.
        turn:
            1-based sequential turn number.
        content:
            Text to validate for this turn.
        previous_turns:
            Optional history of prior turns, each a dict with keys
            ``turn``, ``content``, and ``verdict``.
        disclosure_delivered:
            Whether the AI disclosure has been delivered to the called party
            in a prior turn.  Defaults to ``False``.
        config_seal_hash:
            Optional config-identity seal (SHA-256 of RFC 8785 canonical
            JSON of the active tenant configuration), pinned at call start
            and carried by the proxy so the Validator can stamp the real
            seal without a hot-path Redis read. Empty when unknown.

        Returns
        -------
        ValidateResponse
            Contains the aggregated ``verdict``, ``content`` (possibly
            modified), ``fail_open`` flag, compliance receipt, and
            per-check results. Each entry in ``checks`` carries the
            per-check validator **mode marker** (``"enforce"``/``"shadow"``/
            ``"off"``) and shadow-mode observability fields.
        """
        from .models import ACVFContext, ACVFTurn, CallState

        turns = [
            ACVFTurn(**t) if not isinstance(t, ACVFTurn) else t
            for t in (previous_turns or [])
        ]
        ctx = ACVFContext(
            previous_turns=turns,
            call_state=CallState(disclosure_delivered=disclosure_delivered),
        )
        req = ValidateRequest(
            call_id=call_id,
            tenant_id=tenant_id,
            config_id=config_id,
            turn=turn,
            content=content,
            context=ctx,
            config_seal_hash=config_seal_hash,
        )
        url = f"{self._validator_url}/v1/validate"
        response = await self._request(
            "POST",
            url,
            json=req.model_dump(mode="json"),
        )
        return ValidateResponse.model_validate(response.json())

    async def finalize_call_score(
        self,
        call_id: UUID,
        *,
        agent_id: str = "",
        idempotency_key: str | None = None,
    ) -> FinalizeScoreResponse:
        """
        Finalize the aggregate compliance score for a completed call.

        .. deprecated::
            ``POST /v1/calls/{call_id}/finalize-score`` is an internal
            endpoint and is not routed on the public API. This method only
            works when ``validator_url`` points directly at a validator,
            which the public API does not expose. It will be removed in a
            future release.

        Calls ``POST /v1/calls/{call_id}/finalize-score``. Computes the
        composite compliance score across all recorded turns and emits a
        ``compliance.call_score_finalized`` webhook event.

        Parameters
        ----------
        call_id:
            UUID of the call to finalize.
        agent_id:
            Optional agent identifier to associate with the finalized score.
        idempotency_key:
            Optional ``Idempotency-Key`` header value.

        Returns
        -------
        FinalizeScoreResponse
            ``status`` is ``"finalized"`` (with ``composite_score`` and
            turn counters populated) or ``"skipped"`` (no turns recorded).
        """
        warnings.warn(
            "finalize_call_score is deprecated: POST /v1/calls/{call_id}/finalize-score "
            "is an internal endpoint and is not routed on the public API; "
            "it will be removed in a future release",
            DeprecationWarning,
            stacklevel=2,
        )
        req = FinalizeScoreRequest(agent_id=agent_id)
        url = f"{self._validator_url}/v1/calls/{call_id}/finalize-score"
        response = await self._request(
            "POST",
            url,
            json=req.model_dump(mode="json"),
            idempotency_key=idempotency_key,
        )
        return FinalizeScoreResponse.model_validate(response.json())

    # ─────────────────────────────────────────────────────────────────────────
    # Health — GET /v1/health
    # ─────────────────────────────────────────────────────────────────────────

    async def health(self) -> HealthResponse:
        """
        Check platform health.

        Calls ``GET /v1/health``. No authentication is required. Every
        Audact service exposes its own ``/v1/health``; this method calls
        the Validator's (the documented Audact API has
        a single aggregate ``healthCheck`` operation, and the Validator is
        the canonical instance for it, matching the shipped TypeScript SDK).

        Returns
        -------
        HealthResponse
            ``status`` (``"ok"``/``"degraded"``) plus a per-component
            (Redis, PostgreSQL, etc.) status breakdown.
        """
        url = f"{self._validator_url}/v1/health"
        response = await self._request("GET", url)
        return HealthResponse.model_validate(response.json())

    # ─────────────────────────────────────────────────────────────────────────
    # Evidence Layer — events & chains
    # ─────────────────────────────────────────────────────────────────────────

    async def post_event(
        self,
        call_id: UUID,
        tenant_id: UUID,
        event_type: str,
        data: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> PostEventResponse:
        """
        Append an evidence event to the immutable audit ledger.

        Parameters
        ----------
        call_id:
            UUID of the call this event belongs to.
        tenant_id:
            UUID of the owning Audact tenant.
        event_type:
            String categorisation for the event (e.g. ``"CALL_START"``).
        data:
            Optional arbitrary JSON payload for the event.
        idempotency_key:
            Optional ``Idempotency-Key`` header value.  Duplicate requests
            with the same key+body are deduplicated for 5 minutes.

        Returns
        -------
        PostEventResponse
            The hash receipt for the written event, including ``hash``,
            ``previous_hash``, and ``sequence``.
        """
        req = PostEventRequest(
            call_id=call_id,
            tenant_id=tenant_id,
            event_type=event_type,
            data=data,
        )
        url = f"{self._evidence_layer_url}/v1/events"
        response = await self._request(
            "POST",
            url,
            json=req.model_dump(mode="json"),
            idempotency_key=idempotency_key,
        )
        return PostEventResponse.model_validate(response.json())

    async def get_chain(self, call_id: UUID) -> GetChainResponse:
        """
        Retrieve the full evidence event chain for a call.

        Parameters
        ----------
        call_id:
            UUID of the call whose evidence chain to retrieve.

        Returns
        -------
        GetChainResponse
            Ordered list of all evidence events for the call.
        """
        url = f"{self._evidence_layer_url}/v1/chains/{call_id}"
        response = await self._request("GET", url)
        return GetChainResponse.model_validate(response.json())

    async def verify_chain(self, call_id: UUID) -> VerifyChainResponse:
        """
        Verify the cryptographic integrity of the evidence chain for a call.

        Parameters
        ----------
        call_id:
            UUID of the call to verify.

        Returns
        -------
        VerifyChainResponse
            Contains ``valid`` (bool), ``event_count``, and a ``message``
            describing any integrity violations found.
        """
        url = f"{self._evidence_layer_url}/v1/verify/{call_id}"
        response = await self._request("GET", url)
        return VerifyChainResponse.model_validate(response.json())

    async def reconstruct_chain(self, call_id: UUID) -> ReconstructResponse:
        """
        Reconstruct the evidence chain for a call (compliance audit path).

        Parameters
        ----------
        call_id:
            UUID of the call to reconstruct.

        Returns
        -------
        ReconstructResponse
            Full reconstructed event list with computed hashes.
        """
        url = f"{self._evidence_layer_url}/v1/reconstruct/{call_id}"
        response = await self._request("GET", url)
        return ReconstructResponse.model_validate(response.json())

    # ─────────────────────────────────────────────────────────────────────────
    # Evidence Layer completion — calls, violations, article50,
    # c2pa, receipts, delivery, reconciliation, verification.
    # ─────────────────────────────────────────────────────────────────────────

    async def list_calls(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        status: str | None = None,
        verdict: str | None = None,
        shadow: bool | None = None,
        country: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Page[CallRecord]:
        """
        List calls for the authenticated tenant, most recently started first.

        Calls ``GET /v1/calls``.

        Parameters
        ----------
        date_from, date_to:
            Inclusive/exclusive ``started_at`` bounds (RFC3339 or ``YYYY-MM-DD``).
        status:
            Call status filter: ``"active"``, ``"completed"``, ``"failed"``,
            or ``"abandoned"``.
        verdict:
            ``CHECK_RESULT`` verdict filter (e.g. ``"ALLOW"``, ``"BLOCK"``,
            ``"FAIL_OPEN"``).
        shadow:
            When ``True``, return only calls with at least one shadow-mode
            detection. Shadow never changes the verdict, so this is separate
            from ``verdict``.
        country:
            Country filter (matches ``metadata.country``).
        cursor:
            Opaque keyset pagination cursor from a previous page's
            ``next_cursor`` (cursor pagination convention).
        limit:
            Page size (server caps at 200; server default 50).

        Returns
        -------
        Page[CallRecord]
            ``items`` is the page of calls; pass ``next_cursor`` back as
            ``cursor`` while ``has_more`` is ``True`` to fetch subsequent pages.
        """
        params: dict[str, str] = {}
        if date_from is not None:
            params["date_from"] = date_from
        if date_to is not None:
            params["date_to"] = date_to
        if status is not None:
            params["status"] = status
        if verdict is not None:
            params["verdict"] = verdict
        if shadow is not None:
            params["shadow"] = "true" if shadow else "false"
        if country is not None:
            params["country"] = country
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)

        url = f"{self._evidence_layer_url}/v1/calls"
        response = await self._request("GET", url, params=params or None)
        parsed = ListCallsResponse.model_validate(response.json())
        return Page[CallRecord](
            items=parsed.calls, has_more=parsed.has_more, next_cursor=parsed.next_cursor
        )

    async def get_call_detail(self, call_id: UUID) -> CallDetail:
        """
        Get the full detail of a single call in one request.

        Calls ``GET /v1/calls/{call_id}``. ``transcript`` is returned
        VERBATIM — PII intact, unredacted — and is empty (never ``None``)
        until the ``call_summary`` event has been produced.

        Parameters
        ----------
        call_id:
            UUID of the call.

        Returns
        -------
        CallDetail
        """
        url = f"{self._evidence_layer_url}/v1/calls/{call_id}"
        response = await self._request("GET", url)
        return CallDetail.model_validate(response.json())

    async def get_call_recording(self, call_id: UUID) -> RecordingResponse:
        """
        Get a short-lived signed download URL for a call's recorded audio.

        Calls ``GET /v1/calls/{call_id}/recording``. Raises
        :class:`~audact.exceptions.AudactNotFoundError` (404) when the call
        has no recording (``record_calls`` was off, or it was already
        deleted for retention/GDPR).

        Parameters
        ----------
        call_id:
            UUID of the call.

        Returns
        -------
        RecordingResponse
            ``url`` is valid for 15 minutes from ``expires_at``.
        """
        url = f"{self._evidence_layer_url}/v1/calls/{call_id}/recording"
        response = await self._request("GET", url)
        return RecordingResponse.model_validate(response.json())

    async def delete_call_recording(self, call_id: UUID) -> None:
        """
        Delete a call's recorded audio from object storage (retention/GDPR).

        Calls ``DELETE /v1/calls/{call_id}/recording``. Idempotent: deleting
        a call with no recording still succeeds (204). The evidence hash
        chain is never modified.

        Parameters
        ----------
        call_id:
            UUID of the call.
        """
        url = f"{self._evidence_layer_url}/v1/calls/{call_id}/recording"
        await self._request("DELETE", url)

    async def get_call_summary(self, call_id: UUID) -> CallSummary:
        """
        Get a composite summary of a call: verdict counts, handover context,
        and end-of-call detection context, in one request.

        Calls ``GET /v1/calls/{call_id}/summary``.

        Parameters
        ----------
        call_id:
            UUID of the call.

        Returns
        -------
        CallSummary
        """
        url = f"{self._evidence_layer_url}/v1/calls/{call_id}/summary"
        response = await self._request("GET", url)
        return CallSummary.model_validate(response.json())

    async def list_violations(
        self,
        *,
        call_id: UUID | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        verdict: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Page[ViolationRecord]:
        """
        List ``CHECK_RESULT`` evidence events where ``verdict != ALLOW``.

        Calls ``GET /v1/violations``.

        Parameters
        ----------
        call_id:
            Optional filter to a specific call.
        date_from, date_to:
            Inclusive/exclusive ``recorded_at`` bounds (RFC3339 or ``YYYY-MM-DD``).
        verdict:
            Specific non-``ALLOW`` verdict to filter on (e.g. ``"BLOCK"``,
            ``"FAIL_OPEN"``).
        cursor:
            Opaque keyset pagination cursor from a previous page's
            ``next_cursor`` (cursor pagination convention).
        limit:
            Page size (server caps at 200; server default 50).

        Returns
        -------
        Page[ViolationRecord]
        """
        params: dict[str, str] = {}
        if call_id is not None:
            params["call_id"] = str(call_id)
        if date_from is not None:
            params["date_from"] = date_from
        if date_to is not None:
            params["date_to"] = date_to
        if verdict is not None:
            params["verdict"] = verdict
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)

        url = f"{self._evidence_layer_url}/v1/violations"
        response = await self._request("GET", url, params=params or None)
        parsed = ListViolationsResponse.model_validate(response.json())
        return Page[ViolationRecord](
            items=parsed.violations, has_more=parsed.has_more, next_cursor=parsed.next_cursor
        )

    async def list_compliance_events(
        self,
        *,
        event_subtype: ComplianceEventSubtype | None = None,
        verdict: ComplianceVerdict | None = None,
        severity: ComplianceSeverity | None = None,
        call_id: UUID | str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> ListComplianceEventsResponse:
        """
        List compliance events (validation results including ALLOW, violations
        and fail-opens), cursor-paginated.

        Calls ``GET /v1/compliance/events``.

        Parameters
        ----------
        event_subtype:
            Filter by subtype. ``policy_triggered``, ``audit_logged`` and
            ``receipt_issued`` are webhook-only and always return an empty page.
        verdict:
            Filter by exact verdict (``"MODIFY"`` or ``"BLOCK"``; upper-case).
        severity:
            Filter by severity band (lower-case).
        call_id:
            Restrict to one call.
        cursor:
            Opaque cursor from a previous response's ``next_cursor``.
        limit:
            Page size 1-200 (server default 25).

        Returns
        -------
        ListComplianceEventsResponse
        """
        params: dict[str, str | list[str]] = {}
        if event_subtype is not None:
            params["event_subtype"] = event_subtype
        if verdict is not None:
            params["verdict"] = verdict
        if severity is not None:
            params["severity"] = severity
        if call_id is not None:
            params["call_id"] = str(call_id)
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)

        url = f"{self._evidence_layer_url}/v1/compliance/events"
        response = await self._request("GET", url, params=params or None)
        return ListComplianceEventsResponse.model_validate(response.json())

    async def get_article50_report(
        self, call_id: UUID, *, format: str | None = None
    ) -> Article50Report | bytes:
        """
        Assemble and sign the per-call Article 50 evidence export.

        Calls ``GET /v1/calls/{call_id}/article50-report``. Bundles the
        disclosure & delivery attestation, configuration seal, compliance
        receipts, evidence-chain integrity, cross-tenant Merkle branch proof,
        and RFC 3161 TSA timestamp into a single ECDSA-P256-signed envelope.

        Parameters
        ----------
        call_id:
            UUID of the completed call.
        format:
            ``"json"`` (default) or ``"pdf"``. When ``"pdf"``, the raw PDF
            bytes are returned instead of a typed :class:`Article50Report`.

        Returns
        -------
        Article50Report | bytes
            A typed report for ``format in (None, "json")``; raw PDF bytes
            for ``format="pdf"``.
        """
        url = f"{self._evidence_layer_url}/v1/calls/{call_id}/article50-report"
        params = {"format": format} if format is not None else None
        response = await self._request("GET", url, params=params)
        if format == "pdf":
            return response.content
        return Article50Report.model_validate(response.json())

    async def get_evidence_export(
        self, call_id: UUID, token: str, *, format: str | None = None
    ) -> Article50Report | bytes:
        """
        Download the Article 50 evidence export via a signed, unauthenticated link.

        Calls ``GET /v1/evidence-exports/{call_id}``. Possession of a valid,
        unexpired ``token`` IS the authorisation — no Audact API key is
        required (this method still sends one if configured on the client,
        which the server simply ignores). Serves the SAME export as
        :meth:`get_article50_report`. Per-IP rate-limited (default 30
        downloads/hour); a ``429`` carries ``Retry-After``.

        Parameters
        ----------
        call_id:
            UUID of the call (must match the token's embedded ``call_id``).
        token:
            Evidence-link capability token (``ev1.<payload>.<sig>``).
        format:
            Output format override: ``"json"`` or ``"pdf"``. Defaults to the
            token's own format when omitted.

        Returns
        -------
        Article50Report | bytes
            A typed report for the JSON case; raw PDF bytes for the PDF case.
        """
        url = f"{self._evidence_layer_url}/v1/evidence-exports/{call_id}"
        params = {"token": token}
        if format is not None:
            params["format"] = format
        response = await self._request("GET", url, params=params)
        if format == "pdf":
            return response.content
        content_type = response.headers.get("Content-Type", "")
        if format is None and "application/pdf" in content_type:
            return response.content
        return Article50Report.model_validate(response.json())

    async def generate_c2pa_manifest(
        self, call_id: UUID, *, idempotency_key: str | None = None
    ) -> C2PAManifest:
        """
        Generate a signed C2PA content credential manifest for a completed call.

        Calls ``POST /v1/calls/{call_id}/c2pa``. Fails closed with
        :class:`~audact.exceptions.AudactAPIError` (503) when the signing
        credential or storage is unavailable.

        Every successful call stores a new manifest permanently (evidence is
        append-only), so pass ``idempotency_key`` to make retries safe: a
        retry with the same key replays the first response.

        Parameters
        ----------
        call_id:
            UUID of the completed call.
        idempotency_key:
            Optional ``Idempotency-Key`` header value.

        Returns
        -------
        C2PAManifest
        """
        url = f"{self._evidence_layer_url}/v1/calls/{call_id}/c2pa"
        response = await self._request("POST", url, idempotency_key=idempotency_key)
        return C2PAManifest.model_validate(response.json())

    async def list_c2pa_manifests(
        self, call_id: UUID, *, cursor: str | None = None, limit: int | None = None
    ) -> Page[C2PAManifestListItem]:
        """
        List the C2PA manifests issued for a call (newest first).

        Calls ``GET /v1/calls/{call_id}/c2pa``, which returns
        ``{"manifests": [...], "next_cursor"?}``. Items are
        :class:`C2PAManifestListItem` — a subset of the
        :meth:`generate_c2pa_manifest` summary (no ``claim``/``assertions``).
        ``has_more`` is derived from ``next_cursor`` (the server does not send it).

        Returns
        -------
        Page[C2PAManifestListItem]
        """
        params: dict[str, str] = {}
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)
        url = f"{self._evidence_layer_url}/v1/calls/{call_id}/c2pa"
        response = await self._request("GET", url, params=params or None)
        parsed = C2PAManifestListResponse.model_validate(response.json())
        next_cursor = parsed.next_cursor or None
        return Page[C2PAManifestListItem](
            items=parsed.manifests, has_more=next_cursor is not None, next_cursor=next_cursor
        )

    async def download_c2pa_manifest_store(self, call_id: UUID, manifest_id: str) -> bytes:
        """
        Download the stored C2PA manifest store (``application/c2pa``).

        Calls ``GET /v1/calls/{call_id}/c2pa/{manifest_id}/manifest.c2pa``.
        Verify with ``c2patool <asset> --external-manifest <file>.c2pa``.
        A manifest that is not this tenant's is a 404.
        """
        url = (
            f"{self._evidence_layer_url}/v1/calls/{call_id}/c2pa/"
            f"{quote(str(manifest_id), safe='')}/manifest.c2pa"
        )
        response = await self._request("GET", url)
        return response.content

    async def download_c2pa_asset(self, call_id: UUID, manifest_id: str) -> bytes:
        """
        Download the asset the manifest is hard-bound to.

        Calls ``GET /v1/calls/{call_id}/c2pa/{manifest_id}/asset``. For
        recordings the server answers 302 to a presigned URL; this follows it
        **without** the Authorization header (the URL is self-authenticating
        and S3 rejects a second auth mechanism).
        """
        url = (
            f"{self._evidence_layer_url}/v1/calls/{call_id}/c2pa/"
            f"{quote(str(manifest_id), safe='')}/asset"
        )
        try:
            response = await self._http.request(
                "GET",
                url,
                headers=self._auth_headers(),
                timeout=self._timeout,
                follow_redirects=False,
            )
            if 300 <= response.status_code < 400 and response.headers.get("Location"):
                location = str(httpx.URL(url).join(response.headers["Location"]))
                response = await self._http.request(
                    "GET", location, timeout=self._timeout, follow_redirects=False
                )
        except httpx.TimeoutException as exc:
            raise AudactTimeoutError(f"Request to {url} timed out after {self._timeout}s") from exc
        except httpx.ConnectError as exc:
            raise AudactConnectionError(f"Cannot connect to {url}: {exc}") from exc
        if not response.is_success:
            _raise_for_status(response)
        return response.content

    async def get_c2pa_trust_anchor(self) -> str:
        """
        Fetch the PEM trust anchor (top certificate of the signing chain).

        Calls ``GET /v1/c2pa/trust-anchor`` — **unauthenticated**. Use it with
        ``c2patool --trust_anchors``.
        """
        url = f"{self._evidence_layer_url}/v1/c2pa/trust-anchor"
        response = await self._request("GET", url)
        return response.text

    async def get_receipt(self, call_id: UUID) -> GetReceiptResponse:
        """
        Get a stored compliance receipt and its server-verified HMAC signature.

        Calls ``GET /v1/receipts/{call_id}``. ``verifiability`` distinguishes
        a receipt that predates ``RECEIPT_HMAC_KEY`` provisioning
        (``hmac_valid`` false but NOT tampering — ``"unverifiable_pre_horizon"``)
        from a genuinely invalid signature (``hmac_valid`` false,
        ``verifiability`` ``"verifiable"``).

        Parameters
        ----------
        call_id:
            UUID of the call whose receipt to fetch.

        Returns
        -------
        GetReceiptResponse
        """
        url = f"{self._evidence_layer_url}/v1/receipts/{call_id}"
        response = await self._request("GET", url)
        return GetReceiptResponse.model_validate(response.json())

    async def get_delivery_status(self, call_id: UUID) -> list[TurnDeliveryStatus]:
        """
        Get per-turn delivery confirmation status for a call.

        Calls ``GET /v1/calls/{call_id}/delivery``.

        Parameters
        ----------
        call_id:
            UUID of the call.

        Returns
        -------
        list[TurnDeliveryStatus]
            May be empty.
        """
        url = f"{self._evidence_layer_url}/v1/calls/{call_id}/delivery"
        response = await self._request("GET", url)
        return [TurnDeliveryStatus.model_validate(item) for item in response.json()]

    async def confirm_delivery(
        self,
        req: ConfirmDeliveryRequest,
        *,
        idempotency_key: str | None = None,
    ) -> ProcessConfirmationResult:
        """
        Submit a delivery confirmation signal for a validated turn.

        Calls ``POST /v1/delivery-confirmation``. Writes a
        ``DELIVERY_ATTESTATION`` evidence event linking the confirmation
        back to the corresponding validation event.

        Parameters
        ----------
        req:
            The delivery confirmation payload.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — cached 2xx responses
            are replayed for 24h.

        Returns
        -------
        ProcessConfirmationResult
        """
        url = f"{self._evidence_layer_url}/v1/delivery-confirmation"
        response = await self._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return ProcessConfirmationResult.model_validate(response.json())

    async def reconcile_transcript(
        self,
        req: ReconcileTranscriptRequest,
        *,
        idempotency_key: str | None = None,
    ) -> ReconcileTranscriptResponse:
        """
        Compare a post-call transcript segment-by-segment against validated output events.

        Calls ``POST /v1/transcript-reconciliation``.

        Parameters
        ----------
        req:
            The transcript reconciliation request (``call_id``, ``segments``, ``source``).
        idempotency_key:
            Optional ``Idempotency-Key`` header value — cached 2xx responses
            are replayed for 24h.

        Returns
        -------
        ReconcileTranscriptResponse
        """
        url = f"{self._evidence_layer_url}/v1/transcript-reconciliation"
        response = await self._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return ReconcileTranscriptResponse.model_validate(response.json())

    async def get_article50_public_key(self, kid: str) -> str:
        """
        Fetch an Article 50 report-signing public key by key ID.

        Calls ``GET /v1/keys/{kid}`` — **unauthenticated** (the public key
        is not a secret). Only the current signing key is served; any other
        ``kid`` returns 404.

        Parameters
        ----------
        kid:
            Key ID from a report's ``signature.key_id``.

        Returns
        -------
        str
            PEM-encoded ECDSA-P256 ``SubjectPublicKeyInfo``.
        """
        from urllib.parse import quote

        url = f"{self._evidence_layer_url}/v1/keys/{quote(kid, safe='')}"
        response = await self._request("GET", url)
        return response.text

    # ─────────────────────────────────────────────────────────────────────────
    # Tenant Management — tenants
    # ─────────────────────────────────────────────────────────────────────────

    async def create_tenant(
        self,
        name: str,
        *,
        plan: str = "starter",
        key_name: str = "default",
    ) -> CreateTenantResponse:
        """
        Create a new Audact tenant.

        This endpoint is **unauthenticated** (no API key required).  The
        full plaintext API key for the tenant's first key is returned ONCE
        in the response — store it securely immediately.

        Parameters
        ----------
        name:
            Human-readable tenant name.
        plan:
            Billing tier: ``"starter"``, ``"professional"``, or
            ``"enterprise"``.
        key_name:
            Label for the tenant's first API key.

        Returns
        -------
        CreateTenantResponse
            Tenant record plus the first API key (``api_key.key`` is the
            full plaintext key, returned once only).
        """
        req = CreateTenantRequest(name=name, plan=plan, key_name=key_name)
        url = f"{self._tenant_management_url}/v1/tenants"
        response = await self._request("POST", url, json=req.model_dump())
        return CreateTenantResponse.model_validate(response.json())

    async def get_tenant(self, tenant_id: UUID) -> Tenant:
        """
        Retrieve a tenant record.

        Parameters
        ----------
        tenant_id:
            UUID of the tenant to fetch.

        Returns
        -------
        Tenant
        """
        url = f"{self._tenant_management_url}/v1/tenants/{tenant_id}"
        response = await self._request("GET", url)
        return Tenant.model_validate(response.json())

    async def update_tenant(
        self,
        tenant_id: UUID,
        *,
        name: str | None = None,
        plan: str | None = None,
    ) -> Tenant:
        """
        Update a tenant's mutable fields.

        Parameters
        ----------
        tenant_id:
            UUID of the tenant to update.
        name:
            New human-readable name.
        plan:
            New billing tier.

        Returns
        -------
        Tenant
            Updated tenant record.
        """
        req = UpdateTenantRequest(name=name, plan=plan)
        url = f"{self._tenant_management_url}/v1/tenants/{tenant_id}"
        body = {k: v for k, v in req.model_dump().items() if v is not None}
        response = await self._request("PUT", url, json=body)
        return Tenant.model_validate(response.json())

    async def get_tenant_usage(
        self,
        tenant_id: UUID,
        *,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> UsageRecord:
        """
        Retrieve aggregated usage statistics for a tenant's billing period.

        Calls ``GET /v1/tenants/{tenant_id}/usage``.

        Parameters
        ----------
        tenant_id:
            UUID of the tenant to fetch usage for.
        period_start:
            Optional inclusive start of the billing window (RFC3339).
        period_end:
            Optional exclusive end of the billing window (RFC3339).

        Returns
        -------
        UsageRecord
            Usage counters for the requested (or current) billing period.
            An all-zero record (``tenant_id``/period populated) is returned
            when no usage row exists yet for the requested period.
        """
        params: dict[str, str] = {}
        if period_start is not None:
            params["period_start"] = period_start
        if period_end is not None:
            params["period_end"] = period_end
        url = f"{self._tenant_management_url}/v1/tenants/{tenant_id}/usage"
        response = await self._request("GET", url, params=params or None)
        return UsageRecord.model_validate(response.json())

    # ─────────────────────────────────────────────────────────────────────────
    # Tenant Management — API keys
    # ─────────────────────────────────────────────────────────────────────────

    async def generate_key(
        self,
        tenant_id: UUID,
        *,
        name: str = "default",
        role: str = "developer",
    ) -> GenerateKeyResponse:
        """
        Generate a new API key for a tenant.

        The full plaintext key is returned ONCE — store it immediately.

        Parameters
        ----------
        tenant_id:
            UUID of the tenant to generate a key for.
        name:
            Human-readable label for the new key.
        role:
            RBAC role: ``"owner"``, ``"developer"``, or ``"viewer"``.

        Returns
        -------
        GenerateKeyResponse
            Contains the full plaintext ``key`` (one-time), ``key_prefix``,
            ``name``, ``role``, and ``created_at``.
        """
        req = GenerateKeyRequest(name=name, role=role)
        url = f"{self._tenant_management_url}/v1/tenants/{tenant_id}/keys"
        response = await self._request("POST", url, json=req.model_dump())
        return GenerateKeyResponse.model_validate(response.json())

    async def list_keys(self, tenant_id: UUID) -> list[APIKey]:
        """
        List all active API keys for a tenant.

        Parameters
        ----------
        tenant_id:
            UUID of the tenant whose keys to list.

        Returns
        -------
        list[APIKey]
            Summarised key records (key material NOT included).
        """
        url = f"{self._tenant_management_url}/v1/tenants/{tenant_id}/keys"
        response = await self._request("GET", url)
        return ListKeysResponse.model_validate(response.json()).keys

    async def revoke_key(self, tenant_id: UUID, key_id: str) -> None:
        """
        Revoke an API key.

        Parameters
        ----------
        tenant_id:
            UUID of the tenant that owns the key.
        key_id:
            UUID string of the key to revoke.
        """
        url = f"{self._tenant_management_url}/v1/tenants/{tenant_id}/keys/{key_id}"
        await self._request("DELETE", url)

    # ─────────────────────────────────────────────────────────────────────────
    # Tenant Management — configurations
    # ─────────────────────────────────────────────────────────────────────────

    async def create_configuration(
        self,
        name: str,
        countries: list[str],
        *,
        validator_modes: dict[str, str] | None = None,
        blocklist_patterns: list[dict[str, Any]] | None = None,
        pricing_bands: dict[str, Any] | None = None,
        disclosure_texts: dict[str, Any] | None = None,
        fallback_response: dict[str, Any] | None = None,
    ) -> Configuration:
        """
        Create a new tenant configuration.

        The tenant is identified by the authenticated API key; the
        ``tenant_id`` is derived server-side and is NOT accepted as a
        request parameter.

        Parameters
        ----------
        name:
            Human-readable label for this configuration.
        countries:
            List of ISO 3166-1 alpha-2 country codes from the supported
            launch set: ``NL``, ``DE``, ``BE``, ``FR``, ``IE``, ``AT``,
            ``IT``, ``ES``.
        validator_modes:
            Optional per-check-type mode overrides.  Valid values per key:
            ``"enforce"``, ``"shadow"``, ``"off"``.
        blocklist_patterns:
            Optional list of pattern dicts.  Each dict must have ``id``,
            ``terms``, and ``severity`` keys.
        pricing_bands:
            Optional pricing constraint map.
        disclosure_texts:
            Optional per-language disclosure text map.
        fallback_response:
            Optional per-language fallback string map.

        Returns
        -------
        Configuration
            The persisted configuration record.
        """
        from .models import BlocklistPattern

        parsed_patterns: list[BlocklistPattern] | None = None
        if blocklist_patterns is not None:
            parsed_patterns = [BlocklistPattern(**p) for p in blocklist_patterns]

        req = CreateConfigurationRequest(
            name=name,
            countries=countries,
            validator_modes=validator_modes,
            blocklist_patterns=parsed_patterns,
            pricing_bands=pricing_bands,
            disclosure_texts=disclosure_texts,
            fallback_response=fallback_response,
        )
        url = f"{self._tenant_management_url}/v1/configurations"
        response = await self._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
        )
        return Configuration.model_validate(response.json())

    async def get_configuration(self, config_id: UUID) -> Configuration:
        """
        Retrieve a configuration by ID.

        Parameters
        ----------
        config_id:
            UUID of the configuration to fetch.

        Returns
        -------
        Configuration
        """
        url = f"{self._tenant_management_url}/v1/configurations/{config_id}"
        response = await self._request("GET", url)
        return Configuration.model_validate(response.json())

    async def get_configuration_version(
        self, config_id: UUID, version: int
    ) -> Configuration:
        """
        Retrieve one immutable earlier version of a configuration.

        Calls ``GET /v1/configurations/{config_id}/versions/{version}``.
        Returns the exact settings that calls pinned to that version ran
        with, even after the configuration has been edited. The version is
        the ``config_version`` on a call's receipts, or a ``version`` in a
        call reconstruction's ``config_versions``. Same shape and redaction
        as :meth:`get_configuration`; ``updated_at`` equals ``created_at``.

        Parameters
        ----------
        config_id:
            UUID of the configuration.
        version:
            Configuration version (>= 1).

        Returns
        -------
        Configuration
        """
        if version < 1:
            raise ValueError("version must be >= 1")
        url = (
            f"{self._tenant_management_url}/v1/configurations/{config_id}"
            f"/versions/{version}"
        )
        response = await self._request("GET", url)
        return Configuration.model_validate(response.json())

    async def update_configuration(
        self,
        config_id: UUID,
        *,
        name: str | None = None,
        countries: list[str] | None = None,
        validator_modes: dict[str, str] | None = None,
        blocklist_patterns: list[dict[str, Any]] | None = None,
        pricing_bands: dict[str, Any] | None = None,
        disclosure_texts: dict[str, Any] | None = None,
        fallback_response: dict[str, Any] | None = None,
    ) -> Configuration:
        """
        Update a configuration's mutable fields.

        Only supplied fields are sent; omitted fields remain unchanged.

        Parameters
        ----------
        config_id:
            UUID of the configuration to update.
        name:
            New human-readable label.
        countries:
            New list of country codes.
        validator_modes:
            New per-check-type mode overrides.
        blocklist_patterns:
            New blocklist pattern list.
        pricing_bands:
            New pricing constraint map.
        disclosure_texts:
            New per-language disclosure text map.
        fallback_response:
            New per-language fallback string map.

        Returns
        -------
        Configuration
            Updated configuration record.
        """
        from .models import BlocklistPattern

        parsed_patterns: list[BlocklistPattern] | None = None
        if blocklist_patterns is not None:
            parsed_patterns = [BlocklistPattern(**p) for p in blocklist_patterns]

        req = UpdateConfigurationRequest(
            name=name,
            countries=countries,
            validator_modes=validator_modes,
            blocklist_patterns=parsed_patterns,
            pricing_bands=pricing_bands,
            disclosure_texts=disclosure_texts,
            fallback_response=fallback_response,
        )
        url = f"{self._tenant_management_url}/v1/configurations/{config_id}"
        body = req.model_dump(mode="json", exclude_none=True)
        response = await self._request("PUT", url, json=body)
        return Configuration.model_validate(response.json())

    async def delete_configuration(self, config_id: UUID) -> None:
        """
        Soft-delete a configuration.

        Parameters
        ----------
        config_id:
            UUID of the configuration to delete.
        """
        url = f"{self._tenant_management_url}/v1/configurations/{config_id}"
        await self._request("DELETE", url)

    async def list_configurations(self, tenant_id: UUID) -> list[Configuration]:
        """
        List all active configurations for a tenant.

        Parameters
        ----------
        tenant_id:
            UUID of the owning tenant (path parameter; ownership is also
            enforced from the auth context server-side).

        Returns
        -------
        list[Configuration]
            Active configurations in creation-time ascending order.
        """
        url = f"{self._tenant_management_url}/v1/tenants/{tenant_id}/configurations"
        response = await self._request("GET", url)
        return ListConfigurationsResponse.model_validate(response.json()).configurations

    # ─────────────────────────────────────────────────────────────────────────
    # LLM Proxy — streaming passthrough
    # ─────────────────────────────────────────────────────────────────────────

    async def proxy_stream(
        self,
        path: str,
        *,
        method: str = "POST",
        json: Any = None,
        params: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float | None = None,
        configuration_id: str | None = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream a response from the LLM Proxy service.

        The generator yields raw byte chunks as they arrive from the
        upstream LLM, enabling real-time streaming to the caller without
        buffering the full response.

        Parameters
        ----------
        path:
            URL path relative to the LLM Proxy base URL
            (e.g. ``"/v1/chat/completions"``).
        method:
            HTTP method.  Defaults to ``"POST"``.
        json:
            JSON-serialisable request body.
        params:
            Optional query parameters.
        extra_headers:
            Additional request headers to merge with the auth header.
        timeout:
            Per-request timeout in seconds.  Defaults to the client default.
        configuration_id:
            Optional configuration UUID to apply per-config LLM credentials.
            Passed as the ``configuration_id`` query parameter.

        Yields
        ------
        bytes
            Raw response byte chunks in arrival order.

        Raises
        ------
        AudactAPIError
            If the proxy returns a non-2xx status code.
        AudactTimeoutError
            If the connection or streaming times out.
        AudactConnectionError
            If the proxy cannot be reached.

        Example
        -------
        ::

            async for chunk in client.proxy_stream("/v1/chat/completions", json=body):
                print(chunk.decode(), end="", flush=True)
        """
        merged_params: dict[str, str] = dict(params or {})
        if configuration_id:
            merged_params["configuration_id"] = configuration_id
        url = f"{self._llm_proxy_url}{path}"
        headers = {**self._auth_headers(), **(extra_headers or {})}

        try:
            async with self._http.stream(
                method,
                url,
                json=json,
                params=merged_params or None,
                headers=headers,
                timeout=timeout or self._timeout,
            ) as response:
                rate_limit = _parse_rate_limit_headers(response.headers)
                if rate_limit is not None:
                    self._last_rate_limit = rate_limit
                if not response.is_success:
                    # Read the full error body before raising so that
                    # _raise_for_status can access response.text / response.json().
                    await response.aread()
                    _raise_for_status(response)
                async for chunk in response.aiter_bytes():
                    yield chunk
        except httpx.TimeoutException as exc:
            raise AudactTimeoutError(
                f"Stream from {url} timed out after {timeout or self._timeout}s"
            ) from exc
        except httpx.ConnectError as exc:
            raise AudactConnectionError(f"Cannot connect to LLM proxy at {url}: {exc}") from exc

    async def proxy_openai_stream(
        self,
        call_id: UUID,
        tenant_id: UUID,
        config_id: UUID,
        turn: int,
        model: str,
        messages: list[dict[str, Any]],
        *,
        configuration_id: str | None = None,
        extra_body: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream a chat completion request through the LLM Proxy's typed
        OpenAI-compatible streaming endpoint.

        Calls ``POST /v1/proxy/openai/stream``. Forwards a streaming chat
        completion request, validates it at sentence boundaries via the
        ACVF pipeline, and yields raw SSE byte chunks carrying compliance
        metadata. This is the typed counterpart of :meth:`proxy_stream`
        (which accepts an arbitrary ``path``) for the specific, documented
        ``/v1/proxy/openai/stream`` operation; MCP callers that cannot
        consume SSE should use :meth:`proxy_complete` instead.

        Parameters
        ----------
        call_id, tenant_id, config_id:
            UUIDs sent as the required ``X-Audact-Call-ID`` /
            ``X-Audact-Tenant-ID`` / ``X-Audact-Config-ID`` headers.
        turn:
            1-based turn number, sent as the required ``X-Audact-Turn``
            header.
        model:
            Upstream model identifier (e.g. ``"gpt-4o"``).
        messages:
            OpenAI-format message list.
        configuration_id:
            Optional configuration UUID override, forwarded as the
            ``configuration_id`` query parameter.
        extra_body:
            Additional fields merged into the JSON request body (e.g.
            ``temperature``, ``max_tokens``, ``tools``). ``stream`` is
            always forced to ``True``.
        timeout:
            Per-request timeout in seconds.

        Yields
        ------
        bytes
            Raw SSE byte chunks (``ChatCompletionChunk`` events) in arrival
            order.

        Raises
        ------
        AudactAPIError
            If the proxy returns a non-2xx status code (e.g. ``409`` on a
            ``model_mismatch`` against the sealed configuration).
        AudactTimeoutError
            If the connection or streaming times out.
        AudactConnectionError
            If the proxy cannot be reached.
        """
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            **(extra_body or {}),
            "stream": True,
        }
        extra_headers = {
            "X-Audact-Call-ID": str(call_id),
            "X-Audact-Tenant-ID": str(tenant_id),
            "X-Audact-Config-ID": str(config_id),
            "X-Audact-Turn": str(turn),
        }
        async for chunk in self.proxy_stream(
            "/v1/proxy/openai/stream",
            json=body,
            extra_headers=extra_headers,
            timeout=timeout,
            configuration_id=configuration_id,
        ):
            yield chunk

    async def proxy_request(
        self,
        path: str,
        *,
        method: str = "POST",
        json: Any = None,
        params: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float | None = None,
        configuration_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Send a non-streaming request through the LLM Proxy.

        Parameters
        ----------
        path:
            URL path relative to the LLM Proxy base URL.
        method:
            HTTP method.
        json:
            JSON-serialisable request body.
        params:
            Optional query parameters.
        extra_headers:
            Additional request headers.
        timeout:
            Per-request timeout in seconds.
        configuration_id:
            Optional configuration UUID to apply per-config LLM credentials.
            Passed as the ``configuration_id`` query parameter.

        Returns
        -------
        dict
            Parsed JSON response body.
        """
        merged_params: dict[str, str] = dict(params or {})
        if configuration_id:
            merged_params["configuration_id"] = configuration_id
        url = f"{self._llm_proxy_url}{path}"
        response = await self._request(
            method,
            url,
            json=json,
            params=merged_params or None,
            extra_headers=extra_headers,
            timeout=timeout,
        )
        return cast(dict[str, Any], response.json())

    async def proxy_complete(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        configuration_id: str | None = None,
        extra_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """
        Send a non-streaming chat completion request through the LLM Proxy.

        Posts to ``POST /v1/proxy/openai``.  When ``configuration_id`` is
        supplied it is forwarded as a query parameter so the proxy selects
        the per-configuration LLM credentials.

        Parameters
        ----------
        model:
            Model identifier (e.g. ``"gpt-4o"``).
        messages:
            OpenAI-format message list.
        configuration_id:
            Optional configuration UUID to apply per-config LLM credentials.
            Passed as the ``configuration_id`` query parameter.
        extra_body:
            Additional fields merged into the JSON request body.
        extra_headers:
            Additional request headers.
        timeout:
            Per-request timeout in seconds.

        Returns
        -------
        dict
            Parsed JSON response body from the upstream LLM.
        """
        body: dict[str, Any] = {"model": model, "messages": messages, **(extra_body or {})}
        params: dict[str, str] = {}
        if configuration_id:
            params["configuration_id"] = configuration_id
        url = f"{self._llm_proxy_url}/v1/proxy/openai"
        response = await self._request(
            "POST",
            url,
            json=body,
            params=params or None,
            extra_headers=extra_headers,
            timeout=timeout,
        )
        return cast(dict[str, Any], response.json())

    # ─────────────────────────────────────────────────────────────────────────
    # Platform admin — cross-tenant YAML export/import (Tenant Management)
    #
    # Every method here requires a ``platform_token`` — a super-admin platform
    # token, distinct from (and never a substitute for) the tenant API key
    # configured on this client via ``api_key=``/``AUDACT_API_KEY``. The SDK
    # never mints or caches this token; the caller is responsible for
    # obtaining it out of band and supplying it on every call.
    # ─────────────────────────────────────────────────────────────────────────

    def _platform_headers(
        self, platform_token: str, *, accept: str | None = None
    ) -> dict[str, str]:
        """Build the auth (+ optional Accept) headers for a platform-admin call."""
        headers = {"Authorization": f"Bearer {platform_token}"}
        if accept:
            headers["Accept"] = accept
        return headers

    async def _get_platform_bundle(
        self,
        url: str,
        *,
        platform_token: str,
        format: str | None,
        params: dict[str, str] | None = None,
    ) -> PlatformBundle:
        accept = _accept_header_for_format(format)
        response = await self._request(
            "GET",
            url,
            params=params,
            extra_headers=self._platform_headers(platform_token, accept=accept),
        )
        return PlatformBundle.model_validate(yaml.safe_load(response.text))

    async def export_tenant(
        self,
        tenant_id: UUID,
        *,
        platform_token: str,
        format: str | None = None,
    ) -> PlatformBundle:
        """
        Export every active Configuration, Tool, and Agent owned by a tenant.

        Calls ``GET /v1/platform/export/tenants/{tenant_id}``. The tenant's
        identity for the export is ultimately determined server-side from
        ``platform_token`` (via PlatformAuth) — ``tenant_id`` selects which of
        the token's authorized tenants to export.

        Parameters
        ----------
        tenant_id:
            UUID of the tenant to export.
        platform_token:
            Bearer token for a platform admin authorized to export this
            tenant. Sent as ``Authorization: Bearer <platform_token>``.
        format:
            Wire format to request from the server: ``"yaml"`` (the
            server's default) or ``"json"``. Either way this method returns
            a fully-typed :class:`~audact.models.PlatformBundle`.

        Returns
        -------
        PlatformBundle
            The exported bundle (``apiVersion``/``kind``/``metadata``/``spec``),
            with fresh refs, ``needsSecret`` stubs in place of secrets, and no
            phone/DID bindings.
        """
        url = f"{self._tenant_management_url}/v1/platform/export/tenants/{tenant_id}"
        return await self._get_platform_bundle(url, platform_token=platform_token, format=format)

    async def export_agent(
        self,
        agent_id: UUID,
        *,
        tenant_id: UUID,
        platform_token: str,
        format: str | None = None,
    ) -> PlatformBundle:
        """
        Export a single agent (plus its configuration and tools).

        Calls ``GET /v1/platform/export/agents/{agent_id}``.

        Parameters
        ----------
        agent_id:
            UUID of the agent to export.
        tenant_id:
            UUID of the tenant that owns the agent. Sent as the
            ``tenant_id`` query parameter (required unless ``platform_token``
            authorizes exactly one tenant).
        platform_token:
            Bearer token for a platform admin authorized to export this
            agent's tenant.
        format:
            Wire format to request from the server: ``"yaml"`` (the
            server's default) or ``"json"``. Either way this method returns
            a fully-typed :class:`~audact.models.PlatformBundle`.

        Returns
        -------
        PlatformBundle
            A self-contained ``AgentBundle``: the agent, its dedicated
            Configuration (if any), and every Tool it has attached.
        """
        url = f"{self._tenant_management_url}/v1/platform/export/agents/{agent_id}"
        return await self._get_platform_bundle(
            url,
            platform_token=platform_token,
            format=format,
            params={"tenant_id": str(tenant_id)},
        )

    async def import_tenant(
        self,
        target_tenant_id: UUID,
        bundle: BundleInput,
        *,
        platform_token: str,
        dry_run: bool = False,
        mode: str = "create-only",
        set_secret: Sequence[str] | Mapping[str, str] | None = None,
    ) -> PlatformImportResult:
        """
        Import a platform-provisioning bundle into a tenant.

        Calls ``POST /v1/platform/import/tenants/{target_tenant_id}``. The
        target tenant is taken exclusively from ``platform_token`` server-side
        (via PlatformAuth) — ``target_tenant_id`` must be one of that token's
        authorized targets.

        Parameters
        ----------
        target_tenant_id:
            UUID of the tenant to import into.
        bundle:
            The bundle to import: a :class:`~audact.models.PlatformBundle`
            (e.g. one returned by :meth:`export_tenant`), a plain mapping,
            raw YAML/JSON text or bytes, or an open, readable binary file
            handle. A file handle is streamed to the server as-is rather
            than being fully buffered in memory first.
        platform_token:
            Bearer token for a platform admin authorized to import into
            ``target_tenant_id``.
        dry_run:
            When ``True``, returns the plan without creating anything.
            Defaults to ``False``.
        mode:
            Conflict policy for entities that already exist in the target
            tenant. ``"create-only"`` (default) always creates fresh
            resources; ``"upsert"`` is accepted by the server but not yet
            implemented (raises :class:`~audact.exceptions.AudactAPIError`
            with ``status_code == 501``).
        set_secret:
            Zero or more secret assignments provisioning a real
            secret/connection for a redacted bundle entity: either an
            iterable of ``"<ref>.<field>=<value>"`` strings, or a mapping of
            ``{"<ref>.<field>": "<value>"}``. The raw value is never logged
            by the SDK.

        Returns
        -------
        PlatformImportResult
            The per-entity result manifest: what was (or, under ``dry_run``,
            would be) created, plus counts and warnings.
        """
        url = f"{self._tenant_management_url}/v1/platform/import/tenants/{target_tenant_id}"

        params: dict[str, str | list[str]] = {"mode": mode}
        if dry_run:
            params["dryRun"] = "true"

        # SECURITY: setSecret carries the operator's
        # plaintext BYOK secret. It MUST travel as repeated X-Audact-Set-Secret
        # request headers — never as a URL query parameter, which every reverse
        # proxy logs. The server reads r.Header.Values("X-Audact-Set-Secret"),
        # so each assignment is sent as its own header line.
        secrets = _normalize_set_secret(set_secret)
        repeated_headers = [(_SET_SECRET_HEADER, s) for s in secrets]

        content, content_type = _serialize_bundle_for_import(bundle)
        headers = self._platform_headers(platform_token)
        headers["Content-Type"] = content_type

        response = await self._request(
            "POST",
            url,
            content=content,
            params=params,
            extra_headers=headers,
            repeated_headers=repeated_headers,
        )
        return PlatformImportResult.model_validate(response.json())

    # ─────────────────────────────────────────────────────────────────────────
    # Number provisioning & KYC — voice-gateway
    # ─────────────────────────────────────────────────────────────────────────

    async def list_kyc_documents(self) -> list[KYCDocument]:
        """
        List every KYC document uploaded by the authenticated tenant.

        Calls ``GET /v1/kyc/documents``. Document bytes are never returned
        (metadata only).

        Returns
        -------
        list[KYCDocument]
        """
        url = f"{self._voice_gateway_url}/v1/kyc/documents"
        response = await self._request("GET", url)
        return ListKYCDocumentsResponse.model_validate(response.json()).documents

    async def get_kyc_document(self, document_id: UUID) -> KYCDocument:
        """
        Get a single KYC document's metadata.

        Calls ``GET /v1/kyc/documents/{document_id}``.

        Parameters
        ----------
        document_id:
            UUID of the KYC document.

        Returns
        -------
        KYCDocument
        """
        url = f"{self._voice_gateway_url}/v1/kyc/documents/{document_id}"
        response = await self._request("GET", url)
        return KYCDocument.model_validate(response.json())

    async def upload_kyc_document(
        self,
        file: bytes | IO[bytes],
        doc_type: str,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        idempotency_key: str | None = None,
    ) -> KYCDocument:
        """
        Upload a KYC/regulatory document file.

        Calls ``POST /v1/kyc/documents`` as a ``multipart/form-data`` request
        (net-new multipart support — see :meth:`_request`). The file is
        encrypted at rest server-side and its bytes are never returned by any
        endpoint; use the returned ``sha256`` to verify the right file was
        uploaded without ever downloading it back.

        Parameters
        ----------
        file:
            Raw file bytes, or an open, readable binary file handle.
        doc_type:
            Document category, e.g. ``"passport"`` or ``"proof_of_address"``.
        filename:
            Filename to send. Defaults to ``file.name``'s basename when
            ``file`` is a file handle, else ``"upload"``.
        content_type:
            MIME type to send. Defaults to ``"application/octet-stream"``.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key (with the same doc_type + file content) returns the original
            document instead of creating a duplicate.

        Returns
        -------
        KYCDocument
        """
        url = f"{self._voice_gateway_url}/v1/kyc/documents"
        files = {"file": _kyc_file_part(file, filename=filename, content_type=content_type)}
        response = await self._request(
            "POST",
            url,
            files=files,
            data={"doc_type": doc_type},
            idempotency_key=idempotency_key,
        )
        return KYCDocument.model_validate(response.json())

    async def replace_kyc_document(
        self,
        document_id: UUID,
        file: bytes | IO[bytes],
        *,
        filename: str | None = None,
        content_type: str | None = None,
        idempotency_key: str | None = None,
    ) -> KYCDocument:
        """
        Replace ("resend") an existing KYC document's file.

        Calls ``PUT /v1/kyc/documents/{document_id}`` as a
        ``multipart/form-data`` request, keeping the same document id so any
        KYC document set item still references it. Returns 409 (surfaced as
        :class:`~audact.exceptions.AudactAPIError`) while the document backs
        an in-flight number order.

        Parameters
        ----------
        document_id:
            UUID of the KYC document to replace.
        file:
            Raw file bytes, or an open, readable binary file handle.
        filename:
            Filename to send. Defaults to ``file.name``'s basename when
            ``file`` is a file handle, else ``"upload"``.
        content_type:
            MIME type to send. Defaults to ``"application/octet-stream"``.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key (with the same file content) returns the original document
            instead of replacing it again.

        Returns
        -------
        KYCDocument
        """
        url = f"{self._voice_gateway_url}/v1/kyc/documents/{document_id}"
        files = {"file": _kyc_file_part(file, filename=filename, content_type=content_type)}
        response = await self._request(
            "PUT", url, files=files, idempotency_key=idempotency_key
        )
        return KYCDocument.model_validate(response.json())

    async def delete_kyc_document(self, document_id: UUID) -> None:
        """
        Permanently delete a KYC document.

        Calls ``DELETE /v1/kyc/documents/{document_id}``. Returns 409
        (surfaced as :class:`~audact.exceptions.AudactAPIError`) while the
        document backs an in-flight number order, or is still referenced by a
        document set.

        Parameters
        ----------
        document_id:
            UUID of the KYC document to delete.
        """
        url = f"{self._voice_gateway_url}/v1/kyc/documents/{document_id}"
        await self._request("DELETE", url)

    async def get_kyc_requirements(self, country: str, number_type: str) -> list[KYCRequirement]:
        """
        List Telnyx's live regulatory requirements for (country, number_type).

        Calls ``GET /v1/kyc/requirements``. A legitimate zero-requirements
        result is returned as an explicit empty list — never inferred as a
        pass.

        Parameters
        ----------
        country:
            ISO 3166-1 alpha-2 country code, e.g. ``"NL"``.
        number_type:
            Telnyx ``phone_number_type``, e.g. ``"mobile"``.

        Returns
        -------
        list[KYCRequirement]
        """
        url = f"{self._voice_gateway_url}/v1/kyc/requirements"
        response = await self._request(
            "GET",
            url,
            params={"country": country, "number_type": number_type},
        )
        return ListKYCRequirementsResponse.model_validate(response.json()).requirements

    async def list_kyc_document_sets(self) -> list[KYCDocumentSet]:
        """
        List every KYC document set owned by the authenticated tenant.

        Calls ``GET /v1/kyc/document-sets``. Item detail is omitted here —
        use :meth:`get_kyc_document_set`.

        Returns
        -------
        list[KYCDocumentSet]
        """
        url = f"{self._voice_gateway_url}/v1/kyc/document-sets"
        response = await self._request("GET", url)
        return ListKYCDocumentSetsResponse.model_validate(response.json()).document_sets

    async def create_kyc_document_set(self, req: CreateKYCDocumentSetRequest) -> KYCDocumentSet:
        """
        Create a KYC document set and submit it to Telnyx for approval.

        Calls ``POST /v1/kyc/document-sets``. Coverage against Telnyx's live
        regulatory requirements is validated server-side first — a missing
        REQUIRED requirement raises :class:`~audact.exceptions.AudactAPIError`
        with ``status_code == 422`` and ``details["missing"]`` listing the
        unsatisfied requirement ids. The set starts in ``"submitted"`` status;
        approval/rejection arrives later (poll via :meth:`get_kyc_document_set`).

        Parameters
        ----------
        req:
            The document set request payload.

        Returns
        -------
        KYCDocumentSet
        """
        url = f"{self._voice_gateway_url}/v1/kyc/document-sets"
        response = await self._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
        )
        return KYCDocumentSet.model_validate(response.json())

    async def get_kyc_document_set(self, set_id: UUID) -> KYCDocumentSet:
        """
        Get a single KYC document set's detail, including item mappings.

        Calls ``GET /v1/kyc/document-sets/{set_id}``.

        Parameters
        ----------
        set_id:
            UUID of the KYC document set.

        Returns
        -------
        KYCDocumentSet
        """
        url = f"{self._voice_gateway_url}/v1/kyc/document-sets/{set_id}"
        response = await self._request("GET", url)
        return KYCDocumentSet.model_validate(response.json())

    async def delete_kyc_document_set(self, set_id: UUID) -> None:
        """
        Permanently delete a KYC document set (cascading its items).

        Calls ``DELETE /v1/kyc/document-sets/{set_id}``. Returns 409
        (surfaced as :class:`~audact.exceptions.AudactAPIError`) while an
        in-flight number order references the set.

        Parameters
        ----------
        set_id:
            UUID of the KYC document set to delete.
        """
        url = f"{self._voice_gateway_url}/v1/kyc/document-sets/{set_id}"
        await self._request("DELETE", url)

    async def rotate_kyc_dek(self) -> int:
        """
        Rotate the tenant's KYC Document Encryption Key (DEK).

        Calls ``POST /v1/kyc/dek/rotate``. Existing documents remain fully
        readable — only newly uploaded/replaced documents are sealed under
        the freshly-minted version.

        Returns
        -------
        int
            The tenant's new current DEK version.
        """
        url = f"{self._voice_gateway_url}/v1/kyc/dek/rotate"
        response = await self._request("POST", url)
        return RotateDEKResponse.model_validate(response.json()).new_version

    async def list_available_numbers(self, country: str, number_type: str) -> list[AvailableNumber]:
        """
        Search Telnyx's live inventory for numbers matching country/number_type.

        Calls ``GET /v1/numbers/available``. Returns an explicit empty list
        (never an error) when Telnyx legitimately has no matching inventory.

        Parameters
        ----------
        country:
            ISO 3166-1 alpha-2 country code, e.g. ``"NL"``.
        number_type:
            Telnyx ``phone_number_type``, e.g. ``"local"``.

        Returns
        -------
        list[AvailableNumber]
        """
        url = f"{self._voice_gateway_url}/v1/numbers/available"
        response = await self._request(
            "GET",
            url,
            params={"country": country, "number_type": number_type},
        )
        return ListAvailableNumbersResponse.model_validate(response.json()).numbers

    async def create_number_order(
        self,
        req: CreateNumberOrderRequest,
        *,
        idempotency_key: str | None = None,
    ) -> NumberOrder:
        """
        Place a Telnyx number order against an already-``approved`` KYC document set.

        Calls ``POST /v1/numbers/orders``. The order starts in ``"pending"``
        status; it only reaches ``"success"``/``"failure"`` asynchronously —
        poll with :meth:`get_number_order` or :meth:`wait_for_order`.

        Parameters
        ----------
        req:
            The number order request payload.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying an
            already-used key returns the original order instead of placing a
            duplicate Telnyx order.

        Returns
        -------
        NumberOrder
        """
        url = f"{self._voice_gateway_url}/v1/numbers/orders"
        response = await self._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return NumberOrder.model_validate(response.json())

    async def list_number_orders(self) -> list[NumberOrder]:
        """
        List every Telnyx number order placed by the authenticated tenant.

        Calls ``GET /v1/numbers/orders``, most recent first.

        Returns
        -------
        list[NumberOrder]
        """
        url = f"{self._voice_gateway_url}/v1/numbers/orders"
        response = await self._request("GET", url)
        return ListNumberOrdersResponse.model_validate(response.json()).orders

    async def get_number_order(self, order_id: UUID) -> NumberOrder:
        """
        Get a single Telnyx number order.

        Calls ``GET /v1/numbers/orders/{order_id}``.

        Parameters
        ----------
        order_id:
            UUID of the number order.

        Returns
        -------
        NumberOrder
        """
        url = f"{self._voice_gateway_url}/v1/numbers/orders/{order_id}"
        response = await self._request("GET", url)
        return NumberOrder.model_validate(response.json())

    async def wait_for_order(
        self,
        order_id: UUID,
        *,
        timeout: float = 60.0,
        poll_interval: float = 2.0,
    ) -> NumberOrder:
        """
        Poll a number order until it reaches a terminal status.

        Repeatedly calls :meth:`get_number_order` until ``status`` is one of
        ``"success"``, ``"failure"``, or ``"cancelled"`` — the order only
        reaches a terminal state asynchronously, via the Telnyx webhook or the
        server's poll reconciler, never synchronously at creation time.

        Parameters
        ----------
        order_id:
            UUID of the number order to poll.
        timeout:
            Maximum number of seconds to wait before giving up. Defaults to
            60s.
        poll_interval:
            Seconds to sleep between polls. Defaults to 2s.

        Returns
        -------
        NumberOrder
            The order once it reaches a terminal status.

        Raises
        ------
        AudactTimeoutError
            If ``timeout`` elapses before the order reaches a terminal status.
        """
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while True:
            order = await self.get_number_order(order_id)
            if order.status in _TERMINAL_ORDER_STATUSES:
                return order
            if loop.time() >= deadline:
                raise AudactTimeoutError(
                    f"number order {order_id} did not reach a terminal status within {timeout}s"
                )
            await asyncio.sleep(poll_interval)

    # ─────────────────────────────────────────────────────────────────────────
    # Numbers lifecycle completion — voice-gateway
    # ─────────────────────────────────────────────────────────────────────────

    async def list_numbers(
        self,
        *,
        country: str | None = None,
        status: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Page[PhoneNumber]:
        """
        List DID phone numbers in the pool for the authenticated tenant.

        Calls ``GET /v1/numbers``.

        Parameters
        ----------
        country:
            Optional ISO 3166-1 alpha-2 country code filter, e.g. ``"NL"``.
        status:
            Optional lifecycle-state filter: ``"available"``, ``"assigned"``,
            or ``"suspended"``.
        cursor:
            Opaque pagination cursor from a previous page's ``next_cursor``
            (cursor pagination convention).
        limit:
            Page size (server caps at 200; server default 50).

        Returns
        -------
        Page[PhoneNumber]
            ``items`` is the page of numbers; pass ``next_cursor`` back as
            ``cursor`` while ``has_more`` is ``True`` to fetch subsequent
            pages. ``has_more`` is derived from ``next_cursor`` being
            present — the server does not send an explicit ``has_more``
            field for this surface.
        """
        params: dict[str, str] = {}
        if country is not None:
            params["country"] = country
        if status is not None:
            params["status"] = status
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)

        url = f"{self._voice_gateway_url}/v1/numbers"
        response = await self._request("GET", url, params=params or None)
        parsed = ListNumbersResponse.model_validate(response.json())
        # Page allows extras (extra="allow"): besides the generic
        # items/has_more/next_cursor convention, expose the raw wire field
        # names too (BYO surface). Validating from a dict keeps mypy
        # from rejecting the extra keyword arguments.
        return Page[PhoneNumber].model_validate(
            {
                "items": parsed.numbers,
                "has_more": parsed.next_cursor is not None,
                "next_cursor": parsed.next_cursor,
                "numbers": parsed.numbers,
                "total_count": parsed.total_count,
            }
        )

    async def create_number(
        self,
        req: CreateNumberRequest,
        *,
        idempotency_key: str | None = None,
    ) -> PhoneNumber:
        """
        Add a phone number to the pool — Audact-provisioned or bring-your-own.

        Calls ``POST /v1/numbers``. The DID must be in E.164 format and
        globally unique across all tenants. ``req.origin`` defaults to
        ``"audact"`` server-side when omitted (back-compat with the
        historical Telnyx-only flow). For ``origin="byo"``, supply EITHER
        ``req.byo_connection_id`` (attach to an already-registered
        :class:`~audact.models.BYOConnection`) OR ``req.connection`` (inline
        connection details — the server creates a new connection, or reuses
        a matching one deduped on (provider, sip_host, sip_username)) —
        never both.

        Parameters
        ----------
        req:
            The phone-number creation payload.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key returns the original number instead of a 409 conflict.

        Returns
        -------
        PhoneNumber
        """
        url = f"{self._voice_gateway_url}/v1/numbers"
        response = await self._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return PhoneNumber.model_validate(response.json())

    async def lookup_number(self, did: str) -> PhoneNumber:
        """
        Look up a single DID phone number by its E.164 value.

        Calls ``GET /v1/numbers/lookup``. Useful when the caller knows the
        phone number but not its UUID primary key. Cross-tenant DIDs are
        never revealed (surfaced as a plain 404) to prevent enumeration.

        Parameters
        ----------
        did:
            E.164 phone number to look up, e.g. ``"+31201234567"``.

        Returns
        -------
        PhoneNumber
        """
        url = f"{self._voice_gateway_url}/v1/numbers/lookup"
        response = await self._request("GET", url, params={"did": did})
        return PhoneNumber.model_validate(response.json())

    async def assign_number(
        self,
        number_id: UUID,
        req: AssignNumberRequest,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        """
        Assign a pooled DID to an agent.

        Calls ``POST /v1/numbers/{id}/assign``. The DID must be in
        ``"available"`` status. Raises
        :class:`~audact.exceptions.AudactAPIError` with ``status_code == 409``
        if the number is already assigned — release it first.

        Parameters
        ----------
        number_id:
            UUID of the phone number.
        req:
            The assignment request payload (``agent_id``).
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key + body returns 200 instead of re-assigning.
        """
        url = f"{self._voice_gateway_url}/v1/numbers/{number_id}/assign"
        await self._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )

    async def suspend_number(
        self,
        number_id: UUID,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        """
        Pause inbound routing for an assigned DID (A9 "held but not routed").

        Calls ``POST /v1/numbers/{id}/suspend``. The DID must be in
        ``"assigned"`` status; ``assigned_agent_id`` and tenant ownership are
        preserved — the number is NOT returned to the shared pool. Restore
        routing with :meth:`resume_number`.

        Parameters
        ----------
        number_id:
            UUID of the phone number.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key returns 200 instead of re-suspending.
        """
        url = f"{self._voice_gateway_url}/v1/numbers/{number_id}/suspend"
        await self._request("POST", url, idempotency_key=idempotency_key)

    async def resume_number(
        self,
        number_id: UUID,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        """
        Restore inbound routing for a previously suspended DID.

        Calls ``POST /v1/numbers/{id}/resume``. The DID must be in
        ``"suspended"`` status.

        Parameters
        ----------
        number_id:
            UUID of the phone number.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key returns 200 instead of re-resuming.
        """
        url = f"{self._voice_gateway_url}/v1/numbers/{number_id}/resume"
        await self._request("POST", url, idempotency_key=idempotency_key)

    async def release_number(
        self,
        number_id: UUID,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        """
        Release an assigned DID back to the available pool.

        Calls ``DELETE /v1/numbers/{id}/release``. The DID must be in
        ``"assigned"`` status; on success ``status`` becomes ``"available"``
        and ``assigned_agent_id`` is cleared. On a routing-teardown failure
        the number is left unchanged and a 502 (surfaced as
        :class:`~audact.exceptions.AudactAPIError`) is returned — safe to
        retry.

        Parameters
        ----------
        number_id:
            UUID of the phone number.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key returns 200 instead of re-releasing.
        """
        url = f"{self._voice_gateway_url}/v1/numbers/{number_id}/release"
        await self._request("DELETE", url, idempotency_key=idempotency_key)

    async def delete_number(self, number_id: UUID) -> None:
        """
        Permanently delete a DID phone number from the pool.

        Calls ``DELETE /v1/numbers/{id}``. For a Telnyx-owned number this
        also releases the number at the carrier — this STOPS BILLING and is
        IRREVERSIBLE. Only numbers in ``"available"`` status may be deleted;
        release an assigned number first with :meth:`release_number`.

        Parameters
        ----------
        number_id:
            UUID of the phone number.
        """
        url = f"{self._voice_gateway_url}/v1/numbers/{number_id}"
        await self._request("DELETE", url)

    async def set_number_trunk(
        self,
        number_id: UUID,
        req: SetNumberTrunkRequest,
    ) -> PhoneNumber:
        """
        Set (or clear) a number's outbound SIP trunk.

        Calls ``PUT /v1/numbers/{id}/trunk``. ``req.trunk_id`` is the
        ``sip_trunk_id`` of an outbound trunk from ``GET /v1/sip/trunks``
        (``client.calls.list_trunks``) — used e.g. to warm-transfer on the
        agent's own number. An empty string clears the link.

        Parameters
        ----------
        number_id:
            UUID of the phone number.
        req:
            The trunk-link request payload.

        Returns
        -------
        PhoneNumber
            The updated number.
        """
        url = f"{self._voice_gateway_url}/v1/numbers/{number_id}/trunk"
        response = await self._request(
            "PUT",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
        )
        return PhoneNumber.model_validate(response.json())

    # ─────────────────────────────────────────────────────────────────────────
    # Bring-Your-Own (BYO) telephony connections — voice-gateway
    # ─────────────────────────────────────────────────────────────────────────

    async def list_byo_connections(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListBYOConnectionsResponse:
        """
        List bring-your-own SIP trunk connections for the authenticated tenant.

        Calls ``GET /v1/byo/connections``, paginated (default page size 50,
        max 200).

        Parameters
        ----------
        limit:
            Maximum results per page (default 50, max 200).
        cursor:
            Opaque pagination cursor returned as ``next_cursor`` from a prior
            call.

        Returns
        -------
        ListBYOConnectionsResponse
        """
        url = f"{self._voice_gateway_url}/v1/byo/connections"
        params: dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(limit)
        if cursor is not None:
            params["cursor"] = cursor
        response = await self._request("GET", url, params=params or None)
        return ListBYOConnectionsResponse.model_validate(response.json())

    async def get_byo_connection(self, connection_id: UUID) -> BYOConnection:
        """
        Get a single bring-your-own SIP trunk connection.

        Calls ``GET /v1/byo/connections/{connection_id}``.

        Parameters
        ----------
        connection_id:
            UUID of the BYO connection.

        Returns
        -------
        BYOConnection

        Raises
        ------
        AudactAPIError
            404 if the connection does not exist for this tenant.
        """
        url = f"{self._voice_gateway_url}/v1/byo/connections/{connection_id}"
        response = await self._request("GET", url)
        return BYOConnection.model_validate(response.json())

    async def create_byo_connection(
        self,
        req: CreateBYOConnectionRequest,
        *,
        idempotency_key: str | None = None,
    ) -> BYOConnection:
        """
        Register a new bring-your-own SIP trunk connection.

        Calls ``POST /v1/byo/connections``. Requires EITHER SIP credentials
        (``sip_username`` + ``sip_password``) OR an inbound IP allowlist
        (``inbound_allowed_ips``) — at least one is mandatory. Runs a
        connect-time health probe before returning; check
        ``connection_health`` on the response.

        Parameters
        ----------
        req:
            The connection creation payload.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key returns 200 on replay.

        Returns
        -------
        BYOConnection

        Raises
        ------
        AudactAPIError
            400 on an invalid provider/transport or missing ``name``; 409 if
            a connection with this name already exists for this tenant; 422
            (``missing_connection_material`` or
            ``inbound_allowlist_too_broad``) when neither credentials nor a
            sufficiently narrow allowlist is supplied — see
            :attr:`~audact.exceptions.AudactAPIError.details` for the
            offending field.
        """
        url = f"{self._voice_gateway_url}/v1/byo/connections"
        response = await self._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return BYOConnection.model_validate(response.json())

    async def update_byo_connection(
        self,
        connection_id: UUID,
        req: UpdateBYOConnectionRequest,
        *,
        idempotency_key: str | None = None,
    ) -> BYOConnection:
        """
        Apply a partial update to an existing BYO connection.

        Calls ``PUT /v1/byo/connections/{connection_id}``. Fields omitted
        from ``req`` are left unchanged. Supplying BOTH ``sip_username`` and
        ``sip_password`` rotates the stored SIP credential. Re-registers the
        outbound trunk and re-runs the connect-time health probe
        unconditionally; check ``connection_health`` on the response.

        Parameters
        ----------
        connection_id:
            UUID of the BYO connection to update.
        req:
            The partial update payload.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key returns 200 on replay.

        Returns
        -------
        BYOConnection

        Raises
        ------
        AudactAPIError
            404 if not found, 409 if a connection with the new name already
            exists, 422 if the resulting effective state has no connection
            material or too broad an allowlist.
        """
        url = f"{self._voice_gateway_url}/v1/byo/connections/{connection_id}"
        response = await self._request(
            "PUT",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return BYOConnection.model_validate(response.json())

    async def verify_byo_connection(self, connection_id: UUID) -> BYOConnection:
        """
        Re-run the connect health probe for a BYO connection.

        Calls ``POST /v1/byo/connections/{connection_id}/verify``. Advisory:
        never raises solely because the probe found the connection
        unreachable — check ``connection_health``/``health_detail`` on the
        response instead of catching an exception.

        Parameters
        ----------
        connection_id:
            UUID of the BYO connection to verify.

        Returns
        -------
        BYOConnection

        Raises
        ------
        AudactAPIError
            404 if the connection does not exist for this tenant.
        """
        url = f"{self._voice_gateway_url}/v1/byo/connections/{connection_id}/verify"
        response = await self._request("POST", url)
        return BYOConnection.model_validate(response.json())

    async def delete_byo_connection(self, connection_id: UUID) -> None:
        """
        Permanently delete a bring-your-own SIP trunk connection.

        Calls ``DELETE /v1/byo/connections/{connection_id}``. Tears down the
        connection's LiveKit trunks and Secrets Manager credential entries
        (best-effort), then removes the row. NEVER contacts the carrier —
        this is the customer's own trunk, not an Audact-provisioned one.

        Parameters
        ----------
        connection_id:
            UUID of the BYO connection to delete.

        Raises
        ------
        AudactAPIError
            404 if not found, 409 while any phone number is still attached —
            detach or delete those numbers first.
        """
        url = f"{self._voice_gateway_url}/v1/byo/connections/{connection_id}"
        await self._request("DELETE", url)

    async def get_byo_config(self) -> ByoConfig:
        """
        Get this deployment's SIP ingress configuration.

        Calls ``GET /v1/byo/config``. Values are deployment-wide, not
        tenant-specific — fetch this before creating any BYO connection to
        learn the SIP host/signaling IPs to configure on your own trunk's
        origination URI / allowed-callers list.

        Returns
        -------
        ByoConfig
        """
        url = f"{self._voice_gateway_url}/v1/byo/config"
        response = await self._request("GET", url)
        return ByoConfig.model_validate(response.json())


# ─────────────────────────────────────────────────────────────────────────────
# client.calls — SIP calls sub-client (voice-gateway, 8088)
#
# Outbound/inbound/browser calls, hangup, status, handover, transfers,
# plus trunks/routes/admission-url/ws-ticket. This is the first attribute
# sub-client — it holds a reference back to the parent AudactClient so it
# reuses `_request`/auth/base-URL configuration instead of duplicating
# transport logic. Existing flat methods on AudactClient are never renamed
# or removed; `client.calls.*` is purely additive namespacing for the new
# 22-op SIP surface.
# ─────────────────────────────────────────────────────────────────────────────

class CallsClient:
    """
    Sub-client for the SIP calls surface (``client.calls.*``).

    Backed by the Voice Gateway service (default ``http://localhost:8088``,
    ``voice_gateway_url``/``AUDACT_VOICE_GATEWAY_URL``). Authenticates with
    the parent client's tenant ``api_key`` — this surface has no distinct
    auth scheme of its own.

    Do not construct directly; use ``AudactClient(...).calls``.
    """

    def __init__(self, client: AudactClient) -> None:
        self._client = client

    @property
    def _base_url(self) -> str:
        return self._client._voice_gateway_url

    # ── Outbound / inbound / browser calls ──────────────────────────────────

    async def initiate_outbound_call(
        self,
        req: OutboundCallRequest,
        *,
        idempotency_key: str | None = None,
    ) -> OutboundCallResponse:
        """
        Initiate an outbound SIP call from a DID owned by the authenticated tenant.

        Calls ``POST /v1/sip/calls/outbound``. Creates a LiveKit room, dials
        the destination via the registered outbound SIP trunk, and returns
        the room details for the agent worker to join. When the agent has a
        jurisdiction configured, the server pre-checks the Policy Engine
        before sending the SIP INVITE, raising
        :class:`~audact.exceptions.AudactForbiddenError` (403,
        ``CALL_BLOCKED_BY_POLICY``) with a ``retry_after_seconds``/
        ``next_permitted_at`` detail when the block is time-bounded — use
        :meth:`~audact.client.AudactClient.check_calling_hours` to pre-check
        availability without attempting the call. Fail-open: if the Policy
        Engine is unreachable, the pre-dial check is skipped and the call
        proceeds.

        ``req.from_number`` and ``req.destination_number`` must be strict
        E.164 — a leading ``+``, the country code, then the subscriber number,
        digits only, 8 to 16 characters in total, no spaces, dashes, dots or
        parentheses (e.g. ``"+442079460958"``). Numbers are not normalised:
        ``"+44 20 7946 0958"`` is rejected with
        :class:`~audact.exceptions.AudactAPIError` (400 ``INVALID_REQUEST``).
        ``req.from_number`` must also be one of your own numbers
        (``GET /v1/numbers``).

        Parameters
        ----------
        req:
            The outbound call initiation payload.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key + body returns the original ``call_id``/``room_name`` (200)
            instead of placing a second call.

        Returns
        -------
        OutboundCallResponse
        """
        url = f"{self._base_url}/v1/sip/calls/outbound"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return OutboundCallResponse.model_validate(response.json())

    async def initiate_inbound_call(
        self,
        req: InboundCallRequest,
        *,
        idempotency_key: str | None = None,
    ) -> InboundCallResponse:
        """
        Process an inbound SIP INVITE notification from the telephony provider.

        Calls ``POST /v1/sip/calls/inbound``. Creates a LiveKit room, looks
        up the routing rule for the called DID, and returns the room name
        for the agent worker to join. If the tenant has a pre-connect
        ``admission_url`` configured, it is POSTed to before the room is
        created (500 ms bound, fails open to accept on timeout/error); an
        explicit reject response raises
        :class:`~audact.exceptions.AudactForbiddenError`
        (403, ``CALL_REJECTED_BY_ADMISSION``).

        Parameters
        ----------
        req:
            The inbound call notification payload.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key + body returns the original ``call_id``/``room_name`` (200)
            instead of processing a duplicate INVITE.

        Returns
        -------
        InboundCallResponse
        """
        url = f"{self._base_url}/v1/sip/calls/inbound"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return InboundCallResponse.model_validate(response.json())

    async def create_browser_call(
        self,
        req: BrowserCallRequest,
        *,
        idempotency_key: str | None = None,
    ) -> BrowserCallResponse:
        """
        Start a browser test call.

        Calls ``POST /v1/sip/calls/browser``. Creates a LiveKit room and
        returns a signed participant token for the browser to join via
        WebRTC; the agent is automatically dispatched.

        Parameters
        ----------
        req:
            The browser call request payload (``agent_id`` obtainable from
            ``GET /v1/agents``, i.e. ``client.agents.list_agents``).
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key + body returns the original ``call_id``/LiveKit token (200)
            instead of creating a second room.

        Returns
        -------
        BrowserCallResponse
            ``livekit_url`` + ``livekit_token`` for the browser client to
            join the room. Treat ``livekit_token`` as a short-lived secret;
            do not log it.
        """
        url = f"{self._base_url}/v1/sip/calls/browser"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return BrowserCallResponse.model_validate(response.json())

    # ── Lifecycle: hangup / status ───────────────────────────────────────────

    async def hangup_call(self, call_id: UUID) -> HangupResponse:
        """
        Terminate an active call by deleting the associated LiveKit room.

        Calls ``POST /v1/sip/calls/{call_id}/hangup``. Deleting the room
        disconnects all participants and triggers a SIP BYE. Calls owned by
        a different tenant return 404 (not 403) to avoid information leakage.

        Parameters
        ----------
        call_id:
            UUID of the call to terminate.

        Returns
        -------
        HangupResponse
        """
        url = f"{self._base_url}/v1/sip/calls/{call_id}/hangup"
        response = await self._client._request("POST", url)
        return HangupResponse.model_validate(response.json())

    async def get_call_status(self, call_id: UUID) -> CallStatusResponse:
        """
        Get the current lifecycle status of a call.

        Calls ``GET /v1/sip/calls/{call_id}/status``. This is the polling
        alternative to the ``GET /v1/ws/calls`` WebSocket stream for callers
        (e.g. MCP bridges) that cannot receive webhooks or open a WebSocket
        connection. Calls owned by a different tenant return 404 (not 403)
        to avoid information leakage.

        Parameters
        ----------
        call_id:
            UUID of the call to look up. Obtained from the ``call_id`` field
            returned by :meth:`initiate_inbound_call`,
            :meth:`initiate_outbound_call`, or :meth:`create_browser_call`.

        Returns
        -------
        CallStatusResponse
        """
        url = f"{self._base_url}/v1/sip/calls/{call_id}/status"
        response = await self._client._request("GET", url)
        return CallStatusResponse.model_validate(response.json())

    # ── Warm handover ────────────────────────────────────────────────────────

    async def initiate_handover(self, call_id: UUID, req: HandoverRequest) -> HandoverResponse:
        """
        Start a warm handover for an active call.

        Calls ``POST /v1/sip/calls/{call_id}/handover``. The human
        supervisor is dialed into a private supervisor room and briefed
        (whisper) before being bridged into the caller's room. The caller is
        kept on hold and is never disconnected — this is deliberately NOT a
        cold SIP REFER. Returns a ``handover_id`` that must be used to poll
        :meth:`get_handover` and to drive subsequent lifecycle transitions.
        The destination phone number is hashed immediately; the raw number
        is never stored or logged.

        Parameters
        ----------
        call_id:
            UUID of the active call to hand over.
        req:
            The handover request payload.

        Returns
        -------
        HandoverResponse
        """
        url = f"{self._base_url}/v1/sip/calls/{call_id}/handover"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
        )
        return HandoverResponse.model_validate(response.json())

    async def get_handover(self, handover_id: UUID) -> HandoverStateResponse:
        """
        Get the current state of a warm handover session.

        Calls ``GET /v1/sip/handovers/{handover_id}``. Includes the
        lifecycle state, ``summary_source``, and ``delivery_status``.
        Intended for dashboard polling and reconciliation while a handover
        is in flight. The destination phone number is never returned; only
        its SHA-256 hash.

        Parameters
        ----------
        handover_id:
            UUID of the handover session.

        Returns
        -------
        HandoverStateResponse
        """
        url = f"{self._base_url}/v1/sip/handovers/{handover_id}"
        response = await self._client._request("GET", url)
        return HandoverStateResponse.model_validate(response.json())

    # ── SIP REFER transfers ──────────────────────────────────────────────────

    async def initiate_transfer(
        self,
        call_id: UUID,
        req: TransferRequest,
        *,
        idempotency_key: str | None = None,
    ) -> TransferResponse:
        """
        Initiate a SIP REFER to transfer an active call to a new destination.

        Calls ``POST /v1/sip/calls/{call_id}/transfer``. Returns a
        ``transfer_id`` that must be used to report subsequent lifecycle
        transitions via :meth:`bridge_transfer`/:meth:`cancel_transfer`/
        :meth:`end_transfer`. The destination phone number is hashed
        immediately; the raw number is never stored or logged.

        Parameters
        ----------
        call_id:
            UUID of the active call to transfer.
        req:
            The transfer request payload.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — retrying with the
            same key replays the original response instead of initiating a
            second transfer.

        Returns
        -------
        TransferResponse
        """
        url = f"{self._base_url}/v1/sip/calls/{call_id}/transfer"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return TransferResponse.model_validate(response.json())

    async def get_transfer_state(self, transfer_id: UUID) -> TransferSessionResponse:
        """
        Get the current state of a SIP transfer session.

        Calls ``GET /v1/sip/transfers/{transfer_id}``. This is the polling
        alternative to the ``transfer_started``/``transfer_bridged``/
        ``transfer_cancelled``/``transfer_ended`` webhook events for callers
        that cannot receive webhooks or open the ``GET /v1/ws/calls``
        WebSocket stream. The destination phone number is never returned;
        only its SHA-256 hash.

        Parameters
        ----------
        transfer_id:
            UUID of the transfer session.

        Returns
        -------
        TransferSessionResponse
        """
        url = f"{self._base_url}/v1/sip/transfers/{transfer_id}"
        response = await self._client._request("GET", url)
        return TransferSessionResponse.model_validate(response.json())

    async def bridge_transfer(self, transfer_id: UUID) -> TransferStateResponse:
        """
        Record that the transfer target has answered and both parties are connected.

        Calls ``POST /v1/sip/transfers/{transfer_id}/bridge``. Emits a
        ``transfer_bridged`` webhook event.

        Parameters
        ----------
        transfer_id:
            UUID of the transfer session.

        Returns
        -------
        TransferStateResponse
        """
        url = f"{self._base_url}/v1/sip/transfers/{transfer_id}/bridge"
        response = await self._client._request("POST", url)
        return TransferStateResponse.model_validate(response.json())

    async def cancel_transfer(self, transfer_id: UUID) -> TransferStateResponse:
        """
        Record that the SIP REFER failed or the transfer was aborted.

        Calls ``POST /v1/sip/transfers/{transfer_id}/cancel``. Emits a
        ``transfer_cancelled`` webhook event.

        Parameters
        ----------
        transfer_id:
            UUID of the transfer session.

        Returns
        -------
        TransferStateResponse
        """
        url = f"{self._base_url}/v1/sip/transfers/{transfer_id}/cancel"
        response = await self._client._request("POST", url)
        return TransferStateResponse.model_validate(response.json())

    async def end_transfer(self, transfer_id: UUID) -> TransferStateResponse:
        """
        Record that the transfer leg has disconnected after a successful bridge.

        Calls ``POST /v1/sip/transfers/{transfer_id}/end``. Emits a
        ``transfer_ended`` webhook event.

        Parameters
        ----------
        transfer_id:
            UUID of the transfer session.

        Returns
        -------
        TransferStateResponse
        """
        url = f"{self._base_url}/v1/sip/transfers/{transfer_id}/end"
        response = await self._client._request("POST", url)
        return TransferStateResponse.model_validate(response.json())

    # ── SIP trunks ───────────────────────────────────────────────────────────

    async def list_trunks(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> ListTrunksResponse:
        """
        List inbound and outbound SIP trunks registered for the authenticated tenant.

        Calls ``GET /v1/sip/trunks``. Use this to discover which trunks are
        available before registering routes (:meth:`create_dispatch_rule`)
        or initiating calls (:meth:`initiate_outbound_call`).
        ``inbound_trunks`` supports cursor-based pagination (pass
        ``next_cursor`` from a prior response as ``cursor``); default page
        size is 50 (max 200). ``outbound_trunks`` is always returned in full
        (at most one trunk per tenant).

        Parameters
        ----------
        cursor:
            Opaque pagination cursor from a previous page's ``next_cursor``.
        limit:
            Maximum inbound trunks per page (server default 50, max 200).

        Returns
        -------
        ListTrunksResponse
            Returned as-is rather than reshaped into the generic
            :class:`~audact.models.Page` convention, since it mixes a
            paginated (``inbound_trunks``) and a non-paginated
            (``outbound_trunks``) list in one body.
        """
        params: dict[str, str] = {}
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)

        url = f"{self._base_url}/v1/sip/trunks"
        response = await self._client._request("GET", url, params=params or None)
        return ListTrunksResponse.model_validate(response.json())

    async def create_inbound_trunk(
        self,
        req: CreateInboundTrunkRequest,
        *,
        idempotency_key: str | None = None,
    ) -> CreateInboundTrunkResponse:
        """
        Register an inbound SIP trunk for the authenticated tenant.

        Calls ``POST /v1/sip/trunks/inbound``. The trunk maps a set of DID
        phone numbers to the tenant's account and configures SIP
        authentication credentials stored in AWS Secrets Manager. Use the
        ARNs returned by the SIP provisioner or supply your own Secrets
        Manager ARNs.

        Parameters
        ----------
        req:
            The inbound trunk registration payload.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key + body returns the cached response (200) instead of
            registering a second trunk; the same key with a different body
            raises :class:`~audact.exceptions.AudactAPIError` (409).

        Returns
        -------
        CreateInboundTrunkResponse
        """
        url = f"{self._base_url}/v1/sip/trunks/inbound"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return CreateInboundTrunkResponse.model_validate(response.json())

    async def create_outbound_trunk(
        self,
        req: CreateOutboundTrunkRequest,
        *,
        idempotency_key: str | None = None,
    ) -> CreateOutboundTrunkResponse:
        """
        Register an outbound SIP trunk for the authenticated tenant.

        Calls ``POST /v1/sip/trunks/outbound``. The trunk configures a SIP
        proxy host and authentication credentials used when initiating
        outbound calls via :meth:`initiate_outbound_call`. Credentials must
        be stored in AWS Secrets Manager; supply the ARNs here.

        Parameters
        ----------
        req:
            The outbound trunk registration payload.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key + body returns the cached response (200) instead of
            registering a second trunk; the same key with a different body
            raises :class:`~audact.exceptions.AudactAPIError` (409).

        Returns
        -------
        CreateOutboundTrunkResponse
        """
        url = f"{self._base_url}/v1/sip/trunks/outbound"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return CreateOutboundTrunkResponse.model_validate(response.json())

    # ── SIP dispatch rules (routes) ──────────────────────────────────────────

    async def list_dispatch_rules(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> ListRoutesResponse:
        """
        List SIP dispatch rules (routes) registered for the authenticated tenant.

        Calls ``GET /v1/sip/routes``. Each route maps an inbound DID to an
        agent. Use :meth:`list_trunks` to find available trunks and
        :meth:`create_dispatch_rule` to create new routes. Supports
        cursor-based pagination (pass ``next_cursor`` from a prior response
        as ``cursor``); default page size is 50 (max 200).

        Parameters
        ----------
        cursor:
            Opaque pagination cursor from a previous page's ``next_cursor``.
        limit:
            Maximum results per page (server default 50, max 200).

        Returns
        -------
        ListRoutesResponse
        """
        params: dict[str, str] = {}
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)

        url = f"{self._base_url}/v1/sip/routes"
        response = await self._client._request("GET", url, params=params or None)
        return ListRoutesResponse.model_validate(response.json())

    async def create_dispatch_rule(
        self,
        req: CreateDispatchRuleRequest,
        *,
        idempotency_key: str | None = None,
    ) -> CreateDispatchRuleResponse:
        """
        Map an inbound DID to an agent.

        Calls ``POST /v1/sip/routes``. Creates a routing rule that
        dispatches inbound calls arriving on a specific DID phone number to
        a given agent; when an inbound call arrives on the DID, the voice
        gateway starts the agent worker for the mapped agent. The DID must
        already be registered via :meth:`create_inbound_trunk`.

        Parameters
        ----------
        req:
            The route mapping payload (``did``, ``agent_id``).
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key + body returns the cached response (200) instead of
            creating a second route; the same key with a different body
            raises :class:`~audact.exceptions.AudactAPIError` (409).

        Returns
        -------
        CreateDispatchRuleResponse
        """
        url = f"{self._base_url}/v1/sip/routes"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return CreateDispatchRuleResponse.model_validate(response.json())

    # ── Admission URL (pre-connect inbound-call hook) ────────────────────────

    async def get_admission_url(self) -> AdmissionURLResponse:
        """
        Get the tenant's configured pre-connect admission hook URL.

        Calls ``GET /v1/sip/admission-url``. Returns the tenant's
        configured ``admission_url``, or an empty string when the hook is
        disabled.

        Returns
        -------
        AdmissionURLResponse
        """
        url = f"{self._base_url}/v1/sip/admission-url"
        response = await self._client._request("GET", url)
        return AdmissionURLResponse.model_validate(response.json())

    async def set_admission_url(self, req: SetAdmissionURLRequest) -> AdmissionURLResponse:
        """
        Set the tenant's pre-connect admission hook URL.

        Calls ``PUT /v1/sip/admission-url``. Sets the tenant's
        ``admission_url`` — the http(s) endpoint Audact POSTs
        ``{call_id, caller_number, called_did, agent_id, trunk_id}`` to
        before connecting each inbound call, honouring
        ``{action, dynamic_variables, metadata}`` in the response
        (500ms bounded, fails open). Pass an empty ``admission_url`` to
        disable the hook. The URL is validated (http(s) scheme; localhost
        and private/loopback/link-local literal IPs are rejected).

        Parameters
        ----------
        req:
            The admission URL payload.

        Returns
        -------
        AdmissionURLResponse
        """
        url = f"{self._base_url}/v1/sip/admission-url"
        response = await self._client._request(
            "PUT",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
        )
        return AdmissionURLResponse.model_validate(response.json())

    # ── WebSocket ticket ──────────────────────────────────────────────────────

    async def create_ws_ticket(self) -> WsTicketResponse:
        """
        Issue a single-use WebSocket authentication ticket.

        Calls ``POST /v1/ws/ticket``. Issues a ticket valid for 30 seconds;
        pass it as the ``?ticket=`` query parameter when connecting to
        ``GET /v1/ws/calls`` to authenticate the WebSocket upgrade. The
        ticket is consumed on first use and cannot be replayed. MCP and
        other non-WebSocket clients cannot open the stream at all — poll
        the evidence-layer's ``GET /v1/calls/{call_id}/summary`` (or
        ``GET /v1/calls`` for a filtered list) for call status instead of
        requesting a ticket for this real-time stream.

        Returns
        -------
        WsTicketResponse
        """
        url = f"{self._base_url}/v1/ws/ticket"
        response = await self._client._request("POST", url)
        return WsTicketResponse.model_validate(response.json())


# ─────────────────────────────────────────────────────────────────────────────
# WebhooksClient — client.webhooks.* — tenant-management (8085)
# ─────────────────────────────────────────────────────────────────────────────

class WebhooksClient:
    """
    Sub-client for the webhook subscriptions surface (``client.webhooks.*``).

    Backed by the Tenant Management service (default
    ``http://localhost:8085``, ``tenant_management_url``/
    ``AUDACT_TENANT_MANAGEMENT_URL`` — the host is configurable).
    Authenticates with the parent client's tenant ``api_key``; this surface
    has no distinct auth scheme of its own.

    Do not construct directly; use ``AudactClient(...).webhooks``.
    """

    def __init__(self, client: AudactClient) -> None:
        self._client = client

    @property
    def _base_url(self) -> str:
        return self._client._tenant_management_url

    async def list_webhooks(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Page[WebhookEndpoint]:
        """
        List webhook endpoints for the authenticated tenant.

        Calls ``GET /v1/webhooks``.

        Parameters
        ----------
        cursor:
            Opaque pagination cursor from a previous page's ``next_cursor``
            (cursor pagination convention; the id of the last item on the
            previous page).
        limit:
            Page size (default 20, server caps at 100).

        Returns
        -------
        Page[WebhookEndpoint]
            ``items`` is the page of endpoints; pass ``next_cursor`` back as
            ``cursor`` while ``has_more`` is ``True`` to fetch subsequent
            pages.
        """
        params: dict[str, str] = {}
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)
        url = f"{self._base_url}/v1/webhooks"
        response = await self._client._request("GET", url, params=params or None)
        parsed = ListWebhooksResponse.model_validate(response.json())
        return Page[WebhookEndpoint](
            items=parsed.items, has_more=parsed.has_more, next_cursor=parsed.next_cursor
        )

    async def create_webhook(
        self,
        req: CreateWebhookRequest,
        *,
        idempotency_key: str | None = None,
    ) -> CreateWebhookResponse:
        """
        Create a new webhook endpoint for the authenticated tenant.

        Calls ``POST /v1/webhooks``. ``req.url`` must be HTTPS;
        ``req.events`` must be known event type strings (see
        :meth:`list_webhook_event_types`); ``req.agent_id`` is required
        when ``req.scope == "agent"``. When this is the tenant's first
        webhook endpoint, the response also provisions the per-tenant HMAC
        signing secret and includes it once as ``signing_secret`` — store
        it securely, as no later call (including subsequent creations or
        :meth:`get_webhook_secret_status`) will return it again.

        Parameters
        ----------
        req:
            The webhook endpoint creation payload.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — duplicate requests
            with the same key return the original endpoint (200 OK) for 24
            hours instead of creating a second one.

        Returns
        -------
        CreateWebhookResponse
        """
        url = f"{self._base_url}/v1/webhooks"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return CreateWebhookResponse.model_validate(response.json())

    async def get_webhook(self, endpoint_id: UUID) -> WebhookEndpoint:
        """
        Get a webhook endpoint by ID.

        Calls ``GET /v1/webhooks/{id}``. Enforces tenant ownership.

        Parameters
        ----------
        endpoint_id:
            UUID of the webhook endpoint — get this from
            :meth:`list_webhooks` or the :meth:`create_webhook` response.

        Returns
        -------
        WebhookEndpoint
        """
        url = f"{self._base_url}/v1/webhooks/{endpoint_id}"
        response = await self._client._request("GET", url)
        return WebhookEndpoint.model_validate(response.json())

    async def update_webhook(
        self, endpoint_id: UUID, req: UpdateWebhookRequest
    ) -> WebhookEndpoint:
        """
        Update a webhook endpoint.

        Calls ``PUT /v1/webhooks/{id}``. Only fields set on ``req`` are
        changed (partial update despite the ``PUT`` verb).

        Parameters
        ----------
        endpoint_id:
            UUID of the webhook endpoint to update.
        req:
            Fields to update.

        Returns
        -------
        WebhookEndpoint
        """
        url = f"{self._base_url}/v1/webhooks/{endpoint_id}"
        response = await self._client._request(
            "PUT",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
        )
        return WebhookEndpoint.model_validate(response.json())

    async def delete_webhook(self, endpoint_id: UUID) -> None:
        """
        Permanently delete a webhook endpoint.

        Calls ``DELETE /v1/webhooks/{id}``.

        Parameters
        ----------
        endpoint_id:
            UUID of the webhook endpoint to delete.
        """
        url = f"{self._base_url}/v1/webhooks/{endpoint_id}"
        await self._client._request("DELETE", url)

    async def test_webhook(self, endpoint_id: UUID) -> WebhookTestPingResponse:
        """
        Send a synthetic ``webhook.test`` event to an endpoint.

        Calls ``POST /v1/webhooks/{id}/test``. Uses the tenant's current
        signing key; the delivery is a single attempt with no retries and
        is not persisted to the delivery log.

        Parameters
        ----------
        endpoint_id:
            UUID of the webhook endpoint to ping.

        Returns
        -------
        WebhookTestPingResponse
        """
        url = f"{self._base_url}/v1/webhooks/{endpoint_id}/test"
        response = await self._client._request("POST", url)
        return WebhookTestPingResponse.model_validate(response.json())

    async def list_webhook_deliveries(
        self,
        endpoint_id: UUID,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ListWebhookDeliveriesResponse:
        """
        List delivery attempts for a webhook endpoint.

        Calls ``GET /v1/webhooks/{id}/deliveries``. Enforces tenant
        ownership. This endpoint is **offset**-paginated (``limit``/
        ``offset``), unlike the cursor-based :meth:`list_webhooks` — its
        wire shape carries a ``total`` count instead of
        ``has_more``/``next_cursor``.

        Parameters
        ----------
        endpoint_id:
            UUID of the webhook endpoint.
        limit:
            Maximum number of records to return (default 50, max 200).
        offset:
            Number of records to skip (default 0).

        Returns
        -------
        ListWebhookDeliveriesResponse
            ``deliveries`` is the page of delivery records; ``total`` is
            the full record count.
        """
        params: dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        url = f"{self._base_url}/v1/webhooks/{endpoint_id}/deliveries"
        response = await self._client._request("GET", url, params=params or None)
        return ListWebhookDeliveriesResponse.model_validate(response.json())

    async def resend_webhook_delivery(self, delivery_id: str) -> ResendWebhookDeliveryResponse:
        """
        Re-queue a dead-lettered webhook delivery.

        Calls ``POST /v1/webhooks/deliveries/{id}/resend``. Re-queues a
        delivery that is in ``dead_letter`` status back to the appropriate
        Redis stream and resets its status to ``pending``. The delivery
        must belong to an endpoint owned by the authenticated tenant.

        Parameters
        ----------
        delivery_id:
            ID of the delivery to resend (e.g. ``"dlv_<uuid>"``) — get this
            from :meth:`list_webhook_deliveries`.

        Returns
        -------
        ResendWebhookDeliveryResponse
        """
        from urllib.parse import quote

        url = f"{self._base_url}/v1/webhooks/deliveries/{quote(delivery_id, safe='')}/resend"
        response = await self._client._request("POST", url)
        return ResendWebhookDeliveryResponse.model_validate(response.json())

    async def list_webhook_event_types(self) -> ListWebhookEventTypesResponse:
        """
        List all supported webhook event type strings.

        Calls ``GET /v1/webhooks/event-types``. Returns each event type's
        human-readable description and category grouping — use this to
        discover valid values for :attr:`CreateWebhookRequest.events`.

        Returns
        -------
        ListWebhookEventTypesResponse
        """
        url = f"{self._base_url}/v1/webhooks/event-types"
        response = await self._client._request("GET", url)
        return ListWebhookEventTypesResponse.model_validate(response.json())

    async def get_webhook_event_schema(self, event_type: str) -> WebhookEventSchema:
        """
        Get the example payload schema for a webhook event type.

        Calls ``GET /v1/webhooks/event-schemas?type={type}``. Returns a
        fully-populated, illustrative example of the JSON envelope
        delivered to a customer endpoint for the given event type, plus a
        PII-handling note and a ``schema_version``. Use
        :meth:`list_webhook_event_types` first to discover valid ``type``
        values.

        Parameters
        ----------
        event_type:
            Webhook event type, e.g. ``"call_ended"`` or
            ``"compliance.violation_detected"``.

        Returns
        -------
        WebhookEventSchema
        """
        url = f"{self._base_url}/v1/webhooks/event-schemas"
        response = await self._client._request("GET", url, params={"type": event_type})
        return WebhookEventSchema.model_validate(response.json())

    async def get_webhook_secret_status(self) -> WebhookSecretStatus:
        """
        Get the current rotation state of the tenant's webhook signing secret.

        Calls ``GET /v1/webhooks/secrets/status``. Includes whether the
        72-hour dual-signature grace period is active and when it ends.
        Never returns the plaintext secret itself.

        Returns
        -------
        WebhookSecretStatus
        """
        url = f"{self._base_url}/v1/webhooks/secrets/status"
        response = await self._client._request("GET", url)
        return WebhookSecretStatus.model_validate(response.json())

    async def rotate_webhook_secret(self) -> RotateWebhookSecretResponse:
        """
        Rotate the tenant's webhook HMAC signing secret.

        Calls ``POST /v1/webhooks/secrets/rotate``. The previous key
        remains valid for 72 hours (dual-signature grace period) so
        receivers can verify in-flight deliveries. The response includes
        the new plaintext ``signing_secret`` exactly once (Stripe/Twilio
        "reveal once" pattern) — store it securely; it is never returned
        again by any endpoint.

        Returns
        -------
        RotateWebhookSecretResponse
        """
        url = f"{self._base_url}/v1/webhooks/secrets/rotate"
        response = await self._client._request("POST", url)
        return RotateWebhookSecretResponse.model_validate(response.json())


# ─────────────────────────────────────────────────────────────────────────────
# AgentsClient — agent-worker (8089), client.agents.*
# ─────────────────────────────────────────────────────────────────────────────

_VOICE_DEFAULT_FILENAME = "clip.mp3"
_VOICE_DEFAULT_CONTENT_TYPE = "audio/mpeg"


class AgentsClient:
    """
    Sub-client for the Agent Worker's voice agent management surface
    (``client.agents.*``).

    Backed by the Agent Worker service (default ``http://localhost:8089``,
    ``agent_worker_url``/``AUDACT_AGENT_WORKER_URL``). Authenticates with
    the parent client's tenant ``api_key`` — this surface has no distinct
    auth scheme of its own. Covers agent CRUD (full ``PUT`` and partial
    ``PATCH``), duplication, the TTS voice catalog, and pipeline-load
    status.

    Do not construct directly; use ``AudactClient(...).agents``.
    """

    def __init__(self, client: AudactClient) -> None:
        self._client = client

    @property
    def _base_url(self) -> str:
        return self._client._agent_worker_url

    # ── Agent CRUD ────────────────────────────────────────────────────────────

    async def list_agents(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Page[Agent]:
        """
        List voice agents for the authenticated tenant.

        Calls ``GET /v1/agents``. Returns a page of non-deleted agents,
        ordered by ``created_at`` DESC. Uses cursor pagination — pass the
        returned ``next_cursor`` as ``cursor`` to fetch the next page.

        Parameters
        ----------
        cursor:
            Opaque pagination cursor from a previous page's ``next_cursor``
            (cursor pagination convention).
        limit:
            Page size (server default 50, max 200).

        Returns
        -------
        Page[Agent]
            ``items`` is the page of agents; pass ``next_cursor`` back as
            ``cursor`` while ``has_more`` is ``True`` to fetch subsequent
            pages.
        """
        params: dict[str, str] = {}
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)
        url = f"{self._base_url}/v1/agents"
        response = await self._client._request("GET", url, params=params or None)
        parsed = ListAgentsResponse.model_validate(response.json())
        return Page[Agent](
            items=parsed.agents, has_more=parsed.has_more, next_cursor=parsed.next_cursor
        )

    async def create_agent(
        self,
        req: CreateAgentRequest,
        *,
        idempotency_key: str | None = None,
    ) -> CreateAgentResponse:
        """
        Create a new voice agent for the authenticated tenant.

        Calls ``POST /v1/agents``. When a config provisioner is wired
        server-side, this also atomically provisions a per-agent
        Configuration (``configuration_id`` on the response).

        ``tts_provider`` is ``"voxtral"`` (default) or ``"elevenlabs"``;
        ``tts_model`` is optional (omit it for the provider default) and must
        suit the provider. ``voice_id`` must belong to the chosen provider —
        take it from :meth:`list_voices` — or the API answers 400 naming the
        offending field.

        Parameters
        ----------
        req:
            Agent creation payload.
        idempotency_key:
            Optional ``Idempotency-Key`` header value.

        Returns
        -------
        CreateAgentResponse

        Raises
        ------
        AudactAPIError
            400 on a validation error (missing name, invalid llm_provider,
            unsupported jurisdiction, or temperature outside [0.0, 2.0]);
            404 if a supplied ``tool_id`` does not exist for this tenant.
        """
        url = f"{self._base_url}/v1/agents"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return CreateAgentResponse.model_validate(response.json())

    async def get_agent(self, agent_id: UUID) -> Agent:
        """
        Get a single voice agent by ID.

        Calls ``GET /v1/agents/{agent_id}``. Returns the full agent row,
        including ``configuration_id``, ``assigned_phone``, ``tool_ids``,
        ``version``, and ``jurisdiction``.

        Parameters
        ----------
        agent_id:
            UUID of the agent.

        Returns
        -------
        Agent

        Raises
        ------
        AudactNotFoundError
            404 for a missing, deleted, or cross-tenant agent (no
            information leak).
        """
        url = f"{self._base_url}/v1/agents/{agent_id}"
        response = await self._client._request("GET", url)
        return Agent.model_validate(response.json())

    async def update_agent(
        self,
        agent_id: UUID,
        req: UpdateAgentRequest,
        *,
        idempotency_key: str | None = None,
    ) -> Agent:
        """
        Full-replacement update of the agent row.

        Calls ``PUT /v1/agents/{agent_id}``. The server-managed ``version``
        counter is incremented atomically.

        Parameters
        ----------
        agent_id:
            UUID of the agent to update.
        req:
            All mutable fields, replaced in full.
        idempotency_key:
            Optional ``Idempotency-Key`` header value.

        Returns
        -------
        Agent

        Raises
        ------
        AudactAPIError
            400/401/404 as appropriate.
        """
        url = f"{self._base_url}/v1/agents/{agent_id}"
        response = await self._client._request(
            "PUT",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return Agent.model_validate(response.json())

    async def patch_agent(
        self,
        agent_id: UUID,
        req: PatchAgentRequest,
        *,
        idempotency_key: str | None = None,
    ) -> Agent:
        """
        Partially update the agent row — only the supplied fields change;
        omitted fields keep their current value.

        Calls ``PATCH /v1/agents/{agent_id}``.

        Parameters
        ----------
        agent_id:
            UUID of the agent to update.
        req:
            Only the fields to change.
        idempotency_key:
            Optional ``Idempotency-Key`` header value.

        Returns
        -------
        Agent

        Raises
        ------
        AudactAPIError
            400/401/404 as appropriate.
        """
        url = f"{self._base_url}/v1/agents/{agent_id}"
        response = await self._client._request(
            "PATCH",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return Agent.model_validate(response.json())

    async def delete_agent(self, agent_id: UUID) -> DeleteAgentResponse:
        """
        Soft-delete a voice agent.

        Calls ``DELETE /v1/agents/{agent_id}``. Releases any assigned phone
        number back to available, and deactivates its per-agent
        Configuration when one is set — all within a single transaction.

        Parameters
        ----------
        agent_id:
            UUID of the agent to delete.

        Returns
        -------
        DeleteAgentResponse

        Raises
        ------
        AudactNotFoundError
            404 if not found (cross-tenant agents also return 404, to
            prevent information leakage).
        """
        url = f"{self._base_url}/v1/agents/{agent_id}"
        response = await self._client._request("DELETE", url)
        return DeleteAgentResponse.model_validate(response.json())

    async def duplicate_agent(self, agent_id: UUID) -> Agent:
        """
        Duplicate a voice agent.

        Calls ``POST /v1/agents/{agent_id}/duplicate``. Creates a copy of
        the agent with a new ``agent_id``, name suffixed with ``" (Copy)"``,
        status ``"draft"``, and version 1. Phone number assignments are not
        copied; a provisioned Configuration is cloned when present.

        Parameters
        ----------
        agent_id:
            UUID of the source agent.

        Returns
        -------
        Agent

        Raises
        ------
        AudactNotFoundError
            404 if the source agent is not found.
        """
        url = f"{self._base_url}/v1/agents/{agent_id}/duplicate"
        response = await self._client._request("POST", url)
        return Agent.model_validate(response.json())

    # ── Voices ─────────────────────────────────────────────────────────────────

    async def list_voices(
        self,
        *,
        language: str | None = None,
        provider: TTSProvider | None = None,
        limit: int | None = None,
    ) -> dict[str, VoiceProvider]:
        """
        Return the catalog of available TTS voices, grouped by provider.

        Calls ``GET /v1/voices``. Includes built-in presets, platform-admin
        cloned voices and every voice in the platform ElevenLabs account. Each
        voice lists the ``languages`` it speaks; each provider lists its
        ``models`` and their languages. Use the ``voice_id`` values when
        creating or updating agents.

        Parameters
        ----------
        language:
            Keep only voices (and models) that speak this language, e.g.
            ``"de"`` or ``"de-DE"``; native speakers come first.
        provider:
            Keep only this TTS provider (``"voxtral"`` or ``"elevenlabs"``).
        limit:
            Maximum voices per provider, 1-1000 (server default 100). Each
            provider reports ``total`` and ``truncated``.

        Returns
        -------
        dict[str, VoiceProvider]
            Keyed by provider name: ``"voxtral"`` and ``"elevenlabs"``.
        """
        url = f"{self._base_url}/v1/voices"
        params: dict[str, str | list[str]] = {
            k: v for k, v in (("language", language), ("provider", provider)) if v
        }
        if limit is not None:
            params["limit"] = str(limit)
        response = await self._client._request("GET", url, params=params or None)
        raw = response.json()
        return {name: VoiceProvider.model_validate(entry) for name, entry in raw.items()}

    async def create_voice(
        self,
        audio: bytes | IO[bytes],
        name: str,
        consent_confirmed: bool,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        language: str | None = None,
        accent: str | None = None,
        gender: str | None = None,
        style: str | None = None,
        idempotency_key: str | None = None,
    ) -> CreateVoiceResponse:
        """
        Upload a ~10s reference clip and clone it into a new TTS voice
        (platform admin).

        Calls ``POST /v1/voices`` as a ``multipart/form-data`` request (see
        :meth:`~audact.client.AudactClient._request`'s ``files=`` branch,
        which omits ``Content-Type`` so httpx computes the correct
        ``multipart/form-data; boundary=...`` value itself). Requires
        explicit consent: ``consent_confirmed`` must be ``True``.

        Parameters
        ----------
        audio:
            Reference clip (~10s), raw bytes or an open, readable binary
            file handle. ``audio/mpeg`` or ``audio/wav``, max 2 MiB.
        name:
            Display name for the new voice.
        consent_confirmed:
            Must be ``True`` — confirms consent to clone the supplied voice
            sample.
        filename:
            Filename to send. Defaults to ``"clip.mp3"``.
        content_type:
            MIME type to send. Defaults to ``"audio/mpeg"``.
        language, accent, gender, style:
            Optional voice metadata.
        idempotency_key:
            Optional ``Idempotency-Key`` header value.

        Returns
        -------
        CreateVoiceResponse

        Raises
        ------
        AudactAPIError
            400 on a missing/invalid field or unsupported audio format; 422
            if the sample is rejected by content moderation
            (``VOICE_REJECTED``); 503 if voice cloning is not configured
            for this deployment.
        """
        url = f"{self._base_url}/v1/voices"
        files = {
            "audio": (
                filename or _VOICE_DEFAULT_FILENAME,
                audio,
                content_type or _VOICE_DEFAULT_CONTENT_TYPE,
            )
        }
        data: dict[str, str] = {
            "name": name,
            "consent_confirmed": "true" if consent_confirmed else "false",
        }
        if language is not None:
            data["language"] = language
        if accent is not None:
            data["accent"] = accent
        if gender is not None:
            data["gender"] = gender
        if style is not None:
            data["style"] = style
        response = await self._client._request(
            "POST", url, files=files, data=data, idempotency_key=idempotency_key
        )
        return CreateVoiceResponse.model_validate(response.json())

    async def get_voice(self, voice_id: str) -> Voice:
        """
        Get a single voice by ID.

        Calls ``GET /v1/voices/{voice_id}``. Returns a built-in preset or a
        platform-admin cloned voice.

        Parameters
        ----------
        voice_id:
            Voice ID.

        Returns
        -------
        Voice

        Raises
        ------
        AudactNotFoundError
            404 if the voice does not exist.
        """
        from urllib.parse import quote

        url = f"{self._base_url}/v1/voices/{quote(voice_id, safe='')}"
        response = await self._client._request("GET", url)
        return Voice.model_validate(response.json())

    async def delete_voice(self, voice_id: str) -> None:
        """
        Remove a platform-admin cloned voice.

        Calls ``DELETE /v1/voices/{voice_id}``. Deletes it upstream and
        soft-deletes the local row. Built-in preset voices cannot be
        deleted.

        Parameters
        ----------
        voice_id:
            Voice ID.

        Raises
        ------
        AudactAPIError
            400 if the voice is a built-in preset; 404 if not found; 502 if
            the upstream cloning provider fails.
        """
        from urllib.parse import quote

        url = f"{self._base_url}/v1/voices/{quote(voice_id, safe='')}"
        await self._client._request("DELETE", url)

    # ── Pipeline status ─────────────────────────────────────────────────────────

    async def get_pipeline_status(self) -> PipelineStatusResponse:
        """
        Get the current number of active voice pipeline instances running
        in the agent-worker.

        Calls ``GET /v1/pipeline/status``. Each active LiveKit room with an
        assigned agent contributes one (STT→LLM→TTS chain).

        Returns
        -------
        PipelineStatusResponse
        """
        url = f"{self._base_url}/v1/pipeline/status"
        response = await self._client._request("GET", url)
        return PipelineStatusResponse.model_validate(response.json())


class ToolsClient:
    """
    Sub-client for the Agent Worker's tool management surface
    (``client.tools.*``).

    Backed by the Agent Worker service (default ``http://localhost:8089``,
    ``agent_worker_url``/``AUDACT_AGENT_WORKER_URL``). Authenticates with
    the parent client's tenant ``api_key`` — this surface has no distinct
    auth scheme of its own. Covers custom function-calling tool CRUD
    (including full ``PUT`` and partial ``PATCH``), platform-tool
    validation (``test_tool``), and the agent-tool attachment lifecycle
    (list/attach/detach).

    Do not construct directly; use ``AudactClient(...).tools``.
    """

    def __init__(self, client: AudactClient) -> None:
        self._client = client

    @property
    def _base_url(self) -> str:
        return self._client._agent_worker_url

    # ── Tool CRUD ────────────────────────────────────────────────────────────

    async def list_tools(
        self,
        *,
        name: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Page[ToolConfig]:
        """
        List tools for the authenticated tenant.

        Calls ``GET /v1/tools``. Returns all non-deleted tools, with
        optional exact ``name`` filtering and cursor-based pagination.
        Results are ordered by ``created_at`` DESC.

        Parameters
        ----------
        name:
            Optional exact name filter.
        cursor:
            Opaque pagination cursor from a previous page's ``next_cursor``
            (cursor pagination convention).
        limit:
            Page size (1–100, server default 20).

        Returns
        -------
        Page[ToolConfig]
            ``items`` is the page of tools; pass ``next_cursor`` back as
            ``cursor`` while ``has_more`` is ``True`` to fetch subsequent
            pages.
        """
        params: dict[str, str] = {}
        if name is not None:
            params["name"] = name
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)
        url = f"{self._base_url}/v1/tools"
        response = await self._client._request("GET", url, params=params or None)
        parsed = ListToolsResponse.model_validate(response.json())
        return Page[ToolConfig](
            items=parsed.tools, has_more=parsed.has_more, next_cursor=parsed.cursor
        )

    async def create_tool(
        self,
        req: CreateToolRequest,
        *,
        idempotency_key: str | None = None,
    ) -> ToolConfig:
        """
        Create a new tool for the authenticated tenant.

        Calls ``POST /v1/tools``. Creates a custom function-calling tool,
        or (when ``req.provider`` is set) a platform-supplied tool such as
        Cal.com whose ``method``/``url``/``parameters`` are owned by the
        platform registry. The tool can then be attached to one or more
        agents via :meth:`attach_tool_to_agent`.

        NOTE for ``warm_transfer`` tools: write
        ``req.provider_config["destination"]`` as a plaintext E.164
        number; it is encrypted at rest and thereafter returned only as an
        opaque encrypted token on read (never the plaintext number).

        Parameters
        ----------
        req:
            Tool configuration.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — a retried request
            with the same key replays the original 201 response verbatim
            instead of creating a duplicate tool.

        Returns
        -------
        ToolConfig

        Raises
        ------
        AudactAPIError
            400 on a validation error; 404 if a platform tool's
            ``connection_id`` does not exist; 409 on a name conflict or an
            inactive platform connection.
        """
        url = f"{self._base_url}/v1/tools"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return ToolConfig.model_validate(response.json())

    async def get_tool(self, tool_id: UUID) -> ToolConfig:
        """
        Get a single tool by ID.

        Calls ``GET /v1/tools/{tool_id}``. Returns the full tool
        configuration, scoped to the authenticated tenant. Cross-tenant
        lookups return 404 (no information leakage).

        NOTE for ``warm_transfer`` tools:
        ``provider_config.destination`` is written as a plaintext E.164
        number but is encrypted at rest, so it is returned here as an
        opaque encrypted token, NEVER the original number — this is
        expected, not corruption.

        Parameters
        ----------
        tool_id:
            UUID of the tool.

        Returns
        -------
        ToolConfig

        Raises
        ------
        AudactNotFoundError
            404 if the tool does not exist (or belongs to another tenant).
        """
        url = f"{self._base_url}/v1/tools/{tool_id}"
        response = await self._client._request("GET", url)
        return ToolConfig.model_validate(response.json())

    async def replace_tool(
        self,
        tool_id: UUID,
        req: CreateToolRequest,
        *,
        idempotency_key: str | None = None,
    ) -> ToolConfig:
        """
        Full-replacement update of a tool.

        Calls ``PUT /v1/tools/{tool_id}``. All mutable tool fields
        (including the platform-tool fields ``provider``/``provider_tool``/
        ``connection_id``/``provider_config``) are atomically overwritten
        with the request body.

        Parameters
        ----------
        tool_id:
            UUID of the tool to replace.
        req:
            Full tool configuration.
        idempotency_key:
            Optional ``Idempotency-Key`` header value.

        Returns
        -------
        ToolConfig

        Raises
        ------
        AudactAPIError
            400 on a validation error; 404 if not found, or a platform
            tool's ``connection_id`` does not exist; 409 on a name
            conflict or an inactive platform connection.
        """
        url = f"{self._base_url}/v1/tools/{tool_id}"
        response = await self._client._request(
            "PUT",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return ToolConfig.model_validate(response.json())

    async def update_tool(
        self,
        tool_id: UUID,
        req: UpdateToolRequest,
        *,
        idempotency_key: str | None = None,
    ) -> ToolConfig:
        """
        Partially update a tool — only the supplied fields change; omitted
        fields keep their current value.

        Calls ``PATCH /v1/tools/{tool_id}``. The server fetches the
        current state, merges the patch, validates the merged result, then
        writes the update.

        Parameters
        ----------
        tool_id:
            UUID of the tool to update.
        req:
            Only the fields to change.
        idempotency_key:
            Optional ``Idempotency-Key`` header value.

        Returns
        -------
        ToolConfig

        Raises
        ------
        AudactAPIError
            400 on a validation error; 404 if not found, or a platform
            tool's ``connection_id`` does not exist; 409 on a name
            conflict or an inactive platform connection.
        """
        url = f"{self._base_url}/v1/tools/{tool_id}"
        response = await self._client._request(
            "PATCH",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return ToolConfig.model_validate(response.json())

    async def delete_tool(self, tool_id: UUID, *, force: bool | None = None) -> DeleteToolResponse:
        """
        Soft-delete a tool.

        Calls ``DELETE /v1/tools/{tool_id}``. Without ``force``, returns
        409 if the tool is attached to any agents. Pass ``force=True`` to
        cascade-detach it from all agents before deleting.

        Parameters
        ----------
        tool_id:
            UUID of the tool to delete.
        force:
            When ``True``, cascade-detaches the tool from all agents
            before deleting it.

        Returns
        -------
        DeleteToolResponse

        Raises
        ------
        AudactNotFoundError
            404 if the tool does not exist.
        AudactAPIError
            409 if the tool has active agent attachments and ``force`` is
            not set.
        """
        params: dict[str, str] = {}
        if force is not None:
            params["force"] = "true" if force else "false"
        url = f"{self._base_url}/v1/tools/{tool_id}"
        response = await self._client._request("DELETE", url, params=params or None)
        return DeleteToolResponse.model_validate(response.json())

    async def test_tool(self, tool_id: UUID) -> TestToolResponse:
        """
        Validate a platform-supplied tool (Cal.com) without creating a
        real booking.

        Calls ``POST /v1/tools/{tool_id}/test``. Confirms the connection
        is active, the configured event type resolves against the real
        provider account, and runs a kind-specific probe (availability
        slot probe, or a ``book_appointment`` ``field_mappings`` dry run).

        Parameters
        ----------
        tool_id:
            UUID of the tool to test.

        Returns
        -------
        TestToolResponse
            A distinguishable healthy/checks_passed/error outcome.

        Raises
        ------
        AudactAPIError
            400 if the tool is not a platform tool or the provider is
            unsupported; 404 if the tool or its connection is not found;
            409 if the connection is not active; 500 if platform-tool
            testing is not configured for this deployment.
        """
        url = f"{self._base_url}/v1/tools/{tool_id}/test"
        response = await self._client._request("POST", url)
        return TestToolResponse.model_validate(response.json())

    # ── Agent-tool attachment ────────────────────────────────────────────────

    async def list_agent_tools(
        self,
        agent_id: UUID,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Page[ToolConfig]:
        """
        List the tools attached to an agent.

        Calls ``GET /v1/agents/{agent_id}/tools``. Returns non-deleted
        tools attached to the specified agent, ordered by attachment
        creation time (oldest first).

        Parameters
        ----------
        agent_id:
            UUID of the agent.
        cursor:
            Opaque pagination cursor from a previous page's ``next_cursor``
            (cursor pagination convention).
        limit:
            Page size (server default 50, max 200).

        Returns
        -------
        Page[ToolConfig]
        """
        params: dict[str, str] = {}
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)
        url = f"{self._base_url}/v1/agents/{agent_id}/tools"
        response = await self._client._request("GET", url, params=params or None)
        parsed = ListAgentToolsResponse.model_validate(response.json())
        return Page[ToolConfig](
            items=parsed.items, has_more=parsed.has_more, next_cursor=parsed.next_cursor
        )

    async def attach_tool_to_agent(
        self, agent_id: UUID, tool_id: UUID
    ) -> AttachToolResponse:
        """
        Attach a tool to an agent.

        Calls ``POST /v1/agents/{agent_id}/tools``. Both the agent and
        tool must belong to the authenticated tenant. Idempotent:
        re-attaching an already-attached pair returns 201 without error.

        Parameters
        ----------
        agent_id:
            UUID of the agent.
        tool_id:
            UUID of the tool to attach.

        Returns
        -------
        AttachToolResponse

        Raises
        ------
        AudactNotFoundError
            404 if the agent or tool is not found.
        """
        url = f"{self._base_url}/v1/agents/{agent_id}/tools"
        response = await self._client._request(
            "POST",
            url,
            json=AttachToolRequest(tool_id=tool_id).model_dump(mode="json"),
        )
        return AttachToolResponse.model_validate(response.json())

    async def detach_tool_from_agent(
        self, agent_id: UUID, tool_id: UUID
    ) -> DetachToolResponse:
        """
        Detach a tool from an agent.

        Calls ``DELETE /v1/agents/{agent_id}/tools/{tool_id}``. No-op if
        the tool is not currently attached to the agent.

        Parameters
        ----------
        agent_id:
            UUID of the agent.
        tool_id:
            UUID of the tool to detach.

        Returns
        -------
        DetachToolResponse
        """
        url = f"{self._base_url}/v1/agents/{agent_id}/tools/{tool_id}"
        response = await self._client._request("DELETE", url)
        return DetachToolResponse.model_validate(response.json())


class KnowledgeBasesClient:
    """
    Sub-client for the knowledge-base (RAG) surface (``client.knowledge_bases.*``).

    Backed by the Tenant Management service (default ``http://localhost:8085``,
    ``tenant_management_url``/``AUDACT_TENANT_MANAGEMENT_URL``). Authenticates
    with the parent client's tenant ``api_key``. Covers knowledge-base CRUD,
    sources (url/text JSON, file multipart, re-ingest), agent links with their
    retrieval tuning, crawl exclusions, and the retrieval test harness.

    Every path identifier is percent-encoded as a single path segment.

    Do not construct directly; use ``AudactClient(...).knowledge_bases``.
    """

    def __init__(self, client: AudactClient) -> None:
        self._client = client

    @property
    def _base_url(self) -> str:
        return f"{self._client._tenant_management_url}/v1/knowledge-bases"

    def _kb_url(self, kb_id: UUID | str) -> str:
        return f"{self._base_url}/{_path_segment(kb_id)}"

    # ── Knowledge-base CRUD ──────────────────────────────────────────────────

    async def list_knowledge_bases(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Page[KnowledgeBase]:
        """
        List the tenant's knowledge bases.

        Calls ``GET /v1/knowledge-bases``, ordered by ``kb_id`` ascending.

        Parameters
        ----------
        cursor:
            Opaque cursor from a previous page's ``next_cursor``.
        limit:
            Page size (server default 20, max 100).

        Returns
        -------
        Page[KnowledgeBase]
            Pass ``next_cursor`` back as ``cursor`` while ``has_more`` is ``True``.
        """
        params: dict[str, str] = {}
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)
        response = await self._client._request("GET", self._base_url, params=params or None)
        parsed = ListKnowledgeBasesResponse.model_validate(response.json())
        return Page[KnowledgeBase](
            items=parsed.items, has_more=parsed.has_more, next_cursor=parsed.next_cursor or None
        )

    async def create_knowledge_base(self, req: CreateKnowledgeBaseRequest) -> KnowledgeBase:
        """
        Create a knowledge base.

        Calls ``POST /v1/knowledge-bases`` (201). Requires the developer role.

        Raises
        ------
        AudactAPIError
            400 on a validation error (e.g. empty ``name``).
        """
        response = await self._client._request(
            "POST", self._base_url, json=req.model_dump(mode="json", exclude_none=True)
        )
        return KnowledgeBase.model_validate(response.json())

    async def get_knowledge_base(self, kb_id: UUID | str) -> KnowledgeBase:
        """
        Get a knowledge base.

        Calls ``GET /v1/knowledge-bases/{kb_id}``.

        Raises
        ------
        AudactNotFoundError
            404 if the knowledge base does not exist (or belongs to another tenant).
        """
        response = await self._client._request("GET", self._kb_url(kb_id))
        return KnowledgeBase.model_validate(response.json())

    async def patch_knowledge_base(
        self, kb_id: UUID | str, req: PatchKnowledgeBaseRequest
    ) -> KnowledgeBase:
        """
        Partially update a knowledge base; only the supplied fields change.

        Calls ``PATCH /v1/knowledge-bases/{kb_id}``.

        Raises
        ------
        AudactNotFoundError
            404 if the knowledge base does not exist.
        AudactAPIError
            400 on a validation error.
        """
        response = await self._client._request(
            "PATCH", self._kb_url(kb_id), json=req.model_dump(mode="json", exclude_none=True)
        )
        return KnowledgeBase.model_validate(response.json())

    async def delete_knowledge_base(self, kb_id: UUID | str) -> None:
        """
        Delete a knowledge base and all its sources, chunks and links.

        Calls ``DELETE /v1/knowledge-bases/{kb_id}`` (204). Requires the owner role.

        Raises
        ------
        AudactNotFoundError
            404 if the knowledge base does not exist.
        """
        await self._client._request("DELETE", self._kb_url(kb_id))

    # ── Sources ──────────────────────────────────────────────────────────────

    async def list_kb_sources(self, kb_id: UUID | str) -> ListKBSourcesResponse:
        """
        List every source of a knowledge base.

        Calls ``GET /v1/knowledge-bases/{kb_id}/sources``, ordered by
        ``created_at`` ascending.
        """
        response = await self._client._request("GET", f"{self._kb_url(kb_id)}/sources")
        return ListKBSourcesResponse.model_validate(response.json())

    async def add_kb_source(self, kb_id: UUID | str, req: AddKBSourceRequest) -> KBSource:
        """
        Add a url or text source and enqueue its ingestion.

        Calls ``POST /v1/knowledge-bases/{kb_id}/sources`` with a JSON body
        (202 — ingestion runs asynchronously; poll :meth:`get_kb_source` until
        ``status`` is ``"ready"`` or ``"failed"``). For a file source use
        :meth:`upload_kb_source_file`, which sends the multipart form of the
        same operation.

        Raises
        ------
        AudactAPIError
            400 on a validation error or a per-KB source limit; 404 if the
            knowledge base does not exist; 503 if the ingestion queue is
            unavailable.
        """
        response = await self._client._request(
            "POST",
            f"{self._kb_url(kb_id)}/sources",
            json=req.model_dump(mode="json", exclude_none=True),
        )
        return KBSource.model_validate(response.json())

    async def upload_kb_source_file(
        self,
        kb_id: UUID | str,
        file: bytes | IO[bytes],
        *,
        filename: str | None = None,
        content_type: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> KBSource:
        """
        Upload a file source and enqueue its ingestion.

        Calls ``POST /v1/knowledge-bases/{kb_id}/sources`` (``addKBSource``)
        as ``multipart/form-data`` with a ``file`` part (202). The file limit
        is 50 MiB.

        Parameters
        ----------
        file:
            Raw file bytes, or an open, readable binary file handle.
        filename:
            Display filename (sent as the ``filename`` form field and on the
            part). Defaults to the handle's basename, else ``"upload"``.
        content_type:
            MIME type of the part. Defaults to ``"application/octet-stream"``.
        config:
            Optional per-source config, sent JSON-encoded as the ``config`` field.
        """
        files = {"file": _kyc_file_part(file, filename=filename, content_type=content_type)}
        data: dict[str, str] = {}
        if filename is not None:
            data["filename"] = filename
        if config is not None:
            data["config"] = _json.dumps(config)
        response = await self._client._request(
            "POST", f"{self._kb_url(kb_id)}/sources", files=files, data=data or None
        )
        return KBSource.model_validate(response.json())

    async def get_kb_source(self, kb_id: UUID | str, source_id: UUID | str) -> KBSource:
        """
        Get a source, including its ingestion ``status``.

        Calls ``GET /v1/knowledge-bases/{kb_id}/sources/{source_id}``.

        Raises
        ------
        AudactNotFoundError
            404 if the knowledge base or source does not exist.
        """
        url = f"{self._kb_url(kb_id)}/sources/{_path_segment(source_id)}"
        response = await self._client._request("GET", url)
        return KBSource.model_validate(response.json())

    async def patch_kb_source(
        self, kb_id: UUID | str, source_id: UUID | str, req: PatchKBSourceRequest
    ) -> KBSource:
        """
        Rename a source, or replace a text source's content (which re-ingests it).

        Calls ``PATCH /v1/knowledge-bases/{kb_id}/sources/{source_id}``.
        """
        url = f"{self._kb_url(kb_id)}/sources/{_path_segment(source_id)}"
        response = await self._client._request(
            "PATCH", url, json=req.model_dump(mode="json", exclude_none=True)
        )
        return KBSource.model_validate(response.json())

    async def reingest_kb_source(self, kb_id: UUID | str, source_id: UUID | str) -> KBSource:
        """
        Re-ingest a source under a new ``ingest_version``.

        Calls ``POST /v1/knowledge-bases/{kb_id}/sources/{source_id}/reingest`` (202).
        """
        url = f"{self._kb_url(kb_id)}/sources/{_path_segment(source_id)}/reingest"
        response = await self._client._request("POST", url)
        return KBSource.model_validate(response.json())

    async def delete_kb_source(self, kb_id: UUID | str, source_id: UUID | str) -> None:
        """
        Delete a source and all its chunks.

        Calls ``DELETE /v1/knowledge-bases/{kb_id}/sources/{source_id}`` (204).
        Requires the owner role.
        """
        url = f"{self._kb_url(kb_id)}/sources/{_path_segment(source_id)}"
        await self._client._request("DELETE", url)

    # ── Agent links ──────────────────────────────────────────────────────────

    async def list_kb_agent_links(self, kb_id: UUID | str) -> ListKBAgentLinksResponse:
        """
        List the agents linked to a knowledge base.

        Calls ``GET /v1/knowledge-bases/{kb_id}/agents``.
        """
        response = await self._client._request("GET", f"{self._kb_url(kb_id)}/agents")
        return ListKBAgentLinksResponse.model_validate(response.json())

    async def list_kb_links_by_agent(self, agent_id: UUID | str) -> ListKBAgentLinksResponse:
        """
        List the knowledge bases linked to an agent.

        Calls ``GET /v1/knowledge-bases/agent-links?agent_id=...``.
        """
        response = await self._client._request(
            "GET", f"{self._base_url}/agent-links", params={"agent_id": str(agent_id)}
        )
        return ListKBAgentLinksResponse.model_validate(response.json())

    async def put_kb_agent_link(
        self,
        kb_id: UUID | str,
        agent_id: UUID | str,
        req: PutKBAgentLinkRequest | None = None,
    ) -> KBAgentLink:
        """
        Link an agent to a knowledge base, or replace the link's tuning.

        Calls ``PUT /v1/knowledge-bases/{kb_id}/agents/{agent_id}``. Omitted
        tuning fields take the server defaults (``top_k`` 3,
        ``similarity_threshold`` 0.6, ``retrieval_instruction`` ``""``).

        Raises
        ------
        AudactNotFoundError
            404 if the knowledge base or agent does not exist.
        AudactAPIError
            400 if a tuning value is out of range.
        """
        url = f"{self._kb_url(kb_id)}/agents/{_path_segment(agent_id)}"
        body = req.model_dump(mode="json", exclude_none=True) if req is not None else {}
        response = await self._client._request("PUT", url, json=body)
        return KBAgentLink.model_validate(response.json())

    async def patch_kb_agent_link(
        self, kb_id: UUID | str, agent_id: UUID | str, req: PatchKBAgentLinkRequest
    ) -> KBAgentLink:
        """
        Partially update a link's retrieval tuning; only supplied fields change.

        Calls ``PATCH /v1/knowledge-bases/{kb_id}/agents/{agent_id}``.
        """
        url = f"{self._kb_url(kb_id)}/agents/{_path_segment(agent_id)}"
        response = await self._client._request(
            "PATCH", url, json=req.model_dump(mode="json", exclude_none=True)
        )
        return KBAgentLink.model_validate(response.json())

    async def delete_kb_agent_link(self, kb_id: UUID | str, agent_id: UUID | str) -> None:
        """
        Unlink an agent from a knowledge base.

        Calls ``DELETE /v1/knowledge-bases/{kb_id}/agents/{agent_id}`` (204).
        """
        url = f"{self._kb_url(kb_id)}/agents/{_path_segment(agent_id)}"
        await self._client._request("DELETE", url)

    # ── Crawl exclusions ─────────────────────────────────────────────────────

    async def list_exclusions(self, kb_id: UUID | str) -> ListKBExclusionsResponse:
        """
        List a knowledge base's crawl exclusion rules.

        Calls ``GET /v1/knowledge-bases/{kb_id}/exclusions``.
        """
        response = await self._client._request("GET", f"{self._kb_url(kb_id)}/exclusions")
        return ListKBExclusionsResponse.model_validate(response.json())

    async def add_exclusion(
        self, kb_id: UUID | str, req: AddKBExclusionRequest
    ) -> KBCrawlExclusion:
        """
        Add a crawl exclusion rule (an exact ``url`` or a ``crawl_path`` prefix).

        Calls ``POST /v1/knowledge-bases/{kb_id}/exclusions`` (201).
        """
        response = await self._client._request(
            "POST",
            f"{self._kb_url(kb_id)}/exclusions",
            json=req.model_dump(mode="json", exclude_none=True),
        )
        return KBCrawlExclusion.model_validate(response.json())

    async def delete_exclusion(self, kb_id: UUID | str, exclusion_id: UUID | str) -> None:
        """
        Delete a crawl exclusion rule.

        Calls ``DELETE /v1/knowledge-bases/{kb_id}/exclusions/{id}`` (204).
        """
        url = f"{self._kb_url(kb_id)}/exclusions/{_path_segment(exclusion_id)}"
        await self._client._request("DELETE", url)

    # ── Retrieval test harness ───────────────────────────────────────────────

    async def test_kb_retrieval(
        self, kb_id: UUID | str, req: KBTestRetrievalRequest
    ) -> KBTestRetrievalResponse:
        """
        Run a retrieval against one knowledge base and return the hits.

        Calls ``POST /v1/knowledge-bases/{kb_id}/test-retrieval``. An empty
        result is a 200 with ``empty=True``, not an error.
        """
        response = await self._client._request(
            "POST",
            f"{self._kb_url(kb_id)}/test-retrieval",
            json=req.model_dump(mode="json", exclude_none=True),
        )
        return KBTestRetrievalResponse.model_validate(response.json())


class IntegrationsClient:
    """
    Sub-client for the Agent Worker's third-party integration surface
    (``client.integrations.*``) — currently Cal.com only.

    Backed by the Agent Worker service (default ``http://localhost:8089``,
    ``agent_worker_url``/``AUDACT_AGENT_WORKER_URL``). Authenticates
    with the parent client's tenant ``api_key`` for every method **except**
    :meth:`calcom_oauth_callback`, which the server authenticates solely by
    the single-use ``state`` token (Cal.com's redirect cannot carry a
    ``Authorization`` header).

    Covers connection CRUD (bring-your-own API key), a live health-check
    (``test_connection``), the tenant's Cal.com event-type catalog (for
    configuring a ``cal_com`` tool's ``event_type_id``/``event_type_slug``),
    and the OAuth connect flow (``calcom_oauth_start``/
    ``calcom_oauth_callback``) as an alternative to pasting an API key.

    Do not construct directly; use ``AudactClient(...).integrations``.
    """

    def __init__(self, client: AudactClient) -> None:
        self._client = client

    @property
    def _base_url(self) -> str:
        return self._client._agent_worker_url

    # ── Connection CRUD ──────────────────────────────────────────────────────

    async def list_connections(self, *, provider: str | None = None) -> list[Connection]:
        """
        List the authenticated tenant's integration connections.

        Calls ``GET /v1/integrations``. Returns all non-deleted
        connections. Credentials are always masked — the response only
        ever includes ``has_api_key``/``has_oauth_token`` booleans, never
        an ARN or token.

        Parameters
        ----------
        provider:
            Optional filter, e.g. ``"cal_com"``.

        Returns
        -------
        list[Connection]
        """
        params: dict[str, str] = {}
        if provider is not None:
            params["provider"] = provider
        url = f"{self._base_url}/v1/integrations"
        response = await self._client._request("GET", url, params=params or None)
        parsed = ListConnectionsResponse.model_validate(response.json())
        return parsed.connections

    async def create_connection(
        self,
        req: CreateConnectionRequest,
        *,
        idempotency_key: str | None = None,
    ) -> Connection:
        """
        Create a bring-your-own-account Cal.com connection.

        Calls ``POST /v1/integrations``. Uses a pasted API key (Settings →
        Developer → API Keys in the user's own Cal.com account); the raw
        key is written to AWS Secrets Manager and only its ARN is stored.
        Use :meth:`calcom_oauth_start` for OAuth connections instead.

        Parameters
        ----------
        req:
            Connection configuration.
        idempotency_key:
            Optional ``Idempotency-Key`` header value.

        Returns
        -------
        Connection
            The created connection, with secrets masked.

        Raises
        ------
        AudactAPIError
            400 on a validation error; 409 on a name conflict.
        """
        url = f"{self._base_url}/v1/integrations"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            idempotency_key=idempotency_key,
        )
        return Connection.model_validate(response.json())

    async def get_connection(self, connection_id: UUID) -> Connection:
        """
        Get a single connection by ID.

        Calls ``GET /v1/integrations/{connection_id}``. Scoped to the
        authenticated tenant; cross-tenant lookups return 404 (no
        information leakage). Credentials are always masked.

        Parameters
        ----------
        connection_id:
            UUID of the connection.

        Returns
        -------
        Connection

        Raises
        ------
        AudactNotFoundError
            404 if the connection does not exist (or belongs to another
            tenant).
        """
        url = f"{self._base_url}/v1/integrations/{connection_id}"
        response = await self._client._request("GET", url)
        return Connection.model_validate(response.json())

    async def delete_connection(
        self, connection_id: UUID, *, force: bool | None = None
    ) -> DeleteConnectionResponse:
        """
        Soft-delete (revoke) a connection.

        Calls ``DELETE /v1/integrations/{connection_id}``. Without
        ``force``, returns 409 if any platform tool still references it.
        With ``force=True``, dependent tools are cascade-soft-deleted
        first, then the connection, then (for ``api_key`` connections) the
        Secrets Manager secret is scheduled for deletion. No silent
        fallback to another connection.

        Parameters
        ----------
        connection_id:
            UUID of the connection to delete.
        force:
            When ``True``, cascade-deletes dependent tools before revoking
            the connection.

        Returns
        -------
        DeleteConnectionResponse

        Raises
        ------
        AudactNotFoundError
            404 if the connection does not exist.
        AudactAPIError
            409 if the connection has dependent tools and ``force`` is not
            set.
        """
        params: dict[str, str] = {}
        if force is not None:
            params["force"] = "true" if force else "false"
        url = f"{self._base_url}/v1/integrations/{connection_id}"
        response = await self._client._request("DELETE", url, params=params or None)
        return DeleteConnectionResponse.model_validate(response.json())

    async def test_connection(self, connection_id: UUID) -> TestConnectionResponse:
        """
        Run a live Cal.com health check for a connection.

        Calls ``POST /v1/integrations/{connection_id}/test``. Resolves
        current credentials (transparently refreshing an expiring OAuth
        token) and calls ``GET /v2/event-types``. Updates
        ``health``/``last_checked_at``/``last_error`` and always returns
        200 with a distinguishable healthy/error outcome — never a raw
        credential or Cal.com error message.

        Parameters
        ----------
        connection_id:
            UUID of the connection to test.

        Returns
        -------
        TestConnectionResponse

        Raises
        ------
        AudactNotFoundError
            404 if the connection does not exist.
        AudactAPIError
            500 if connection testing is not configured for this
            deployment.
        """
        url = f"{self._base_url}/v1/integrations/{connection_id}/test"
        response = await self._client._request("POST", url)
        return TestConnectionResponse.model_validate(response.json())

    async def list_connection_event_types(
        self, connection_id: UUID
    ) -> list[CalcomEventType]:
        """
        List a connection's Cal.com event types.

        Calls ``GET /v1/integrations/{connection_id}/event-types``.
        Resolves the connection's current credentials and returns the
        tenant's own Cal.com event types (``GET /v2/event-types``), for
        use when configuring a platform tool's
        ``event_type_id``/``event_type_slug``.

        Parameters
        ----------
        connection_id:
            UUID of the connection.

        Returns
        -------
        list[CalcomEventType]

        Raises
        ------
        AudactNotFoundError
            404 if the connection does not exist.
        AudactAPIError
            409 if the connection is revoked/needs re-authorization; 429
            if Cal.com rate-limited the request; 502 if Cal.com is
            currently unavailable.
        """
        url = f"{self._base_url}/v1/integrations/{connection_id}/event-types"
        response = await self._client._request("GET", url)
        parsed = ListEventTypesResponse.model_validate(response.json())
        return parsed.event_types

    # ── Cal.com OAuth connect flow ───────────────────────────────────────────

    async def calcom_oauth_start(
        self,
        *,
        name: str | None = None,
        cal_username: str | None = None,
    ) -> OAuthStartResponse:
        """
        Start the Cal.com OAuth connect flow.

        Calls ``GET /v1/integrations/cal_com/oauth/start``. Mints a
        single-use state token bound to the authenticated tenant
        (10-minute TTL) and returns the Cal.com authorize URL to redirect
        the user's browser to. The caller's frontend performs that
        redirect; Cal.com's own redirect back is handled unauthenticated
        by :meth:`calcom_oauth_callback`.

        Parameters
        ----------
        name:
            Requested connection name (defaults server-side if omitted).
        cal_username:
            Cal.com username, to disambiguate event types by slug.

        Returns
        -------
        OAuthStartResponse

        Raises
        ------
        AudactAPIError
            500 if OAuth is not configured, or the state store fails.
        """
        params: dict[str, str] = {}
        if name is not None:
            params["name"] = name
        if cal_username is not None:
            params["cal_username"] = cal_username
        url = f"{self._base_url}/v1/integrations/cal_com/oauth/start"
        response = await self._client._request("GET", url, params=params or None)
        return OAuthStartResponse.model_validate(response.json())

    async def calcom_oauth_callback(
        self,
        *,
        state: str,
        code: str | None = None,
        error: str | None = None,
    ) -> str | None:
        """
        Complete the Cal.com OAuth connect flow.

        Calls ``GET /v1/integrations/cal_com/oauth/callback``. This
        endpoint is normally hit by Cal.com's own browser redirect, not by
        an SDK caller — it is included here for completeness/parity only.
        It is authenticated **solely** by the single-use ``state`` token
        minted by :meth:`calcom_oauth_start` (no ``Authorization`` header
        is sent: Cal.com's redirect cannot carry one). On success the
        server recovers the tenant from the state record, exchanges
        ``code``, persists a new connection, and responds ``302`` with a
        ``Location`` redirect to the dashboard
        (``?connected=1`` on success, ``?error=<code>`` on decline).

        Parameters
        ----------
        state:
            Single-use state token minted by :meth:`calcom_oauth_start`.
        code:
            Authorization code (absent when the provider returned an
            error).
        error:
            Cal.com-side error code (e.g. the user declined consent).

        Returns
        -------
        str | None
            The ``Location`` header value from the server's ``302``
            redirect response, or ``None`` if absent.

        Raises
        ------
        AudactAPIError
            400 on an unknown/expired state or missing code; 500 if OAuth
            is not configured; 502 if the Cal.com token exchange failed.
        """
        params: dict[str, str] = {"state": state}
        if code is not None:
            params["code"] = code
        if error is not None:
            params["error"] = error
        url = f"{self._base_url}/v1/integrations/cal_com/oauth/callback"
        # This endpoint is unauthenticated (state-token-only) and responds
        # with a 302 redirect on success, not a 2xx JSON body — bypass
        # `_request`'s auth-header injection and 2xx-only success check
        # accordingly, but still surface 4xx/5xx via the shared error mapper.
        response = await self._client._http.request(
            "GET", url, params=params, follow_redirects=False
        )
        if 300 <= response.status_code < 400:
            return cast(str | None, response.headers.get("Location"))
        _raise_for_status(response)
        return cast(  # pragma: no cover - always raises above
            str | None, response.headers.get("Location")
        )


# ─────────────────────────────────────────────────────────────────────────────
# OrgClient — org self-service surface — org-management (8092)
# ─────────────────────────────────────────────────────────────────────────────

class OrgClient:
    """
    Sub-client for the org self-service surface (``client.org.*``).

    Backed by the Org Management service (default
    ``http://localhost:8092``, ``org_management_url``/
    ``AUDACT_ORG_MANAGEMENT_URL``). Authenticates with **OrgBearer**, not
    the tenant ``api_key``: :meth:`signup`/:meth:`login` are public routes
    that mint and store an org access token (via
    ``AudactClient.set_org_token``) on the parent client; every other
    method here sends that token (``self._client.org_token``) as
    ``Authorization: Bearer <token>``, falling back to the tenant
    ``api_key`` only when no org token has been established yet.

    Token state is in-memory only on the parent :class:`AudactClient`
    instance — never written to disk. :meth:`refresh` relies on the
    underlying ``httpx.AsyncClient``'s cookie jar to carry the httpOnly,
    ``SameSite=Strict`` refresh-token cookie set by :meth:`login`/
    :meth:`signup`/a prior :meth:`refresh` across calls made on the *same*
    ``AudactClient`` instance — this flow is browser-first and is not
    designed for a non-browser/MCP client that discards cookies between
    calls; such a caller should re-authenticate via :meth:`login` instead.

    The org-tenant lifecycle (``client.org.*`` tenant management, still
    OrgBearer) lives on this same sub-client. The platform-admin org surface
    (``client.platform.orgs``, PlatformBearer) is a separate sub-client —
    see :class:`PlatformOrgsClient`.

    Do not construct directly; use ``AudactClient(...).org``.

    Example
    -------
    ::

        async with AudactClient() as client:
            await client.org.login(
                OrgLoginRequest(email="admin@acme.example", password="hunter222222")
            )
            # client.org.* now sends `Authorization: Bearer <jwt>` automatically.
            profile = await client.org.get_profile()
    """

    def __init__(self, client: AudactClient) -> None:
        self._client = client

    @property
    def _base_url(self) -> str:
        return self._client._org_management_url

    # ── Auth / session lifecycle ─────────────────────────────────────────────

    async def signup(self, req: OrgSignupRequest) -> OrgSignupResponse:
        """
        Create a brand-new organization, its first org_admin, and its
        initial KYC record, all atomically.

        Calls ``POST /v1/org/signup``. Public — no authentication
        required (IP-rate-limited at the router: default 5 signups per
        hour per IP; a 429 sets ``Retry-After``). ``req.entity_type`` must
        be exactly ``"individual"`` or ``"company"``; ``req.country`` must
        be an ISO 3166-1 alpha-2 code. On success, stores the returned
        access token via :meth:`AudactClient.set_org_token` so subsequent
        ``client.org.*`` calls are authenticated immediately.

        Parameters
        ----------
        req:
            Signup payload.

        Returns
        -------
        OrgSignupResponse

        Raises
        ------
        AudactAPIError
            400 on a malformed body/invalid ``entity_type``/``country``/
            email or a too-short password; 409 ``email_taken``; 422
            ``kyc_invalid``.
        AudactRateLimitError
            429 if the per-IP signup rate limit is exceeded.
        """
        url = f"{self._base_url}/v1/org/signup"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            auth_token=self._client.org_token,
        )
        parsed = OrgSignupResponse.model_validate(response.json())
        if parsed.token:
            self._client.set_org_token(parsed.token)
        return parsed

    async def login(self, req: OrgLoginRequest) -> OrgLoginResponse:
        """
        Authenticate an org_admin by email/password.

        Calls ``POST /v1/org/login``. Public — no authentication
        required (IP+email rate-limited: 10 attempts per 15-minute window
        per email; a 429 sets ``Retry-After``). Always returns the
        identical 401 ``invalid_credentials`` for both an unknown email
        and a wrong password (no user-enumeration timing oracle). On
        success, stores the returned access token via
        :meth:`AudactClient.set_org_token` so subsequent ``client.org.*``
        calls are authenticated immediately, and the server sets an
        httpOnly refresh-token cookie on the shared ``httpx.AsyncClient``
        for a later :meth:`refresh`.

        Parameters
        ----------
        req:
            Login payload.

        Returns
        -------
        OrgLoginResponse

        Raises
        ------
        AudactAuthError
            401 ``invalid_credentials``.
        AudactRateLimitError
            429 ``rate_limit_exceeded``.
        """
        url = f"{self._base_url}/v1/org/login"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            auth_token=self._client.org_token,
        )
        parsed = OrgLoginResponse.model_validate(response.json())
        if parsed.token:
            self._client.set_org_token(parsed.token)
        return parsed

    async def refresh(self) -> OrgRefreshResponse:
        """
        Rotate the org refresh token and mint a fresh access token.

        Calls ``POST /v1/org/refresh``. No ``Authorization`` header is
        required — the server validates the httpOnly refresh-token cookie
        set by a prior :meth:`login`/:meth:`signup`/:meth:`refresh` (the
        old cookie's ``jti`` is invalidated even on success, single-use).
        This flow is browser-first and relies on the shared
        ``httpx.AsyncClient`` cookie jar; non-browser/MCP callers that
        cannot retain cookies between calls should re-authenticate via
        :meth:`login` instead when the access token expires. On success,
        stores the freshly minted access token via
        :meth:`AudactClient.set_org_token`.

        Returns
        -------
        OrgRefreshResponse

        Raises
        ------
        AudactAuthError
            401 if the refresh token is missing, unknown, or expired.
        """
        url = f"{self._base_url}/v1/org/refresh"
        response = await self._client._request(
            "POST", url, auth_token=self._client.org_token
        )
        parsed = OrgRefreshResponse.model_validate(response.json())
        if parsed.token:
            self._client.set_org_token(parsed.token)
        return parsed

    async def logout(self) -> None:
        """
        Revoke the current org session.

        Calls ``POST /v1/org/logout``. Requires OrgBearer. Revokes the
        presented refresh-token ``jti`` and clears the org refresh
        cookie; idempotent — always 204, even without a refresh cookie.
        Clears the in-memory org token via
        :meth:`AudactClient.set_org_token` on success (subsequent
        ``client.org.*`` calls fall back to the tenant ``api_key``, if
        any).

        Raises
        ------
        AudactAuthError
            401 if not authenticated.
        """
        url = f"{self._base_url}/v1/org/logout"
        await self._client._request(
            "POST", url, auth_token=self._client.org_token
        )
        self._client.set_org_token(None)

    # ── Profile ───────────────────────────────────────────────────────────────

    async def get_profile(self) -> OrgProfileResponse:
        """
        Get the calling organization and admin account.

        Calls ``GET /v1/org/profile``. Requires OrgBearer. Scoped to the
        org/admin identified by the OrgBearer session — never by a
        request parameter.

        Returns
        -------
        OrgProfileResponse

        Raises
        ------
        AudactAuthError
            401 if not authenticated.
        AudactNotFoundError
            404 if the org/admin no longer exists.
        """
        url = f"{self._base_url}/v1/org/profile"
        response = await self._client._request(
            "GET", url, auth_token=self._client.org_token
        )
        return OrgProfileResponse.model_validate(response.json())

    async def update_profile(self, req: OrgUpdateProfileRequest) -> OrgProfileResponse:
        """
        Update the organization display name and/or the calling admin's
        display name.

        Calls ``PATCH /v1/org/profile``. Requires OrgBearer. Absent/empty
        fields are left unchanged.

        Parameters
        ----------
        req:
            Fields to update.

        Returns
        -------
        OrgProfileResponse

        Raises
        ------
        AudactAPIError
            400 on a malformed body.
        AudactAuthError
            401 if not authenticated.
        """
        url = f"{self._base_url}/v1/org/profile"
        response = await self._client._request(
            "PATCH",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            auth_token=self._client.org_token,
        )
        return OrgProfileResponse.model_validate(response.json())

    # ── KYC ───────────────────────────────────────────────────────────────────

    async def get_kyc(self) -> OrgKYCResponse:
        """
        Get the calling organization's KYC record.

        Calls ``GET /v1/org/kyc``. Requires OrgBearer. Scoped to the org
        identified by the OrgBearer session.

        Returns
        -------
        OrgKYCResponse

        Raises
        ------
        AudactAuthError
            401 if not authenticated.
        AudactNotFoundError
            404 if no KYC record exists yet.
        """
        url = f"{self._base_url}/v1/org/kyc"
        response = await self._client._request(
            "GET", url, auth_token=self._client.org_token
        )
        return OrgKYCResponse.model_validate(response.json())

    async def update_kyc(self, req: OrgKYCPatchRequest) -> OrgKYCResponse:
        """
        Merge fields onto the organization's existing KYC record.

        Calls ``PATCH /v1/org/kyc``. Requires OrgBearer. Absent fields
        are left unchanged; a provided-but-malformed field returns 422
        ``kyc_invalid``.

        Parameters
        ----------
        req:
            KYC fields to update (subset).

        Returns
        -------
        OrgKYCResponse

        Raises
        ------
        AudactAPIError
            400 on a malformed body; 422 ``kyc_invalid``.
        AudactAuthError
            401 if not authenticated.
        """
        url = f"{self._base_url}/v1/org/kyc"
        response = await self._client._request(
            "PATCH",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            auth_token=self._client.org_token,
        )
        return OrgKYCResponse.model_validate(response.json())

    # ── Org-tenant lifecycle (org-tenants) ────────────────────────

    async def list_tenants(
        self,
        *,
        include_deleted: bool | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Page[OrgTenantSummary]:
        """
        List tenants owned by the caller's organization, newest first.

        Calls ``GET /v1/org/tenants``. Requires OrgBearer.

        Parameters
        ----------
        include_deleted:
            When ``True``, include soft-deleted tenants (default ``False``).
        cursor:
            Opaque pagination cursor from a previous page's ``next_cursor``
            (cursor pagination convention).
        limit:
            Page size (server default 50, max 200).

        Returns
        -------
        Page[OrgTenantSummary]
            ``items`` is the page of tenants; pass ``next_cursor`` back as
            ``cursor`` while ``has_more`` is ``True`` to fetch subsequent
            pages. ``has_more`` is derived from ``next_cursor`` being
            present — the server does not send an explicit ``has_more``
            field for this surface.

        Raises
        ------
        AudactAPIError
            400 on an invalid ``limit`` or ``cursor``.
        AudactAuthError
            401 if not authenticated.
        """
        params: dict[str, str] = {}
        if include_deleted is not None:
            params["include_deleted"] = "true" if include_deleted else "false"
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)

        url = f"{self._base_url}/v1/org/tenants"
        response = await self._client._request(
            "GET", url, params=params or None, auth_token=self._client.org_token
        )
        parsed = ListOrgTenantsResponse.model_validate(response.json())
        return Page[OrgTenantSummary](
            items=parsed.tenants,
            has_more=parsed.next_cursor is not None,
            next_cursor=parsed.next_cursor,
        )

    async def create_tenant(self, req: OrgCreateTenantRequest) -> OrgCreateTenantResponse:
        """
        Provision a new tenant owned by the caller's organization.

        Calls ``POST /v1/org/tenants``. Requires OrgBearer and a verified
        organization. The tenant is created WITHOUT an API key or default
        configuration — those are deferred to :meth:`initialize_tenant`.

        Parameters
        ----------
        req:
            Tenant creation payload.

        Returns
        -------
        OrgCreateTenantResponse

        Raises
        ------
        AudactAPIError
            400 on a malformed body.
        AudactAuthError
            401 if not authenticated.
        AudactForbiddenError
            403 ``org_not_verified`` or ``org_rejected``.
        """
        url = f"{self._base_url}/v1/org/tenants"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            auth_token=self._client.org_token,
        )
        return OrgCreateTenantResponse.model_validate(response.json())

    async def get_tenant(self, tenant_id: UUID) -> OrgGetTenantResponse:
        """
        Get a single tenant owned by the caller's organization.

        Calls ``GET /v1/org/tenants/{id}``. Requires OrgBearer. A
        ``tenant_id`` that belongs to another organization is
        indistinguishable from one that does not exist — both return 404
        ``tenant_not_found``.

        Parameters
        ----------
        tenant_id:
            UUID of the tenant to fetch.

        Returns
        -------
        OrgGetTenantResponse

        Raises
        ------
        AudactAuthError
            401 if not authenticated.
        AudactNotFoundError
            404 ``tenant_not_found``.
        """
        url = f"{self._base_url}/v1/org/tenants/{tenant_id}"
        response = await self._client._request(
            "GET", url, auth_token=self._client.org_token
        )
        return OrgGetTenantResponse.model_validate(response.json())

    async def soft_delete_tenant(self, tenant_id: UUID) -> OrgTenantActionResponse:
        """
        Soft-delete a tenant owned by the caller's organization.

        Calls ``DELETE /v1/org/tenants/{id}``. Requires OrgBearer and a
        verified organization. Sets ``deleted_at=NOW()`` (logical delete
        only — the tenant's KMS HMAC key is retained, never
        deprovisioned) and sets the ``org:tenant-disabled`` Redis marker.
        Writes one ``org_audit_log`` row (``tenant.soft_delete``).

        Parameters
        ----------
        tenant_id:
            UUID of the tenant to soft-delete.

        Returns
        -------
        OrgTenantActionResponse

        Raises
        ------
        AudactAuthError
            401 if not authenticated.
        AudactForbiddenError
            403 ``org_not_verified`` or ``org_rejected``.
        AudactNotFoundError
            404 ``tenant_not_found``.
        """
        url = f"{self._base_url}/v1/org/tenants/{tenant_id}"
        response = await self._client._request(
            "DELETE", url, auth_token=self._client.org_token
        )
        return OrgTenantActionResponse.model_validate(response.json())

    async def disable_tenant(self, tenant_id: UUID) -> OrgTenantActionResponse:
        """
        Disable a tenant owned by the caller's organization.

        Calls ``POST /v1/org/tenants/{id}/disable``. Requires OrgBearer
        and a verified organization. Transitions the tenant to
        ``status=disabled`` and sets the ``org:tenant-disabled`` Redis
        marker so ``APIKeyAuth`` rejects the tenant's API keys on the hot
        path. Writes one ``org_audit_log`` row (``tenant.disable``).

        Parameters
        ----------
        tenant_id:
            UUID of the tenant to disable.

        Returns
        -------
        OrgTenantActionResponse

        Raises
        ------
        AudactAuthError
            401 if not authenticated.
        AudactForbiddenError
            403 ``org_not_verified`` or ``org_rejected``.
        AudactNotFoundError
            404 ``tenant_not_found``.
        """
        url = f"{self._base_url}/v1/org/tenants/{tenant_id}/disable"
        response = await self._client._request(
            "POST", url, auth_token=self._client.org_token
        )
        return OrgTenantActionResponse.model_validate(response.json())

    async def enable_tenant(self, tenant_id: UUID) -> OrgTenantActionResponse:
        """
        Enable a tenant owned by the caller's organization.

        Calls ``POST /v1/org/tenants/{id}/enable``. Requires OrgBearer and
        a verified organization. Transitions the tenant to
        ``status=active`` and clears the ``org:tenant-disabled`` Redis
        marker. Writes one ``org_audit_log`` row (``tenant.enable``).

        Parameters
        ----------
        tenant_id:
            UUID of the tenant to enable.

        Returns
        -------
        OrgTenantActionResponse

        Raises
        ------
        AudactAuthError
            401 if not authenticated.
        AudactForbiddenError
            403 ``org_not_verified`` or ``org_rejected``.
        AudactNotFoundError
            404 ``tenant_not_found``.
        """
        url = f"{self._base_url}/v1/org/tenants/{tenant_id}/enable"
        response = await self._client._request(
            "POST", url, auth_token=self._client.org_token
        )
        return OrgTenantActionResponse.model_validate(response.json())

    async def restore_tenant(self, tenant_id: UUID) -> OrgTenantActionResponse:
        """
        Restore a soft-deleted tenant owned by the caller's organization.

        Calls ``POST /v1/org/tenants/{id}/restore``. Requires OrgBearer
        and a verified organization. Clears ``deleted_at`` on a currently
        soft-deleted tenant (the original ``hmac_key_arn`` is reused
        as-is — no KMS re-provision, no new configuration or key is
        created) and clears the ``org:tenant-disabled`` Redis marker.
        Writes one ``org_audit_log`` row (``tenant.restore``).

        Parameters
        ----------
        tenant_id:
            UUID of the tenant to restore.

        Returns
        -------
        OrgTenantActionResponse

        Raises
        ------
        AudactAuthError
            401 if not authenticated.
        AudactForbiddenError
            403 ``org_not_verified`` or ``org_rejected``.
        AudactNotFoundError
            404 ``tenant_not_found``.
        AudactAPIError
            409 ``not_deleted``.
        """
        url = f"{self._base_url}/v1/org/tenants/{tenant_id}/restore"
        response = await self._client._request(
            "POST", url, auth_token=self._client.org_token
        )
        return OrgTenantActionResponse.model_validate(response.json())

    async def initialize_tenant(
        self,
        tenant_id: UUID,
        *,
        idempotency_key: str | None = None,
    ) -> OrgInitializeTenantResponse:
        """
        Seed a tenant's first sealed default configuration and reveal its
        first owner API key.

        Calls ``POST /v1/org/tenants/{id}/initialize``. Requires
        OrgBearer. Idempotent by *outcome*: calling it again on an
        already-initialized tenant returns 409 ``already_initialized``
        without duplicating the configuration or re-revealing a key. Pass
        ``idempotency_key`` to make a retried request replay the original
        201 response verbatim instead of erroring.

        Parameters
        ----------
        tenant_id:
            UUID of the tenant to initialize.
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key replays the original 201 response.

        Returns
        -------
        OrgInitializeTenantResponse
            Includes the tenant and the raw API key (``api_key.key``),
            revealed exactly once.

        Raises
        ------
        AudactAuthError
            401 if not authenticated.
        AudactForbiddenError
            403 ``org_not_verified`` or ``org_rejected``.
        AudactNotFoundError
            404 if the tenant does not exist / is not owned by the caller's
            organization.
        AudactAPIError
            409 if the tenant is not active, or ``already_initialized``.
        """
        url = f"{self._base_url}/v1/org/tenants/{tenant_id}/initialize"
        response = await self._client._request(
            "POST",
            url,
            auth_token=self._client.org_token,
            idempotency_key=idempotency_key,
        )
        return OrgInitializeTenantResponse.model_validate(response.json())

    async def issue_tenant_key(
        self,
        tenant_id: UUID,
        req: OrgIssueKeyRequest | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> OrgIssueKeyResponse:
        """
        Mint a new "owner" API key for a tenant already owned by the
        caller's organization.

        Calls ``POST /v1/org/tenants/{id}/keys``. Requires OrgBearer.
        Unlike :meth:`initialize_tenant`, this does not require the
        tenant to be initialized and does not touch configuration. The
        full key is returned exactly once and is never stored in
        plaintext. Pass ``idempotency_key`` to make a retried request
        replay the original 201 response verbatim instead of minting a
        second key.

        Parameters
        ----------
        tenant_id:
            UUID of the tenant to issue a key for.
        req:
            Optional key label (defaults to ``"owner"`` when omitted).
        idempotency_key:
            Optional ``Idempotency-Key`` header value — replaying the same
            key replays the original 201 response.

        Returns
        -------
        OrgIssueKeyResponse

        Raises
        ------
        AudactAPIError
            400 on a malformed body.
        AudactAuthError
            401 if not authenticated.
        AudactForbiddenError
            403 ``org_not_verified`` or ``org_rejected``.
        AudactNotFoundError
            404 ``tenant_not_found``.
        """
        url = f"{self._base_url}/v1/org/tenants/{tenant_id}/keys"
        body = (req or OrgIssueKeyRequest()).model_dump(mode="json", exclude_none=True)
        response = await self._client._request(
            "POST",
            url,
            json=body,
            auth_token=self._client.org_token,
            idempotency_key=idempotency_key,
        )
        return OrgIssueKeyResponse.model_validate(response.json())

    async def impersonate_tenant(self, tenant_id: UUID) -> OrgImpersonateTenantResponse:
        """
        Mint a short-lived tenant JWT letting the caller act as the
        tenant's owner against tenant-facing services.

        Calls ``POST /v1/org/tenants/{id}/impersonate``. Requires
        OrgBearer. Requires the tenant to belong to the caller's
        organization and be active (not disabled or soft-deleted). There
        is no password/confirmation step — the short token lifetime
        (~20 minutes) is the safety mechanism. Every call writes a
        ``tenant.impersonate`` audit row naming the acting admin. The
        returned token is never stored server-side and must not be
        logged.

        Parameters
        ----------
        tenant_id:
            UUID of the tenant to impersonate.

        Returns
        -------
        OrgImpersonateTenantResponse

        Raises
        ------
        AudactAuthError
            401 if not authenticated.
        AudactForbiddenError
            403 ``org_not_verified`` or ``org_rejected``.
        AudactNotFoundError
            404 if the tenant does not exist / is not owned by the caller's
            organization.
        AudactAPIError
            409 ``tenant_inactive``.
        """
        url = f"{self._base_url}/v1/org/tenants/{tenant_id}/impersonate"
        response = await self._client._request(
            "POST", url, auth_token=self._client.org_token
        )
        return OrgImpersonateTenantResponse.model_validate(response.json())


class PlatformOrgsClient:
    """
    Sub-client for the platform-admin org-management surface
    (``client.platform.orgs.*``).

    Backed by the Org Management service (default
    ``http://localhost:8092``, ``org_management_url``/
    ``AUDACT_ORG_MANAGEMENT_URL``). Authenticates with **PlatformBearer** —
    a pre-minted Ed25519 platform-admin token, entirely distinct from both
    the tenant ``api_key`` and the ``OrgBearer`` JWT :class:`OrgClient`
    uses. The SDK **never mints** this token; the caller supplies it via
    ``AudactClient(platform_token=...)``/``AUDACT_PLATFORM_TOKEN``, or by
    calling :meth:`AudactClient.set_platform_token` directly. Every method
    here sends ``self._client.platform_token`` as
    ``Authorization: Bearer <token>``, falling back to the tenant
    ``api_key`` only when no platform token has been established.

    Covers the ``org-platform`` tag: organizations list/verify/reject
    (the verification queue for new signups) and org_admin
    find/change-email/reset-password (locked-out-admin recovery flows).

    Do not construct directly; use ``AudactClient(...).platform.orgs``.

    Example
    -------
    ::

        async with AudactClient(platform_token="plat_...") as client:
            page = await client.platform.orgs.list_organizations(
                status="unverified"
            )
            for org in page.items:
                await client.platform.orgs.verify_organization(org.org_id)
    """

    def __init__(self, client: AudactClient) -> None:
        self._client = client

    @property
    def _base_url(self) -> str:
        return self._client._org_management_url

    async def list_organizations(
        self,
        *,
        status: str | None = None,
        email: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page[Organization]:
        """
        List/find organizations for the verification queue or support
        lookup, newest first.

        Calls ``GET /v1/platform/organizations``. Requires PlatformBearer.
        Read-only — writes no audit row. Requires a platform token minted
        for the ``"org"`` action.

        Parameters
        ----------
        status:
            Optional filter on ``verification_status``: ``"unverified"``,
            ``"verified"``, or ``"rejected"``.
        email:
            Optional filter matching an org_admin's exact (case-insensitive)
            email, returning its owning organization.
        limit:
            Max number of organizations to return (server default 50, max
            200).
        cursor:
            Opaque pagination cursor from a previous page's ``next_cursor``
            (cursor pagination convention).

        Returns
        -------
        Page[Organization]
            ``items`` is the page of organizations; pass ``next_cursor``
            back as ``cursor`` while ``has_more`` is ``True`` to fetch
            subsequent pages. ``has_more`` is derived from ``next_cursor``
            being non-empty — the server does not send an explicit
            ``has_more`` field for this surface.

        Raises
        ------
        AudactAPIError
            400 on an invalid ``status``, ``limit``, or ``cursor``.
        AudactAuthError
            401 if not authenticated with a valid platform token.
        """
        params: dict[str, str] = {}
        if status is not None:
            params["status"] = status
        if email is not None:
            params["email"] = email
        if limit is not None:
            params["limit"] = str(limit)
        if cursor is not None:
            params["cursor"] = cursor

        url = f"{self._base_url}/v1/platform/organizations"
        response = await self._client._request(
            "GET", url, params=params or None, auth_token=self._client.platform_token
        )
        parsed = PlatformListOrganizationsResponse.model_validate(response.json())
        return Page[Organization](
            items=parsed.organizations,
            has_more=bool(parsed.next_cursor),
            next_cursor=parsed.next_cursor or None,
        )

    async def verify_organization(self, org_id: UUID) -> PlatformOrganizationResponse:
        """
        Verify an organization, unblocking its tenant lifecycle.

        Calls ``POST /v1/platform/organizations/{org_id}/verify``. Requires
        PlatformBearer and a platform token minted for the ``"org"``
        action. Sets ``verification_status=verified``,
        ``verified_at=NOW()``, ``verified_by_kid=<the calling platform
        key's kid>``. Idempotent-friendly: verifying an already-verified
        organization succeeds without error. Writes one ``org_audit_log``
        row (action ``"org.verify"``).

        Parameters
        ----------
        org_id:
            UUID of the organization to verify.

        Returns
        -------
        PlatformOrganizationResponse

        Raises
        ------
        AudactAPIError
            400 if ``org_id`` is not a valid UUID.
        AudactAuthError
            401 if not authenticated with a valid platform token.
        AudactNotFoundError
            404 if the organization does not exist.
        """
        url = f"{self._base_url}/v1/platform/organizations/{org_id}/verify"
        response = await self._client._request(
            "POST", url, auth_token=self._client.platform_token
        )
        return PlatformOrganizationResponse.model_validate(response.json())

    async def reject_organization(
        self, org_id: UUID, req: PlatformRejectOrganizationRequest
    ) -> PlatformOrganizationResponse:
        """
        Reject an organization.

        Calls ``POST /v1/platform/organizations/{org_id}/reject``. Requires
        PlatformBearer and a platform token minted for the ``"org"``
        action. Sets ``verification_status=rejected``. ``req.reason`` is
        required — persisted only in the ``org_audit_log`` ``"org.reject"``
        row's metadata, never on the organization record itself.

        Parameters
        ----------
        org_id:
            UUID of the organization to reject.
        req:
            Rejection reason (required, non-empty).

        Returns
        -------
        PlatformOrganizationResponse

        Raises
        ------
        AudactAPIError
            400 if ``org_id`` is not a valid UUID or the body is malformed;
            422 if ``reason`` is empty.
        AudactAuthError
            401 if not authenticated with a valid platform token.
        AudactNotFoundError
            404 if the organization does not exist.
        """
        url = f"{self._base_url}/v1/platform/organizations/{org_id}/reject"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            auth_token=self._client.platform_token,
        )
        return PlatformOrganizationResponse.model_validate(response.json())

    async def find_org_admins(
        self,
        *,
        email: str | None = None,
        org_id: UUID | None = None,
    ) -> PlatformFindOrgAdminsResponse:
        """
        Look up org_admins by exact (case-insensitive) email and/or
        ``org_id`` — the lookup step before a reset-password or
        change-email recovery action.

        Calls ``GET /v1/platform/org-admins``. Requires PlatformBearer.
        Never returns ``password_hash``. Read-only — writes no audit row.

        Parameters
        ----------
        email:
            Optional exact org_admin email (CITEXT, case-insensitive).
        org_id:
            Optional organization UUID.

        Returns
        -------
        PlatformFindOrgAdminsResponse

        Raises
        ------
        AudactAPIError
            400 if ``org_id`` is not a valid UUID.
        AudactAuthError
            401 if not authenticated with a valid platform token.
        """
        params: dict[str, str] = {}
        if email is not None:
            params["email"] = email
        if org_id is not None:
            params["org_id"] = str(org_id)

        url = f"{self._base_url}/v1/platform/org-admins"
        response = await self._client._request(
            "GET", url, params=params or None, auth_token=self._client.platform_token
        )
        return PlatformFindOrgAdminsResponse.model_validate(response.json())

    async def change_org_admin_email(
        self, admin_id: UUID, req: PlatformChangeOrgAdminEmailRequest
    ) -> PlatformOrgAdminResponse:
        """
        Change a locked-out org_admin's login email.

        Calls ``PATCH /v1/platform/org-admins/{admin_id}``. Requires
        PlatformBearer. Validates RFC-ish format and CITEXT-unique
        collision (mapped to a stable 409 ``email_taken`` — never a raw
        Postgres constraint dump). Audits ``"org_admin.email_changed"``
        with metadata ``{kid}`` only — old/new email are never logged.

        Parameters
        ----------
        admin_id:
            UUID of the org_admin.
        req:
            New login email.

        Returns
        -------
        PlatformOrgAdminResponse

        Raises
        ------
        AudactAPIError
            400 if ``admin_id`` is not a valid UUID, email missing, or
            email malformed; 409 ``email_taken`` if another org_admin
            already uses this email.
        AudactAuthError
            401 if not authenticated with a valid platform token.
        AudactNotFoundError
            404 if no org_admin has this ``admin_id``.
        """
        url = f"{self._base_url}/v1/platform/org-admins/{admin_id}"
        response = await self._client._request(
            "PATCH",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            auth_token=self._client.platform_token,
        )
        return PlatformOrgAdminResponse.model_validate(response.json())

    async def reset_org_admin_password(
        self,
        admin_id: UUID,
        req: PlatformResetOrgAdminPasswordRequest | None = None,
    ) -> PlatformResetOrgAdminPasswordResponse:
        """
        Reset a locked-out org_admin's password.

        Calls ``POST /v1/platform/org-admins/{admin_id}/reset-password``.
        Requires PlatformBearer. Sets a new bcrypt-hashed password directly
        (``req.new_password`` supplied, >= 12 chars) OR mints a single-use,
        short-TTL reset token (``new_password`` omitted/empty) for the
        operator to hand to the admin out of band. Either way, every
        existing refresh session for the admin is revoked, forcing
        re-authentication. Audits ``"org_admin.reset_password"``. Never
        echoes the password or hash.

        Parameters
        ----------
        admin_id:
            UUID of the org_admin.
        req:
            Optional ``new_password``; omit to mint a one-time reset token
            instead.

        Returns
        -------
        PlatformResetOrgAdminPasswordResponse
            ``reset`` is ``"password_set"`` or ``"token"`` (with ``token``
            + ``expires_in`` present only in ``"token"`` mode).

        Raises
        ------
        AudactAPIError
            400 if ``admin_id`` is not a valid UUID, or ``new_password`` is
            too short.
        AudactAuthError
            401 if not authenticated with a valid platform token.
        AudactNotFoundError
            404 if no org_admin has this ``admin_id``.
        """
        url = f"{self._base_url}/v1/platform/org-admins/{admin_id}/reset-password"
        body = (
            req or PlatformResetOrgAdminPasswordRequest()
        ).model_dump(mode="json", exclude_none=True)
        response = await self._client._request(
            "POST", url, json=body, auth_token=self._client.platform_token
        )
        return PlatformResetOrgAdminPasswordResponse.model_validate(response.json())


class PlatformClient:
    """
    Sub-client for platform-admin surfaces (``client.platform.*``).

    Exposes the platform admin-key methods (:meth:`list_admin_keys`,
    :meth:`add_admin_key`, :meth:`disable_admin_key`), the tenant lifecycle
    methods (:meth:`list_tenants`, :meth:`get_tenant`,
    :meth:`soft_delete_tenant`, :meth:`restore_tenant`) and :attr:`orgs`
    (:class:`PlatformOrgsClient`, ``client.platform.orgs.*``). Both are
    served by org-management (8092) and use the shared platform token set
    with :meth:`AudactClient.set_platform_token`. Platform tokens are
    single-use and action-scoped (``admin_keys`` for admin keys, ``org`` for
    organisations, ``tenant_lifecycle`` for tenants), so set a freshly minted
    token before each call. The
    pre-existing cross-tenant YAML export/import surface
    (:meth:`AudactClient.export_tenant`/:meth:`~AudactClient.export_agent`/
    :meth:`~AudactClient.import_tenant`, Tenant Management 8085) predates
    this sub-client and remains a set of flat methods on
    :class:`AudactClient` taking an explicit ``platform_token`` argument
    per call, rather than the shared in-memory token this sub-client uses.

    Do not construct directly; use ``AudactClient(...).platform``.
    """

    def __init__(self, client: AudactClient) -> None:
        self._client = client
        self.orgs = PlatformOrgsClient(client)

    @property
    def _base_url(self) -> str:
        return self._client._org_management_url

    async def list_admin_keys(self) -> ListAdminKeysResponse:
        """
        List every platform-admin key in the allowlist (active and disabled).

        Calls ``GET /v1/platform/admin-keys``. Requires PlatformBearer and a
        platform token minted for the ``"admin_keys"`` action. Identifiers
        only — never key material.

        Returns:
            ListAdminKeysResponse: ``admin_keys``, oldest first.

        Raises:
            AudactAuthError: 401/403 if the platform token is missing/invalid.
        """
        response = await self._client._request(
            "GET",
            f"{self._base_url}/v1/platform/admin-keys",
            auth_token=self._client.platform_token,
        )
        return ListAdminKeysResponse.model_validate(response.json())

    async def add_admin_key(
        self,
        *,
        kid: str,
        public_key_pem: str,
        operator: str | None = None,
    ) -> AdminKeyResponse:
        """
        Allowlist a platform-admin public key.

        Calls ``POST /v1/platform/admin-keys``. Requires a platform token
        minted for the ``admin_keys`` action. Responds 201 with the stored key.

        Args:
            kid: Key identifier.
            public_key_pem: PEM-encoded Ed25519 public key.
            operator: Optional operator name; omitted from the body when None.

        Returns:
            AdminKeyResponse: The newly allowlisted key.

        Raises:
            AudactAPIError: 400 on a malformed body; 409 if ``kid`` already exists.
            AudactAuthError: 401/403 if the platform token is missing/invalid.
        """
        req = AddAdminKeyRequest(kid=kid, public_key_pem=public_key_pem, operator=operator)
        response = await self._client._request(
            "POST",
            f"{self._base_url}/v1/platform/admin-keys",
            json=req.model_dump(mode="json", by_alias=True, exclude_none=True),
            auth_token=self._client.platform_token,
        )
        return AdminKeyResponse.model_validate(response.json())

    async def disable_admin_key(self, kid: str) -> AdminKeyResponse:
        """
        Disable a platform-admin key.

        Calls ``POST /v1/platform/admin-keys/{kid}/disable``. Requires a
        platform token minted for the ``admin_keys`` action. Disabling an
        already-disabled key succeeds.

        Args:
            kid: Identifier of the key to disable (URL-escaped).

        Returns:
            AdminKeyResponse: The disabled key.

        Raises:
            AudactNotFoundError: 404 if the key does not exist.
            AudactAPIError: 409 if it is the last active admin key (allowlist
                another key first).
            AudactAuthError: 401/403 if the platform token is missing/invalid.
        """
        response = await self._client._request(
            "POST",
            f"{self._base_url}/v1/platform/admin-keys/{quote(kid, safe='')}/disable",
            auth_token=self._client.platform_token,
        )
        return AdminKeyResponse.model_validate(response.json())

    async def list_tenants(
        self,
        q: str | None = None,
        organization: str | None = None,
        include_deleted: bool = False,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> PlatformListTenantsResponse:
        """
        List tenants across all organizations, newest first.

        Calls ``GET /v1/platform/tenants``. Requires a platform token minted
        for the ``tenant_lifecycle`` action. Soft-deleted tenants are omitted
        unless ``include_deleted`` is true.

        Args:
            q: Case-insensitive substring of the tenant name.
            organization: ``"any"`` (server default), ``"none"`` (tenants with
                no organization) or an organization id.
            include_deleted: Include soft-deleted tenants.
            limit: Page size (server default 50, maximum 200).
            cursor: ``next_cursor`` from a previous response, passed back verbatim.

        Returns:
            PlatformListTenantsResponse: ``tenants`` and ``next_cursor``.

        Raises:
            AudactAPIError: 400 on an invalid filter, limit or cursor.
            AudactAuthError: 401/403 if the platform token is missing/invalid.
        """
        params: dict[str, str | list[str]] = {}
        if q is not None:
            params["q"] = q
        if organization is not None:
            params["organization"] = organization
        if include_deleted:
            params["include_deleted"] = "true"
        if limit is not None:
            params["limit"] = str(limit)
        if cursor is not None:
            params["cursor"] = cursor
        response = await self._client._request(
            "GET",
            f"{self._base_url}/v1/platform/tenants",
            params=params or None,
            auth_token=self._client.platform_token,
        )
        return PlatformListTenantsResponse.model_validate(response.json())

    async def get_tenant(self, tenant_id: str) -> PlatformTenantResponse:
        """
        Fetch one tenant, including a soft-deleted one.

        Calls ``GET /v1/platform/tenants/{tenant_id}``. Requires a platform
        token minted for the ``tenant_lifecycle`` action.

        Args:
            tenant_id: Tenant id (URL-escaped).

        Returns:
            PlatformTenantResponse: ``tenant``.

        Raises:
            AudactNotFoundError: 404 if the tenant does not exist.
            AudactAuthError: 401/403 if the platform token is missing/invalid.
        """
        response = await self._client._request(
            "GET",
            f"{self._base_url}/v1/platform/tenants/{quote(tenant_id, safe='')}",
            auth_token=self._client.platform_token,
        )
        return PlatformTenantResponse.model_validate(response.json())

    async def soft_delete_tenant(self, tenant_id: str, reason: str) -> PlatformTenantResponse:
        """
        Soft-delete a tenant. Its API keys are rejected until it is restored.

        Calls ``POST /v1/platform/tenants/{tenant_id}/soft-delete``. Requires
        a platform token minted for the ``tenant_lifecycle`` action whose
        targets include ``tenant_id``. No data is erased.

        Args:
            tenant_id: Tenant id (URL-escaped).
            reason: Audit-log reason, 1-500 characters after trimming. Do not
                put PII in it.

        Returns:
            PlatformTenantResponse: The deleted tenant.

        Raises:
            ValueError: If ``reason`` is empty or whitespace; no request is sent.
            AudactNotFoundError: 404 if the tenant does not exist.
            AudactAPIError: 409 if the tenant is already deleted.
            AudactAuthError: 401/403 if the platform token is missing/invalid
                or was not minted for this tenant.
        """
        if not reason or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        req = PlatformSoftDeleteTenantRequest(reason=reason)
        response = await self._client._request(
            "POST",
            f"{self._base_url}/v1/platform/tenants/{quote(tenant_id, safe='')}/soft-delete",
            json=req.model_dump(mode="json", exclude_none=True),
            auth_token=self._client.platform_token,
        )
        return PlatformTenantResponse.model_validate(response.json())

    async def restore_tenant(
        self, tenant_id: str, reason: str | None = None
    ) -> PlatformTenantResponse:
        """
        Restore a soft-deleted tenant.

        Calls ``POST /v1/platform/tenants/{tenant_id}/restore``. Requires a
        platform token minted for the ``tenant_lifecycle`` action whose
        targets include ``tenant_id``. A tenant that is also disabled stays
        rejected.

        Args:
            tenant_id: Tenant id (URL-escaped).
            reason: Optional audit-log reason, at most 500 characters.

        Returns:
            PlatformTenantResponse: The restored tenant.

        Raises:
            AudactNotFoundError: 404 if the tenant does not exist.
            AudactAPIError: 409 if the tenant is not deleted.
            AudactAuthError: 401/403 if the platform token is missing/invalid
                or was not minted for this tenant.
        """
        req = PlatformRestoreTenantRequest(reason=reason)
        response = await self._client._request(
            "POST",
            f"{self._base_url}/v1/platform/tenants/{quote(tenant_id, safe='')}/restore",
            json=req.model_dump(mode="json", exclude_none=True),
            auth_token=self._client.platform_token,
        )
        return PlatformTenantResponse.model_validate(response.json())


# ─────────────────────────────────────────────────────────────────────────────
# AggregationClient — Merkle aggregation surface — aggregator (8087)
# ─────────────────────────────────────────────────────────────────────────────

class AggregationClient:
    """
    Sub-client for the Merkle aggregation surface (``client.aggregation.*``).

    Backed by the Aggregator service (default ``http://localhost:8087``,
    ``aggregator_url``/``AUDACT_AGGREGATOR_URL``). Aggregation periodically
    batches every tenant's per-window evidence into a padded Merkle tree,
    RFC 3161-timestamps the root, and chains the roots themselves into a
    meta-chain (chain-of-chains) — see ``docs/aggregator``.

    :meth:`list_proofs` and :meth:`get_proof` are tenant-scoped
    (``BearerAuth``, the tenant ``api_key``). :meth:`get_metachain` and
    :meth:`verify_inclusion` are **public** endpoints — no authentication
    or database access is required server-side (the SDK still sends the
    configured ``api_key`` header when present, which the server simply
    ignores for these two routes). :meth:`trigger_aggregation` requires the
    owner role.

    Do not construct directly; use ``AudactClient(...).aggregation``.
    """

    def __init__(self, client: AudactClient) -> None:
        self._client = client

    @property
    def _base_url(self) -> str:
        return self._client._aggregator_url

    async def list_proofs(
        self, *, cursor: str | None = None, limit: int | None = None
    ) -> Page[ProofSummary]:
        """
        List aggregation windows the authenticated tenant participated in.

        Calls ``GET /v1/proofs``. Results are ordered newest-first
        (``created_at DESC``).

        Parameters
        ----------
        cursor:
            Opaque pagination cursor from a previous page's
            ``next_cursor`` (cursor pagination convention).
        limit:
            Page size (server default 50, max 200).

        Returns
        -------
        Page[ProofSummary]
            ``items`` is the page of proof summaries; pass ``next_cursor``
            back as ``cursor`` while ``has_more`` is ``True`` to fetch
            subsequent pages.

        Raises
        ------
        AudactAuthError
            401 if unauthenticated.
        """
        params: dict[str, str] = {}
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)
        url = f"{self._base_url}/v1/proofs"
        response = await self._client._request("GET", url, params=params or None)
        parsed = ProofListResponse.model_validate(response.json())
        return Page[ProofSummary](
            items=parsed.proofs, has_more=parsed.has_more, next_cursor=parsed.next_cursor
        )

    async def get_proof(self, window_id: str) -> ProofResponse:
        """
        Get the per-tenant Merkle branch proof for a specific window.

        Calls ``GET /v1/proofs/{window_id}``. Returns the tenant's branch
        proof (authentication path from the tenant's aggregate-hash leaf to
        the window's Merkle root), the RFC 3161 timestamp token attesting
        that root, and the aggregation metadata.

        Parameters
        ----------
        window_id:
            Aggregation window ID — the canonical RFC 3339 timestamp string
            identifying the window (equals ``window_start`` in UTC).

        Returns
        -------
        ProofResponse

        Raises
        ------
        AudactAuthError
            401 if unauthenticated.
        AudactNotFoundError
            404 if the proof does not exist, or the tenant did not
            participate in that window.
        """
        from urllib.parse import quote

        url = f"{self._base_url}/v1/proofs/{quote(window_id, safe='')}"
        response = await self._client._request("GET", url)
        return ProofResponse.model_validate(response.json())

    async def get_metachain(
        self, *, cursor: str | None = None, limit: int | None = None
    ) -> Page[MetaChainEntry]:
        """
        Get a page of the meta-chain (chain-of-chains) of Merkle roots.

        Calls ``GET /v1/metachain`` — **public**, no authentication
        required. Entries are returned in ascending sequence order and
        contain only root hashes and integrity fields, never
        tenant-specific data.

        Parameters
        ----------
        cursor:
            Opaque pagination cursor from a previous page's
            ``next_cursor`` (cursor pagination convention).
        limit:
            Entries per page (server default 50, max 200).

        Returns
        -------
        Page[MetaChainEntry]
            ``items`` is the page of meta-chain entries; pass
            ``next_cursor`` back as ``cursor`` while ``has_more`` is
            ``True`` to fetch subsequent pages.
        """
        params: dict[str, str] = {}
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)
        url = f"{self._base_url}/v1/metachain"
        response = await self._client._request("GET", url, params=params or None)
        parsed = MetaChainResponse.model_validate(response.json())
        return Page[MetaChainEntry](
            items=parsed.entries, has_more=parsed.has_more, next_cursor=parsed.next_cursor
        )

    async def verify_inclusion(
        self, req: VerifyInclusionRequest
    ) -> VerifyInclusionResponse:
        """
        Cryptographically verify a Merkle inclusion proof.

        Calls ``POST /v1/verify-inclusion`` — **public**, no authentication
        or database access required server-side. Verifies that ``leaf_hash``
        is included in ``root`` via the supplied authentication ``steps``,
        entirely from the request body (no lookup against stored proofs).

        Parameters
        ----------
        req:
            The branch proof to verify (``leaf_hash``, ``root``, ``steps``,
            plus informational ``leaf_index``/``leaf_count``/``pad_count``/
            ``tree_depth`` fields not used in the verification computation).

        Returns
        -------
        VerifyInclusionResponse
            ``valid`` is ``True`` iff the proof cryptographically
            demonstrates inclusion.

        Raises
        ------
        AudactAPIError
            400 if the request body is invalid or missing required fields.
        """
        url = f"{self._base_url}/v1/verify-inclusion"
        response = await self._client._request(
            "POST", url, json=req.model_dump(mode="json", exclude_none=True)
        )
        return VerifyInclusionResponse.model_validate(response.json())

    async def trigger_aggregation(
        self,
        req: AdminAggregateRequest | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> AdminAggregateResponse:
        """
        Manually trigger the Merkle aggregation pipeline.

        Calls ``POST /v1/admin/aggregate``. Admin-only — requires the
        owner role. Runs the aggregation pipeline for the specified window
        (``window_start``/``window_end``, both RFC 3339 UTC — required
        together or omitted together) or, when the body is empty, for a
        server-computed window.

        Parameters
        ----------
        req:
            Optional window boundaries. Omit (or pass ``None``) to let the
            server compute the window.
        idempotency_key:
            Optional ``Idempotency-Key`` header value.

        Returns
        -------
        AdminAggregateResponse
            The resulting aggregation batch (Merkle root, leaf/tenant
            counts, RFC 3161 timestamp attestation).

        Raises
        ------
        AudactAPIError
            400 on invalid window parameters.
        AudactAuthError
            401 if unauthenticated.
        AudactForbiddenError
            403 if the caller does not have the owner role.
        """
        url = f"{self._base_url}/v1/admin/aggregate"
        body = (req or AdminAggregateRequest()).model_dump(mode="json", exclude_none=True)
        response = await self._client._request(
            "POST", url, json=body, idempotency_key=idempotency_key
        )
        return AdminAggregateResponse.model_validate(response.json())


class AudioClient:
    """
    Sub-client for the Audio Validator surface (``client.audio.*``).

    Backed by the Audio Validator service (default
    ``http://localhost:8086``, ``audio_validator_url``/
    ``AUDACT_AUDIO_VALIDATOR_URL``): per-turn audio compliance validation
    (ASR + segmentation + policy checks) and post-call audio-to-transcript
    reconciliation.

    Do not construct directly; use ``AudactClient(...).audio``.
    """

    def __init__(self, client: AudactClient) -> None:
        self._client = client

    @property
    def _base_url(self) -> str:
        return self._client._audio_validator_url

    async def validate_audio(self, req: ValidateAudioRequest) -> ValidateAudioResponse:
        """
        Validate a single turn of audio for compliance.

        Calls ``POST /v1/validate-audio``. Receives base64-encoded PCM (or
        WAV/MP3) audio, performs ASR transcription and compliance
        validation, and returns per-segment verdicts (``ALLOW``/``BLOCK``/
        ``MODIFY``), an audio routing action (``forward``/``substitute``/
        ``block``), and a compliance receipt carrying an HMAC integrity
        tag, with dual ``audio_hash`` + ``text_hash``.

        Parameters
        ----------
        req:
            The audio validation request (``call_id``, ``turn_number``,
            ``audio_data``, ``audio_format``, and optional ASR/
            segmentation overrides).

        Returns
        -------
        ValidateAudioResponse
            Aggregated ``verdict``, per-segment ``segments``, the signed
            ``receipt``, and evidence-write status.

        Raises
        ------
        AudactAPIError
            400 on a malformed request.
        AudactAuthError
            401 if unauthenticated.
        AudactForbiddenError
            403 on a cross-tenant call.
        """
        url = f"{self._base_url}/v1/validate-audio"
        response = await self._client._request(
            "POST", url, json=req.model_dump(mode="json", exclude_none=True)
        )
        return ValidateAudioResponse.model_validate(response.json())

    async def reconcile_audio(
        self,
        req: AudioReconciliationRequest,
        *,
        limit: int | None = None,
        after_sequence: int | None = None,
        idempotency_key: str | None = None,
    ) -> AudioReconciliationResponse:
        """
        Reconcile a full call recording against the validated evidence chain.

        Calls ``POST /v1/audio-reconciliation``. Accepts a full call
        recording, transcribes it via ASR, and reconciles the
        transcription segment-by-segment against the validated output
        events in the evidence chain.

        This is a **synchronous** endpoint — the call blocks until
        transcription and reconciliation are complete; for long recordings
        this may take several seconds. Supports PCM (``pcm_s16le_16000``),
        WAV, and MP3 audio formats.

        When ``req.configuration_id`` is supplied, the per-agent ASR
        credentials from that configuration are used; omit it to fall back
        to the tenant's first active configuration, or to the global ASR
        client when none is configured.

        Parameters
        ----------
        req:
            The reconciliation request (``call_id``, ``audio_data``,
            ``audio_format``, and optional ``configuration_id``/
            ``asr_provider``/``language``).
        limit:
            Max ``segment_results`` entries to return (server default
            100, max 200).
        after_sequence:
            Return only ``segment_results`` with ``sequence_number``
            greater than this value, for paging.
        idempotency_key:
            Optional ``Idempotency-Key`` header value; retried requests
            with the same key replay the original response.

        Returns
        -------
        AudioReconciliationResponse
            Full-count ``total_segments``/``matched_segments``/
            ``mismatched_segments``/``unvalidated_segments`` plus a page
            of ``segment_results`` (see ``has_more``).

        Raises
        ------
        AudactAPIError
            400 on invalid request (missing fields, bad audio format).
        AudactAuthError
            401 if unauthenticated.
        AudactForbiddenError
            403 if the call does not belong to the authenticated tenant.
        """
        params: dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(limit)
        if after_sequence is not None:
            params["after_sequence"] = str(after_sequence)
        url = f"{self._base_url}/v1/audio-reconciliation"
        response = await self._client._request(
            "POST",
            url,
            json=req.model_dump(mode="json", exclude_none=True),
            params=params or None,
            idempotency_key=idempotency_key,
        )
        return AudioReconciliationResponse.model_validate(response.json())


class AuthClient:
    """
    Sub-client for the API-key ↔ JWT session bridge (``client.auth.*``).

    Backed by the Tenant Management service (default
    ``http://localhost:8085``, ``tenant_management_url``/
    ``AUDACT_TENANT_MANAGEMENT_URL``), ``/v1/auth/*``: built for
    dashboard-style UIs that want a short-lived JWT instead of sending the
    raw tenant ``api_key`` on every request.

    :meth:`exchange_key` requires the tenant ``api_key`` (sent
    automatically as ``Authorization: Bearer <api_key>``, like every other
    method) and returns a 15-minute access token; the server also sets a
    7-day refresh token as an httpOnly, ``SameSite=Strict`` cookie scoped
    to ``/v1/auth``. :meth:`refresh_token` reads that cookie (never present
    in either JSON body) to rotate both tokens — this SDK's
    ``httpx.AsyncClient`` retains cookies across requests automatically, so
    calling ``exchange_key()`` then ``refresh_token()`` on the *same*
    ``AudactClient`` instance works without any extra plumbing.

    Do not construct directly; use ``AudactClient(...).auth``.
    """

    def __init__(self, client: AudactClient) -> None:
        self._client = client

    @property
    def _base_url(self) -> str:
        return self._client._tenant_management_url

    async def exchange_key(self) -> ExchangeKeyResponse:
        """
        Exchange the tenant API key for a short-lived JWT session.

        Calls ``POST /v1/auth/exchange-key``. Validates the ``Bearer`` API
        key and issues a short-lived access token (15 min, in the response
        body) plus a long-lived refresh token (7 days, as an httpOnly
        cookie).

        Returns
        -------
        ExchangeKeyResponse
            ``access_token``, ``token_type`` (``"Bearer"``), and
            ``expires_in`` (seconds).

        Raises
        ------
        AudactAuthError
            401 if the API key is invalid.
        """
        url = f"{self._base_url}/v1/auth/exchange-key"
        response = await self._client._request("POST", url)
        return ExchangeKeyResponse.model_validate(response.json())

    async def refresh_token(self) -> RefreshTokenResponse:
        """
        Rotate the JWT session using the refresh-token cookie.

        Calls ``POST /v1/auth/refresh``. Validates the refresh-token
        cookie set by :meth:`exchange_key` (or a previous
        :meth:`refresh_token` call) and issues a new access token plus a
        rotated refresh token (single-use rotation).

        Returns
        -------
        RefreshTokenResponse
            ``access_token``, ``token_type`` (``"Bearer"``), and
            ``expires_in`` (seconds).

        Raises
        ------
        AudactAuthError
            401 if the refresh token is missing, invalid, or expired.
        """
        url = f"{self._base_url}/v1/auth/refresh"
        response = await self._client._request("POST", url)
        return RefreshTokenResponse.model_validate(response.json())


# ─────────────────────────────────────────────────────────────────────────────
# Webhook signature verification helper
# ─────────────────────────────────────────────────────────────────────────────

def verify_webhook_signature(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    """
    Verify an inbound webhook delivery's HMAC-SHA256 signature.

    Mirrors the server's signing scheme:
    the header is ``"t=<unix_ts>,v1=<hex_hmac>"`` (or, during a secret
    rotation's 72-hour grace period, two ``v1=`` values — the old and new
    key's signatures — separated by commas: ``"t=<unix_ts>,v1=<hmac_old>,
    v1=<hmac_new>"``). The signed message is the exact byte concatenation
    ``"<unix_ts>." + <raw body bytes>``, HMACed with the tenant's webhook
    signing secret (from :meth:`WebhooksClient.rotate_webhook_secret` or
    the first :meth:`WebhooksClient.create_webhook` response) and
    hex-encoded. Returns ``True`` if **any** ``v1=`` value in the header
    matches — this lets a receiver holding either the old or the new
    secret verify deliveries made during a rotation grace period.

    All comparisons use :func:`hmac.compare_digest` (constant-time) to
    avoid timing side-channel attacks.

    This function does **not** enforce timestamp staleness — callers
    wanting replay protection should additionally check that the ``t=``
    timestamp in ``signature_header`` is recent (e.g. within 5 minutes),
    mirroring the server's ``VerifyWithTolerance``.

    Parameters
    ----------
    payload_bytes:
        The raw, exact request body bytes as received — do not
        re-serialize a parsed/re-encoded copy, as any byte difference
        (whitespace, key order) will make the signature fail to verify.
    signature_header:
        The value of the delivery's signature header
        (``"t=<ts>,v1=<hex>[,v1=<hex>]"``).
    secret:
        The tenant's webhook HMAC signing secret (64 lowercase hex
        characters).

    Returns
    -------
    bool
        ``True`` if the signature is valid, ``False`` otherwise (including
        on any malformed ``signature_header``).
    """
    import hashlib
    import hmac as hmac_module

    timestamp: str | None = None
    v1_values: list[str] = []
    for part in signature_header.split(","):
        part = part.strip()
        if part.startswith("t="):
            timestamp = part[len("t=") :]
        elif part.startswith("v1="):
            v1_values.append(part[len("v1=") :])

    if not timestamp or not v1_values:
        return False

    message = timestamp.encode("utf-8") + b"." + payload_bytes
    expected = hmac_module.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    return any(hmac_module.compare_digest(v1, expected) for v1 in v1_values)


# ─────────────────────────────────────────────────────────────────────────────
# Platform admin — module-level helpers
# ─────────────────────────────────────────────────────────────────────────────

def _accept_header_for_format(format: str | None) -> str | None:
    """
    Map a ``format`` argument to an ``Accept`` header value.

    ``None`` sends no ``Accept`` header at all, matching the server's own
    default (YAML). Any other value must be ``"yaml"`` or ``"json"``
    (case-insensitive).
    """
    if format is None:
        return None
    normalized = format.strip().lower()
    if normalized == "json":
        return "application/json"
    if normalized == "yaml":
        return "application/yaml"
    raise ValueError(f'format must be "yaml" or "json", got {format!r}')


# Repeatable request header carrying each `<ref>.<field>=<value>` secret
# assignment for import. A HEADER, never a URL query param, so the plaintext
# BYOK secret never lands in a reverse-proxy access log.
_SET_SECRET_HEADER = "X-Audact-Set-Secret"


def _normalize_set_secret(set_secret: Sequence[str] | Mapping[str, str] | None) -> list[str]:
    """Normalize ``set_secret`` into the repeated ``<ref>.<field>=<value>`` header values."""
    if set_secret is None:
        return []
    if isinstance(set_secret, Mapping):
        return [f"{key}={value}" for key, value in set_secret.items()]
    return list(set_secret)


_KYC_DEFAULT_CONTENT_TYPE = "application/octet-stream"
_KYC_DEFAULT_FILENAME = "upload"


def _path_segment(value: UUID | str) -> str:
    """Percent-encode ``value`` as exactly one URL path segment (``/`` included)."""
    return quote(str(value), safe="")


def _kyc_file_part(
    file: bytes | bytearray | IO[bytes],
    *,
    filename: str | None = None,
    content_type: str | None = None,
) -> tuple[str, bytes | bytearray | IO[bytes], str]:
    """
    Build the ``(filename, file, content_type)`` tuple httpx's ``files=``
    expects for a KYC document upload/replace multipart part.

    ``file`` may be raw bytes or an open, readable binary file handle. When
    ``filename`` is omitted and ``file`` exposes a string ``.name`` attribute
    (as an open file handle does), the base name of that path is used;
    otherwise falls back to ``"upload"``, the same default the server
    applies.
    """
    resolved_name = filename
    if resolved_name is None:
        name_attr = getattr(file, "name", None)
        if isinstance(name_attr, str) and name_attr:
            resolved_name = os.path.basename(name_attr)
        else:
            resolved_name = _KYC_DEFAULT_FILENAME
    return resolved_name, file, content_type or _KYC_DEFAULT_CONTENT_TYPE


_IMPORT_FILE_CHUNK_SIZE = 64 * 1024


async def _iter_file_chunks(
    fh: IO[bytes], chunk_size: int = _IMPORT_FILE_CHUNK_SIZE
) -> AsyncGenerator[bytes, None]:
    """
    Wrap a synchronous, readable binary file handle in an async byte-chunk
    generator so it can be streamed as the body of an ``AsyncClient`` request
    without ever buffering the whole file in memory at once.
    """
    while True:
        chunk = fh.read(chunk_size)
        if not chunk:
            break
        yield chunk


def _serialize_bundle_for_import(
    bundle: BundleInput,
) -> tuple[bytes | AsyncGenerator[bytes, None], str]:
    """
    Serialize ``bundle`` into the ``(content, content_type)`` pair for the
    import request body.

    ``PlatformBundle``/mapping inputs are serialized to YAML (the server
    accepts both YAML and JSON bodies, since bundle parsing is YAML-based and
    JSON is valid YAML). ``str``/``bytes`` inputs are passed through
    unmodified so a caller can reuse the exact bytes ``export_tenant()``
    would otherwise have produced. An open, readable binary file handle is
    wrapped in an async generator so the upload is streamed to the server
    rather than buffered in SDK memory.
    """
    if isinstance(bundle, PlatformBundle):
        data = bundle.model_dump(mode="json", by_alias=True, exclude_none=True)
        return yaml.safe_dump(data, sort_keys=False).encode("utf-8"), "application/yaml"
    if isinstance(bundle, Mapping):
        return yaml.safe_dump(dict(bundle), sort_keys=False).encode("utf-8"), "application/yaml"
    if isinstance(bundle, str):
        return bundle.encode("utf-8"), "application/yaml"
    if isinstance(bundle, (bytes, bytearray)):
        return bytes(bundle), "application/yaml"
    # Anything else is assumed to be an open, readable binary file handle (or
    # another object exposing a blocking `.read(size)` method).
    return _iter_file_chunks(bundle), "application/yaml"


class PIIClient:
    """
    Sub-client for the PII vault (``client.pii.*``).

    Evidence-layer routes (shred, identities, decrypt, shreds, exemptions) use
    ``evidence_layer_url``; ``get_settings``/``update_settings`` use the
    tenant-management URL. Callers pass identifier **hashes** only; compute
    them with :func:`audact.pii.client_hash`. Never log hashes or plaintext.
    """

    def __init__(self, client: AudactClient) -> None:
        self._client = client

    @property
    def _ev(self) -> str:
        return self._client._evidence_layer_url

    @staticmethod
    def _check_hash(identifier_type: str, identifier_hash: str) -> dict[str, str]:
        if identifier_type not in ("name", "email", "phone"):
            raise ValueError("identifier_type must be one of name, email, phone")
        if len(identifier_hash) != 64 or any(c not in "0123456789abcdef" for c in identifier_hash):
            raise ValueError("identifier_hash must be 64 lowercase hex characters")
        return PIIShredRequest.model_validate(
            {"identifier_type": identifier_type, "identifier_hash": identifier_hash}
        ).model_dump(mode="json")

    async def shred(
        self, identifier_type: str, identifier_hash: str, *, idempotency_key: str | None = None
    ) -> PIIShredResponse:
        """
        ``POST /v1/pii/shred``: erase every call that has this identity.

        Irreversible. Pass ``idempotency_key`` (sent as ``Idempotency-Key``) so
        a retry after a timeout replays the original response instead of
        running the erasure again.
        """
        body = self._check_hash(identifier_type, identifier_hash)
        r = await self._client._request(
            "POST", f"{self._ev}/v1/pii/shred", json=body, idempotency_key=idempotency_key
        )
        return PIIShredResponse.model_validate(r.json())

    async def list_call_identities(self, call_id: UUID) -> PIIIdentitiesResponse:
        """``GET /v1/calls/{call_id}/pii/identities``."""
        r = await self._client._request("GET", f"{self._ev}/v1/calls/{call_id}/pii/identities")
        return PIIIdentitiesResponse.model_validate(r.json())

    async def link_call_identity(
        self, call_id: UUID, identifier_type: str, identifier_hash: str
    ) -> PIILinkIdentityResponse:
        """``POST /v1/calls/{call_id}/pii/identities``: link an identity after the call."""
        body = self._check_hash(identifier_type, identifier_hash)
        r = await self._client._request(
            "POST", f"{self._ev}/v1/calls/{call_id}/pii/identities", json=body
        )
        return PIILinkIdentityResponse.model_validate(r.json())

    async def shred_call(
        self,
        call_id: UUID,
        identity_ids: Sequence[UUID] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> PIIShredResponse:
        """
        ``POST /v1/calls/{call_id}/pii/shred``; omitted ``identity_ids`` shreds all.

        Irreversible. Pass ``idempotency_key`` (sent as ``Idempotency-Key``) to
        make retries safe.
        """
        body: dict[str, Any] = {}
        if identity_ids is not None:
            body["identity_ids"] = [str(i) for i in identity_ids]
        r = await self._client._request(
            "POST",
            f"{self._ev}/v1/calls/{call_id}/pii/shred",
            json=body,
            idempotency_key=idempotency_key,
        )
        return PIIShredResponse.model_validate(r.json())

    async def decrypt(
        self, call_id: UUID, *, text: str | None = None, texts: Sequence[str] | None = None
    ) -> PIIDecryptResponse:
        """
        ``POST /v1/calls/{call_id}/pii/decrypt``; pass exactly one of ``text``/``texts``.

        Deliberately takes **no** idempotency key: an idempotency cache would
        store the decrypted plaintext response server-side. Decrypt is
        read-only, so a plain retry is already safe.
        """
        if (text is None) == (texts is None):
            raise ValueError("pass exactly one of text or texts")
        body: dict[str, Any] = {"text": text} if text is not None else {"texts": list(texts or [])}
        r = await self._client._request(
            "POST", f"{self._ev}/v1/calls/{call_id}/pii/decrypt", json=body
        )
        return PIIDecryptResponse.model_validate(r.json())

    async def list_erased_keysets(
        self, call_id: UUID | str, keyset_ids: Sequence[str]
    ) -> PIIErasedKeysetsResponse:
        """
        List which of the given keysets were crypto-erased for a call.

        Calls ``GET /v1/calls/{call_id}/pii/erased-keysets``.

        Args:
            call_id: The call the keysets belong to.
            keyset_ids: Keyset UUIDs taken from tokens; sent as repeated
                ``keyset_id`` query parameters.

        Returns:
            PIIErasedKeysetsResponse: the subset of ``keyset_ids`` that were erased.

        Raises:
            TypeError: ``keyset_ids`` is a bare ``str`` (not a sequence of ids).
            ValueError: ``keyset_ids`` is empty. Raised before any request.
        """
        if isinstance(keyset_ids, (str, bytes)):
            raise TypeError("keyset_ids must be a sequence of keyset ids, not a single string")
        ids = [str(k) for k in keyset_ids]
        if not ids:
            raise ValueError("keyset_ids must contain at least one keyset id")
        r = await self._client._request(
            "GET",
            f"{self._ev}/v1/calls/{quote(str(call_id), safe='')}/pii/erased-keysets",
            params={"keyset_id": ids},
        )
        return PIIErasedKeysetsResponse.model_validate(r.json())

    async def list_shreds(
        self, *, cursor: str | None = None, limit: int | None = None
    ) -> PIIShredsResponse:
        """``GET /v1/pii/shreds``: PII-free erasure log."""
        params: dict[str, str] = {}
        if cursor:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = str(limit)
        r = await self._client._request("GET", f"{self._ev}/v1/pii/shreds", params=params or None)
        return PIIShredsResponse.model_validate(r.json())

    async def get_settings(self) -> PIISettingsResponse:
        """``GET /v1/pii/settings`` (tenant-management)."""
        url = f"{self._client._tenant_management_url}/v1/pii/settings"
        r = await self._client._request("GET", url)
        return PIISettingsResponse.model_validate(r.json())

    async def update_settings(
        self, encryption_enabled: bool, *, idempotency_key: str | None = None
    ) -> PIISettingsResponse:
        """
        ``PUT /v1/pii/settings`` (tenant-management; owner role).

        ``idempotency_key``, when given, is sent as ``Idempotency-Key``.
        """
        url = f"{self._client._tenant_management_url}/v1/pii/settings"
        r = await self._client._request(
            "PUT", url, json={"encryption_enabled": encryption_enabled},
            idempotency_key=idempotency_key,
        )
        return PIISettingsResponse.model_validate(r.json())

    async def list_exemptions(self) -> PIIExemptionsResponse:
        """``GET /v1/pii/exemptions``."""
        r = await self._client._request("GET", f"{self._ev}/v1/pii/exemptions")
        return PIIExemptionsResponse.model_validate(r.json())

    async def add_exemption(self, exempt_type: str, identifier_hash: str) -> PIIExemption:
        """``POST /v1/pii/exemptions``: returns the stored exemption (201)."""
        body = {"exempt_type": exempt_type, "identifier_hash": self._check_hash(
            exempt_type, identifier_hash)["identifier_hash"]}
        r = await self._client._request("POST", f"{self._ev}/v1/pii/exemptions", json=body)
        return PIIExemption.model_validate(r.json())

    async def remove_exemption(self, exempt_type: str, identifier_hash: str) -> None:
        """``DELETE /v1/pii/exemptions/{exempt_type}/{identifier_hash}``.

        Uses the body-less path form: many proxies and HTTP clients drop DELETE bodies.
        The legacy body form (``DELETE /v1/pii/exemptions``) remains on the server.
        """
        h = self._check_hash(exempt_type, identifier_hash)["identifier_hash"]
        await self._client._request(
            "DELETE", f"{self._ev}/v1/pii/exemptions/{exempt_type}/{h}")

    async def remove_exemption_with_body(self, exempt_type: str, identifier_hash: str) -> None:
        """``DELETE /v1/pii/exemptions`` with a JSON body (legacy form).

        Prefer :meth:`remove_exemption`: some proxies and HTTP clients drop DELETE bodies.
        """
        body = {"exempt_type": exempt_type, "identifier_hash": self._check_hash(
            exempt_type, identifier_hash)["identifier_hash"]}
        await self._client._request("DELETE", f"{self._ev}/v1/pii/exemptions", json=body)
