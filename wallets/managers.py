from django.db import models
from .context import get_current_tenant_id

class TenantScopedManager(models.Manager):
    def get_queryset(self):
        queryset = super().get_queryset()
        # queryset.__class__ = TenantScopedManager
        tenant_id = get_current_tenant_id()
        
        if tenant_id is not None:
            return queryset.filter(tenant_id=tenant_id)
        return queryset
    
class UnscopedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()