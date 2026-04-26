from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_payout_task(self, payout_id):
    from payouts.services import process_payout
    try:
        process_payout(payout_id)
    except Exception as exc:
        logger.error(f"Error processing payout {payout_id}: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@shared_task
def retry_stuck_payouts():
    """
    Runs every 30 seconds via Celery Beat.
    Finds payouts stuck in 'processing' > 30s.
    Retries with exponential backoff, max 3 attempts, then marks failed.
    Uses skip_locked=True so multiple beat workers don't double-process.
    """
    from payouts.models import Payout
    from payouts.services import _fail_payout
    from django.db import transaction

    cutoff = timezone.now() - timedelta(seconds=30)

    with transaction.atomic():
        stuck = Payout.objects.select_for_update(skip_locked=True).filter(
            state=Payout.State.PROCESSING,
            processing_started_at__lt=cutoff,
        )

        for payout in stuck:
            if payout.attempt_count >= payout.max_attempts:
                logger.warning(f"Payout {payout.id} exceeded max attempts → failing")
                _fail_payout(payout.id, reason=f"Exceeded {payout.max_attempts} retry attempts")
            else:
                backoff = 2 ** payout.attempt_count  # 2s, 4s, 8s
                payout.state = Payout.State.PENDING
                payout.next_retry_at = timezone.now() + timedelta(seconds=backoff)
                payout.save(update_fields=['state', 'next_retry_at', 'updated_at'])
                logger.info(f"Retrying payout {payout.id} (attempt {payout.attempt_count})")
                process_payout_task.apply_async(args=[payout.id], countdown=backoff)