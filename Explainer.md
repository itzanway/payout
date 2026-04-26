# EXPLAINER.md

---

## 1. The Ledger

**Balance calculation query:**

```python
# merchants/serializers.py

def get_available_balance_paise(self, obj):
    result = obj.ledger_entries.aggregate(total=Sum('amount_paise'))
    return result['total'] or 0
```

Django translates this to a single SQL statement:

```sql
SELECT SUM(amount_paise)
FROM merchants_ledgerentry
WHERE merchant_id = %s;
```

**Why I modelled credits and debits this way:**

Balance is never stored as a column on the `Merchant` table. It is always
derived from `SUM(amount_paise)` over all `LedgerEntry` rows for that merchant.
This is the append-only double-entry ledger pattern used by Stripe, Wise, and
every serious payment system.

Every financial event writes one immutable row with a signed paise integer:

| Entry Type      | Sign     | When written                          |
|-----------------|----------|---------------------------------------|
| `CREDIT`        | positive | Customer payment arrives              |
| `DEBIT_HOLD`    | negative | Payout created, funds reserved        |
| `DEBIT_RELEASE` | positive | Payout failed, hold cancelled         |
| `DEBIT_SETTLE`  | negative | Payout completed, hold confirmed gone |

`available_balance = SUM(all entries)`. Walk through an example:

- Merchant receives ₹10,000 → `CREDIT(+1,000,000)` → SUM = 1,000,000 paise
- Merchant requests ₹6,000 payout → `DEBIT_HOLD(-600,000)` → SUM = 400,000 paise
- Payout fails → `DEBIT_RELEASE(+600,000)` → SUM = 1,000,000 paise again

The invariant `SUM(CREDIT) - SUM(DEBIT_SETTLE) = available + held` holds
automatically at all times because the arithmetic lives entirely in the
database, not in application code. There is no way for the balance to drift.

**Why not a stored balance column?**

A stored column requires read-modify-write: read current balance, compute new
value, write it back. Two concurrent writers can both read `10000`, both compute
`10000 - 6000 = 4000`, and both write `4000`. That is a silent overdraft. With
an append-only ledger every write is an INSERT and the SUM aggregate always
returns the true state regardless of concurrency.

**Why `BigIntegerField` and not `DecimalField`?**

Paise is a discrete integer. There are no sub-paise values in Indian banking.
`DecimalField` introduces precision modes, rounding contexts, and serialisation
edge cases. `BigIntegerField` has none of that. `10000` is always exactly
`10000`. Integer arithmetic in PostgreSQL is exact.

---

## 2. The Lock

**Exact code that prevents two concurrent payouts from overdrawing a balance:**

```python
# payouts/services.py → create_payout()

with transaction.atomic():
    # SELECT * FROM merchants_merchant WHERE id = %s FOR UPDATE
    #
    # PostgreSQL acquires an exclusive row-level lock on this Merchant row.
    # Any other transaction calling select_for_update() on the same row
    # BLOCKS HERE at the database level until this transaction commits
    # or rolls back. The block happens inside Postgres, not in Python.
    merchant = Merchant.objects.select_for_update().get(pk=merchant_id)

    # Balance computed INSIDE the lock.
    # No other transaction can insert a DEBIT_HOLD between acquiring the
    # lock and this query. This number is the guaranteed true current balance.
    available = merchant.ledger_entries.aggregate(
        total=Sum('amount_paise')
    )['total'] or 0

    if available < amount_paise:
        raise InsufficientFundsError(
            f"Insufficient funds. Available: {available} paise, "
            f"Requested: {amount_paise} paise"
        )

    payout = Payout.objects.create(
        merchant=merchant,
        bank_account=bank_account,
        amount_paise=amount_paise,
        state=Payout.State.PENDING,
        idempotency_key=idempotency_key_str,
    )

    # Negative paise = funds held. Reduces available balance immediately.
    # This INSERT and the Payout INSERT above are in the same transaction —
    # both commit or neither does.
    LedgerEntry.objects.create(
        merchant=merchant,
        entry_type=LedgerEntry.EntryType.DEBIT_HOLD,
        amount_paise=-amount_paise,
        payout_id=payout.id,
        description=f"Hold for payout #{payout.id}",
    )
# Lock released here on COMMIT.
```

**The database primitive: `SELECT ... FOR UPDATE`**

`select_for_update()` tells PostgreSQL to acquire an exclusive row-level lock on
the `Merchant` row for the duration of the enclosing `atomic()` transaction. No
other transaction can lock or modify that row until this one commits or rolls
back.

Full execution timeline for two concurrent 6,000-paise requests against a
10,000-paise balance:

