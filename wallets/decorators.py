import json
from functools import wraps
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from wallets.models import IdempotencyKey

def idempotent_endpoint():
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(self, request, *args, **kwargs):
            if request.method not in ['POST', 'PUT', 'PATCH']:
                return view_func(self, request, *args, **kwargs)

            idem_key = request.headers.get('Idempotency-Key') or request.headers.get('X-Idempotency-Key')
            tenant_id = getattr(request, 'tenant_id', None)

            if not idem_key or not tenant_id:
                return view_func(self, request, *args, **kwargs)

            existing = IdempotencyKey.objects.filter(tenant_id=tenant_id, key=idem_key).first()
            if existing:
                if existing.response_status == 102:
                    return Response({'detail': 'Request currently processing.'}, status=status.HTTP_409_CONFLICT)
                return Response(existing.response_body, status=existing.response_status)

            idem_obj = None
            try:
                with transaction.atomic():
                    idem_obj = IdempotencyKey.objects.create(
                        tenant_id=tenant_id,
                        key=idem_key,
                        response_status=102,
                        response_body={}
                    )
            except IntegrityError:
                existing = IdempotencyKey.objects.get(tenant_id=tenant_id, key=idem_key)
                if existing.response_status == 102:
                    return Response({'detail': 'Request currently processing.'}, status=status.HTTP_409_CONFLICT)
                return Response(existing.response_body, status=existing.response_status)

            try:
                response = view_func(self, request, *args, **kwargs)
                
                response_data = getattr(response, 'data', {})
                rendered_content = JSONRenderer().render(response_data)
                sanitized_data = json.loads(rendered_content.decode('utf-8'))

                idem_obj.response_status = response.status_code
                idem_obj.response_body = sanitized_data
                idem_obj.save(update_fields=['response_status', 'response_body'])

                response.data = sanitized_data
                return response
            except Exception as exc:
                if idem_obj and idem_obj.pk:
                    idem_obj.delete()
                raise exc

        return _wrapped_view
    return decorator