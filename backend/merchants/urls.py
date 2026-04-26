from django.urls import path
from .views import MerchantListView, MerchantDetailView, MerchantLedgerView

urlpatterns = [
    path('merchants/', MerchantListView.as_view()),
    path('merchants/<int:merchant_id>/', MerchantDetailView.as_view()),
    path('merchants/<int:merchant_id>/ledger/', MerchantLedgerView.as_view()),
]