# audact

Async Python SDK for the [Audact](https://audact.ai) compliance validation platform.

## Requirements

- Python 3.11+
- [`httpx`](https://www.python-httpx.org/) for async HTTP
- [`pydantic`](https://docs.pydantic.dev/) v2 for type safety

## Installation

```bash
pip install audact
```

For development:

```bash
pip install 'audact[dev]'
```

## Quick start

```python
import asyncio
import os
import uuid
from audact import AudactClient

async def main():
    async with AudactClient(api_key=os.environ["AUDACT_API_KEY"]) as client:
        # Validate a conversation turn
        result = await client.validate(
            call_id=uuid.uuid4(),
            tenant_id=uuid.UUID("..."),
            config_id=uuid.UUID("..."),
            turn=1,
            content="Hello, this is an automated message.",
        )
        print(result.verdict)  # "ALLOW" | "BLOCK" | "MODIFY"

asyncio.run(main())
```

## Base URL

Point the client at one host with `base_url`; every service resolves to it
and the SDK adds the `/v1/...` paths itself (a trailing `/` or `/v1` on
`base_url` is stripped):

```python
client = AudactClient(api_key="aud_live_...", base_url="https://api.audact.ai")
```

For another deployment set the environment instead, no code change:

```bash
export AUDACT_BASE_URL=https://your-audact-host.example
```

Resolution order per service: `<service>_url=` kwarg → `AUDACT_<SERVICE>_URL`
env → `base_url=` kwarg → `AUDACT_BASE_URL` env → `http://localhost:<port>`.
Per-service URLs are only needed for local stacks where each service runs on
its own port (see [Configuration](#configuration)).

## Configuration

All service base URLs default to `http://localhost:<port>` for local development.
Override them via constructor keyword arguments or environment variables:

| Environment variable            | Default                   |
|----------------------------------|---------------------------|
| `AUDACT_API_KEY`                 | *(empty)*                 |
| `AUDACT_BASE_URL`                | *(unset)* — one host for every service (see [Base URL](#base-url)) |
| `AUDACT_POLICY_ENGINE_URL`       | `http://localhost:8081`   |
| `AUDACT_VALIDATOR_URL`           | `http://localhost:8082`   |
| `AUDACT_EVIDENCE_LAYER_URL`      | `http://localhost:8083`   |
| `AUDACT_LLM_PROXY_URL`           | `http://localhost:8084`   |
| `AUDACT_TENANT_MANAGEMENT_URL`   | `http://localhost:8085`   |
| `AUDACT_AUDIO_VALIDATOR_URL`     | `http://localhost:8086`   |
| `AUDACT_AGGREGATOR_URL`          | `http://localhost:8087`   |
| `AUDACT_VOICE_GATEWAY_URL`       | `http://localhost:8088`   |
| `AUDACT_AGENT_WORKER_URL`        | `http://localhost:8089`   |
| `AUDACT_ORG_MANAGEMENT_URL`      | `http://localhost:8092`   |
| `AUDACT_ORG_TOKEN`               | *(empty)* — OrgBearer JWT for `client.org.*` |
| `AUDACT_PLATFORM_TOKEN`          | *(empty)* — PlatformBearer token for `client.platform.orgs.*` |

`max_retries` (constructor kwarg, default `0`) opts into a bounded
retry-with-backoff for idempotent `GET`s and `429`/`5xx` responses — see
[Retries](#retries--rate-limits) below.

## Coverage

The SDK is at full parity with the documented API: **208 of 210** operations in
the documented API are covered. The remaining 2 are receive-side
provider→platform webhooks — `POST /telnyx/webhook` and
`POST /webhooks/livekit` — which are ingress endpoints Audact *receives*,
never calls. An internal parity test fails the build if any documented operation
loses SDK coverage.

The SDK is **monolithic with attribute sub-clients**: every pre-existing
flat method on `AudactClient` (e.g. `client.validate`, `client.evaluate`,
`client.create_tenant`) keeps working unchanged, and the large new surfaces
added for parity are exposed as `client.<name>.*` sub-clients:

| Sub-client              | Service (port)          | Auth                          | What it covers |
|--------------------------|--------------------------|-------------------------------|----------------|
| *(flat methods)*        | Validator (8082)         | API key                       | Per-turn ACVF validation, `finalize_call_score` |
| *(flat methods)*        | Policy Engine (8081)     | API key                       | Policy evaluation, jurisdiction policy documents, `check_calling_hours` |
| *(flat methods)*        | Evidence Layer (8083)    | API key                       | Evidence events, chains, verify/reconstruct, calls, violations, `list_compliance_events` (validation results incl. ALLOW, violations and fail-opens; cursor-paginated), Article 50 reports/exports, C2PA, receipts, delivery, transcript reconciliation |
| *(flat methods)*        | LLM Proxy (8084)         | API key                       | Compliance-validated LLM chat completion (sync + streaming), `proxy_openai_stream` |
| *(flat methods)*        | Tenant Management (8085) | API key                       | Tenant CRUD, `get_tenant_usage`, API keys, configurations, KYC documents/sets, platform export/import (`export_tenant`/`export_agent`/`import_tenant` take a per-call `platform_token` minted for the `export`/`import` action) |
| *(flat methods)*        | Voice Gateway (8088)     | API key                       | Number provisioning order flow + management lifecycle (list/create/lookup/assign/suspend/resume/release/delete/set-trunk, origin-aware `create_number`), bring-your-own (BYO) SIP trunk connection CRUD/verify + deployment SIP ingress config |
| `client.calls`           | Voice Gateway (8088)     | API key                       | SIP call lifecycle (outbound/inbound/browser, hangup, status, handover, transfer), trunks, dispatch rules, admission URL, WS tickets |
| `client.webhooks`        | Tenant Management (8085) | API key                       | Webhook endpoint CRUD, test-ping, delivery history/resend, event-type/schema discovery, secret status/rotation, `verify_webhook_signature` helper |
| `client.agents`          | Agent Worker (8089)      | API key                       | Agent CRUD + duplicate, TTS voice catalog CRUD, pipeline status |
| `client.tools`           | Agent Worker (8089)      | API key                       | Function-calling tool CRUD/test, agent-tool attach/detach |
| `client.knowledge_bases` | Tenant Management (8085) | API key                       | Knowledge-base (RAG) CRUD, sources (url/text, `upload_kb_source_file` multipart, re-ingest), agent links + retrieval tuning, crawl exclusions, `test_kb_retrieval` harness |
| `client.integrations`    | Agent Worker (8089)      | API key                       | Cal.com connection CRUD/test, event-type discovery, OAuth start/callback |
| `client.aggregation`     | Aggregator (8087)        | API key (public: `get_metachain`, `verify_inclusion`) | Merkle aggregation proofs, public meta-chain, offline inclusion verification |
| `client.audio`           | Audio Validator (8086)   | API key                       | Synchronous per-turn audio validation, post-call audio-to-transcript reconciliation |
| `client.auth`            | Tenant Management (8085) | API key                       | API-key ↔ JWT session bridge (`exchange_key`, `refresh_token`) |
| `client.org`             | Org Management (8092)    | **OrgBearer** (JWT)           | Org self-service: signup/login/refresh/logout, profile, KYC, plus the org-owned tenant lifecycle (list/create/get, soft-delete/enable/disable/restore, initialize, issue key, impersonate) |
| `client.platform`        | Org Management (8092)    | **PlatformBearer** (Ed25519, `admin_keys` action) | Admin signing keys: `list_admin_keys`, `add_admin_key`, `disable_admin_key` (export/import are the flat Tenant Management methods above) |
| `client.pii`             | Evidence Layer (8083)    | API key                       | PII keyset erasure status, incl. `list_erased_keysets(call_id, keyset_ids)` |
| `client.platform.orgs`   | Org Management (8092)    | **PlatformBearer** (Ed25519)  | Platform-admin org surface: list/verify/reject organizations, find/recover org admins |

### Auth flows

Most methods send `Authorization: Bearer <api_key>` using the `api_key`
passed to the `AudactClient` constructor. Two surfaces use a different
bearer token:

- **OrgBearer** — a JWT obtained from `client.org.login()`. The SDK stores it
  in-memory on the client automatically; every subsequent `client.org.*`
  call sends it instead of the API key.
- **PlatformBearer** — a pre-minted Ed25519 token. The SDK **never mints
  this token** — pass it via the `platform_token` constructor kwarg (or the
  `AUDACT_PLATFORM_TOKEN` env var) up front.

```python
async with AudactClient(api_key="aud_live_...") as client:
    # login() is public (no bearer required) and stores the returned access
    # token on client.org automatically.
    await client.org.login(OrgLoginRequest(email="admin@example.com", password="hunter2"))

    # Subsequent calls send `Authorization: Bearer <jwt>`.
    profile = await client.org.get_profile()
    tenants = await client.org.list_tenants()

    # Rotate the token before it expires, then clear it when done.
    await client.org.refresh()
    await client.org.logout()

# Or start pre-authenticated:
client = AudactClient(
    api_key="aud_live_...",
    org_token="<jwt from a prior login>",
    platform_token="<pre-minted Ed25519 token>",
)
```

## Choosing a TTS provider

Agents speak through Voxtral by default. To use ElevenLabs, set the provider,
optionally a model, and a voice from the provider's group in `list_voices()`:

```python
voices = await client.agents.list_voices()
voice = voices["elevenlabs"].voices[0].voice_id

await client.agents.create_agent(
    CreateAgentRequest(
        name="Concierge",
        tts_provider="elevenlabs",
        tts_model="eleven_flash_v2_5",  # omit for the provider default
        voice_id=voice,
    )
)
```

A voice from another provider is rejected with a 400 naming `voice_id`.

## Streaming

```python
async with AudactClient(api_key="...") as client:
    async for chunk in client.proxy_stream(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [...], "stream": True},
    ):
        print(chunk.decode(), end="", flush=True)
```

## KYC documents & number provisioning

Tenant identity is always taken from the API key — none of these methods
take a `tenant_id` parameter. Document uploads are `multipart/form-data`;
document bytes are never returned by any endpoint (metadata + `sha256` only).

```python
async with AudactClient(api_key="aud_live_...") as client:
    # Upload a KYC document (raw bytes or an open file handle both work).
    doc = await client.upload_kyc_document(
        open("passport.pdf", "rb"), doc_type="passport"
    )

    # Discover what Telnyx requires, then create + submit a document set.
    requirements = await client.get_kyc_requirements(country="NL", number_type="mobile")
    doc_set = await client.create_kyc_document_set(
        CreateKYCDocumentSetRequest(
            name="NL mobile KYC",
            country_code="NL",
            number_type="mobile",
            items=[
                KYCDocumentSetItemRequest(requirement_id=req.id, document_id=doc.id)
                for req in requirements
            ],
        )
    )

    # Once doc_set.status == "approved" (poll get_kyc_document_set), place an order.
    order = await client.create_number_order(
        CreateNumberOrderRequest(country_code="NL", number_type="mobile", set_id=doc_set.id)
    )
    order = await client.wait_for_order(order.id)  # polls until success/failure/cancelled
```

## Bring-your-own (BYO) telephony

Tenant identity is always taken from the API key. BYO is pure JSON — no
multipart involved. SIP credentials (`sip_username`/`sip_password`) are
write-only: stored in AWS Secrets Manager and never echoed back on any
response (`has_credentials` is a boolean flag only).

```python
async with AudactClient(api_key="aud_live_...") as client:
    # Fetch this deployment's SIP ingress host before configuring any trunk.
    config = await client.get_byo_config()
    print(config.sip_ingress_host, config.signaling_ips)

    # Register a BYO SIP trunk connection (either creds or an IP allowlist
    # is required) — runs a connect-time health probe before returning.
    conn = await client.create_byo_connection(
        CreateBYOConnectionRequest(
            name="Acme HQ Twilio Trunk",
            provider="twilio",
            sip_host="acme.pstn.twilio.com",
            sip_username="acme-trunk-user",
            sip_password="correct-horse-battery-staple",
        )
    )
    print(conn.connection_health)  # "healthy" | "unreachable"

    # Add a number over that connection — origin-aware create_number.
    number = await client.create_number(
        CreateNumberRequest(
            did="+12125551234",
            country_code="US",
            origin="byo",
            byo_connection_id=conn.id,
        )
    )
    print(number.origin, number.provider, number.connection_health)
```

## A new sub-client: webhooks

```python
async with AudactClient(api_key="aud_live_...") as client:
    endpoint = await client.webhooks.create_webhook(
        CreateWebhookRequest(
            scope="account",
            url="https://example.com/hooks/audact",
            events=["call.completed", "violation.detected"],
        )
    )
    # `endpoint.signing_secret` is returned ONLY on this first call — store it.

    await client.webhooks.test_webhook(endpoint.id)
    deliveries = await client.webhooks.list_webhook_deliveries(endpoint.id)
```

Verify inbound deliveries with the bundled signature helper (constant-time,
tolerant of a secret-rotation grace period):

```python
from audact import verify_webhook_signature

is_valid = verify_webhook_signature(
    payload_bytes=raw_request_body,          # the exact, unparsed bytes
    signature_header=request.headers["X-Audact-Signature"],
    secret=stored_signing_secret,
)
```

## Examples

Runnable, SDK-only example scripts live under [`examples/`](examples/):

- `examples/end_to_end_flow.py` — the common flow: create an agent, provision
  + assign a phone number via the order flow, place a browser test call, then
  list/read calls. Run it against a local stack with `AUDACT_API_KEY` set, or
  dry-run it with `--check` (mocks every HTTP call in-process, no network
  access required).

- `examples/smoke_staging.py` — smoke test against a live deployment: list agents, place an outbound
  call, poll to a terminal status, read the summary. Configured via
  `AUDACT_API_KEY`, `AUDACT_BASE_URL` (set to your Audact host), `AUDACT_SMOKE_AGENT_ID`,
  `AUDACT_SMOKE_FROM_NUMBER`, `AUDACT_SMOKE_TO_NUMBER`; exits 2 if any is missing.
  Both numbers must be strict E.164 with no spaces or separators (e.g.
  `+442079460958`; they are not normalised), and the from number must be one
  of your own numbers.

## Error handling

All errors inherit from `audact.exceptions.AudactAPIError`:

| Exception                 | HTTP status |
|---------------------------|-------------|
| `AudactAuthError`         | 401         |
| `AudactForbiddenError`    | 403         |
| `AudactNotFoundError`     | 404         |
| `AudactRateLimitError`    | 429         |
| `AudactTimeoutError`      | timeout     |
| `AudactConnectionError`   | conn error  |

The server wraps every error as a nested envelope,
`{"error": {"code", "message", "hint", "details", "request_id"}}`
by the API. `AudactAPIError` parses this and exposes
`code`, `message`, `details`, `hint`, and `request_id` (the last also
falls back to the `X-Request-ID` response header) — quote `request_id`
when contacting support:

```python
from audact import AudactAPIError, AudactRateLimitError

try:
    await client.validate(...)
except AudactRateLimitError as exc:
    print("retry in", exc.retry_after, "seconds", exc.request_id)
except AudactAPIError as exc:
    print(exc.code, exc.message, exc.hint, exc.request_id)
```

### Retries & rate limits

- `AudactRateLimitError` (HTTP 429) additionally exposes `retry_after`
  (parsed from the `Retry-After` header) and `rate_limit` (a
  `RateLimitInfo` snapshot of `X-RateLimit-Limit`/`-Remaining`/`-Reset`).
  `client.last_rate_limit` holds the most recent `X-RateLimit-*` snapshot
  seen on *any* response, success or error.
- Retries are **opt-in and off by default** — pass `max_retries=N` to the
  constructor to enable a bounded retry-with-backoff for idempotent `GET`s
  and `429`/`5xx` responses (honoring `Retry-After`). Retries are **never**
  applied to Validator-adjacent calls (`/v1/validate`), which have a
  40ms hot-path budget.

## Contributing

This repository is published from Audact's private source repository; every commit here is an
automated sync. Please open issues here. Pull requests can't be merged directly, but they are
welcome as proposals and will be ported by the maintainers. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
