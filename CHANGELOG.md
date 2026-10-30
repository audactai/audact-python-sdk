# Changelog

All notable changes to the `audact` Python SDK are documented in this file.

## [Unreleased]

## [0.4.0] - 2026-10-29

### Packaging

- The package is now typed: it ships a `py.typed` marker (PEP 561).
- `setup.py` was removed; install with any PEP 660-capable pip.
- License metadata uses an SPDX expression (`MIT`) and the license file is
  included in the wheel.
- Python 3.14 is supported.

### Breaking

- `CallRecord.metadata` and `CallDetail.metadata` are now `dict[str, Any] | None`
  (were `str`); `ViolationRecord.data` and `PolicyRuleConditionDoc.value` are
  now `Any` (were `str`). `scope` on webhook models is now the `WebhookScope`
  `Literal["account", "agent", "compliance"]` instead of `str`.

### Fixed

- Listing and reading calls, listing violations and reading a policy raised
  `ValidationError` (`Input should be a valid string`) on real API responses,
  because the models typed object/bool/list fields as `str`.

### Deprecated

- `finalize_call_score`: `POST /v1/calls/{call_id}/finalize-score` is an
  internal endpoint, not routed on the public API. It emits a
  `DeprecationWarning` and will be removed in a future release.

### Added

- Platform tenant lifecycle on `client.platform`: `list_tenants(q=..., organization=...,
  include_deleted=..., limit=..., cursor=...)`, `get_tenant`, `soft_delete_tenant(tenant_id,
  reason)` and `restore_tenant(tenant_id, reason=None)`, with the models `PlatformTenant`,
  `PlatformListTenantsResponse`, `PlatformTenantResponse`, `PlatformSoftDeleteTenantRequest`
  and `PlatformRestoreTenantRequest`. They need a platform token minted for the
  `tenant_lifecycle` action.
- `TTSModel` accepts `"eleven_v4_turbo"` and `"eleven_v3_conversational"`
  (ElevenLabs realtime models).
- `KBSource.chunk_count`, `KBSource.crawl_coverage` (new `KBCrawlCoverage`:
  discovered / stored / excluded / failed pages) and `KBSource.last_ingested_at`:
  the outcome of the source's latest successful ingestion. `None`
  until a first ingestion has finished.
- `list_voices(limit=...)` (1-1000; server default 100 per provider) and
  `VoiceProvider.total` / `VoiceProvider.truncated`.

- ElevenLabs languages: `Voice.languages`, `VoiceProvider.models` /
  `TTSModelInfo`, and `list_voices(language=..., provider=...)` (native
  speakers first; keyword-only and optional).
- ElevenLabs TTS: `TTSProvider` accepts `"elevenlabs"`; new `TTSModel`
  Literal (`""` = provider default, `eleven_flash_v2_5`, `eleven_turbo_v2_5`,
  `eleven_multilingual_v2`, `voxtral-mini-tts-2603`) as `tts_model` on
  create/update/patch requests (omitted when `None`), `tts_model` on `Agent` /
  `CreateAgentResponse`, and `ttsModel` on `PlatformAgentSpec`. `list_voices()`
  returns an `elevenlabs` group; the voice must belong to the chosen provider.

### Changed

- `AddKBSourceRequest.type` is narrowed to `"url" | "text"`; `"file"` was always
  rejected on that JSON body (use `upload_kb_source_file`).

- `get_configuration_version(config_id, version)` for
  `GET /v1/configurations/{config_id}/versions/{version}`: one
  immutable earlier version of a configuration, as a `Configuration`.
- `ResolvedConfigVersion` carries the settings the version ran with
  (`countries`, `validator_modes`, `blocklist_patterns`, `pricing_bands`,
  `consent_config`, `prompt_confidentiality_config`, `disclosure_texts`,
  `fallback_response`, `output_constraint`, `end_call`, `voicemail`,
  `begin_message`, `llm_provider`, `llm_model`).
- `AudioComplianceReceipt.call_id`, `turn_number`, `timestamp`,
  `config_seal_hash`, `auth_mechanism` and `receipt_format_version`.
- `UsageRecord.source` (`UsageRecordSource`: `"stored"` | `"live"`).
- `AudioSegmentResult.transcription_status` (`TranscriptionStatus`:
  `"transcribed"` | `"no_speech"`), closing a schema drift.
- `ValidateAudioRequest.config_seal_hash` and
  `TurnDeliveryStatus.confirmation_count`, closing schema drift.
- `generate_c2pa_manifest(call_id, *, idempotency_key=None)` sends an
  `Idempotency-Key`. Every manifest is stored permanently, so retries
  should carry a key.

### Fixed

