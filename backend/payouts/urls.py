from django.urls import path
from .views import PayoutCreateView, PayoutListView, PayoutDetailView

urlpatterns = [
    path('payouts/', PayoutCreateView.as_view()),
    path('payouts/list/', PayoutListView.as_view()),
    path('payouts/<int:payout_id>/', PayoutDetailView.as_view()),
]