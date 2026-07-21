import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, IdempotencyGuard
from app.config import settings
from app.models.idempotency import IdempotencyKey as IdempotencyKeyModel
from app.schemas.wallet import (
    DepositRequest,
    DepositResponse,
    TransferRequest,
    TransferResponse,
    WalletCreateRequest,
    WalletCreateResponse,
    WalletDetailResponse,
)
from app.services import wallet_service

router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.post(
    "",
    response_model=WalletCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new wallet",
)
async def create_wallet(
    body: WalletCreateRequest = WalletCreateRequest(),
    db: AsyncSession = Depends(get_db),
) -> WalletCreateResponse:
    return await wallet_service.create_wallet(db)


@router.get(
    "/{wallet_id}",
    response_model=WalletDetailResponse,
    summary="Get wallet balance and transaction history",
)
async def get_wallet(
    wallet_id: uuid.UUID,
    limit: int = settings.DEFAULT_TRANSACTION_HISTORY,
    db: AsyncSession = Depends(get_db),
) -> WalletDetailResponse:
    return await wallet_service.get_wallet_with_history(db, wallet_id, limit)


@router.post(
    "/{wallet_id}/deposit",
    response_model=DepositResponse,
    status_code=status.HTTP_200_OK,
    summary="Deposit funds into a wallet",
)
async def deposit(
    wallet_id: uuid.UUID,
    body: DepositRequest,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: AsyncSession = Depends(get_db),
) -> DepositResponse | dict:
    guard = IdempotencyGuard()
    guard.key = idempotency_key
    guard._db = db

    if idempotency_key:
        result = await db.execute(
            select(IdempotencyKeyModel).where(IdempotencyKeyModel.key == idempotency_key)
        )
        guard.cached_response = result.scalar_one_or_none()

    if guard.has_cached_response():
        response.status_code = guard.get_cached_status_code()
        return guard.get_cached_json()

    result = await wallet_service.deposit(
        session=db,
        wallet_id=wallet_id,
        amount=body.amount,
        idempotency_key=idempotency_key,
    )

    result_dict = result.model_dump()
    await guard.save_response(result_dict, status.HTTP_200_OK)

    return result


@router.post(
    "/transfer",
    response_model=TransferResponse,
    status_code=status.HTTP_200_OK,
    summary="Transfer funds between two wallets",
)
async def transfer(
    body: TransferRequest,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: AsyncSession = Depends(get_db),
) -> TransferResponse | dict:
    guard = IdempotencyGuard()
    guard.key = idempotency_key
    guard._db = db

    if idempotency_key:
        result_cache = await db.execute(
            select(IdempotencyKeyModel).where(IdempotencyKeyModel.key == idempotency_key)
        )
        guard.cached_response = result_cache.scalar_one_or_none()

    if guard.has_cached_response():
        response.status_code = guard.get_cached_status_code()
        return guard.get_cached_json()

    result = await wallet_service.transfer(
        session=db,
        from_wallet_id=body.from_wallet_id,
        to_wallet_id=body.to_wallet_id,
        amount=body.amount,
        idempotency_key=idempotency_key,
    )

    result_dict = result.model_dump()
    await guard.save_response(result_dict, status.HTTP_200_OK)

    return result
