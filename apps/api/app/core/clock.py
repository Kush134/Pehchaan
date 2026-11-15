"""Merchant business dates use India time; all persisted instants remain UTC."""
from datetime import datetime,time,timezone
from zoneinfo import ZoneInfo

MERCHANT_TIMEZONE=ZoneInfo('Asia/Kolkata')
def business_today():return datetime.now(timezone.utc).astimezone(MERCHANT_TIMEZONE).date()
def business_day_start():return datetime.combine(business_today(),time.min,tzinfo=MERCHANT_TIMEZONE).astimezone(timezone.utc)