- Agent create/update/patch `voice_id` accepts any string
  (`AgentCreateVoiceId | str`, `AgentVoiceId | str`). Tenant-cloned voice ids
  (`POST /v1/voices`) used to fail pydantic validation.
- Secret request and response fields (`upstream_llm_key`, `sip_password`,
  `auth_password`, `signing_secret`, `api_key`, `password`, `token`,
  `tenant_token`, `new_password`) are excluded from `repr()`, so `print(req)`
  or a log line cannot leak them. They are still serialised normally.
- `disable_admin_key` documents the server's real semantics. 409 means "last
  active admin key", and disabling an already-disabled key succeeds. The
  admin-key methods name the `admin_keys` token action, and the
  `PlatformClient` docstring lists the admin-key methods.
- `list_compliance_events` is no longer described as "non-ALLOW results".
  README: the `client.platform` row names Org Management and the platform
  token, not Tenant Management and an API key.

### Changed

- New `Literal` aliases `KBRobotsPolicy` (`"honor"` | `"override"`) and
  `KBRetrievalTurnRole` (`"user"` | `"assistant"` | `"system"`).
- `CreateKnowledgeBaseRequest.robots_policy`, `KnowledgeBase.robots_policy`
  and `KBTestHarnessTurn.role` are narrowed from `str` to these types.
- `KnowledgeBase.robots_policy` now defaults to `None` instead of `""`.

### Added — knowledge bases

- New sub-client `client.knowledge_bases` (`KnowledgeBasesClient`, Tenant
  Management 8085) covering the 20 `knowledge-bases` operations:
  `list_knowledge_bases` (cursor `Page`), `create_knowledge_base`,
  `get_knowledge_base`, `patch_knowledge_base`, `delete_knowledge_base`;
  `list_kb_sources`, `add_kb_source` (JSON url/text), `get_kb_source`,
  `patch_kb_source`, `reingest_kb_source`, `delete_kb_source`;
  `list_kb_agent_links`, `list_kb_links_by_agent`, `put_kb_agent_link`,
  `patch_kb_agent_link`, `delete_kb_agent_link`; `list_exclusions`,
  `add_exclusion`, `delete_exclusion`; `test_kb_retrieval`.
- `upload_kb_source_file(kb_id, file, *, filename, content_type, config)`
  sends the multipart form of `addKBSource` for file sources.
- Every path identifier is percent-encoded as a single segment.
- New models (one per `kb.*` definition): `KnowledgeBase`,
  `ListKnowledgeBasesResponse`, `CreateKnowledgeBaseRequest`,
  `PatchKnowledgeBaseRequest`, `KBSource`, `ListKBSourcesResponse`,
  `AddKBSourceRequest`, `PatchKBSourceRequest`, `KBAgentLink`,
  `ListKBAgentLinksResponse`, `PutKBAgentLinkRequest`,
  `PatchKBAgentLinkRequest`, `KBCrawlExclusion`, `ListKBExclusionsResponse`,
  `AddKBExclusionRequest`, `KBTestHarnessTurn`, `KBTestHarnessHit`,
  `KBTestRetrievalRequest`, `KBTestRetrievalResponse`; enum aliases
  `KBSourceType` and `KBSourceStatus` (default `None`). The SDK now covers
  208 of 210 operations.

### ⚠️ Breaking — C2PA manifests are now really signed (generator 2.0.0)

- `C2PAManifest.signature` (HMAC hex) is **removed**; `signature_algorithm`
  is now `"ES256"`. Anything reading `manifest.signature` must switch to
  downloading the manifest store and verifying it with `c2patool`.
- `C2PAManifest` gains `manifest_id`, `call_id`, `asset`, `manifest_store`
  and `signing_credential`. New models: `C2PAHashDataAssertionData`
  (`c2pa.hash.data`, added to the assertion `data` union), `C2PAAssetRef`,
  `C2PAManifestStoreRef`, `C2PASigningCredential`.
- New methods: `list_c2pa_manifests(call_id)`,
  `download_c2pa_manifest_store(call_id, manifest_id) -> bytes`,
  `download_c2pa_asset(call_id, manifest_id) -> bytes` (follows the 302 to
  the presigned URL without forwarding credentials), and
  `get_c2pa_trust_anchor() -> str`.
- The C2PA enum fields follow the spec as `Literal` aliases that default to
  `None`, per the 0.3.0 convention: `C2PAAssertion.label`
  (`C2PAAssertionLabel`), `C2PAAssetRef.kind` (`C2PAAssetKind`), and
  `C2PASigningCredential.trust` / `C2PAListSigner.trust` (`C2PATrust`).
- New model `C2PAManifestListResponse` (the raw list body, reshaped into
  `Page` by `list_c2pa_manifests`). The SDK now covers 188 of 190 operations.

## [0.3.0] - 2026-10-15

