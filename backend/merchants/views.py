from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Merchant
from .serializers import MerchantBalanceSerializer, LedgerEntrySerializer


class MerchantListView(APIView):
    def get(self, request):
        merchants = Merchant.objects.prefetch_related('bank_accounts').all()
        return Response(MerchantBalanceSerializer(merchants, many=True).data)


class MerchantDetailView(APIView):
    def get(self, request, merchant_id):
        try:
            merchant = Merchant.objects.prefetch_related('bank_accounts').get(pk=merchant_id)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=404)
        return Response(MerchantBalanceSerializer(merchant).data)


class MerchantLedgerView(APIView):
    def get(self, request, merchant_id):
        try:
            merchant = Merchant.objects.get(pk=merchant_id)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=404)
        entries = merchant.ledger_entries.all()[:50]
        return Response(LedgerEntrySerializer(entries, many=True).data)