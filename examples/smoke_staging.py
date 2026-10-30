"""
Staging smoke test: list agents, place an outbound call, poll it to a
terminal status, then read the call summary.

Environment (all required; a missing one is named and the script exits 2)::

    AUDACT_API_KEY             tenant API key
    AUDACT_BASE_URL            e.g. https://api.audact.ai
    AUDACT_SMOKE_AGENT_ID      UUID of an existing voice agent
    AUDACT_SMOKE_FROM_NUMBER   E.164 DID owned by the tenant
    AUDACT_SMOKE_TO_NUMBER     E.164 destination to call

Exit codes: 0 success, 1 a step failed, 2 missing configuration.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from uuid import UUID

from audact import AudactAPIError, AudactClient, OutboundCallRequest

REQUIRED_ENV = (
    "AUDACT_API_KEY",
    "AUDACT_BASE_URL",
    "AUDACT_SMOKE_AGENT_ID",
    "AUDACT_SMOKE_FROM_NUMBER",
    "AUDACT_SMOKE_TO_NUMBER",
)
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 180
TERMINAL_STATUSES = {"terminated"}


def _step(message: str) -> None:
    print(f"[smoke] {message}", flush=True)


async def run(env: dict[str, str]) -> None:
    agent_id = UUID(env["AUDACT_SMOKE_AGENT_ID"])
    async with AudactClient(
        api_key=env["AUDACT_API_KEY"], base_url=env["AUDACT_BASE_URL"]
    ) as client:
        # 1. List agents (all pages) and assert the smoke agent is present.
        _step("1/4 listing agents")
        cursor: str | None = None
        found = False
        while True:
            page = await client.agents.list_agents(cursor=cursor, limit=200)
            if any(a.agent_id == agent_id for a in page.items):
                found = True
                break
            if not page.has_more or not page.next_cursor:
                break
            cursor = page.next_cursor
        if not found:
            raise RuntimeError(f"agent {agent_id} not found in list_agents")
        _step(f"    agent {agent_id} present")

        # 2. Place an outbound call.
        _step("2/4 placing outbound call")
        started = await client.calls.initiate_outbound_call(
            OutboundCallRequest(
                from_number=env["AUDACT_SMOKE_FROM_NUMBER"],
                destination_number=env["AUDACT_SMOKE_TO_NUMBER"],
                agent_id=agent_id,
            )
        )
        call_id = started.call_id
        _step(f"    call_id={call_id}")

        # 3. Poll until terminal.
        _step("3/4 polling call status")
        deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
        while True:
            status = await client.calls.get_call_status(call_id)
            _step(f"    status={status.status}")
            if status.status in TERMINAL_STATUSES:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"call {call_id} not terminal after {POLL_TIMEOUT_SECONDS}s"
                )
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

        # 4. Read the summary (GET /v1/calls/{id}/summary).
        _step("4/4 fetching call summary")
        summary = await client.get_call_summary(call_id)
        _step(
            f"    status={summary.status} events={summary.event_count} "
            f"allow={summary.allow_count} modify={summary.modify_count} "
            f"block={summary.block_count}"
        )


async def main() -> int:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        print(f"missing required environment: {', '.join(missing)}", file=sys.stderr)
        return 2
    env = {name: os.environ[name] for name in REQUIRED_ENV}
    try:
        await run(env)
    except AudactAPIError as exc:
        print(
            f"[smoke] FAILED: {exc.status_code} {exc.code} {exc.message} "
            f"request_id={exc.request_id}",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # noqa: BLE001 - report any failure, non-zero exit
        print(f"[smoke] FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    _step("OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
