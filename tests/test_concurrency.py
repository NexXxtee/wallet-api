import asyncio
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


async def make_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def create_wallet_direct() -> str:
    async with make_client() as c:
        resp = await c.post("/api/v1/wallets")
        assert resp.status_code == 201
        return resp.json()["wallet_id"]


async def deposit_direct(wallet_id: str, amount: str) -> dict:
    async with make_client() as c:
        resp = await c.post(
            f"/api/v1/wallets/{wallet_id}/deposit", json={"amount": amount}
        )
        assert resp.status_code == 200
        return resp.json()


async def get_balance_direct(wallet_id: str) -> Decimal:
    async with make_client() as c:
        resp = await c.get(f"/api/v1/wallets/{wallet_id}")
        assert resp.status_code == 200
        return Decimal(resp.json()["balance"])


async def transfer_direct(
    from_id: str, to_id: str, amount: str, idem_key: str | None = None
) -> tuple[int, dict]:
    headers = {}
    if idem_key:
        headers["Idempotency-Key"] = idem_key
    async with make_client() as c:
        resp = await c.post(
            "/api/v1/wallets/transfer",
            json={"from_wallet_id": from_id, "to_wallet_id": to_id, "amount": amount},
            headers=headers,
        )
        return resp.status_code, resp.json()


async def test_concurrent_deposits_no_lost_update():
    wallet_id = await create_wallet_direct()
    n = 20
    amount = "10.00"

    results = await asyncio.gather(
        *[deposit_direct(wallet_id, amount) for _ in range(n)]
    )

    assert all(r["wallet_id"] == wallet_id for r in results)

    balance = await get_balance_direct(wallet_id)
    assert balance == Decimal(amount) * n


async def test_concurrent_transfers_balance_never_negative():
    wallet_a = await create_wallet_direct()
    wallet_b = await create_wallet_direct()
    await deposit_direct(wallet_a, "100.00")

    n = 10
    results = await asyncio.gather(
        *[transfer_direct(wallet_a, wallet_b, "100.00") for _ in range(n)],
        return_exceptions=True,
    )

    statuses = [r[0] for r in results if isinstance(r, tuple)]
    successes = [s for s in statuses if s == 200]
    failures = [s for s in statuses if s == 422]

    assert len(successes) == 1
    assert len(failures) == n - 1

    balance_a = await get_balance_direct(wallet_a)
    balance_b = await get_balance_direct(wallet_b)
    assert balance_a >= Decimal("0")
    assert balance_a + balance_b == Decimal("100.00")


async def test_concurrent_partial_transfers_conserve_money():
    wallet_a = await create_wallet_direct()
    wallet_b = await create_wallet_direct()
    await deposit_direct(wallet_a, "1000.00")

    n = 50
    results = await asyncio.gather(
        *[transfer_direct(wallet_a, wallet_b, "10.00") for _ in range(n)],
        return_exceptions=True,
    )

    statuses = [r[0] for r in results if isinstance(r, tuple)]
    successes = [s for s in statuses if s == 200]

    assert len(successes) == n

    balance_a = await get_balance_direct(wallet_a)
    balance_b = await get_balance_direct(wallet_b)
    assert balance_a == Decimal("500.00")
    assert balance_b == Decimal("500.00")


async def test_bidirectional_transfers_no_deadlock():
    wallet_a = await create_wallet_direct()
    wallet_b = await create_wallet_direct()
    await deposit_direct(wallet_a, "500.00")
    await deposit_direct(wallet_b, "500.00")

    n = 20
    a_to_b = [transfer_direct(wallet_a, wallet_b, "10.00") for _ in range(n)]
    b_to_a = [transfer_direct(wallet_b, wallet_a, "10.00") for _ in range(n)]

    results = await asyncio.gather(*a_to_b, *b_to_a, return_exceptions=True)

    exceptions = [r for r in results if isinstance(r, Exception)]
    assert not exceptions

    balance_a = await get_balance_direct(wallet_a)
    balance_b = await get_balance_direct(wallet_b)

    total = balance_a + balance_b
    assert total == Decimal("1000.00")
    assert balance_a >= Decimal("0")
    assert balance_b >= Decimal("0")


async def test_idempotent_transfer_fired_concurrently():
    wallet_a = await create_wallet_direct()
    wallet_b = await create_wallet_direct()
    await deposit_direct(wallet_a, "500.00")

    idem_key = str(uuid.uuid4())
    n = 5

    results = await asyncio.gather(
        *[transfer_direct(wallet_a, wallet_b, "100.00", idem_key) for _ in range(n)],
        return_exceptions=True,
    )

    statuses = [r[0] for r in results if isinstance(r, tuple)]
    assert all(s == 200 for s in statuses)

    bodies = [r[1] for r in results if isinstance(r, tuple)]
    first = bodies[0]
    for body in bodies[1:]:
        assert body == first

    balance_a = await get_balance_direct(wallet_a)
    balance_b = await get_balance_direct(wallet_b)
    assert balance_a == Decimal("400.00")
    assert balance_b == Decimal("100.00")
