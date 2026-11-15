from fastapi import APIRouter, Depends, Query

from app.database.session import get_db
from app.services.business_analytics import business_summary

router=APIRouter()

@router.get('/business/summary')
@router.get('/business/analytics')
def summary(days:int=Query(default=7,ge=1,le=90),db=Depends(get_db)):
    return business_summary(db,days)

@router.get('/business/daily-summary')
def daily_summary(db=Depends(get_db)):
    return business_summary(db,1)
