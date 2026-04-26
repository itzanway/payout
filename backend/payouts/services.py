"""
All money-moving logic lives here.

THE LOCK:
  Merchant.objects.select_for_update().get(pk=merchant_id)
  → issues:  SELECT ... FROM merchants_merchant WHERE id=%s FOR UPDATE
  → PostgreSQL exclusive row lock, held until transaction commits.
  → Any concurrent request for same merchant blocks at the DB — not in Python.

WHY NOT PYTHON LOCKS:
  Gunicorn runs multiple processes. threading.Lock() is invisible across processes.
  Only the DB provides a lock that spans all workers.
"""

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

from merchants.models import Merchant, LedgerEntry
from payouts.models import Payout, IdempotencyKey


class InsufficientFundsError(Exception):
    pass

class InvalidAmountError(Exception):
    pass

class BankAccountError(Exception):
    pass


def _available_balance(merchant):
    """Single DB-level SUM — called inside a select_for_update block."""
    result = merchant.ledger_entries.aggregate(total=Sum('amount_paise'))
    return result['total'] or 0


def create_payout(merchant_id, amount_paise, bank_account_id, idempotency_key_str):
    """
    Creates a payout and holds funds atomically.
    Returns (response_data, http_status, was_created).
    """
    if amount_paise <= 0:
        raise InvalidAmountError("Amount must be positive")

    ttl = getattr(settings, 'IDEMPOTENCY_KEY_TTL', 86400)

    # --- Fast path: idempotency check BEFORE acquiring the row lock ---
    try:
        existing = IdempotencyKey.objects.get(merchant_id=merchant_id, key=idempotency_key_str)
        if not existing.is_expired():
            return existing.response_body, existing.response_status, False
        existing.delete()
    except IdempotencyKey.DoesNotExist:
        pass

    # --- Critical section: row lock on Merchant ---
    with transaction.atomic():
        try:
            # SELECT ... FOR UPDATE — blocks any other transaction touching this row
            merchant = Merchant.objects.select_for_update().get(pk=merchant_id)
        except Merchant.DoesNotExist:
            raise ValueError("Merchant not found")

        try:
            bank_account = merchant.bank_accounts.get(pk=bank_account_id)
        except Exception:
            raise BankAccountError("Bank account not found for this merchant")

        # Balance computed INSIDE the lock — guaranteed consistent
        available = _available_balance(merchant)

        if available < amount_paise:
            raise InsufficientFundsError(
                f"Insufficient funds. Available: {available} paise, Requested: {amount_paise} paise"
            )

        payout = Payout.objects.create(
            merchant=merchant,
            bank_account=bank_account,
            amount_paise=amount_paise,
            state=Payout.State.PENDING,
            idempotency_key=idempotency_key_str,
        )

        # Negative paise = funds held (reduces available balance immediately)
        LedgerEntry.objects.create(
            merchant=merchant,
            entry_type=LedgerEntry.EntryType.DEBIT_HOLD,
            amount_paise=-amount_paise,
            payout_id=payout.id,
            description=f"Hold for payout #{payout.id}",
        )
    # Lock released here on commit

    # Store idempotency key AFTER successful commit (don't cache a rolled-back result)
    from payouts.serializers import PayoutSerializer
    payout_data = PayoutSerializer(payout).data

    IdempotencyKey.objects.get_or_create(
        merchant_id=merchant_id,
        key=idempotency_key_str,
        defaults={
            'response_status': 201,
            'response_body': payout_data,
            'expires_at': timezone.now() + timedelta(seconds=ttl),
        }
    )

    return payout_data, 201, True


def process_payout(payout_id):
    """
    Simulates bank settlement. Called by Celery worker.
    70% success, 20% fail, 10% hang (stays processing for retry).
    """
    import random

    with transaction.atomic():
        try:
            payout = Payout.objects.select_for_update().get(pk=payout_id)
        except Payout.DoesNotExist:
            return

        if payout.state != Payout.State.PENDING:
            return

        payout.transition_to(Payout.State.PROCESSING)
        payout.processing_started_at = timezone.now()
        payout.attempt_count += 1
        payout.save(update_fields=['state', 'processing_started_at', 'attempt_count', 'updated_at'])

    # Simulate bank call OUTSIDE the lock
    roll = random.random()
    if roll < 0.70:
        _settle_payout(payout_id)
    elif roll < 0.90:
        _fail_payout(payout_id, reason="Bank rejected the transfer")
    # else: left in 'processing' — retry worker picks it up after 30s


def _settle_payout(payout_id):
    """Atomically: mark completed + write DEBIT_SETTLE entry."""
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(pk=payout_id)
        payout.transition_to(Payout.State.COMPLETED)
        payout.save(update_fields=['state', 'updated_at'])

        LedgerEntry.objects.create(
            merchant=payout.merchant,
            entry_type=LedgerEntry.EntryType.DEBIT_SETTLE,
            amount_paise=-payout.amount_paise,
            payout_id=payout.id,
            description=f"Settlement confirmed for payout #{payout.id}",
        )


def _fail_payout(payout_id, reason=""):
    """
    Atomically: mark failed + release held funds back to merchant.
    Both happen in ONE transaction — if either fails, both roll back.
    """
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(pk=payout_id)
        payout.transition_to(Payout.State.FAILED)  # raises if illegal (e.g. already completed)
        payout.failure_reason = reason
        payout.save(update_fields=['state', 'failure_reason', 'updated_at'])

        # Positive entry cancels the original negative DEBIT_HOLD
        LedgerEntry.objects.create(
            merchant=payout.merchant,
            entry_type=LedgerEntry.EntryType.DEBIT_RELEASE,
            amount_paise=payout.amount_paise,
            payout_id=payout.id,
            description=f"Funds released for failed payout #{payout.id}: {reason}",
        )