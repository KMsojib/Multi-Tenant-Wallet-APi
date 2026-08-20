from django.contrib import admin,messages
from .models import Tenant, Customer, Wallet, Transaction, IdempotencyKey
from django import forms 
from django.contrib.auth.models import User
from .services import WalletService
from django.core.exceptions import ValidationError
@admin.register(Tenant)


class TenantAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at')
    search_fields = ('name',)
    ordering = ('-created_at',)


class TenantScopedAdminBase(admin.ModelAdmin):
    def get_queryset(self, request):
        return self.model.unscoped_objects.all()

class CustomerCreationForm(forms.ModelForm):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = Customer
        fields = ('tenant', 'is_active')

    def save(self, commit=True):
        # Create Django User with hashed password automatically
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password']
        )
        customer = super().save(commit=False)
        customer.user = user
        if commit:
            customer.save()
        return customer
    
@admin.register(Customer)
class CustomerAdmin(TenantScopedAdminBase):
    form = CustomerCreationForm
    list_display = ('id', 'tenant', 'user', 'is_active')

class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    can_delete = True
    readonly_fields = ('tenant', 'type', 'amount', 'reference_id', 'created_at')
    
    def had_add_permission(self, request, obj=None):
        return False

@admin.register(Wallet)
class WalletAdmin(TenantScopedAdminBase):
    list_display = ('id', 'tenant', 'customer', 'currency', 'current_balance', 'created_at')
    list_filter = ('tenant', 'currency')
    search_fields = ('customer__user__username', 'id')
    readonly_fields = ('current_balance',)

    inlines = [TransactionInline]
    
    def current_balance(self, obj):
        return obj.balance
    current_balance.short_description = 'Live Balance (Minor Units)'

class WalletTransferForm(forms.Form):
    to_wallet = forms.ModelChoiceField(
        queryset=Wallet.unscoped_objects.none(),
        label="Recipient Wallet",
        widget=forms.Select(attrs={'style': 'width: 300px; padding: 5px;'})
    )
    amount = forms.IntegerField(
        label="Amount (Minor Units)",
        min_value=1
    )

    def __init__(self, *args, **kwargs):
        sender_wallet = kwargs.pop('sender_wallet', None)
        super().__init__(*args, **kwargs)
        if sender_wallet:
            self.fields['to_wallet'].queryset = Wallet.unscoped_objects.filter(
                tenant_id=sender_wallet.tenant_id,
                currency=sender_wallet.currency
            ).exclude(id=sender_wallet.id)

