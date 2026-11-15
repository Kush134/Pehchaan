from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import TypedDict
from uuid import uuid4

from fastapi import HTTPException
from langgraph.graph import StateGraph, START, END
from sqlalchemy import select

from app.models import BulkOrder, BulkOrderItem, NegotiationSession, PaymentSimulation, Seller
from app.core.clock import business_today
from app.security.policy import sign_mandate, verify_mandate, validate_policy
from app.security.seller_policies import seller_floor
from app.services.events import emit
from app.services.negotiation import PRODUCTS, money, seller_stock
from app.integrations.paytm import SimulatedPaymentProvider


def order_dict(order: BulkOrder) -> dict:
    return {'id':order.id,'status':order.status,'created_at':order.created_at.isoformat(),
            **{k:v for k,v in order.payload.items() if not k.startswith('_')}}


def load_order(db,oid: str, *, lock=False) -> BulkOrder:
    stmt=select(BulkOrder).where(BulkOrder.id==oid)
    if lock: stmt=stmt.with_for_update()
    order=db.scalar(stmt)
    if not order: raise HTTPException(404,'Order not found.')
    return order


def stamp(state: str, detail: str):
    return {'state':state,'detail':detail,'created_at':datetime.now(timezone.utc).isoformat()}


def validated_action(db, order: BulkOrder, operation: str):
    payload=order.payload
    # Authorization context comes exclusively from the stored, signed order mandate.
    mandate=payload['_mandate']
    if not verify_mandate(mandate,payload['_signature']):
        raise HTTPException(409,'Stored order mandate failed verification.')
    proposal={'amount':mandate['amount'],'budget':mandate['budget'], 'seller_id':'optimized-bundle',
        'round_number':mandate['round_number'],'operation':operation,
        'merchant_approved':payload.get('merchant_approved',False),'buyer_confirmed':payload.get('buyer_confirmed',False),
        'quantity_available':True,'delivery_feasible':True,'expiry':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),
        'nonce':f'{operation}:{order.id}:{uuid4()}'}
    proposal['signature']=sign_mandate(proposal)
    decision=validate_policy(db,proposal,floor=0)
    if decision['status']=='BLOCKED':
        raise HTTPException(409,detail={'message':'Order action blocked by policy.','reasons':decision['reasons']})


class ConfirmationState(TypedDict):
    db: object
    session: object
    order: object


def order_confirmation(state: ConfirmationState):
    db=state['db']; row=state['session']; deal=row.payload['best_deal']
    mandate={'amount':deal['total_amount'],'budget':row.payload['budget'],'round_number':deal['round_number'],
        'session_id':row.id,'products':deal['products'],'confirmed_at':datetime.now(timezone.utc).isoformat()}
    payload={'session_id':row.id,'seller_name':deal['seller_name'],'items':deal['products'],
        'subtotal':deal['subtotal'],'delivery_cost':deal['delivery_cost'],'total_amount':deal['total_amount'],
        'delivery_date':deal['delivery_date'],'payment_state':'ORDER_CREATED','simulated':True,
        'merchant_approved':True,'buyer_confirmed':True,'packed':False,'delivery_confirmed':False,
        'inspection':None,'timeline':[stamp('ORDER_CREATED','Both merchant and buyer explicitly confirmed the selected deal.')],
        '_mandate':mandate,'_signature':sign_mandate(mandate)}
    order=BulkOrder(id=row.id,status='confirmed',payload=payload)
    db.add(order); db.flush()
    for item in deal['products']:
        db.add(BulkOrderItem(id=str(uuid4()),status='confirmed',payload={'order_id':order.id,**item}))
    row.status='confirmed'
    emit(db,'order.confirmed','Bulk order confirmed',f"₹{deal['total_amount']:,.2f}; merchant and buyer approvals recorded.",agent='supervisor',data={'order_id':order.id})
    state['order']=order
    return state


