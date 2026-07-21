import asyncio
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://wallet_user:wallet_pass@localhost:5432/wallet_db",
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_pre_ping=True)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def wallet_id(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/wallets")
    assert resp.status_code == 201
    return resp.json()["wallet_id"]


@pytest_asyncio.fixture
async def funded_wallet(client: AsyncClient) -> dict:
    resp = await client.post("/api/v1/wallets")
    assert resp.status_code == 201
    wid = resp.json()["wallet_id"]

    resp = await client.post(
        f"/api/v1/wallets/{wid}/deposit",
        json={"amount": "1000.00"},
    )
    assert resp.status_code == 200
    return {"wallet_id": wid, "balance": "1000.00000000"}
