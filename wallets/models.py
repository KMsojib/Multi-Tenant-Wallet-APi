import uuid
from django.db import models
from django.contrib.auth.models import User 
from .managers import TenantScopedManager,UnscopedManager
import secrets
from django.utils import timezone
from datetime import timedelta

class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    api_key = models.CharField(max_length=64, unique=True, editable=False)
    previous_api_key = models.CharField(max_length=64, null=True, blank=True, editable=False)
    previous_api_key_expires_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @staticmethod
    def generate_api_key():
        return secrets.token_hex(32) 

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = self.generate_api_key()
        super().save(*args, **kwargs)

    def rotate_api_key(self, grace_period_hours: int = 24):
        self.previous_api_key = self.api_key
        self.previous_api_key_expires_at = timezone.now() + timedelta(hours=grace_period_hours)
        self.api_key = self.generate_api_key()
        self.save(update_fields=[
            'api_key',
            'previous_api_key',
            'previous_api_key_expires_at',
            'updated_at'
        ])
        return self.api_key

    def is_api_key_valid(self, key: str) -> bool:
        if key == self.api_key:
            return True
        if (
            self.previous_api_key
            and key == self.previous_api_key
            and self.previous_api_key_expires_at
            and timezone.now() < self.previous_api_key_expires_at
        ):
            return True
        return False


class TenantScopedModel(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantScopedManager()
    unscoped_objects = UnscopedManager()

    class Meta:
        abstract = True
        base_manager_name = 'unscoped_objects'


class Customer(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='customer_profiles')
    email = models.EmailField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('tenant', 'user')

    def __str__(self):
        return f"{self.user.username} ({self.tenant.name})"


class Wallet(TenantScopedModel):
    CURRENCY_CHOICES = (
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('BDT', 'Bangladeshi Taka'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='wallets') 
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')       

    class Meta:
        unique_together = ('tenant', 'customer', 'currency')

    @property
    def balance(self):
        aggregates = self.transactions.aggregate(total=models.Sum('amount'))
        return aggregates['total'] or 0

    def __str__(self):
        return f"{self.customer.user.username}'s Wallet ({self.currency})"


class Transaction(TenantScopedModel):
    TRANSACTION_TYPES = (
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAW', 'Withdraw'),
        ('TRANSFER_IN', 'Transfer In'), 
        ('TRANSFER_OUT', 'Transfer Out'), 
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name='transactions')
    amount = models.IntegerField()
    type = models.CharField(max_length=15, choices=TRANSACTION_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    reference_id = models.UUIDField(null=True, blank=True)

    def __str__(self):
        return f"[{self.type}] {self.amount} Minor Units -> {self.wallet.id}"

class IdempotencyKey(TenantScopedModel):
    key = models.CharField(max_length=255)
    response_status = models.IntegerField()
    response_body = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tenant', 'key')
        
    def __str__(self):
        return f"Idempotency Key: {self.key} [{self.response_status}]"