from django.contrib import admin
from .models import Merchant, BankAccount, LedgerEntry

admin.site.register(Merchant)
admin.site.register(BankAccount)
admin.site.register(LedgerEntry)