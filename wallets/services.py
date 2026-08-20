import uuid
from django.db import transaction
from wallets.models import Wallet, Transaction
from wallets.exceptions import InsufficientFundsError, WalletNotFoundError, CrossTenantOperationError

class WalletService:
    @staticmethod
    def deposit(tenant_id, wallet_id, amount):
        if amount <= 0:
            raise ValueError("Deposite amount must be positive.")
        with transaction.atomic():
            wallet = Wallet.unscoped_objects.select_for_update().filter(id = wallet_id,tenant_id=tenant_id).first()
            if not wallet:
                raise WalletNotFoundError("wallet not found")
            return Transaction.objects.create(
                tenant_id=tenant_id,
                wallet=wallet,
                amount=amount,
                type="DEPOSIT"
            )
            
    @staticmethod
    def withdraw(tenant_id, wallet_id, amount):
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")
        with transaction.atomic():
            wallet = Wallet.unscoped_objects.select_for_update().filter(id=wallet_id, tenant_id=tenant_id).first()
            if not wallet:
                raise WalletNotFoundError("Wallet not found.")
            if wallet.balance < amount:
                raise InsufficientFundsError("Insufficient wallet balance.")
            return Transaction.objects.create(
                tenant_id=tenant_id,
                wallet=wallet,
                amount=-amount,
                type='WITHDRAW'
            )

    @staticmethod
    def transfer(tenant_id, sender_wallet_id, recipient_wallet_id, amount, reference_id=None):
        if amount <= 0:
            raise ValueError("Transfer amount must be positive.")

        # Normalize everything to UUID objects
        try:
            sender_id = uuid.UUID(str(sender_wallet_id))
            recipient_id = uuid.UUID(str(recipient_wallet_id))
            tenant_id = uuid.UUID(str(tenant_id))
        except (ValueError, TypeError):
            raise WalletNotFoundError("Invalid wallet or tenant ID format.")

        if sender_id == recipient_id:
            raise ValueError("Cannot transfer funds to the same wallet.")

        # Sort UUIDs to prevent deadlocks
        ids = sorted([sender_id, recipient_id])

        with transaction.atomic():
            wallets_dict = (
                Wallet.unscoped_objects
                .select_for_update()
                .in_bulk(ids)
            )

            sender = wallets_dict.get(sender_id)
            recipient = wallets_dict.get(recipient_id)

            if not sender or not recipient:
                raise WalletNotFoundError("One or both wallets not found.")

            if sender.tenant_id != tenant_id or recipient.tenant_id != tenant_id:
                raise CrossTenantOperationError("Cross-tenant operations forbidden.")

            if sender.balance < amount:
                raise InsufficientFundsError("Insufficient balance for transfer.")

            tx_out = Transaction.objects.create(
                tenant_id=tenant_id,
                wallet=sender,
                amount=-amount,
                type='TRANSFER_OUT',
                reference_id=reference_id
            )
            tx_in = Transaction.objects.create(
                tenant_id=tenant_id,
                wallet=recipient,
                amount=amount,
                type='TRANSFER_IN',
                reference_id=reference_id
            )
            return tx_out, tx_in