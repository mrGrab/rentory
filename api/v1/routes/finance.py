from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends

from core.dependencies import CurrentSuperuser, SessionDep
from models.finance import FinanceSummary
from services.finance_service import FinanceService

router = APIRouter(prefix="/finance", tags=["Finance"])


def get_finance_service(session: SessionDep) -> FinanceService:
    return FinanceService(session)


@router.get(
    "/summary",
    summary="Finance summary",
    description="Returns aggregated payment statistics. Superusers only.")
def get_finance_summary(_: CurrentSuperuser,
                        service: Annotated[FinanceService,
                                           Depends(get_finance_service)],
                        date_from: Optional[date] = None,
                        date_to: Optional[date] = None) -> FinanceSummary:
    return service.get_summary(date_from=date_from, date_to=date_to)
