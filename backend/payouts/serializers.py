from rest_framework import serializers
from .models import Payout


class PayoutSerializer(serializers.ModelSerializer):
    merchant_name       = serializers.CharField(source='merchant.name', read_only=True)
    bank_account_display = serializers.SerializerMethodField()

    class Meta:
        model = Payout
        fields = [
            'id', 'merchant', 'merchant_name', 'bank_account',
            'bank_account_display', 'amount_paise', 'state',
            'idempotency_key', 'attempt_count', 'failure_reason',
            'created_at', 'updated_at', 'processing_started_at',
        ]
        read_only_fields = fields

    def get_bank_account_display(self, obj):
        a = obj.bank_account
        return f"{a.account_holder_name} (···{a.account_number[-4:]})"