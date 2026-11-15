"""Merchant-managed khata, expenses and reviewable digital receipt sharing."""
import html,re
from datetime import date,datetime,timezone
from decimal import Decimal
from typing import Literal
from urllib.parse import urlencode
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select,func
from app.database.session import get_db
from app.api.core import merchant_role,mutate
from app.models import CustomerToken,Merchant
from app.models.retail import RetailSale
from app.models.finance import Expense,KhataPayment
from app.core.clock import business_today
from app.core.config import settings
from app.services.campaigns import money
from app.services.retail import sale_dict
from app.services.events import emit

router=APIRouter(prefix='/business',dependencies=[Depends(merchant_role)])

class ExpenseInput(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    category:str=Field(min_length=1,max_length=80)
    amount:Decimal=Field(gt=0,le=10000000,max_digits=12,decimal_places=2)
    description:str=Field(default='',max_length=500)
    incurred_on:date

class Repayment(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    customer_token:str=Field(min_length=1,max_length=100)
    amount:Decimal=Field(gt=0,le=10000000,max_digits=12,decimal_places=2)
    payment_method:Literal['cash','upi']='cash'
    note:str=Field(default='',max_length=500)

class ShareDraft(BaseModel):
    model_config=ConfigDict(extra='forbid')
    purpose:Literal['invoice','reminder','daily_summary']
    sale_id:str|None=None
    customer_token:str|None=None
    phone:str|None=Field(default=None,max_length=20)


def customer_name(token):return settings.telephony_demo_customer_name if token==settings.telephony_demo_customer_token else token

def paid_against(db,sale_id):return money(db.scalar(select(func.coalesce(func.sum(KhataPayment.amount),0)).where(KhataPayment.sale_id==sale_id)) or 0)

def credit_accounts(db):
    rows=db.scalars(select(RetailSale).where(RetailSale.payment_method=='credit').order_by(RetailSale.created_at)).all()
    payments={}
    for sid,total in db.execute(select(KhataPayment.sale_id,func.sum(KhataPayment.amount)).group_by(KhataPayment.sale_id)):payments[sid]=float(total)
    customers={}
    for sale in rows:
        item=customers.setdefault(sale.customer_token,{'customer_token':sale.customer_token,'customer_name':customer_name(sale.customer_token),'total_credit':0,'total_repaid':0,'outstanding':0,'sales':[]})
        credit=money(sale.total_amount-sale.amount_paid);repaid=money(payments.get(sale.id,0));balance=money(max(0,credit-repaid))
        item['total_credit']=money(item['total_credit']+credit);item['total_repaid']=money(item['total_repaid']+repaid);item['outstanding']=money(item['outstanding']+balance)
        item['sales'].append({'id':sale.id,'total_amount':sale.total_amount,'initial_paid':sale.amount_paid,'repaid':repaid,'outstanding':balance,'created_at':sale.created_at.isoformat()})
    return {'items':list(customers.values()),'total_outstanding':money(sum(i['outstanding'] for i in customers.values())),'simulated':True}

@router.get('/khata')
def khata(db=Depends(get_db)):return credit_accounts(db)

@router.post('/khata/payments')
def repayment(body:Repayment,request:Request,db=Depends(get_db)):
    def run():
        # A customer lock serializes repayment allocation across all their invoices.
        customer=db.scalar(select(CustomerToken).where(CustomerToken.customer_token==body.customer_token).with_for_update())
        if not customer:raise HTTPException(404,'Customer not found')
        sales=db.scalars(select(RetailSale).where(RetailSale.customer_token==body.customer_token,RetailSale.payment_method=='credit').order_by(RetailSale.created_at,RetailSale.id).with_for_update()).all()
        balances=[(s,money(s.total_amount-s.amount_paid-paid_against(db,s.id))) for s in sales]
        available=money(sum(max(0,b) for _,b in balances))
        if body.amount>Decimal(str(available)):raise HTTPException(409,f'Repayment exceeds the outstanding balance of ₹{available:.2f}')
        remaining=body.amount;ids=[]
        for sale,balance in balances:
            take=min(remaining,Decimal(str(max(0,balance))))
            if take<=0:continue
            row=KhataPayment(customer_token=body.customer_token,sale_id=sale.id,amount=float(take),payment_method=body.payment_method,note=body.note)
            db.add(row);db.flush();ids.append(row.id);remaining-=take
        emit(db,'khata.repaid','Credit repayment recorded',f'₹{body.amount} allocated to oldest unpaid invoices; no real transfer.',agent='payment',data={'customer_token':body.customer_token,'payment_ids':ids})
        return {'id':ids[0],'payment_ids':ids,'amount':float(body.amount),'outstanding':money(available-float(body.amount)),'simulated':True}
    return mutate(db,request,body.model_dump(mode='json'),run)

@router.get('/expenses')
def expenses(db=Depends(get_db)):
    rows=db.scalars(select(Expense).order_by(Expense.expense_date.desc(),Expense.created_at.desc()).limit(500)).all()
    return {'items':[{'id':e.id,'category':e.category,'amount':e.amount,'description':e.description,'incurred_on':e.expense_date.isoformat()} for e in rows]}

@router.post('/expenses')
def expense_create(body:ExpenseInput,request:Request,db=Depends(get_db)):
    def run():
        if body.incurred_on>business_today():raise HTTPException(422,'Expense date cannot be in the future')
        row=Expense(merchant_id='sharma-kirana',category=body.category,amount=float(body.amount),description=body.description,expense_date=body.incurred_on)
        db.add(row);db.flush();emit(db,'expense.recorded','Operating expense recorded',body.category,agent='merchant',data={'expense_id':row.id})
        return {'id':row.id,**body.model_dump(mode='json'),'amount':float(body.amount),'simulated':True}
    return mutate(db,request,body.model_dump(mode='json'),run)


def invoice_data(db,id):
    sale=db.get(RetailSale,id)
    if not sale:raise HTTPException(404,'Sale not found')
    result=sale_dict(db,sale);repaid=paid_against(db,sale.id)
    merchant=db.get(Merchant,'sharma-kirana')
    return {**result,'merchant_name':merchant.name,'merchant_location':merchant.location,'customer_name':customer_name(sale.customer_token),'repaid':repaid,'outstanding':money(max(0,sale.total_amount-sale.amount_paid-repaid)),'simulated':True,'invoice_number':'PK-'+sale.id[:8].upper()}

@router.get('/sales/{id}/invoice')
def invoice(id:str,db=Depends(get_db)):return invoice_data(db,id)

@router.get('/sales/{id}/invoice.html',response_class=HTMLResponse)
def printable_invoice(id:str,db=Depends(get_db)):
    data=invoice_data(db,id);esc=lambda s:html.escape(str(s))
    lines=''.join('<tr><td>'+esc(i['product_name'])+' · '+esc(i['variant'])+'</td><td>'+esc(i['quantity'])+'</td><td>₹'+format(i['unit_price'],'.2f')+'</td><td>₹'+format(i['line_total'],'.2f')+'</td></tr>' for i in data['items'])
    return HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8"><title>'+esc(data['invoice_number'])+'</title><style>body{font:16px system-ui;max-width:760px;margin:48px auto;color:#18324c;padding:24px}table{width:100%;border-collapse:collapse}td,th{padding:14px;text-align:left;border-bottom:1px solid #ddd}.note{background:#edf7ff;padding:16px}@media print{button{display:none}}</style><h1>'+esc(data['merchant_name'])+'</h1><p>'+esc(data['merchant_location'])+'</p><h2>Invoice '+esc(data['invoice_number'])+'</h2><p>Customer: '+esc(data['customer_name'])+' · '+esc(data['created_at'])+'</p><table><tr><th>Product / variant</th><th>Qty</th><th>Price</th><th>Total</th></tr>'+lines+'</table><h2>Total ₹'+format(data['total_amount'],'.2f')+'</h2><p>Initially paid: ₹'+format(data['amount_paid'],'.2f')+' · Repaid: ₹'+format(data['repaid'],'.2f')+' · Outstanding: ₹'+format(data['outstanding'],'.2f')+'</p><p class="note">Synthetic merchant receipt. No real payment transfer was initiated.</p><button onclick="window.print()">Print / save PDF</button></html>',headers={'Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'"})