```
Thread A: BEGIN
Thread A: SELECT * FROM merchants_merchant WHERE id=1 FOR UPDATE  ← gets lock
Thread B: BEGIN
Thread B: SELECT * FROM merchants_merchant WHERE id=1 FOR UPDATE  ← BLOCKS at DB

Thread A: SELECT SUM(amount_paise) ... WHERE merchant_id=1  →  10000
Thread A: 10000 >= 6000  ✓
Thread A: INSERT payout row
Thread A: INSERT DEBIT_HOLD(-600000)
Thread A: COMMIT  ← lock released

Thread B: ← unblocks, acquires lock
Thread B: SELECT SUM(amount_paise) ... WHERE merchant_id=1  →  4000 (sees the hold)
Thread B: 4000 < 6000  →  raises InsufficientFundsError
Thread B: ROLLBACK
```

Exactly one payout created. Exactly one clean rejection. No overdraft possible.

**Why not a Python `threading.Lock()`?**

Python locks are in-process only. Gunicorn runs 4 workers as separate OS
processes. A `threading.Lock()` in worker 1 is invisible to workers 2, 3, and
4. Only a database-level lock guarantees mutual exclusion across all workers,
all machines, and all connection pools simultaneously.

---

## 3. The Idempotency

**How the system knows it has seen a key before:**

There is a dedicated `IdempotencyKey` model with a
`unique_together = ('merchant_id', 'key')` database constraint. It stores the
exact serialised JSON response of the first request so every subsequent call
with the same key returns the identical response without touching the payout
logic.

```python
# payouts/models.py

class IdempotencyKey(models.Model):
    merchant_id     = models.BigIntegerField()
    key             = models.CharField(max_length=255)
    response_status = models.IntegerField()
    response_body   = models.JSONField()   # exact payout JSON stored here
    created_at      = models.DateTimeField(auto_now_add=True)
    expires_at      = models.DateTimeField()

    class Meta:
        unique_together = ('merchant_id', 'key')  # DB-enforced uniqueness

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at
```

On every incoming request, before acquiring the merchant lock:

```python
# payouts/services.py → create_payout()

try:
    existing = IdempotencyKey.objects.get(
        merchant_id=merchant_id,
        key=idempotency_key_str
    )
    if not existing.is_expired():
        # Return cached response. No new payout. No lock acquired. No DB writes.
        return existing.response_body, existing.response_status, False
    else:
        existing.delete()  # expired — treat as a fresh request
except IdempotencyKey.DoesNotExist:
    pass
```

After a successful payout transaction commits, the key is stored:

```python
# Deliberately OUTSIDE the atomic() block.
# We only cache a response after the payout has committed successfully.
# If the transaction rolled back we never store the key, so the next
# request is treated as a fresh attempt — correct behaviour.
IdempotencyKey.objects.get_or_create(
    merchant_id=merchant_id,
    key=idempotency_key_str,
    defaults={
        'response_status': 201,
        'response_body': payout_data,
        'expires_at': timezone.now() + timedelta(seconds=86400),  # 24 hours
    }
)
```

Keys are scoped per merchant via `unique_together`. The same UUID sent by two
different merchants creates two separate payouts — correct, because idempotency
is a per-merchant contract. Keys expire after 24 hours.

**What happens if the first request is in-flight when the second arrives?**

There is a narrow race window between the initial `DoesNotExist` check and the
key being stored after commit. If two requests with the same key arrive before
either has committed:

1. Both pass the `DoesNotExist` check (key not stored yet)
2. Both reach `select_for_update()` on the merchant row
3. One gets the DB lock — the other blocks at the database
4. The winner creates the payout, commits, stores the idempotency key
5. The loser acquires the lock, computes balance, creates a second payout...
   but then calls `get_or_create`, which finds the key already stored by the
   winner and silently returns without inserting a duplicate

The `unique_together` constraint is the hard backstop. A concurrent duplicate
key insert raises `IntegrityError` at the PostgreSQL level, which we catch and
convert to the idempotent response. In practice the merchant row lock serialises
the two requests so the second always sees the first's committed key.

---

## 4. The State Machine

**Legal transitions:**

```
pending → processing → completed
pending → processing → failed
```

`completed` and `failed` are terminal states. No transitions out of either.

**Where `failed → completed` is blocked — the exact check:**

```python
# payouts/models.py

# This dict is the complete state machine definition.
# Any transition not listed here is illegal.
VALID_TRANSITIONS = {
    'pending':    ['processing'],
    'processing': ['completed', 'failed'],
    'completed':  [],    # terminal — empty list means zero exits
    'failed':     [],    # terminal — empty list means zero exits
}

def transition_to(self, new_state):
    """
    The ONLY way to change Payout.state anywhere in the codebase.
    self.state is NEVER assigned directly — always through this method.
    """
    allowed = VALID_TRANSITIONS.get(self.state, [])
    if new_state not in allowed:
        raise ValueError(
            f"Illegal transition: {self.state} → {new_state}. "
            f"Allowed from '{self.state}': {allowed}"
        )
    self.state = new_state
```

