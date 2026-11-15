from decimal import Decimal
from typing import Annotated
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, ConfigDict
from app.api.core import merchant_role, mutate
from app.database.session import get_db
from app.services import checkout

router = APIRouter(prefix='/checkout', dependencies=[Depends(merchant_role)])


class QuoteInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    customer_token: str = Field(min_length=1, max_length=100)
    bill_amount: Annotated[Decimal, Field(gt=0, le=1000000, max_digits=9, decimal_places=2, allow_inf_nan=False)]


class PayInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    quote_id: str = Field(min_length=1, max_length=100)


@router.get('/offers')
def list_offers(db=Depends(get_db)):
    return checkout.offers(db)


@router.post('/quote')
def create_quote(body: QuoteInput, request: Request, db=Depends(get_db)):
    return mutate(db, request, body.model_dump(mode='json'), lambda: checkout.quote(db, body.customer_token, body.bill_amount))


@router.post('/pay')
def complete_payment(body: PayInput, request: Request, db=Depends(get_db)):
    return mutate(db, request, body.model_dump(), lambda: checkout.pay(db, body.quote_id))
