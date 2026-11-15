from __future__ import annotations

import asyncio
import copy
import itertools
import json
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import TypedDict
from uuid import uuid4

from fastapi import HTTPException
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select

from app.database.session import SessionLocal
from app.core.clock import business_today
from app.models import NegotiationSession, SellerQuote, AgentRun, Seller
from app.security.seller_policies import SELLER_POLICIES, seller_floor
from app.security.policy import validate_policy, sign_mandate
from app.services.events import emit
from app.integrations.sarvam import SarvamProvider

PRODUCTS = {
    'rice': {'name': 'Basmati Rice', 'unit': 'kg', 'price': 85},
    'atta': {'name': 'Whole Wheat Atta', 'unit': 'kg', 'price': 46},
    'oil': {'name': 'Sunflower Oil', 'unit': 'l', 'price': 145},
    'snacks': {'name': 'Assorted Snacks', 'unit': 'pack', 'price': 38},
    'tea': {'name': 'Premium Tea', 'unit': 'kg', 'price': 360},
}
SELLERS = [
    {'id': 'seller-a', 'name': 'Sharma Wholesale Mart', 'strategy': 'Relationship-led; steady concessions for a recurring order.', 'delivery_cost': 450, 'lead_days': 1},
    {'id': 'seller-b', 'name': 'Pune Grocery Distributors', 'strategy': 'Volume-led; stronger concessions on oil and tea.', 'delivery_cost': 300, 'lead_days': 2},
    {'id': 'seller-c', 'name': 'Sai General Suppliers', 'strategy': 'Fast local delivery; strongest value on snacks.', 'delivery_cost': 550, 'lead_days': 1},
]
DEFAULT_ITEMS = [{'product_id': key, 'name': PRODUCTS[key]['name'], 'quantity': qty, 'unit': PRODUCTS[key]['unit']} for key, qty in [('rice',100),('atta',100),('oil',80),('snacks',200),('tea',20)]]
TASKS: dict[str, asyncio.Task] = {}


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


class BasketItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_id: str
    name: str | None = None
    quantity: int = Field(gt=0, le=10000)
    unit: str | None = None