Brings the SDK in line with the documented Audact API (186 operations, 184
covered).

### ⚠️ Behavioural change — wire-type fixes

- Enum-typed fields are now `Literal[...]` aliases mirroring the swagger
  enums: a request value outside the spec enum raises a pydantic
  `ValidationError` client-side, and a response carrying an unlisted value
  fails validation.
- Response enum fields that defaulted to `""` now default to `None`, and a
  wire `""` is normalised to `None` (`CallDetail.termination_class`,
  `PhoneNumber.trunk_provider`, `CallStatusResponse.status`,
  `TransferSessionResponse.status`/`transfer_option`,
  `Inbound/OutboundTrunkSummary.provider`, `Create*TrunkResponse.provider`,
  `WebhookDeliveryRecord.status`, `Article50Report.direction`,
  `PIIExemption.exempt_type`, `PIIIdentity.type`/`role`/`source`,
  `PIIShredRecord.identity_type`/`scope`, `CallingHoursCheckResponse.reason`).
- Trunk `provider` is now `TrunkProvider` (`telnyx`|`twilio`), not `SipProvider`.
- `key_id` is now filled from `api_key_id` where both exist.

### Added

- **5 new operations:** `list_erased_keysets` (`GET /v1/calls/{call_id}/pii/erased-keysets`),
  `list_compliance_events` (`GET /v1/compliance/events`), and platform
  `list_admin_keys`, `add_admin_key`, `disable_admin_key`.
- **Models:** `PIIErasedKeysetsResponse`, `ComplianceEvent`,
  `ListComplianceEventsResponse`, `AdminKey`, `AddAdminKeyRequest`,
  `ListAdminKeysResponse`, `AdminKeyResponse`, the compliance literals, and
  `CreateVoiceJSONRequest`.
- **`base_url` / `AUDACT_BASE_URL`:** one host for every service. Precedence
  per service: `x_url=` kwarg, `AUDACT_X_URL`, `base_url`, `AUDACT_BASE_URL`,
  default. A trailing `/` or `/v1` is stripped.
- **Schema-parity test** (`tests/test_schema_parity.py`) comparing pydantic
  models with swagger definitions.
- Error-envelope tests (nested/flat bodies, `X-Request-ID` fallback,
  `retry_after`).

### Fixed

- Many models gained fields missing from the spec (e.g. `CallRecord.channel`,
  `CallDetail.pii_mode`/`transcript_status`, `CallSummary.analysis_status`/
  `summary_status`/`sentiment`/`disposition`/`key_facts`/`extraction`,
  `ToolConfig.destination_hint`) plus 33 further models brought to spec.
- The parity test reads the documented API specification.

### Changed

- Project metadata: author email `sdk@audact.ai`; Homepage, Repository,
  Documentation and Bug Tracker URLs point to `audact.ai` and
  `github.com/audactai/audact-python-sdk`.
- `ComplianceEvent.event_subtype` is one of the 3 values the event log
  returns (`ComplianceEventLogSubtype`); the 6-value `ComplianceEventSubtype`
  is the `list_compliance_events` filter. Only `agent_id`, `event_subtype` and
  `timestamp` are always present on a `ComplianceEvent`; the other fields are
  `None` when the server omits them (an ALLOW turn has no check or severity).

## [0.2.0]

Full parity with the documented API: **160 of 162** operations in
the documented API are now covered (the remaining 2 are receive-side
provider→platform webhooks, ignore-listed — see `tests/test_parity.py`).
This is a ~4x expansion over `0.1.0`'s 37 operations (~23%).

### ⚠️ Behavioural change — error-envelope parsing (was a P0 bug)

`AudactAPIError`/`AudactRateLimitError` previously read `code`/`message`/
`details` from the **top level** of an error response body. The Audact API
actually nests these under `error` — `{"error": {"code", "message", "hint",
"details", "request_id"}}` — so in practice every
real API error degraded to `code="UNKNOWN"` with `message` set to the raw
response text, and `hint`/`request_id` were silently dropped.

`_raise_for_status()` now parses `body["error"]` first, falling back to the
top level only if `error` is absent (forward-compatible with any endpoint
that is not yet migrated to the envelope). **If you were pattern-matching
on `exc.code == "UNKNOWN"` or parsing `str(exc)` to recover error details,
`exc.code`/`exc.message` will now reflect the real server-provided values**
— update any such workarounds.

New attributes on `AudactAPIError`: `hint` (optional remediation string)
and `request_id` (also read from the `X-Request-ID` response header as a
fallback) — quote `request_id` when contacting support.

### Added

- **Auth:** `org_token`/`platform_token` constructor kwargs (+
  `AUDACT_ORG_TOKEN`/`AUDACT_PLATFORM_TOKEN` env fallbacks) so a sub-client
  can authenticate with a bearer token other than the API key.
