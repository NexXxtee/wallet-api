import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient


async def test_create_wallet(client: AsyncClient):
    resp = await client.post("/api/v1/wallets")
    assert resp.status_code == 201
    data = resp.json()
    assert "wallet_id" in data
    assert Decimal(data["balance"]) == Decimal("0")


async def test_create_multiple_wallets_have_unique_ids(client: AsyncClient):
    ids = set()
    for _ in range(5):
        resp = await client.post("/api/v1/wallets")
        assert resp.status_code == 201
        ids.add(resp.json()["wallet_id"])
    assert len(ids) == 5


async def test_deposit_increases_balance(client: AsyncClient, wallet_id: str):
    resp = await client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": "250.50"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["balance"]) == Decimal("250.50")
    assert "transaction_id" in data


async def test_deposit_accumulates_correctly(client: AsyncClient, wallet_id: str):
    for amount in ["100.00", "200.00", "50.75"]:
        resp = await client.post(
            f"/api/v1/wallets/{wallet_id}/deposit",
            json={"amount": amount},
        )
        assert resp.status_code == 200
    resp = await client.get(f"/api/v1/wallets/{wallet_id}")
    assert Decimal(resp.json()["balance"]) == Decimal("350.75")


async def test_deposit_invalid_amount_zero(client: AsyncClient, wallet_id: str):
    resp = await client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": "0"},
    )
    assert resp.status_code == 422


async def test_deposit_invalid_amount_negative(client: AsyncClient, wallet_id: str):
    resp = await client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": "-50"},
    )
    assert resp.status_code == 422


async def test_deposit_wallet_not_found(client: AsyncClient):
    resp = await client.post(
        f"/api/v1/wallets/{uuid.uuid4()}/deposit",
        json={"amount": "100"},
    )
    assert resp.status_code == 404


async def test_get_wallet_returns_balance_and_history(
    client: AsyncClient, wallet_id: str
):
    await client.post(
        f"/api/v1/wallets/{wallet_id}/deposit", json={"amount": "500"}
    )
    resp = await client.get(f"/api/v1/wallets/{wallet_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["balance"]) == Decimal("500")
    assert len(data["transactions"]) == 1
    assert data["transactions"][0]["type"] == "deposit"


async def test_get_wallet_not_found(client: AsyncClient):
    resp = await client.get(f"/api/v1/wallets/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_history_limit_default(client: AsyncClient, wallet_id: str):
    for _ in range(15):
        await client.post(
            f"/api/v1/wallets/{wallet_id}/deposit", json={"amount": "1"}
        )
    resp = await client.get(f"/api/v1/wallets/{wallet_id}")
    assert len(resp.json()["transactions"]) == 10


async def test_history_custom_limit(client: AsyncClient, wallet_id: str):
    for _ in range(15):
        await client.post(
            f"/api/v1/wallets/{wallet_id}/deposit", json={"amount": "1"}
        )
    resp = await client.get(f"/api/v1/wallets/{wallet_id}?limit=5")
    assert len(resp.json()["transactions"]) == 5


async def test_transfer_moves_funds(client: AsyncClient, funded_wallet: dict):
    target = (await client.post("/api/v1/wallets")).json()["wallet_id"]
    from_wid = funded_wallet["wallet_id"]

    resp = await client.post(
        "/api/v1/wallets/transfer",
        json={
            "from_wallet_id": from_wid,
            "to_wallet_id": target,
            "amount": "300.00",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "from_transaction_id" in data
    assert "to_transaction_id" in data

    from_resp = await client.get(f"/api/v1/wallets/{from_wid}")
    target_resp = await client.get(f"/api/v1/wallets/{target}")
    assert Decimal(from_resp.json()["balance"]) == Decimal("700.00")
    assert Decimal(target_resp.json()["balance"]) == Decimal("300.00")


async def test_transfer_insufficient_funds(client: AsyncClient, funded_wallet: dict):
    target = (await client.post("/api/v1/wallets")).json()["wallet_id"]
    resp = await client.post(
        "/api/v1/wallets/transfer",
        json={
            "from_wallet_id": funded_wallet["wallet_id"],
            "to_wallet_id": target,
            "amount": "9999.99",
        },
    )
    assert resp.status_code == 422


async def test_transfer_same_wallet(client: AsyncClient, funded_wallet: dict):
    wid = funded_wallet["wallet_id"]
    resp = await client.post(
        "/api/v1/wallets/transfer",
        json={"from_wallet_id": wid, "to_wallet_id": wid, "amount": "10"},
    )
    assert resp.status_code == 422


async def test_transfer_source_not_found(client: AsyncClient):
    target = (await client.post("/api/v1/wallets")).json()["wallet_id"]
    resp = await client.post(
        "/api/v1/wallets/transfer",
        json={
            "from_wallet_id": str(uuid.uuid4()),
            "to_wallet_id": target,
            "amount": "10",
        },
    )
    assert resp.status_code == 404


async def test_transfer_target_not_found(client: AsyncClient, funded_wallet: dict):
    resp = await client.post(
        "/api/v1/wallets/transfer",
        json={
            "from_wallet_id": funded_wallet["wallet_id"],
            "to_wallet_id": str(uuid.uuid4()),
            "amount": "10",
        },
    )
    assert resp.status_code == 404


async def test_deposit_idempotency_same_key_returns_same_result(
    client: AsyncClient, wallet_id: str
):
    idem_key = str(uuid.uuid4())
    headers = {"Idempotency-Key": idem_key}

    resp1 = await client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": "100"},
        headers=headers,
    )
    assert resp1.status_code == 200

    resp2 = await client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": "100"},
        headers=headers,
    )
    assert resp2.status_code == 200

    assert resp1.json() == resp2.json()

    balance_resp = await client.get(f"/api/v1/wallets/{wallet_id}")
    assert Decimal(balance_resp.json()["balance"]) == Decimal("100")


async def test_deposit_different_keys_are_independent(
    client: AsyncClient, wallet_id: str
):
    for _ in range(3):
        await client.post(
            f"/api/v1/wallets/{wallet_id}/deposit",
            json={"amount": "100"},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
    balance_resp = await client.get(f"/api/v1/wallets/{wallet_id}")
    assert Decimal(balance_resp.json()["balance"]) == Decimal("300")


async def test_transfer_idempotency_same_key_does_not_double_spend(
    client: AsyncClient, funded_wallet: dict
):
    target = (await client.post("/api/v1/wallets")).json()["wallet_id"]
    idem_key = str(uuid.uuid4())
    headers = {"Idempotency-Key": idem_key}
    payload = {
        "from_wallet_id": funded_wallet["wallet_id"],
        "to_wallet_id": target,
        "amount": "200",
    }

    resp1 = await client.post("/api/v1/wallets/transfer", json=payload, headers=headers)
    assert resp1.status_code == 200

    resp2 = await client.post("/api/v1/wallets/transfer", json=payload, headers=headers)
    assert resp2.status_code == 200

    assert resp1.json() == resp2.json()

    from_resp = await client.get(f"/api/v1/wallets/{funded_wallet['wallet_id']}")
    target_resp = await client.get(f"/api/v1/wallets/{target}")
    assert Decimal(from_resp.json()["balance"]) == Decimal("800")
    assert Decimal(target_resp.json()["balance"]) == Decimal("200")


async def test_health_check(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
