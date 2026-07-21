import json
from typing import AsyncGenerator

from fastapi import Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.idempotency import IdempotencyKey


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


class IdempotencyGuard:
    def __init__(self) -> None:
        self.key: str | None = None
        self.cached_response: IdempotencyKey | None = None
        self._db: AsyncSession | None = None

    async def __call__(
        self,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        db: AsyncSession = ...,
    ) -> "IdempotencyGuard":
        self.key = idempotency_key
        self._db = db

        if idempotency_key:
            result = await db.execute(
                select(IdempotencyKey).where(IdempotencyKey.key == idempotency_key)
            )
            self.cached_response = result.scalar_one_or_none()

        return self

    def has_cached_response(self) -> bool:
        return self.cached_response is not None

    def get_cached_json(self) -> dict:
        assert self.cached_response is not None
        return json.loads(self.cached_response.response_body)

    def get_cached_status_code(self) -> int:
        assert self.cached_response is not None
        return self.cached_response.status_code

    async def save_response(self, body: dict, status_code: int) -> None:
        if not self.key or not self._db:
            return
        record = IdempotencyKey(
            key=self.key,
            response_body=json.dumps(body, default=str),
            status_code=status_code,
        )
        self._db.add(record)
        await self._db.commit()
