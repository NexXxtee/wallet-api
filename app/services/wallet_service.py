import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InsufficientFundsError, WalletNotFoundError, SameWalletTransferError
from app.models.transaction import Transaction, TransactionType
from app.models.wallet import Wallet
from app.schemas.wallet import (
    DepositResponse,
    TransferResponse,
    WalletCreateResponse,
    WalletDetailResponse,
)
from app.schemas.transaction import TransactionSchema
from app.config import settings


async def create_wallet(session: AsyncSession) -> WalletCreateResponse:
    wallet = Wallet(balance=Decimal("0"))
    session.add(wallet)
    await session.commit()
    await session.refresh(wallet)
    return WalletCreateResponse(wallet_id=wallet.id, balance=Decimal(wallet.balance))


async def get_wallet_with_history(
    session: AsyncSession,
    wallet_id: uuid.UUID,
    limit: int = settings.DEFAULT_TRANSACTION_HISTORY,
) -> WalletDetailResponse:
    wallet = await _get_wallet_or_404(session, wallet_id)

    result = await session.execute(
        select(Transaction)
        .where(Transaction.wallet_id == wallet_id)
        .order_by(Transaction.created_at.desc())
        .limit(min(limit, settings.MAX_TRANSACTION_HISTORY))
    )
    transactions = result.scalars().all()

    return WalletDetailResponse(
        wallet_id=wallet.id,
        balance=Decimal(wallet.balance),
        transactions=[TransactionSchema.model_validate(t) for t in transactions],
    )


async def deposit(
    session: AsyncSession,
    wallet_id: uuid.UUID,
    amount: Decimal,
    idempotency_key: str | None = None,
) -> DepositResponse:
    try:
        wallet = await _lock_wallet(session, wallet_id)
        wallet.balance = Decimal(wallet.balance) + amount

        tx = Transaction(
            wallet_id=wallet.id,
            type=TransactionType.deposit,
            amount=amount,
            idempotency_key=idempotency_key,
        )
        session.add(tx)
        await session.flush()
        await session.commit()
        await session.refresh(tx)
        await session.refresh(wallet)
    except Exception:
        await session.rollback()
        raise

    return DepositResponse(
        wallet_id=wallet.id,
        balance=Decimal(wallet.balance),
        transaction_id=tx.id,
    )


async def transfer(
    session: AsyncSession,
    from_wallet_id: uuid.UUID,
    to_wallet_id: uuid.UUID,
    amount: Decimal,
    idempotency_key: str | None = None,
) -> TransferResponse:
    if from_wallet_id == to_wallet_id:
        raise SameWalletTransferError()

    try:
        first_id, second_id = sorted(
            [from_wallet_id, to_wallet_id], key=lambda x: str(x)
        )

        first_wallet = await _lock_wallet(session, first_id)
        second_wallet = await _lock_wallet(session, second_id)

        from_wallet = first_wallet if first_id == from_wallet_id else second_wallet
        to_wallet = second_wallet if first_id == from_wallet_id else first_wallet

        from_balance = Decimal(from_wallet.balance)
        if from_balance < amount:
            raise InsufficientFundsError(
                wallet_id=str(from_wallet_id),
                balance=str(from_balance),
                requested=str(amount),
            )

        from_wallet.balance = from_balance - amount
        to_wallet.balance = Decimal(to_wallet.balance) + amount

        tx_out = Transaction(
            wallet_id=from_wallet.id,
            type=TransactionType.transfer_out,
            amount=amount,
            related_wallet_id=to_wallet.id,
            idempotency_key=idempotency_key,
        )
        tx_in = Transaction(
            wallet_id=to_wallet.id,
            type=TransactionType.transfer_in,
            amount=amount,
            related_wallet_id=from_wallet.id,
        )
        session.add(tx_out)
        session.add(tx_in)
        await session.flush()
        await session.commit()
        await session.refresh(tx_out)
        await session.refresh(tx_in)
    except Exception:
        await session.rollback()
        raise

    return TransferResponse(
        from_wallet_id=from_wallet.id,
        to_wallet_id=to_wallet.id,
        amount=amount,
        from_transaction_id=tx_out.id,
        to_transaction_id=tx_in.id,
    )


async def _get_wallet_or_404(session: AsyncSession, wallet_id: uuid.UUID) -> Wallet:
    result = await session.execute(
        select(Wallet).where(Wallet.id == wallet_id)
    )
    wallet = result.scalar_one_or_none()
    if wallet is None:
        raise WalletNotFoundError(str(wallet_id))
    return wallet


async def _lock_wallet(session: AsyncSession, wallet_id: uuid.UUID) -> Wallet:
    result = await session.execute(
        select(Wallet)
        .where(Wallet.id == wallet_id)
        .with_for_update()
    )
    wallet = result.scalar_one_or_none()
    if wallet is None:
        raise WalletNotFoundError(str(wallet_id))
    return wallet
