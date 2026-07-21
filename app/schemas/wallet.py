import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.transaction import TransactionSchema


class WalletCreateRequest(BaseModel):
    """Optional metadata on wallet creation — reserved for future use."""

    metadata: dict | None = Field(default=None, description="Optional metadata")


class WalletCreateResponse(BaseModel):
    wallet_id: uuid.UUID
    balance: Decimal

    model_config = {"from_attributes": True}


class WalletDetailResponse(BaseModel):
    wallet_id: uuid.UUID
    balance: Decimal
    transactions: list[TransactionSchema]

    model_config = {"from_attributes": True}


class DepositRequest(BaseModel):
    amount: Decimal = Field(
        ...,
        gt=0,
        description="Amount to deposit. Must be > 0.",
        examples=["100.00"],
    )


class DepositResponse(BaseModel):
    wallet_id: uuid.UUID
    balance: Decimal
    transaction_id: uuid.UUID

    model_config = {"from_attributes": True}


class TransferRequest(BaseModel):
    from_wallet_id: uuid.UUID
    to_wallet_id: uuid.UUID
    amount: Decimal = Field(
        ...,
        gt=0,
        description="Amount to transfer. Must be > 0.",
        examples=["50.00"],
    )


class TransferResponse(BaseModel):
    from_wallet_id: uuid.UUID
    to_wallet_id: uuid.UUID
    amount: Decimal
    from_transaction_id: uuid.UUID
    to_transaction_id: uuid.UUID