def simulated_payment(state: ConfirmationState):
    db=state['db']; order=state['order']
    validated_action(db,order,'payment')
    payment=SimulatedPaymentProvider().authorize(order.id,order.payload['total_amount'])
    timeline=[*order.payload['timeline'],stamp('PAYMENT_INITIATED','Local simulated payment initiated.'),
        stamp('AUTHORIZATION_SIMULATED',payment['notice']),
        stamp('DELIVERY_CONFIRMATION_PENDING','Merchant packing and human delivery confirmation required.')]
    order.payload={**order.payload,'payment_state':'DELIVERY_CONFIRMATION_PENDING','timeline':timeline,'payment_notice':payment['notice']}
    db.add(PaymentSimulation(id=f'payment-{order.id}',status='DELIVERY_CONFIRMATION_PENDING',payload={**payment,'timeline':timeline}))
    emit(db,'payment.simulated','Payment authorization simulated',payment['notice'],agent='payment',data={'order_id':order.id,'state':'AUTHORIZATION_SIMULATED'})
    return state


def final_ledger_update(state: ConfirmationState):
    emit(state['db'],'ledger.updated','Simulated order ledger updated','No real money moved. Settlement waits for packing and human confirmation.',agent='payment',data={'order_id':state['order'].id})
    return state


def confirmation_graph():
    graph=StateGraph(ConfirmationState)
    graph.add_node('order_confirmation',order_confirmation)
    graph.add_node('simulated_payment',simulated_payment)
    graph.add_node('final_ledger_update',final_ledger_update)
    graph.add_edge(START,'order_confirmation'); graph.add_edge('order_confirmation','simulated_payment')
    graph.add_edge('simulated_payment','final_ledger_update'); graph.add_edge('final_ledger_update',END)
    return graph.compile()


CONFIRMATION_GRAPH=confirmation_graph()


def confirm_session(db,sid: str, *, merchant_approved: bool, buyer_confirmed: bool):
    # Deterministic one-order-per-session ID plus row lock protects concurrent confirmations.
    row=db.scalar(select(NegotiationSession).where(NegotiationSession.id==sid).with_for_update())
    if not row: raise HTTPException(404,'Negotiation session not found.')
    existing=db.get(BulkOrder,sid)
    if existing: return order_dict(existing)
    if row.status!='awaiting_approval' or not row.payload.get('best_deal'):
        raise HTTPException(409,'An eligible completed negotiation is required before confirmation.')
    if not merchant_approved or not buyer_confirmed:
        raise HTTPException(403,'Both merchant approval and buyer confirmation are required.')
    payload=row.payload
    mandate=payload.get('_mandate')
    if not mandate or not verify_mandate(mandate,payload.get('_signature','')) or mandate['deal']!=payload['best_deal'] or mandate['budget']!=payload['budget']:
        raise HTTPException(409,'Negotiation mandate is missing or has been modified. Run negotiation again.')
    if datetime.fromisoformat(mandate['expiry'])<=datetime.now(timezone.utc):
        raise HTTPException(409,'The selected offer has expired. Run a new negotiation.')
    deal=mandate['deal']; groups={}
    for item in deal['products']:
        groups.setdefault(item.get('seller_id',deal['seller_id']),[]).append(item)
    # Seller rows are locked in stable order to reserve stock atomically.
    floor=Decimal(0)
    quantity_ok=True
    for seller_id in sorted(groups):
        seller=db.scalar(select(Seller).where(Seller.id==seller_id).with_for_update())
        if not seller: raise HTTPException(409,'Seller catalogue is unavailable.')
        stock=copy.deepcopy(seller_stock(db,seller_id))
        for item in groups[seller_id]:
            if stock.get(item['product_id'],0)<item['quantity']: quantity_ok=False
        floor+=seller_floor(seller_id,groups[seller_id],PRODUCTS)
    delivery_ok=deal['delivery_date']<=payload['delivery_date'] and date.fromisoformat(payload['delivery_date'])>=business_today()
    proposal={'amount':deal['total_amount'],'budget':payload['budget'],'seller_id':deal['seller_id'],
        'round_number':deal['round_number'],'operation':'confirm_order','merchant_approved':True,'buyer_confirmed':True,
        'quantity_available':quantity_ok,'delivery_feasible':delivery_ok,'expiry':mandate['expiry'],'nonce':f'confirm:{sid}'}
    proposal['signature']=sign_mandate(proposal)
    decision=validate_policy(db,proposal,floor=floor)
    if decision['status']=='BLOCKED':
        db.commit()
        raise HTTPException(409,detail={'message':'Confirmation blocked by policy.','reasons':decision['reasons']})
    for seller_id,items in groups.items():
        seller=db.get(Seller,seller_id); stock=copy.deepcopy(seller_stock(db,seller_id))
        for item in items: stock[item['product_id']]-=item['quantity']
        seller.payload={**seller.payload,'available_stock':stock}
    result=CONFIRMATION_GRAPH.invoke({'db':db,'session':row,'order':None})
    db.commit()
    return order_dict(result['order'])