class TransactionAdminForm(forms.ModelForm):
    tenant = forms.ModelChoiceField(
        queryset=Tenant.objects.all(),
        required=True,
        label="Tenant"
    )
    wallet = forms.ModelChoiceField(
        queryset=Wallet.unscoped_objects.all(),
        required=True,
        label="Source Wallet"
    )
    to_wallet = forms.ModelChoiceField(
        queryset=Wallet.unscoped_objects.all(),
        required=False,
        label="Recipient Wallet (For Transfers Only)",
        help_text="Select the destination wallet if executing a Transfer."
    )

    class Meta:
        model = Transaction
        fields = ['tenant', 'wallet', 'type', 'amount', 'to_wallet']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        self.fields['tenant'].queryset = Tenant.objects.all()
        self.fields['wallet'].queryset = Wallet.unscoped_objects.all()
        self.fields['to_wallet'].queryset = Wallet.unscoped_objects.all()

        t_id = None
        if self.instance and self.instance.pk and getattr(self.instance, 'tenant_id', None):
            t_id = self.instance.tenant_id
        elif self.request and getattr(self.request, 'tenant_id', None):
            t_id = self.request.tenant_id

        if t_id:
            self.fields['wallet'].queryset = Wallet.unscoped_objects.filter(tenant_id=t_id)
            self.fields['to_wallet'].queryset = Wallet.unscoped_objects.filter(tenant_id=t_id)

    def clean(self):
        cleaned_data = super().clean()
        selected_tenant = cleaned_data.get('tenant')
        wallet = cleaned_data.get('wallet')
        to_wallet = cleaned_data.get('to_wallet')
        tx_type = cleaned_data.get('type')
        amount = cleaned_data.get('amount')

        if amount and amount <= 0:
            raise ValidationError({"amount": "Transaction amount must be a positive integer."})

        if wallet and selected_tenant and wallet.tenant_id != selected_tenant.id:
            raise ValidationError({
                "wallet": f"Security Violation: Selected wallet belongs to tenant '{wallet.tenant.name}', "
                          f"not the chosen form tenant '{selected_tenant.name}'."
            })

        if tx_type == 'WITHDRAW' and wallet and amount:
            if wallet.balance < amount:
                raise ValidationError({
                    "amount": f"Insufficient funds! '{wallet.customer.user.username}' only has {wallet.balance} units, "
                              f"cannot execute withdrawal of {amount} units."
                })

        if tx_type in ['TRANSFER_IN', 'TRANSFER_OUT']:
            if not to_wallet:
                raise ValidationError({"to_wallet": "A recipient wallet must be selected for transfers."})
            
            if to_wallet.tenant_id != selected_tenant.id:
                raise ValidationError({
                    "to_wallet": f"Security Violation: Recipient wallet belongs to tenant '{to_wallet.tenant.name}', "
                                 f"not the chosen form tenant '{selected_tenant.name}'."
                })

            if wallet == to_wallet:
                raise ValidationError({"to_wallet": "Cannot transfer funds to the same wallet account."})

            if wallet.currency != to_wallet.currency:
                raise ValidationError({"to_wallet": f"Currency mismatch! {wallet.currency} cannot go to {to_wallet.currency}."})

            if wallet and amount and wallet.balance < amount:
                raise ValidationError({
                    "amount": f"Insufficient balance for transfer. Available: {wallet.balance} units."
                })

        return cleaned_data


@admin.register(Transaction)
class TransactionAdmin(TenantScopedAdminBase):
    form = TransactionAdminForm
    list_display = ('id', 'tenant', 'wallet', 'type', 'amount_display', 'reference_id', 'created_at')
    list_filter = ('tenant', 'type', 'created_at')
    search_fields = ('wallet__id', 'reference_id')
    readonly_fields = ('created_at', 'reference_id')

    def amount_display(self, obj):
        return f"{obj.amount} units"
    amount_display.short_description = 'Amount'

    def get_form(self, request, obj=None, change=False, **kwargs):
        Form = super().get_form(request, obj, change, **kwargs)
        class RequestForm(Form):
            def __init__(self, *args, **kwargs):
                kwargs['request'] = request
                super().__init__(*args, **kwargs)
        return RequestForm

    def save_model(self, request, obj, form, change):
        positive_amount = abs(obj.amount)

        if obj.type == 'WITHDRAW':
            obj.amount = -positive_amount
            super().save_model(request, obj, form, change)

        elif obj.type == 'DEPOSIT':
            obj.amount = positive_amount
            super().save_model(request, obj, form, change)

        elif obj.type in ['TRANSFER_OUT', 'TRANSFER_IN']:
            to_wallet = form.cleaned_data.get('to_wallet')
            try:
                WalletService.transfer(
                    tenant_id=obj.tenant_id,
                    sender_wallet_id=obj.wallet.id,
                    recipient_wallet_id=to_wallet.id,
                    amount=positive_amount
                )
                self.message_user(request, "Atomic Transfer completed successfully!", level=messages.SUCCESS)
            except ValidationError as e:
                self.message_user(request, f"Transfer Failed: {str(e)}", level=messages.ERROR)
            except Exception as e:
                self.message_user(request, f"Transfer Failed: {str(e)}", level=messages.ERROR)
                
@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(TenantScopedAdminBase):
    list_display = ('id', 'tenant', 'key', 'response_status', 'created_at')
    list_filter = ('tenant', 'response_status', 'created_at')
    search_fields = ('key', 'id')
    readonly_fields = ('created_at', 'key', 'response_status', 'response_body')

    def has_add_permission(self, request):
        return False                