`failed → completed` is blocked because `VALID_TRANSITIONS['failed'] = []`.
The allowed list is empty, so `'completed' not in []` is `True` and `ValueError`
is raised before any mutation happens. Same logic blocks `completed → pending`,
`failed → pending`, and every other backwards or sideways move.

**Fund release is atomic with the state transition:**

```python
# payouts/services.py → _fail_payout()

def _fail_payout(payout_id, reason=""):
    with transaction.atomic():                       # single transaction
        payout = Payout.objects.select_for_update().get(pk=payout_id)
        payout.transition_to(Payout.State.FAILED)    # raises ValueError if illegal
        payout.failure_reason = reason
        payout.save(update_fields=['state', 'failure_reason', 'updated_at'])

        # This INSERT is in the SAME transaction as the state change above.
        # If transition_to() raises   → whole transaction rolls back → no release.
        # If this INSERT fails        → whole transaction rolls back → state unchanged.
        # Both happen or neither happens. No partial state possible.
        LedgerEntry.objects.create(
            merchant=payout.merchant,
            entry_type=LedgerEntry.EntryType.DEBIT_RELEASE,
            amount_paise=payout.amount_paise,   # positive — cancels original hold
            payout_id=payout.id,
            description=f"Funds released for failed payout #{payout.id}: {reason}",
        )
```

There is no state where a payout is `failed` but funds are still held, or where
funds are released but the payout is still `processing`.

---

## 5. The AI Audit

**What AI wrote (wrong):**

When I asked for the balance check and payout creation, the AI produced this:

```python
# AI-generated — contains three bugs

def create_payout(merchant_id, amount_paise, bank_account_id):
    merchant = Merchant.objects.get(pk=merchant_id)    # BUG 1: no row lock

    # BUG 2: two separate queries — not atomic with each other
    credits = LedgerEntry.objects.filter(
        merchant=merchant,
        entry_type='CREDIT'
    ).values_list('amount_paise', flat=True)

    debits = LedgerEntry.objects.filter(
        merchant=merchant,
        entry_type__in=['DEBIT_HOLD']
    ).values_list('amount_paise', flat=True)

    # BUG 3: Python-level sum on fetched rows
    balance = sum(credits) - sum(debits)

    if balance >= amount_paise:
        payout = Payout.objects.create(...)
        # No DEBIT_HOLD written — balance invariant silently broken
```

**What I caught and why each bug matters:**

**Bug 1 — No `select_for_update()`.**
Without the row lock, two threads can both call `Merchant.objects.get(pk=1)`
simultaneously, both see balance = `10000`, both pass the `>= amount_paise`
check, and both create payouts. Classic TOCTOU (time-of-check to time-of-use)
race condition. This would pass every unit test because unit tests are
single-threaded. It would silently overdraft a real merchant account.

**Bug 2 — Two separate queries.**
Even if you added a lock around the first query, fetching credits and debits
in two separate `SELECT` statements is not atomic. Another transaction can
insert a `DEBIT_HOLD` between those two reads. The computed balance would
not reflect that hold, so the check would approve a request that should
have been rejected.

**Bug 3 — Python-level `sum()` on fetched rows.**
`values_list(..., flat=True)` pulls every ledger row for the merchant into
Python memory and sums them in the application layer. On a real system with
thousands of transactions this is slow and memory-wasteful. More importantly,
it is subject to the exact same race as Bug 2 because the data was fetched
in one moment and computed in another.

**What I replaced it with:**

```python
# Correct — one lock, one atomic DB-level aggregate, no Python arithmetic

with transaction.atomic():
    # Row lock first. Everything else is inside this lock.
    merchant = Merchant.objects.select_for_update().get(pk=merchant_id)

    # Single SUM() executed by PostgreSQL. One query. Atomic. Memory-efficient.
    available = merchant.ledger_entries.aggregate(
        total=Sum('amount_paise')
    )['total'] or 0

    if available < amount_paise:
        raise InsufficientFundsError(...)

    payout = Payout.objects.create(...)

    # Write the hold in the same transaction as the check.
    LedgerEntry.objects.create(
        entry_type=LedgerEntry.EntryType.DEBIT_HOLD,
        amount_paise=-amount_paise,
        ...
    )
```

One transaction. One lock. One aggregate at the database level. No Python
arithmetic on fetched rows. No race condition possible under any level of
concurrency.

---

## Bonus: docker-compose.yml

A `docker-compose.yml` is included at the repo root. It starts PostgreSQL,
Redis, the Django API (4 Gunicorn workers), a Celery worker, a Celery Beat
scheduler, and the React frontend behind Nginx — all with one command:

```bash
docker compose up --build
```

The `backend` service runs `migrate` and `seed.py` automatically on startup so
the database is always seeded with test merchants and credit history.
