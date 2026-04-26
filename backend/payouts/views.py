import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Payout
from .serializers import PayoutSerializer
from .services import create_payout, InsufficientFundsError, InvalidAmountError, BankAccountError
from .tasks import process_payout_task


class PayoutCreateView(APIView):
    def post(self, request):
        # Validate Idempotency-Key header
        idempotency_key = request.headers.get('Idempotency-Key', '').strip()
        if not idempotency_key:
            return Response({'error': 'Idempotency-Key header is required'}, status=400)
        try:
            uuid.UUID(idempotency_key)
        except ValueError:
            return Response({'error': 'Idempotency-Key must be a valid UUID'}, status=400)

        # Get merchant from header
        merchant_id = request.headers.get('X-Merchant-Id', '').strip()
        if not merchant_id:
            return Response({'error': 'X-Merchant-Id header is required'}, status=400)
        try:
            merchant_id = int(merchant_id)
        except ValueError:
            return Response({'error': 'X-Merchant-Id must be an integer'}, status=400)

        amount_paise    = request.data.get('amount_paise')
        bank_account_id = request.data.get('bank_account_id')

        if amount_paise is None or bank_account_id is None:
            return Response({'error': 'amount_paise and bank_account_id are required'}, status=400)

        try:
            payout_data, http_status, was_created = create_payout(
                merchant_id=merchant_id,
                amount_paise=int(amount_paise),
                bank_account_id=int(bank_account_id),
                idempotency_key_str=idempotency_key,
            )
        except InsufficientFundsError as e:
            return Response({'error': str(e)}, status=422)
        except (InvalidAmountError, BankAccountError) as e:
            return Response({'error': str(e)}, status=400)
        except ValueError as e:
            return Response({'error': str(e)}, status=404)

        if was_created:
            process_payout_task.apply_async(args=[payout_data['id']], countdown=1)

        return Response(payout_data, status=http_status)


class PayoutListView(APIView):
    def get(self, request):
        merchant_id = request.query_params.get('merchant_id')
        if not merchant_id:
            return Response({'error': 'merchant_id query param required'}, status=400)
        payouts = Payout.objects.filter(merchant_id=merchant_id).order_by('-created_at')[:50]
        return Response(PayoutSerializer(payouts, many=True).data)


class PayoutDetailView(APIView):
    def get(self, request, payout_id):
        try:
            payout = Payout.objects.get(pk=payout_id)
        except Payout.DoesNotExist:
            return Response({'error': 'Payout not found'}, status=404)
        return Response(PayoutSerializer(payout).data)