class BuyerRequirement(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requirement: str = Field(default='Grocery items and snacks for an office event. Total budget ₹40,000.', min_length=4, max_length=2000)
    budget: float = Field(default=40000, gt=0, le=1000000, allow_inf_nan=False)
    delivery_date: date | None = None
    items: list[BasketItem] | None = Field(default=None, max_length=20)


class NegotiationState(TypedDict, total=False):
    session_id: str
    requirement: str
    budget: float
    delivery_date: str
    items: list[dict]
    round_number: int
    quotes: list[dict]
    rounds: list[dict]
    best_deal: dict | None
    provider: str
    provider_error: str | None
    active_node: str
    started_at: str
    elapsed_ms: int
    status: str
    optimization_explanation: str
    explanation_provider: str


def serialize(row: NegotiationSession) -> dict:
    return {'id': row.id, **{k:v for k,v in row.payload.items() if not k.startswith('_')}, 'status': row.status, 'created_at': row.created_at.isoformat()}


def create_session(db, data: BuyerRequirement) -> dict:
    items = [v.model_dump() for v in data.items] if data.items else copy.deepcopy(DEFAULT_ITEMS)
    if not items:
        raise HTTPException(422, 'A negotiation requires at least one product.')
    if len({v['product_id'] for v in items}) != len(items):
        raise HTTPException(422, 'Each product may appear only once in the basket.')
    for item in items:
        if item['product_id'] not in PRODUCTS:
            raise HTTPException(422, f"Unsupported product: {item['product_id']}. Review extracted lines and choose catalogue products.")
        item['name'] = PRODUCTS[item['product_id']]['name']
        item['unit'] = PRODUCTS[item['product_id']]['unit']
    today=business_today()
    delivery = data.delivery_date or (today + timedelta(days=(4-today.weekday()) % 7 or 7))
    if delivery < today:
        raise HTTPException(422, 'Delivery date must be today or later.')
    payload: NegotiationState = {'requirement': data.requirement, 'budget': float(money(data.budget)),
        'delivery_date': delivery.isoformat(), 'items': items, 'round_number': 0, 'quotes': [], 'rounds': [],
        'best_deal': None, 'provider': 'demo', 'active_node': 'idle', 'elapsed_ms': 0}
    row = NegotiationSession(id=str(uuid4()), status='created', payload=payload)
    db.add(row)
    for seller in SELLERS:
        if not db.get(Seller, seller['id']):
            db.add(Seller(id=seller['id'], status='ready', payload={**seller, 'catalogue': PRODUCTS, 'available_stock': SELLER_POLICIES[seller['id']]['stock']}))
    emit(db, 'negotiation.created', 'Buyer request created', f'{len(items)} product lines; budget ₹{data.budget:,.0f}.', agent='buyer', data={'session_id': row.id})
    db.flush()
    return serialize(row)


def load_session(db, sid: str) -> NegotiationSession:
    row = db.get(NegotiationSession, sid)
    if not row:
        raise HTTPException(404, 'Negotiation session not found.')
    return row


def seller_stock(db, sid: str) -> dict:
    seller = db.get(Seller, sid)
    return seller.payload.get('available_stock', SELLER_POLICIES[sid]['stock']) if seller else SELLER_POLICIES[sid]['stock']


async def checkpoint(state: NegotiationState, node: str, title: str, *, agent='supervisor', detail='', status='running'):
    # Every stage consults durable control state. Cancel/pause survives API requests.
    while True:
        with SessionLocal() as db:
            row = db.get(NegotiationSession, state['session_id'])
            if row is None or row.status == 'cancelled':
                raise asyncio.CancelledError
            if row.status != 'paused':
                state['active_node'] = node
                state['elapsed_ms'] = int((datetime.now(timezone.utc)-datetime.fromisoformat(state['started_at'])).total_seconds()*1000)
                row.payload = copy.deepcopy(dict(state))
                row.status = status
                emit(db, f'agent.{node}', title, detail, agent=agent, data={'session_id': row.id, 'round_number': state.get('round_number', 0), 'node': node, 'elapsed_ms': state['elapsed_ms']})
                db.commit()
                break
        await asyncio.sleep(.2)
    await asyncio.sleep(.18)


async def parse_requirement(state: NegotiationState):
    await checkpoint(state, 'parse_requirement', 'Buyer requirement validated', agent='buyer', detail='Structured basket and authorized budget accepted. No financial action authorized.')
    return state


async def normalize_catalogue(state: NegotiationState):
    await checkpoint(state, 'normalize_catalogue', 'Product catalogue normalized', detail=f"{len(state['items'])} product identifiers matched across three catalogues.")
    return state


async def dispatch_request(state: NegotiationState):
    await checkpoint(state, 'dispatch_request', 'Buyer request dispatched', agent='buyer', detail='Three seller agents received the public basket, budget and delivery deadline.')
    return state


async def initialize_sellers(state: NegotiationState):
    await checkpoint(state, 'initialize_sellers', 'Seller strategies initialized', detail='Independent seller contexts; private pricing policies remain server-side.')
    return state


def quote_for(seller: dict, state: NegotiationState, summary: str) -> dict:
    policy = SELLER_POLICIES[seller['id']]
    round_no = state['round_number']
    concessions = {'seller-a':[0,3,6,8], 'seller-b':[0,4,8,11], 'seller-c':[0,2,5,7]}
    concession = Decimal(concessions[seller['id']][round_no-1]) / 100
    products=[]
    for item in state['items']:
        special = Decimal('.98') if seller['id']=='seller-b' and item['product_id'] in ('oil','tea') else Decimal('.97') if seller['id']=='seller-c' and item['product_id']=='snacks' else Decimal('1')
        price = money(Decimal(str(PRODUCTS[item['product_id']]['price'])) * policy['factor'] * (1-concession) * special)
        products.append({**item, 'unit_price': float(price), 'total':float(money(price*item['quantity']))})
    subtotal = sum((money(p['total']) for p in products), Decimal(0))
    return {'id':str(uuid4()),'seller_id':seller['id'],'seller_name':seller['name'], 'products':products,
        'quantities':[p['quantity'] for p in products], 'unit_prices':[p['unit_price'] for p in products],
        'subtotal':float(subtotal),'delivery_cost':seller['delivery_cost'],'discounts':0,
        'discount_percent':float(concession*100),'total_amount':float(money(subtotal+seller['delivery_cost'])),
        'delivery_date':(business_today()+timedelta(days=seller['lead_days'])).isoformat(),
        'validity':(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat(),
        'round_number':round_no,'status':'pending_validation','summary':summary}


async def collect_quotes(state: NegotiationState):
    state['round_number'] = state.get('round_number',0)+1
    round_no=state['round_number']
    await checkpoint(state, 'collect_quotes', f'Negotiation round {round_no} started', detail='Independent seller proposals are evaluated in parallel.')
    async def run_seller(seller):
        seller_started=time.perf_counter()
        default=f"Round {round_no}: {seller['strategy']} Authorized concession { {'seller-a':[0,3,6,8],'seller-b':[0,4,8,11],'seller-c':[0,2,5,7]}[seller['id']][round_no-1]}%."
        # One bounded model call per seller, in round one; all arithmetic is deterministic.
        if round_no == 1:
            provider=await SarvamProvider().chat([
                {'role':'system','content':'You are a merchant seller agent. Give one short, customer-facing negotiation strategy sentence. Do not invent prices, authorizations or confidential thresholds. This is a simulated marketplace.'},
                {'role':'user','content':json.dumps({'seller':seller['name'],'strategy':seller['strategy'],'basket':state['items'],'budget':state['budget'],'deadline':state['delivery_date']})},
            ])
            if not provider['demo']:
                default=provider['text'][:650]
            quote=quote_for(seller,state,default)
            quote['duration_ms']=round((time.perf_counter()-seller_started)*1000)
            return quote,provider
        quote=quote_for(seller,state,default)
        quote['duration_ms']=round((time.perf_counter()-seller_started)*1000)
        return quote,None
    results=await asyncio.gather(*(run_seller(s) for s in SELLERS))
    state['quotes']=[result[0] for result in results]
    providers=[result[1] for result in results if result[1]]
    if providers:
        state['provider']='sarvam' if all(p['provider']=='sarvam' for p in providers) else 'demo'
        state['provider_error']=next((p['error'] for p in providers if p.get('error')),None)
    for quote in state['quotes']:
        with SessionLocal() as db:
            db.add(SellerQuote(id=quote['id'],status='submitted',payload=quote))
            db.add(AgentRun(id=str(uuid4()),status='success',payload={'agent':quote['seller_id'],'task':f'Round {round_no} seller quote','session_id':state['session_id'],
                'node':'collect_quotes','duration_ms':quote['duration_ms'],'tool_calls':1}))
            emit(db,'seller.quote',f"{quote['seller_name']} submitted ₹{quote['total_amount']:,.0f}",quote['summary'],agent=quote['seller_id'],data={'session_id':state['session_id'],'round_number':round_no,'total':quote['total_amount'],'duration_ms':quote['duration_ms']})
            db.commit()
    return state


async def buyer_evaluation(state: NegotiationState):
    eligible=[q for q in state['quotes'] if money(q['total_amount'])<=money(state['budget'])]
    await checkpoint(state,'buyer_evaluation','Buyer compared seller proposals',agent='buyer',detail=f"{len(eligible)} of 3 full-basket quotes are within the authorized budget.")
    return state


async def seller_counteroffers(state: NegotiationState):
    await checkpoint(state,'seller_counteroffers','Seller counteroffer instructions prepared',detail='Concessions are bounded by each seller policy; quantity and delivery constraints remain binding.')
    return state


async def firewall_validation(state: NegotiationState):
    for quote in state['quotes']:
        seller=next(s for s in SELLERS if s['id']==quote['seller_id'])
        policy=SELLER_POLICIES[seller['id']]
        delivery_ok=quote['delivery_date']<=state['delivery_date']
        with SessionLocal() as db:
            current_stock=seller_stock(db,seller['id'])
            quantity_ok=all(p['quantity']<=current_stock[p['product_id']] for p in quote['products'])
            decision=validate_policy(db,{'amount':quote['total_amount'],'budget':state['budget'],
                'seller_id':quote['seller_id'],'round_number':state['round_number'],'operation':'quote',
                'quantity_available':quantity_ok,'delivery_feasible':delivery_ok,
                'discount_percent':quote['discount_percent'],'max_discount_percent':policy['max_discount'],
                'expiry':quote['validity']},floor=float(seller_floor(seller['id'],quote['products'],PRODUCTS)))
            quote['status']='eligible' if decision['status']!='BLOCKED' else 'blocked'
            quote['validation']={'status':decision['status'],'reasons':decision.get('reasons',[])}
            stored=db.get(SellerQuote,quote['id'])
            if stored:
                stored.payload=copy.deepcopy(quote)
                stored.status=quote['status']
            db.commit()
    state['rounds']=[*state.get('rounds',[]),{'round_number':state['round_number'],'quotes':copy.deepcopy(state['quotes']), 'summary':'Deterministic budget, stock, delivery and seller policy checks completed.'}]
    await checkpoint(state,'firewall_validation',f"Round {state['round_number']} firewall checks completed",agent='firewall',detail=f"{sum(q['status']=='eligible' for q in state['quotes'])} eligible full-basket proposals.")
    return state


def optimize_bundle(state: NegotiationState) -> dict | None:
    """Exhaustive bounded integer assignment: 3 sellers ^ at most 8 lines.

    Includes per-seller delivery cost; filters stock, deadline, budget and private
    floors. Exact Decimal money makes the comparison reproducible.
    """
    if len(state['items'])>8:
        eligible=[q for q in state['quotes'] if q['status']=='eligible']
        winner=copy.deepcopy(min(eligible,key=lambda q:money(q['total_amount']))) if eligible else None
        if winner:
            winner['products']=[{**p,'seller_id':winner['seller_id'],'seller_name':winner['seller_name']} for p in winner['products']]
        return winner
    quotes={q['seller_id']:q for q in state['quotes']}
    with SessionLocal() as db:
        stock={s['id']:seller_stock(db,s['id']) for s in SELLERS}
    winner=None
    for allocation in itertools.product(SELLERS, repeat=len(state['items'])):
        groups={}
        feasible=True
        for index,seller in enumerate(allocation):
            item=state['items'][index]
            if item['quantity']>stock[seller['id']][item['product_id']] or quotes[seller['id']]['delivery_date']>state['delivery_date']:
                feasible=False; break
            groups.setdefault(seller['id'],[]).append(copy.deepcopy(quotes[seller['id']]['products'][index]))
        if not feasible: continue
        products=[]; total=Decimal(0); delivery=Decimal(0)
        for sid,lines in groups.items():
            subtotal=sum((money(p['total']) for p in lines),Decimal(0))
            if subtotal<seller_floor(sid,lines,PRODUCTS): feasible=False;break
            products.extend([{**p,'seller_id':sid,'seller_name':quotes[sid]['seller_name']} for p in lines])
            total+=subtotal
            delivery+=money(quotes[sid]['delivery_cost'])
        total+=delivery
        if not feasible or total>money(state['budget']): continue
        if winner is None or total<money(winner['total_amount']):
            winner={'id':str(uuid4()),'seller_id':next(iter(groups)) if len(groups)==1 else 'optimized-bundle',
                'seller_name':quotes[next(iter(groups))]['seller_name'] if len(groups)==1 else f'Optimized bundle · {len(groups)} sellers',
                'products':products,'subtotal':float(total-delivery),'delivery_cost':float(delivery),'discounts':0,
                'total_amount':float(total),'delivery_date':max(quotes[sid]['delivery_date'] for sid in groups),
                'validity':min(quotes[sid]['validity'] for sid in groups),'round_number':state['round_number'],
                'status':'eligible','summary':'Lowest eligible exact product assignment, including delivery, subject to private seller policies.',
                'supplier_count':len(groups),'validation':{'status':'ELIGIBLE_PENDING_APPROVALS','reasons':[]}}
    return winner


async def optimize_final_bundle(state: NegotiationState):
    state['best_deal']=optimize_bundle(state)
    if state['best_deal']:
        # The supervisor explains a completed deterministic result; it cannot
        # alter the selected bundle, arithmetic, eligibility or authorization.
        result=await SarvamProvider().chat([
            {'role':'system','content':'You are the negotiation supervisor of a simulated grocery marketplace. Give a concise two-sentence merchant-facing explanation of the supplied already-validated best bundle. Use supplied amounts only; do not calculate new numbers, claim approval/payment, or mention private prices. Explain budget, delivery and stock eligibility. The deterministic optimizer alone selects the deal.'},
            {'role':'user','content':json.dumps({'authorized_budget':state['budget'],'required_by':state['delivery_date'],
                'selected_bundle':state['best_deal'],'eligible_full_basket_quotes':[{'seller_name':q['seller_name'],'total_amount':q['total_amount'],'delivery_date':q['delivery_date']} for q in state['quotes'] if q['status']=='eligible']})},
        ])
        state['optimization_explanation']=result['text'] if not result['demo'] else state['best_deal']['summary']
        state['explanation_provider']=result['provider']
    await checkpoint(state,'optimize_final_bundle','Best eligible bundle selected' if state['best_deal'] else 'No eligible bundle found',detail='Exact constrained allocation across seller offers; no cheaper ineligible offer is selected.')
    return state


async def merchant_approval(state: NegotiationState):
    status='awaiting_approval' if state['best_deal'] else 'no_deal'
    await checkpoint(state,'merchant_approval','Merchant and buyer approval required' if state['best_deal'] else 'Negotiation ended without an eligible deal',detail='No order or payment is created until both parties explicitly confirm.',status=status)
    if state['best_deal']:
        with SessionLocal() as db:
            row=load_session(db,state['session_id'])
            mandate={'session_id':row.id,'budget':state['budget'],'deal':state['best_deal'],
                     'expiry':state['best_deal']['validity']}
            row.payload={**row.payload,'_mandate':mandate,'_signature':sign_mandate(mandate)}
            db.commit()
    state['status']=status
    return state


def build_graph():
    graph=StateGraph(NegotiationState)
    nodes={'parse_requirement':parse_requirement,'normalize_catalogue':normalize_catalogue,'dispatch_request':dispatch_request,
        'initialize_sellers':initialize_sellers,'collect_quotes':collect_quotes,'buyer_evaluation':buyer_evaluation,
        'seller_counteroffers':seller_counteroffers,'firewall_validation':firewall_validation,
        'optimize_final_bundle':optimize_final_bundle,'merchant_approval':merchant_approval}
    agents={'parse_requirement':'buyer','dispatch_request':'buyer','buyer_evaluation':'buyer','firewall_validation':'firewall'}
    def measured(name,fn):
        async def execute(state):
            started=time.perf_counter()
            result=await fn(state)
            duration=round((time.perf_counter()-started)*1000)
            with SessionLocal() as db:
                if db.get(NegotiationSession,state['session_id']):
                    agent=agents.get(name,'supervisor')
                    db.add(AgentRun(id=str(uuid4()),status='success',payload={'agent':agent,'task':name.replace('_',' '),
                        'session_id':state['session_id'],'node':name,'duration_ms':duration,'tool_calls':1}))
                    emit(db,'agent.completed',name.replace('_',' ').capitalize()+' completed',f'Execution duration {duration} ms.',agent=agent,
                        data={'session_id':state['session_id'],'node':name,'duration_ms':duration,'round_number':state.get('round_number',0)})
                    db.commit()
            return result
        return execute
    for name,fn in nodes.items(): graph.add_node(name,measured(name,fn))
    graph.add_edge(START,'parse_requirement')
    chain=['parse_requirement','normalize_catalogue','dispatch_request','initialize_sellers','collect_quotes','buyer_evaluation','seller_counteroffers','firewall_validation']
    for left,right in zip(chain,chain[1:]): graph.add_edge(left,right)
    graph.add_conditional_edges('firewall_validation',lambda s:'again' if s['round_number']<4 else 'finish',{'again':'collect_quotes','finish':'optimize_final_bundle'})
    graph.add_edge('optimize_final_bundle','merchant_approval'); graph.add_edge('merchant_approval',END)
    return graph.compile()


NEGOTIATION_GRAPH=build_graph()


async def run_session(sid: str):
    try:
        with SessionLocal() as db:
            row=load_session(db,sid)
            state={**row.payload,'session_id':sid,'started_at':row.payload.get('started_at',datetime.now(timezone.utc).isoformat())}
            # Restart an unfinished stage from the last fully validated round.
            # This avoids skipping a round after a process interruption mid-call.
            state['round_number']=len(state.get('rounds',[]))
        # If process restarted after all rounds, don't produce a fifth proposal.
        if state.get('round_number',0)>=4:
            await optimize_final_bundle(state); await merchant_approval(state)
        else:
            await NEGOTIATION_GRAPH.ainvoke(state,config={'recursion_limit':60})
    except asyncio.CancelledError:
        return
    except Exception:
        with SessionLocal() as db:
            row=db.get(NegotiationSession,sid)
            if row:
                row.status='failed'
                row.payload={**row.payload,'error':'Negotiation interrupted. Reset this session and retry.'}
                emit(db,'negotiation.failed','Negotiation interrupted','The session is safely stopped. No order or payment was created.',agent='supervisor')
                db.commit()
        import logging
        logging.getLogger('pehchaan').exception('negotiation_workflow_failed',extra={'session_id':sid})
    finally:
        TASKS.pop(sid,None)


def launch(sid: str):
    if sid not in TASKS:
        TASKS[sid]=asyncio.create_task(run_session(sid))
