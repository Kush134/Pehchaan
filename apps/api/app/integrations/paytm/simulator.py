"""A deliberately local payment adapter. No Paytm request or money movement."""
from typing import Protocol

class PaymentProvider(Protocol):
    def authorize(self, order_id: str, amount: float) -> dict: ...

class SimulatedPaymentProvider:
    def authorize(self, order_id: str, amount: float) -> dict:
        return {'provider':'local-simulator','simulated':True,'order_id':order_id,
                'amount':amount,'state':'AUTHORIZATION_SIMULATED',
                'notice':'SIMULATED ONLY. No Paytm authorization, escrow or real financial transaction occurred.'}
