"""Evidence-backed customer explanations and observed weekly cohorts."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select

from app.core.clock import MERCHANT_TIMEZONE
from app.models import CustomerMetric, Transaction
from app.services.campaigns import money


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def transaction_dict(transaction: Transaction) -> dict:
    return {
        "id": transaction.id,
        "customer_token": transaction.customer_token,
        "amount": money(transaction.amount),
        "category": transaction.category,
        "created_at": aware(transaction.created_at).isoformat(),
        "campaign_id": transaction.campaign_id,
        "simulated": transaction.simulated,
    }


def customer_detail(db, token: str) -> dict:
    metric = db.get(CustomerMetric, token)
    if metric is None:
        raise HTTPException(404, "Customer token not found.")
    customer = metric.payload
    transactions = db.scalars(
        select(Transaction)
        .where(Transaction.customer_token == token)
        .order_by(Transaction.created_at.desc())
    ).all()
    daily = defaultdict(float)
    for transaction in transactions:
        day = aware(transaction.created_at).astimezone(MERCHANT_TIMEZONE).date().isoformat()
        daily[day] += transaction.amount
    interval = customer.get("average_intervisit_interval")
    deviation = customer.get("intervisit_standard_deviation", 0)
    first = datetime.fromisoformat(customer["first_transaction_date"])
    last = datetime.fromisoformat(customer["last_transaction_date"])
    enough_history = customer["total_transactions"] >= 5 and (datetime.now(timezone.utc) - aware(first)).days >= 21 and interval is not None
    threshold = round(max(interval * 2, interval + 2 * deviation, 7), 1) if enough_history else None
    overdue = enough_history and customer["recency_days"] > threshold
    cadence = "overdue" if overdue else "within_cadence" if enough_history else "insufficient_history"
    previous = customer["previous_30_day_spend"]
    current = customer["current_30_day_spend"]
    change = round((current - previous) / previous * 100, 1) if previous > 0 else None
    if not enough_history:
        explanation = "More purchase history is needed before treating this customer as an inactive regular."
    elif overdue:
        explanation = (
            f"This customer last visited {customer['recency_days']} days ago, outside an expected "
            f"{threshold:g}-day inactivity threshold based on their own purchase cadence."
        )
    else:
        explanation = "This customer's latest visit remains within their personalized purchase-cadence threshold."
    if change is not None:
        explanation += (
            f" Spending at this store changed by {change:+.1f}% across comparable 30-day windows."
        )
    explanation += " These records cannot identify purchases at other businesses."
    return {
        "customer": customer,
        "transactions": [transaction_dict(transaction) for transaction in transactions[:50]],
        "spend_trend": [{"date": day, "amount": money(amount)} for day, amount in sorted(daily.items())],
        "insights": {
            "cadence_status": cadence,
            "spend_change_percent": change,
            "description": explanation,
            "expected_interval_days": interval,
            "inactivity_threshold_days": threshold,
        },
        "rfm": {
            "recency_days": customer["recency_days"],
            "frequency": customer["frequency"],
            "monetary": customer["monetary"],
        },
        "synthetic": True,
    }


def weekly_cohorts(transactions, reference: datetime) -> list[dict]:
    """First-purchase weeks, with future observation windows left unmeasured.

    Each denominator is an actual nonempty signup cohort. Week zero is the first
    purchase week; activity is measured in Indian business calendar weeks.
    """
    reference = aware(reference).astimezone(MERCHANT_TIMEZONE)
    first_seen: dict[str, datetime] = {}
    for transaction in transactions:
        instant = aware(transaction.created_at).astimezone(MERCHANT_TIMEZONE)
        if instant > reference:
            continue
        token = transaction.customer_token
        if token not in first_seen or instant < first_seen[token]:
            first_seen[token] = instant
    grouped = defaultdict(set)
    for token, instant in first_seen.items():
        monday = (instant - timedelta(days=instant.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        grouped[monday].add(token)
    # At most six real cohorts keeps the heatmap readable while retaining new cohorts.
    cohort_weeks = sorted(grouped)
    if len(cohort_weeks) > 6:
        cohort_weeks = cohort_weeks[:3] + cohort_weeks[-3:]
    result = []
    for beginning in cohort_weeks:
        tokens = grouped[beginning]
        values = []
        for age in range(6):
            start = beginning + timedelta(weeks=age)
            end = start + timedelta(weeks=1)
            if start > reference:
                values.append(None)
                continue
            active = {
                transaction.customer_token
                for transaction in transactions
                if transaction.customer_token in tokens
                and start <= aware(transaction.created_at).astimezone(MERCHANT_TIMEZONE) < end
                and aware(transaction.created_at).astimezone(MERCHANT_TIMEZONE) <= reference
            }
            values.append(round(len(active) / len(tokens) * 100))
        result.append({
            "cohort": beginning.strftime("%d %b"),
            "start_date": beginning.date().isoformat(),
            "size": len(tokens),
            "period_days": 7,
            "values": values,
        })
    return result
