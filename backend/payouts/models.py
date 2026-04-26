from django.db import models

# Legal transitions only. Anything not listed is ILLEGAL.
VALID_TRANSITIONS = {
    'pending':    ['processing'],
    'processing': ['completed', 'failed'],
    'completed':  [],   # terminal
    'failed':     [],   # terminal
}


class IdempotencyKey(models.Model):
    """
    Stores the serialized response of the first request for (merchant_id, key).
    Repeated requests return this cached response without creating a new payout.
    Keys expire after 24 hours (checked in services.py).
    """
    merchant_id   = models.BigIntegerField()
    key           = models.CharField(max_length=255)
    response_status = models.IntegerField()
    response_body = models.JSONField()
    created_at    = models.DateTimeField(auto_now_add=True)
    expires_at    = models.DateTimeField()

    class Meta:
        unique_together = ('merchant_id', 'key')
        indexes = [models.Index(fields=['merchant_id', 'key'])]

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at


class Payout(models.Model):
    class State(models.TextChoices):
        PENDING    = 'pending',    'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED  = 'completed',  'Completed'
        FAILED     = 'failed',     'Failed'

    merchant         = models.ForeignKey('merchants.Merchant', on_delete=models.CASCADE, related_name='payouts')
    bank_account     = models.ForeignKey('merchants.BankAccount', on_delete=models.CASCADE)
    amount_paise     = models.BigIntegerField()    # integer paise — never float
    state            = models.CharField(max_length=20, choices=State.choices, default=State.PENDING)
    idempotency_key  = models.CharField(max_length=255, blank=True, default='')
    attempt_count    = models.IntegerField(default=0)
    max_attempts     = models.IntegerField(default=3)
    next_retry_at    = models.DateTimeField(null=True, blank=True)
    failure_reason   = models.CharField(max_length=500, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['merchant', 'state']),
            models.Index(fields=['state', 'next_retry_at']),
        ]

    def transition_to(self, new_state):
        """
        The ONLY way to change state. Raises ValueError for any illegal transition.
        self.state is never set directly anywhere in the codebase.
        """
        allowed = VALID_TRANSITIONS.get(self.state, [])
        if new_state not in allowed:
            raise ValueError(
                f"Illegal transition: {self.state} → {new_state}. "
                f"Allowed from '{self.state}': {allowed}"
            )
        self.state = new_state

    def __str__(self):
        return f"Payout #{self.id} | {self.merchant} | {self.amount_paise}p | {self.state}"