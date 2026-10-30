"""
End-to-end example: the common flow with the Python SDK.

    1. Create a voice agent.
    2. Provision + assign a phone number via the Telnyx order flow
       (against an already-``approved`` KYC document set).
    3. Place a browser test call against the new agent.
    4. List calls and read one call's detail.

This script uses ONLY the ``audact`` SDK for every network call — no
direct ``httpx``/``requests`` calls are made against the Audact services.

Live run — point the SDK at one host with ``base_url`` / ``AUDACT_BASE_URL``
(the normal setup; the SDK appends ``/v1/...`` itself)::

    export AUDACT_BASE_URL=https://api.audact.ai
    # Local stack alternative: per-service ports (policy engine 8081 ...
    # org management 8092) are the defaults when
    # neither ``base_url`` nor ``AUDACT_BASE_URL`` is set, and can be
    # overridden one by one with ``AUDACT_<SERVICE>_URL``.
    export AUDACT_API_KEY=aud_live_...
    # An already-approved KYC document set id (see README.md "KYC documents
    # & number provisioning" for how to create + approve one).
    export AUDACT_EXAMPLE_KYC_SET_ID=11111111-1111-1111-1111-111111111111
    python examples/end_to_end_flow.py

Dry run (no network access; every HTTP call is served by an in-process
``httpx.MockTransport`` instead of a live Audact deployment)::

    python examples/end_to_end_flow.py --check
"""

from __future__ import annotations

import argparse
import asyncio
import os
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from audact import (
    AssignNumberRequest,
    AudactClient,
    BrowserCallRequest,
    CreateAgentRequest,
    CreateNumberOrderRequest,
)


async def run_flow(client: AudactClient) -> None:
    """Run the common create-agent -> provision-number -> call -> list flow."""

    # 1. Create a voice agent.
    agent = await client.agents.create_agent(
        CreateAgentRequest(
            name="Example Outbound Agent",
            language="en-US",
            jurisdiction="DE",
            prompt="You are a helpful, compliant AI voice agent.",
        )
    )
    print(f"created agent {agent.agent_id} ({agent.name!r})")

    # 2. Provision + assign a phone number via the order flow. This assumes
    # a KYC document set has already been created and approved out of band
    # (see README.md's "KYC documents & number provisioning" section for the
    # full upload -> requirements -> document-set flow); pass its id via
    # AUDACT_EXAMPLE_KYC_SET_ID.
    kyc_set_id_raw = os.environ.get("AUDACT_EXAMPLE_KYC_SET_ID")
    if kyc_set_id_raw:
        order = await client.create_number_order(
            CreateNumberOrderRequest(
                country_code="NL",
                number_type="mobile",
                set_id=UUID(kyc_set_id_raw),
            )
        )
        print(f"placed number order {order.id} (status={order.status})")

        order = await client.wait_for_order(order.id, timeout=60.0, poll_interval=2.0)
        print(f"number order {order.id} reached terminal status: {order.status}")

        if order.status == "success" and order.phone_number_id:
            number_id = UUID(order.phone_number_id)
            await client.assign_number(number_id, AssignNumberRequest(agent_id=agent.agent_id))
            print(f"assigned number {number_id} to agent {agent.agent_id}")
    else:
        print(
            "AUDACT_EXAMPLE_KYC_SET_ID not set — skipping number provisioning "
            "(see README.md for the KYC document-set flow)"
        )

    # 3. Place a browser test call against the new agent.
    call = await client.calls.create_browser_call(BrowserCallRequest(agent_id=agent.agent_id))
    print(f"started browser call {call.call_id} (room={call.room_name!r})")

    status = await client.calls.get_call_status(call.call_id)
    print(f"call {status.call_id} status: {status.status!r}")

    # 4. List calls and read one call's detail.
    page = await client.list_calls(limit=5)
    print(f"listed {len(page.items)} call(s) (has_more={page.has_more})")
    for record in page.items:
        print(f"  - {record.call_id} [{record.status}] started_at={record.started_at}")

    if page.items:
        detail = await client.get_call_detail(page.items[0].call_id)
        print(
            f"call {detail.call_id} detail: direction={detail.direction!r} "
            f"transcript_turns={len(detail.transcript)}"
        )


if TYPE_CHECKING:
    import httpx


def _build_mock_transport() -> httpx.MockTransport:
    """
    Build an in-process transport that answers every request this example
    issues, so ``--check`` can validate the script end-to-end without a
    live Audact deployment. Only used in dry-run mode.
    """
    import httpx

    agent_id = str(uuid4())
    order_id = str(uuid4())
    number_id = str(uuid4())
    call_id = str(uuid4())
    now = "2026-09-18T12:00:00Z"

    def handler(request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path

        if method == "POST" and path == "/v1/agents":
            return httpx.Response(
                201,
                json={
                    "agent_id": agent_id,
                    "tenant_id": str(uuid4()),
                    "name": "Example Outbound Agent",
                    "language": "en-US",
                },
            )
        if method == "POST" and path == "/v1/numbers/orders":
            return httpx.Response(
                202,
                json={
                    "id": order_id,
                    "country_code": "NL",
                    "number_type": "mobile",
                    "set_id": str(uuid4()),
                    "status": "pending",
                    "created_at": now,
                    "updated_at": now,
                },
            )
        if method == "GET" and path == f"/v1/numbers/orders/{order_id}":
            return httpx.Response(
                200,
                json={
                    "id": order_id,
                    "country_code": "NL",
                    "number_type": "mobile",
                    "set_id": str(uuid4()),
                    "status": "success",
                    "phone_number": "+31201234567",
                    "phone_number_id": number_id,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        if method == "POST" and path == f"/v1/numbers/{number_id}/assign":
            return httpx.Response(200, json={})
        if method == "POST" and path == "/v1/sip/calls/browser":
            return httpx.Response(
                200,
                json={
                    "call_id": call_id,
                    "room_name": "example-room",
                    "livekit_url": "wss://livekit.example.com",
                    "livekit_token": "example-token",
                },
            )
        if method == "GET" and path == f"/v1/sip/calls/{call_id}/status":
            return httpx.Response(
                200,
                json={"call_id": call_id, "room_name": "example-room", "status": "active"},
            )
        if method == "GET" and path == "/v1/calls":
            return httpx.Response(
                200,
                json={
                    "calls": [
                        {
                            "call_id": call_id,
                            "tenant_id": str(uuid4()),
                            "direction": "outbound",
                            "status": "active",
                            "started_at": now,
                            "created_at": now,
                        }
                    ],
                    "has_more": False,
                    "next_cursor": None,
                },
            )
        if method == "GET" and path == f"/v1/calls/{call_id}":
            return httpx.Response(
                200,
                json={
                    "call_id": call_id,
                    "tenant_id": str(uuid4()),
                    "direction": "outbound",
                    "status": "active",
                    "started_at": now,
                    "transcript": [],
                },
            )
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND", "message": path}})

    return httpx.MockTransport(handler)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="dry-run against an in-process mock transport instead of a live deployment",
    )
    args = parser.parse_args()

    if args.check:
        import httpx

        transport = _build_mock_transport()
        httpx_client = httpx.AsyncClient(transport=transport)
        async with AudactClient(api_key="aud_test_check", httpx_client=httpx_client) as client:
            await run_flow(client)
        print("--check: OK (dry run against mock transport)")
        return

    async with AudactClient(api_key=os.environ.get("AUDACT_API_KEY")) as client:
        await run_flow(client)


if __name__ == "__main__":
    asyncio.run(main())
