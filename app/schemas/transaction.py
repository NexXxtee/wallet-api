import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.transaction import TransactionType


class TransactionSchema(BaseModel):
    id: uuid.UUID
    wallet_id: uuid.UUID
    type: TransactionType
    amount: Decimal
    related_wallet_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
