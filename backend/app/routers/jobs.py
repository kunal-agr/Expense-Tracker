from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.services.recurring_service import run_daily_job
from app.errors import AppException

router = APIRouter(prefix="/internal/jobs", tags=["Internal Scheduled Jobs"])


@router.post("/daily", status_code=status.HTTP_200_OK)
def trigger_daily_job(
    x_cron_secret: str | None = Header(None, alias="X-Cron-Secret"),
    db: Session = Depends(get_db),
):
    """
    Daily scheduled job endpoint (FR-052b, NFR-009).
    Secured with X-Cron-Secret header.
    Processes:
    1. Recurring transaction schedule execution
    2. Split bill 7-day expiration
    3. Notification cleanup (> 90 days)
    """
    if not x_cron_secret or x_cron_secret != settings.CRON_SECRET:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INVALID_CRON_SECRET",
            message="Invalid or missing X-Cron-Secret header.",
        )

    summary = run_daily_job(db)
    return summary
