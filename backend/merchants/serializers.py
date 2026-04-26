from rest_framework import serializers
from django.db.models import Sum
from .models import Merchant, BankAccount, LedgerEntry


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = ['id', 'account_number', 'ifsc_code', 'account_holder_name', 'is_primary']


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ['id', 'entry_type', 'amount_paise', 'description', 'created_at', 'payout_id']


class MerchantBalanceSerializer(serializers.ModelSerializer):
    """
    Balance is always computed at DB level — never stored as a column.
    available_balance = SUM(all ledger entries) for the merchant
    held_balance      = |SUM(DEBIT_HOLD)| - released - settled
    """
    available_balance_paise = serializers.SerializerMethodField()
    held_balance_paise      = serializers.SerializerMethodField()
    total_credited_paise    = serializers.SerializerMethodField()
    bank_accounts           = BankAccountSerializer(many=True, read_only=True)

    class Meta:
        model = Merchant
        fields = ['id', 'name', 'email',
                  'available_balance_paise', 'held_balance_paise',
                  'total_credited_paise', 'bank_accounts']

    def get_available_balance_paise(self, obj):
        result = obj.ledger_entries.aggregate(total=Sum('amount_paise'))
        return result['total'] or 0

    def get_held_balance_paise(self, obj):
        def _sum(qs):
            return qs.aggregate(t=Sum('amount_paise'))['t'] or 0

        holds    = _sum(obj.ledger_entries.filter(entry_type=LedgerEntry.EntryType.DEBIT_HOLD))
        released = _sum(obj.ledger_entries.filter(entry_type=LedgerEntry.EntryType.DEBIT_RELEASE))
        settled  = _sum(obj.ledger_entries.filter(entry_type=LedgerEntry.EntryType.DEBIT_SETTLE))
        return abs(holds) - released - abs(settled)

    def get_total_credited_paise(self, obj):
        result = obj.ledger_entries.filter(
            entry_type=LedgerEntry.EntryType.CREDIT
        ).aggregate(total=Sum('amount_paise'))
        return result['total'] or 0