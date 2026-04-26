from django.contrib import admin
from .models import Payout, IdempotencyKey

admin.site.register(Payout)
admin.site.register(IdempotencyKey)