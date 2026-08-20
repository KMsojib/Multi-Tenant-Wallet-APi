from django.urls import path, include
from rest_framework.routers import DefaultRouter #type:ignore
from .views import (
    TenantViewSet, CustomerViewSet, WalletViewSet,
    TransactionViewSet, IdempotencyKeyViewSet
)
router = DefaultRouter()
router.register(r'tenants', TenantViewSet, basename='tenant')
router.register(r'customer', CustomerViewSet, basename='customer')
router.register(r'wallets', WalletViewSet, basename='wallet')
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'idempotency-keys', IdempotencyKeyViewSet, basename='idempotency-key')

# app_name = 'wallets'

urlpatterns = [
    path('api/', include(router.urls)),
]