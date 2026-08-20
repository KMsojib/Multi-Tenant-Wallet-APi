from rest_framework import serializers # type:ignore
from .models import Tenant, Customer, Wallet, Transaction, IdempotencyKey
from django.contrib.auth.models import User
from django.db import transaction


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'api_key', 'created_at']
        read_only_fields = ['id','api_key', 'created_at']


class CustomerSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    username_display = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id', 'user_id', 'username_display', 
            'username', 'password', 'email', 
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'user_id', 'created_at']

    def create(self, validated_data):
        username = validated_data.pop('username')
        password = validated_data.pop('password')
        email = validated_data.get('email', '')

        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            
            customer = Customer.objects.create(
                user=user,
                **validated_data
            )
            
            return customer


class WalletSerializer(serializers.ModelSerializer):
    balance = serializers.IntegerField(read_only=True)
    customer_username = serializers.CharField(source='customer.user.username', read_only=True)
    
    class Meta:
        model = Wallet
        fields = ['id', 'customer', 'customer_username', 'currency', 'balance', 'created_at']
        read_only_fields = ["id", "balance", "created_at"]

    def validate_customer(self, value):
        request = self.context.get('request')
        if request and hasattr(request, 'tenant_id'):
            if str(value.tenant_id) != str(request.tenant_id):
                raise serializers.ValidationError(
                    "Access Denied: The specified Customer profile does not exist within your organization."
                )
        return value
    
class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'wallet', 'amount', 'type', 'reference_id', 'created_at']
        read_only_fields = fields


class IdempotencyKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = IdempotencyKey
        fields = ['id', 'key', 'response_status', 'response_body', 'created_at']        
        read_only_fields = fields

class DepositWithdrawSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1, error_messages={
        'min_value': 'The transaction amount must be greater than zero minor units.'
    })
    description = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )

class TransferSerializer(serializers.Serializer):
    to_wallet_id = serializers.UUIDField()
    amount = serializers.IntegerField(min_value=1,error_messages = {
        'min_value': 'The transfer volume must be greater than zero minor units.'
    })

    description = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    
    def validate(self, data):
        request = self.context.get('request')
        if not request or not hasattr(request, 'tenant_id'):
            return data

        to_wallet_id = data.get('to_wallet_id')
        
        try:
            target_wallet = Wallet.objects.get(id=to_wallet_id)
            if str(target_wallet.tenant_id) != str(request.tenant_id):
                raise serializers.ValidationError(
                    {"to_wallet_id": "Targeted destination wallet account does not exist inside your scope."}
                )
        except Wallet.DoesNotExist:
            raise serializers.ValidationError(
                {"to_wallet_id": "Targeted destination wallet account does not exist inside your scope."}
            )
            
        return data