from django.db import models


class Merchant(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class BankAccount(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='bank_accounts')
    account_number = models.CharField(max_length=20)
    ifsc_code = models.CharField(max_length=11)
    account_holder_name = models.CharField(max_length=255)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_holder_name} - {self.account_number[-4:]}"


class LedgerEntry(models.Model):
    """
    Append-only ledger. Balance is NEVER stored — always derived as SUM(amount_paise).
    Credits: positive paise. Holds: negative. Releases: positive. Settles: negative.
    """

    class EntryType(models.TextChoices):
        CREDIT         = 'CREDIT',         'Credit'
        DEBIT_HOLD     = 'DEBIT_HOLD',     'Debit Hold'
        DEBIT_RELEASE  = 'DEBIT_RELEASE',  'Debit Release'
        DEBIT_SETTLE   = 'DEBIT_SETTLE',   'Debit Settle'

    merchant     = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='ledger_entries')
    entry_type   = models.CharField(max_length=20, choices=EntryType.choices)
    amount_paise = models.BigIntegerField()   # NEVER float or decimal
    payout_id    = models.BigIntegerField(null=True, blank=True, db_index=True)
    description  = models.CharField(max_length=500, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['merchant', 'created_at'])]

    def __str__(self):
        return f"{self.merchant.name} | {self.entry_type} | {self.amount_paise}"