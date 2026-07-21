from fastapi import HTTPException, status


class WalletNotFoundError(HTTPException):
    def __init__(self, wallet_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet '{wallet_id}' not found.",
        )


class InsufficientFundsError(HTTPException):
    def __init__(self, wallet_id: str, balance: str, requested: str) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Insufficient funds in wallet '{wallet_id}': "
                f"balance={balance}, requested={requested}."
            ),
        )


class InvalidAmountError(HTTPException):
    def __init__(self, detail: str = "Amount must be greater than 0.") -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


class SameWalletTransferError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot transfer funds to the same wallet.",
        )


class IdempotencyConflictError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency-Key has already been used with different request parameters.",
        )
