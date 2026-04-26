import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from merchants.models import Merchant, BankAccount, LedgerEntry
from django.db.models import Sum

print("Seeding...")

LedgerEntry.objects.all().delete()
BankAccount.objects.all().delete()
Merchant.objects.all().delete()

m1 = Merchant.objects.create(name="Priya Design Studio", email="priya@design.in")
m2 = Merchant.objects.create(name="Rohan Dev Works",     email="rohan@devworks.in")
m3 = Merchant.objects.create(name="Meera Content Co",    email="meera@content.in")

BankAccount.objects.create(merchant=m1, account_number="12345678901234", ifsc_code="HDFC0001234", account_holder_name="Priya Sharma",  is_primary=True)
BankAccount.objects.create(merchant=m2, account_number="98765432109876", ifsc_code="ICIC0005678", account_holder_name="Rohan Mehta",   is_primary=True)
BankAccount.objects.create(merchant=m3, account_number="11223344556677", ifsc_code="SBIN0009012", account_holder_name="Meera Nair",    is_primary=True)

# 1 USD ≈ 83 INR → 8300 paise per dollar
credits = [
    (m1, 500*8300,  "Customer payment – Logo design"),
    (m1, 1200*8300, "Customer payment – Brand identity"),
    (m1, 750*8300,  "Customer payment – Website mockups"),
    (m2, 800*8300,  "Customer payment – API integration"),
    (m2, 2000*8300, "Customer payment – Full-stack build"),
    (m2, 600*8300,  "Customer payment – Bug fix sprint"),
    (m3, 300*8300,  "Customer payment – Blog content"),
    (m3, 900*8300,  "Customer payment – Social strategy"),
    (m3, 450*8300,  "Customer payment – Newsletter series"),
]

for merchant, amount, desc in credits:
    LedgerEntry.objects.create(
        merchant=merchant,
        entry_type=LedgerEntry.EntryType.CREDIT,
        amount_paise=amount,
        description=desc,
    )

print(f"✓ 3 merchants, 3 bank accounts, {len(credits)} credit entries\n")
for m in [m1, m2, m3]:
    bal = m.ledger_entries.aggregate(t=Sum('amount_paise'))['t'] or 0
    print(f"  {m.name}: ₹{bal//100:,} ({bal} paise)")

print("\nDone!")