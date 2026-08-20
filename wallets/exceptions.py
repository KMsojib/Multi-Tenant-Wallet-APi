from rest_framework.views import exception_handler # type: ignore
from rest_framework.response import Response # type: ignore
from rest_framework import status # type: ignore

class WalletError(Exception):
    default_message = "Wallet operation failed."
    code = "wallet_error"

    def __init__(self, message=None):
        self.message = message or self.default_message
        super().__init__(self.message)


class InsufficientFundsError(WalletError):
    default_message = "Insufficient funds for withdrawal or ledger routing."
    code = "insufficient_funds"


class WalletNotFoundError(WalletError):
    default_message = "Targeted wallet not found within active organization."
    code = "wallet_not_found"


class InvalidAmountError(WalletError):
    default_message = "Amount must be a positive integer expressed in minor units."
    code = "invalid_amount"


class SameWalletTransferError(WalletError):
    default_message = "Cannot execute ledger transfer from a wallet to itself."
    code = "same_wallet_transfer"


class WalletInactiveError(WalletError):
    default_message = "Targeted wallet is currently deactivated."
    code = "wallet_inactive"


class CrossTenantOperationError(WalletError):
    default_message = "Security Exception: Cross-tenant data isolation boundary violation."
    code = "cross_tenant_operation"


ERROR_STATUS_MAP = {
    "insufficient_funds": status.HTTP_422_UNPROCESSABLE_ENTITY, # 422 is standard for semantic/balance issues
    "wallet_not_found": status.HTTP_404_NOT_FOUND,
    "cross_tenant_operation": status.HTTP_403_FORBIDDEN,
    "invalid_amount": status.HTTP_400_BAD_REQUEST,
    "same_wallet_transfer": status.HTTP_400_BAD_REQUEST,
    "wallet_inactive": status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def custom_wallet_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, WalletError):
        http_status = ERROR_STATUS_MAP.get(exc.code, status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message
                }
            },
            status=http_status
        )

    return response