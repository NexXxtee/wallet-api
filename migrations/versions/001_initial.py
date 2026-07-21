from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE transaction_type AS ENUM ('deposit', 'transfer_in', 'transfer_out')"
    )

    op.create_table(
        "wallets",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "balance",
            sa.Numeric(precision=20, scale=8),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_table(
        "transactions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("wallet_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "type",
            sa.Enum("deposit", "transfer_in", "transfer_out", name="transaction_type"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("related_wallet_id", UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=True, unique=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"], ["wallets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["related_wallet_id"], ["wallets.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "ix_transactions_wallet_id_created_at",
        "transactions",
        ["wallet_id", "created_at"],
    )
    op.create_index(
        "ix_transactions_idempotency_key",
        "transactions",
        ["idempotency_key"],
        unique=True,
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("response_body", sa.Text, nullable=False),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_index("ix_transactions_idempotency_key", table_name="transactions")
    op.drop_index("ix_transactions_wallet_id_created_at", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("wallets")
    op.execute("DROP TYPE transaction_type")
