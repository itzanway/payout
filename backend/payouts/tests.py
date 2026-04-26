import threading
import uuid
from django.test import TestCase, TransactionTestCase
from django.db.models import Sum

from merchants.models import Merchant, BankAccount, LedgerEntry
from payouts.models import Payout
from payouts.services import create_payout, InsufficientFundsError


def _make_merchant(balance_paise=10000, email=None):
    email = email or f"test-{uuid.uuid4()}@test.com"
    m = Merchant.objects.create(name="Test Merchant", email=email)
    ba = BankAccount.objects.create(
        merchant=m, account_number="00001111222233",
        ifsc_code="HDFC0000001", account_holder_name="Test User", is_primary=True,
    )
    LedgerEntry.objects.create(
        merchant=m, entry_type=LedgerEntry.EntryType.CREDIT,
        amount_paise=balance_paise, description="Seed credit",
    )
    return m, ba


class IdempotencyTest(TestCase):

    def test_same_key_returns_same_payout(self):
        m, ba = _make_merchant(100_000)
        key = str(uuid.uuid4())

        d1, s1, c1 = create_payout(m.id, 5000, ba.id, key)
        d2, s2, c2 = create_payout(m.id, 5000, ba.id, key)

        self.assertEqual(d1['id'], d2['id'])
        self.assertTrue(c1)
        self.assertFalse(c2)
        # Only ONE payout and ONE hold created
        self.assertEqual(Payout.objects.filter(merchant=m).count(), 1)
        self.assertEqual(
            LedgerEntry.objects.filter(merchant=m, entry_type='DEBIT_HOLD').count(), 1
        )

    def test_different_keys_make_different_payouts(self):
        m, ba = _make_merchant(200_000)
        create_payout(m.id, 5000, ba.id, str(uuid.uuid4()))
        create_payout(m.id, 5000, ba.id, str(uuid.uuid4()))
        self.assertEqual(Payout.objects.filter(merchant=m).count(), 2)

    def test_key_scoped_per_merchant(self):
        m1, ba1 = _make_merchant(100_000, email="m1@test.com")
        m2, ba2 = _make_merchant(100_000, email="m2@test.com")
        shared_key = str(uuid.uuid4())
        d1, _, c1 = create_payout(m1.id, 5000, ba1.id, shared_key)
        d2, _, c2 = create_payout(m2.id, 5000, ba2.id, shared_key)
        self.assertNotEqual(d1['id'], d2['id'])
        self.assertTrue(c1)
        self.assertTrue(c2)


class ConcurrencyTest(TransactionTestCase):
    """
    MUST use TransactionTestCase — not TestCase.
    TestCase wraps tests in one transaction; SELECT FOR UPDATE needs real commits
    to release locks between threads. TransactionTestCase flushes the DB instead.
    """

    def test_concurrent_overdraft_rejected(self):
        """
        Two threads, 6000 paise each, against 10000 paise balance.
        Exactly one must succeed. The other must get InsufficientFundsError.
        """
        m, ba = _make_merchant(balance_paise=10_000)
        results, errors = [], []

        def attempt():
            try:
                data, status, created = create_payout(m.id, 6000, ba.id, str(uuid.uuid4()))
                results.append(data)
            except InsufficientFundsError as e:
                errors.append(str(e))

        t1 = threading.Thread(target=attempt)
        t2 = threading.Thread(target=attempt)
        t1.start(); t2.start()
        t1.join(); t2.join()

        self.assertEqual(len(results), 1, f"Expected 1 success, got: {results}")
        self.assertEqual(len(errors),  1, f"Expected 1 error, got: {errors}")

        # Ledger invariant: 10000 - 6000 = 4000
        balance = m.ledger_entries.aggregate(t=Sum('amount_paise'))['t'] or 0
        self.assertEqual(balance, 4000)
        self.assertEqual(Payout.objects.filter(merchant=m).count(), 1)

    def test_ledger_invariant_holds(self):
        m, ba = _make_merchant(50_000)
        for _ in range(3):
            create_payout(m.id, 5000, ba.id, str(uuid.uuid4()))
        total = m.ledger_entries.aggregate(t=Sum('amount_paise'))['t'] or 0
        self.assertEqual(total, 35_000)  # 50000 - 3*5000


class StateMachineTest(TestCase):

    def _make_payout(self, state):
        m = Merchant.objects.create(name="SM", email=f"sm-{uuid.uuid4()}@t.com")
        ba = BankAccount.objects.create(
            merchant=m, account_number="11111111111111",
            ifsc_code="TEST0000001", account_holder_name="SM"
        )
        return Payout(merchant=m, bank_account=ba, amount_paise=1000, state=state)

    def test_completed_to_pending_blocked(self):
        p = self._make_payout('completed')
        with self.assertRaises(ValueError):
            p.transition_to('pending')

    def test_failed_to_completed_blocked(self):
        p = self._make_payout('failed')
        with self.assertRaises(ValueError):
            p.transition_to('completed')

    def test_pending_to_processing_allowed(self):
        p = self._make_payout('pending')
        p.transition_to('processing')
        self.assertEqual(p.state, 'processing')

    def test_processing_to_completed_allowed(self):
        p = self._make_payout('processing')
        p.transition_to('completed')
        self.assertEqual(p.state, 'completed')