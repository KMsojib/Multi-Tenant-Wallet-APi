import uuid
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from .context import set_current_tenant_id, clear_current_tenant_id


class TenantIsolationMiddleware(MiddlewareMixin):

    def process_request(self, request):
        normalized_path = request.path.rstrip('/')

        # ========== Public routes (no tenant required) ==========
        public_paths = [
            '/admin',
            '/api/schema',
            '/api/docs',
            '/api/tenants',
        ]

        if any(request.path.startswith(p) for p in public_paths) or normalized_path == '/api':
            set_current_tenant_id(None)
            return None

        tenant_id = None

        # ========== Method 1: X-Tenant-ID ==========
        tenant_id = (
            request.headers.get('X-Tenant-ID') or
            request.headers.get('x-tenant-id') or
            request.META.get('HTTP_X_TENANT_ID')
        )

        # ========== Method 2: API Key ==========
        if not tenant_id:
            api_key = (
                request.headers.get('X-API-Key') or
                request.headers.get('x-api-key') or
                request.META.get('HTTP_X_API_KEY')
            )

            if not api_key:
                auth_header = request.headers.get('Authorization', '')
                if auth_header.lower().startswith('api-key '):
                    api_key = auth_header[8:].strip()

            if api_key:
                from .models import Tenant
                try:
                    tenant = Tenant.objects.filter(api_key=api_key).first()
                    if tenant is None and hasattr(Tenant, 'previous_api_key'):
                        # support rotation if you added it
                        tenant = Tenant.objects.filter(previous_api_key=api_key).first()

                    if tenant is None:
                        return JsonResponse(
                            {'error': 'Invalid or expired API Key.'},
                            status=401
                        )
                    tenant_id = str(tenant.id)
                except Exception:
                    return JsonResponse(
                        {'error': 'Invalid or expired API Key.'},
                        status=401
                    )

        # ========== Still no tenant → reject cleanly ==========
        if not tenant_id:
            return JsonResponse(
                {
                    'error': (
                        'Security Exception: Multi-tenant boundary breach. '
                        'Provide either X-Tenant-ID or X-API-Key header.'
                    )
                },
                status=400
            )

        # ========== Validate UUID ==========
        try:
            tenant_id = str(uuid.UUID(str(tenant_id)))
        except (ValueError, TypeError):
            return JsonResponse(
                {'error': 'Bad Request: Invalid X-Tenant-ID UUID format.'},
                status=400
            )

        set_current_tenant_id(tenant_id)
        request.tenant_id = tenant_id
        return None

    def process_response(self, request, response):
        clear_current_tenant_id()
        return response

    def process_exception(self, request, exception):
        clear_current_tenant_id()
        return None