def transition(db,oid: str, action: str, confirmed=False):
    order=load_order(db,oid,lock=True); data=copy.deepcopy(order.payload)
    if action=='packed':
        if data['packed']: return order_dict(order)
        if data['payment_state']!='DELIVERY_CONFIRMATION_PENDING': raise HTTPException(409,'Order cannot be packed in its current state.')
        data['packed']=True; data['timeline'].append(stamp('PACKED','Merchant marked the demo order packed.'))
    elif action=='delivery-confirm':
        if data['payment_state'] not in {'DELIVERY_CONFIRMATION_PENDING','SETTLEMENT_ELIGIBLE','RELEASED_SIMULATED'}:
            raise HTTPException(409,'Only a pending delivery can be confirmed. A voided simulation cannot be resumed.')
        if data['delivery_confirmed']: return order_dict(order)
        if not data['packed']: raise HTTPException(409,'Mark the order packed before confirming delivery.')
        if not confirmed: raise HTTPException(403,'Explicit human delivery confirmation is required.')
        validated_action(db,order,'settlement')
        data['delivery_confirmed']=True; data['payment_state']='SETTLEMENT_ELIGIBLE'
        data['timeline'].append(stamp('SETTLEMENT_ELIGIBLE','Human confirmed delivery. Advisory image inspection did not authorize settlement.'))
    elif action=='release':
        if data['payment_state']=='RELEASED_SIMULATED': return order_dict(order)
        if data['payment_state']!='SETTLEMENT_ELIGIBLE' or not data['delivery_confirmed']:
            raise HTTPException(409,'Human-confirmed delivery is required before simulated release.')
        validated_action(db,order,'settlement')
        data['payment_state']='RELEASED_SIMULATED';order.status='completed'
        data['timeline'].append(stamp('RELEASED_SIMULATED','Local simulator recorded a release. No Paytm transaction or real settlement occurred.'))
    elif action=='void':
        if data['payment_state']=='VOIDED_SIMULATED': return order_dict(order)
        if data['payment_state']=='RELEASED_SIMULATED': raise HTTPException(409,'A completed simulation cannot be voided.')
        data['payment_state']='VOIDED_SIMULATED';order.status='voided'
        data['timeline'].append(stamp('VOIDED_SIMULATED','Local simulated payment voided.'))
        for item in data['items']:
            sid=item['seller_id'];seller=db.scalar(select(Seller).where(Seller.id==sid).with_for_update())
            stock=copy.deepcopy(seller_stock(db,sid));stock[item['product_id']]+=item['quantity'];seller.payload={**seller.payload,'available_stock':stock}
    else: raise HTTPException(422,'Unknown payment transition.')
    order.payload=data
    payment=db.get(PaymentSimulation,f'payment-{oid}')
    if payment:
        payment.status=data['payment_state'];payment.payload={**payment.payload,'state':data['payment_state'],'timeline':data['timeline']}
    emit(db,'payment.updated',f"Demo order {action}",f"Simulated payment state: {data['payment_state']}.",agent='payment',data={'order_id':oid,'state':data['payment_state']})
    db.commit()
    return order_dict(order)
