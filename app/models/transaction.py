import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import TIMESTAMP, Enum, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TransactionType(str, enum.Enum):
    deposit = "deposit"
    transfer_in = "transfer_in"
    transfer_out = "transfer_out"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type"),
        nullable=False,
    )
    amount: Mapped[float] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
    )
    related_wallet_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )

    wallet: Mapped["Wallet"] = relationship(  # noqa: F821
        "Wallet",
        back_populates="transactions",
        foreign_keys=[wallet_id],
    )

    __table_args__ = (
        Index("ix_transactions_wallet_id_created_at", "wallet_id", "created_at"),
    )
