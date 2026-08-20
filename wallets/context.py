import threading

_thread_locals = threading.local()

def set_current_tenant_id(tenant_id):
    setattr(_thread_locals,'tenant_id', tenant_id)

def get_current_tenant_id():
    return getattr(_thread_locals, 'tenant_id', None)

def clear_current_tenant_id():
    if hasattr(_thread_locals,'tenant_id'):
        delattr(_thread_locals, 'tenant_id')
    
    _thread_locals.tenant_id = None