- **4 new service base URLs:** `audio_validator_url` (8086),
  `aggregator_url` (8087), `agent_worker_url` (8089),
  `org_management_url` (8092), each with the standard constructor
  kwarg / `AUDACT_*_URL` env-var / `http://localhost:<port>` default
  pattern.
- **Idempotency:** `idempotency_key` is now a uniform optional parameter on
  every POST mutation (previously ad-hoc on a handful of methods).
- **Pagination:** a generic `Page[T]` model (`items`/`has_more`/
  `next_cursor`) and a `cursor` parameter convention on every list method
  (manual cursor — no automatic `async for` iterator, matching the
  TypeScript SDK).
- **Rate limits:** `AudactRateLimitError.retry_after` (from `Retry-After`)
  and `retry_after`/`rate_limit` (an `X-RateLimit-Limit`/`-Remaining`/
  `-Reset` snapshot via the new `RateLimitInfo` model); `client.last_rate_limit`
  exposes the most recent snapshot seen on any response.
- **Retries:** an opt-in, off-by-default (`max_retries=0`) bounded
  retry-with-backoff for idempotent `GET`s and `429`/`5xx` responses,
  honoring `Retry-After`. Never applied to Validator-adjacent calls
  (`/v1/validate`), which have a hard 40ms budget.
- **New sub-clients:** `client.calls` (SIP call lifecycle, trunks, routes,
  admission URL, WS tickets), `client.webhooks` (CRUD, test, deliveries,
  event-type/schema discovery, secret rotation, plus a
  `verify_webhook_signature()` helper), `client.agents` (agent CRUD +
  duplicate, voice catalog, pipeline status; the `Agent`/`CreateAgentRequest`/
  `UpdateAgentRequest` models now cover the full current agent config —
  `begin_message`, `start_speaker`, `greet_on_connect`,
  `max_duration_seconds`, `post_call_summary`, `post_call_extraction`,
  `voicemail`, `end_call`, `jurisdiction`, `llm_model`/`llm_provider`,
  `tool_ids`, `voice_id`/`stt_provider`/`tts_provider`),
  `client.tools` (tool CRUD/test, agent-tool attach/detach),
  `client.integrations` (Cal.com connections + OAuth), `client.org`
  (OrgBearer: signup/login/refresh/logout, profile, KYC, org-tenant
  lifecycle), `client.platform.orgs` (PlatformBearer: organization
  verify/reject, org-admin recovery), `client.aggregation` (Merkle
  aggregation proofs, public meta-chain, inclusion verification),
  `client.audio` (per-turn audio validation, audio-transcript
  reconciliation), `client.auth` (API-key ↔ JWT exchange/refresh).
- **Evidence completion:** `list_calls`, `get_call_detail`,
  `get_call_recording`, `delete_call_recording`, `get_call_summary`,
  `list_violations`, `get_article50_report`, `get_evidence_export`,
  `generate_c2pa_manifest`, `get_receipt` (including the
  `verifiability` field — `"unknown"`/`"verifiable"`/
  `"unverifiable_pre_horizon"`), `get_delivery_status`,
  `confirm_delivery`, `reconcile_transcript`,
  `get_article50_public_key`.
- **Numbers lifecycle completion:** `list_numbers`, `create_number`,
  `lookup_number`, `assign_number`, `suspend_number`, `resume_number`,
  `release_number`, `delete_number`, `set_number_trunk`.
- **Tenants/validator/policy/proxy/health completion:** `get_tenant_usage`,
  `finalize_call_score` (plus validator mode-marker and config-seal fields
  on the verdict model), `check_calling_hours`, `proxy_openai_stream`,
  `health`.
- **Examples:** `examples/end_to_end_flow.py` — create an agent, provision
  + assign a phone number via the order flow, place a browser test call,
  then list/read calls; supports a `--check` dry-run mode with no network
  access required.
- **Parity guard:** `tests/test_parity.py`, an anti-drift ratchet that loads
  the documented API specification and asserts every documented operation (minus the
  2-webhook ignore-list) maps to a callable SDK method.

### Preserved

- Every previously-exported flat method on `AudactClient` (`validate`,
  `evaluate`, `get_policy`, `post_event`, `get_chain`, `verify_chain`,
  `reconstruct_chain`, tenant/key/configuration CRUD, `proxy_stream`/
  `proxy_request`, the full KYC document/document-set surface, and the
  Telnyx number-order flow) keeps its existing name and signature —
  no breaking renames.

## [0.1.0]

Initial hand-written async SDK: Validator, Policy Engine, Evidence Layer
(core events/chains), Tenants, API Keys, Configurations, LLM Proxy, and the
KYC + Telnyx number-order flow.