@router.post('/whatsapp/draft')
def whatsapp_draft(body:ShareDraft,db=Depends(get_db)):
    token=body.customer_token
    if body.purpose=='invoice':
        if not body.sale_id:raise HTTPException(422,'Choose a sale invoice')
        data=invoice_data(db,body.sale_id);token=data['customer_token']
        items='; '.join(f"{i['product_name']} × {i['quantity']} = Rs {i['line_total']:.2f}" for i in data['items'])
        message=f"{data['merchant_name']} — receipt {data['invoice_number']}\n{items}\nTotal Rs {data['total_amount']:.2f}; outstanding Rs {data['outstanding']:.2f}.\nDemonstration receipt; no real payment transferred."
    elif body.purpose=='reminder':
        account=next((c for c in credit_accounts(db)['items'] if c['customer_token']==token),None)
        if not account or account['outstanding']<=0:raise HTTPException(409,'No outstanding credit for this customer')
        message=f"Hello {account['customer_name']}, your recorded balance at Sharma Kirana Store is Rs {account['outstanding']:.2f}. Please visit the store to settle it. Demonstration reminder."
    else:
        from app.services.business_analytics import business_summary
        message='Sharma Kirana Store · Daily business summary\n'+business_summary(db,1)['summary_text']
    phone=body.phone or (settings.telephony_demo_phone if token==settings.telephony_demo_customer_token else '')
    if phone and not re.fullmatch(r'\+[1-9]\d{7,14}',phone):raise HTTPException(422,'Enter a phone number with country code, such as +15005550006')
    url='https://wa.me/'+phone.lstrip('+')+'?'+urlencode({'text':message})
    return {'message':message,'url':url,'delivery_status':'draft','notice':'Open WhatsApp to choose the recipient, review and send. Nothing has been sent automatically.'}
