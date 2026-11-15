"""Reviewable sales, FEFO stock consumption, and supplier receipts.

All retail money records remain synthetic. Legacy aggregate transactions are
never guessed into product lines. Integer quantities represent labelled units.
"""
from collections import defaultdict
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
import csv,io,hashlib
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field,model_validator
from typing import Literal
from sqlalchemy import select,func,update
from app.models import Product,Inventory,CustomerToken,Transaction
from app.models.retail import StockBatch,RetailSale,RetailSaleLine,StockMovement,SupplierReorder
from app.core.clock import business_today,business_day_start
from app.services.campaigns import money
from app.services.events import emit

class SaleItem(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    product_id:str=Field(min_length=1,max_length=100)
    quantity:int=Field(ge=1,le=100000)
    expected_unit_price:float|None=Field(default=None,gt=0,le=1000000)

class SaleInput(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    items:list[SaleItem]=Field(min_length=1,max_length=100)
    customer_token:str|None=Field(default=None,max_length=100)
    payment_method:Literal['cash','upi','credit']='cash'
    amount_paid:float|None=Field(default=None,ge=0,le=100000000)
    sold_at:datetime|None=None
    source:str=Field(default='quick-sale',max_length=50)
    @model_validator(mode='after')
    def unique_products(self):
        if len({x.product_id for x in self.items})!=len(self.items):raise ValueError('Combine duplicate products into one line')
        return self

class BatchInput(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    product_id:str=Field(min_length=1,max_length=100)
    quantity:int=Field(ge=1,le=10000000)
    batch_number:str=Field(min_length=1,max_length=100)
    expires_on:date|None=None
    cost_price:float|None=Field(default=None,ge=0,le=1000000)

class AdjustmentInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    product_id:str=Field(min_length=1,max_length=100)
    quantity_delta:int=Field(ge=-10000000,le=10000000)
    reason:str=Field(min_length=3,max_length=200)

class ReorderInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    supplier:str=Field(min_length=1,max_length=120)
    items:list[SaleItem]=Field(min_length=1,max_length=100)


def require_product(db,id,lock=False):
    q=select(Product).where(Product.id==id,Product.merchant_id=='sharma-kirana')
    row=db.scalar(q.with_for_update() if lock else q)
    if not row:raise HTTPException(404,'Product not found')
    return row


def ensure_opening_batch(db,p):
    if not db.scalar(select(StockBatch.id).where(StockBatch.product_id==p.id).limit(1)) and p.available_stock>0:
        db.add(StockBatch(product_id=p.id,batch_number='Opening balance',quantity_remaining=p.available_stock,cost_price=p.purchase_price))
        db.flush()


def batch_dict(db,b):
    p=db.get(Product,b.product_id);days=(b.expires_on-business_today()).days if b.expires_on else None
    return {'id':b.id,'product_id':b.product_id,'product_name':p.name if p else 'Archived product','batch_number':b.batch_number,'quantity_remaining':b.quantity_remaining,'cost_price':money(b.cost_price),'expires_on':b.expires_on.isoformat() if b.expires_on else None,'received_at':b.received_at.isoformat(),'days_to_expiry':days,'expired':days is not None and days<0}


def batches(db):
    rows=db.scalars(select(StockBatch).order_by(StockBatch.expires_on.asc().nulls_last(),StockBatch.received_at)).all()
    return {'items':[batch_dict(db,b) for b in rows]}


def products(db):
    today=business_today();result=[]
    all_batches=defaultdict(list)
    for b in db.scalars(select(StockBatch)):all_batches[b.product_id].append(b)
    for p in db.scalars(select(Product).where(Product.merchant_id=='sharma-kirana').order_by(Product.name)):
        bs=all_batches[p.id];expired=sum(b.quantity_remaining for b in bs if b.expires_on and b.expires_on<today)
        expiring=sum(b.quantity_remaining for b in bs if b.expires_on and today<=b.expires_on<=today+timedelta(days=7))
        sellable=max(0,p.available_stock-expired)
        upcoming=[b.expires_on for b in bs if b.quantity_remaining>0 and b.expires_on and b.expires_on>=today]
        result.append({k:getattr(p,k) for k in ('id','name','category','unit','selling_price','purchase_price','minimum_selling_price','available_stock','supplier','sku','barcode','variant','reorder_point')}|{'sellable_stock':sellable,'low_stock':sellable<=p.reorder_point,'expired_quantity':expired,'expiring_quantity':expiring,'next_expiry':min(upcoming).isoformat() if upcoming else None})
    return {'items':result,'quantity_policy':'Whole labelled units; quantities must be positive integers.'}


def add_batch(db,data,reason='Stock received'):
    data=BatchInput.model_validate(data)
    p=require_product(db,data.product_id,lock=True);ensure_opening_batch(db,p)
    if data.expires_on and data.expires_on<business_today():raise HTTPException(422,'Cannot receive an already expired batch')
    b=StockBatch(product_id=p.id,batch_number=data.batch_number,quantity_remaining=data.quantity,cost_price=p.purchase_price if data.cost_price is None else data.cost_price,expires_on=data.expires_on)
    db.add(b);db.flush()
    p.available_stock+=data.quantity
    inv=db.scalar(select(Inventory).where(Inventory.product_id==p.id))
    if not inv:db.add(Inventory(product_id=p.id,quantity=p.available_stock))
    else:inv.quantity=p.available_stock
    db.add(StockMovement(product_id=p.id,batch_id=b.id,quantity_delta=data.quantity,reason=reason));db.flush()
    emit(db,'inventory.received','Stock batch received',f'{p.name}: {data.quantity} {p.unit}; batch {b.batch_number}.',agent='merchant',data={'product_id':p.id,'batch_id':b.id})
    return batch_dict(db,b)


def consume(db,p,quantity,*,sale_id=None,reason='Sale',exclude_expired=True):
    """Product lock plus guarded updates prevents concurrent overselling."""
    ensure_opening_batch(db,p)
    q=select(StockBatch).where(StockBatch.product_id==p.id,StockBatch.quantity_remaining>0)
    if exclude_expired:q=q.where((StockBatch.expires_on.is_(None))|(StockBatch.expires_on>=business_today()))
    rows=db.scalars(q.order_by(StockBatch.expires_on.asc().nulls_last(),StockBatch.received_at,StockBatch.id).with_for_update()).all()
    if sum(b.quantity_remaining for b in rows)<quantity:raise HTTPException(409,f'Insufficient sellable stock for {p.name}; expired batches cannot be sold')
    remaining=quantity;cost=Decimal('0')
    for b in rows:
        take=min(remaining,b.quantity_remaining)
        if take<=0:break
        claimed=db.execute(update(StockBatch).where(StockBatch.id==b.id,StockBatch.quantity_remaining>=take).values(quantity_remaining=StockBatch.quantity_remaining-take))
        if claimed.rowcount!=1:raise HTTPException(409,'Stock changed during sale. Review the cart again.')
        db.add(StockMovement(product_id=p.id,batch_id=b.id,sale_id=sale_id,quantity_delta=-take,reason=reason))
        cost+=Decimal(str(b.cost_price))*take;remaining-=take
    claimed=db.execute(update(Product).where(Product.id==p.id,Product.available_stock>=quantity).values(available_stock=Product.available_stock-quantity))
    if claimed.rowcount!=1:raise HTTPException(409,'Stock balance changed. Review the cart again.')
    db.refresh(p)
    inv=db.scalar(select(Inventory).where(Inventory.product_id==p.id))
    if not inv:db.add(Inventory(product_id=p.id,quantity=p.available_stock))
    else:inv.quantity=p.available_stock
    return money(cost)


def adjust_stock(db,data):
    data=AdjustmentInput.model_validate(data);p=require_product(db,data.product_id,lock=True)
    if data.quantity_delta==0:raise HTTPException(422,'Stock adjustment must change the quantity')
    if data.quantity_delta>0:return add_batch(db,{'product_id':p.id,'quantity':data.quantity_delta,'batch_number':'Adjustment '+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')},reason=data.reason)
    # Write-offs remove expired units first. Sales always use FEFO sellable units.
    consume(db,p,-data.quantity_delta,reason=data.reason,exclude_expired=False);db.flush()
    emit(db,'inventory.adjusted','Stock adjustment recorded',data.reason,agent='merchant',data={'product_id':p.id,'quantity_delta':data.quantity_delta})
    return {'product_id':p.id,'available_stock':p.available_stock,'reason':data.reason}


def create_sale(db,data):
    data=SaleInput.model_validate(data)
    sold_at=data.sold_at or datetime.now(timezone.utc)
    sold_at=sold_at.replace(tzinfo=timezone.utc) if sold_at.tzinfo is None else sold_at
    if sold_at>datetime.now(timezone.utc)+timedelta(minutes=5):raise HTTPException(422,'Sale time cannot be in the future')
    token=data.customer_token or 'WALK-IN'
    if token=='WALK-IN' and not db.get(CustomerToken,token):
        db.add(CustomerToken(customer_token=token,merchant_id='sharma-kirana'));db.flush()
    if not db.get(CustomerToken,token):raise HTTPException(422,'Choose an existing customer token')
    catalog={}
    for item in sorted(data.items,key=lambda item:item.product_id):
        p=require_product(db,item.product_id,lock=True)
        if item.expected_unit_price is not None and money(item.expected_unit_price)!=money(p.selling_price):raise HTTPException(409,f'{p.name} price changed; review the cart again')
        catalog[p.id]=p
    total=money(sum(Decimal(str(catalog[x.product_id].selling_price))*x.quantity for x in data.items))
    paid=money((0 if data.payment_method=='credit' else total) if data.amount_paid is None else data.amount_paid)
    if paid>total:raise HTTPException(422,'Amount paid cannot exceed the sale total')
    if data.payment_method!='credit' and paid!=total:raise HTTPException(422,'Partial payments must use the credit payment method')
    if data.payment_method=='credit' and token=='WALK-IN':raise HTTPException(422,'Select a customer token before recording credit')
    transaction=Transaction(merchant_id='sharma-kirana',customer_token=token,amount=total,gross_profit=0,category='Grocery',simulated=True,created_at=sold_at)
    db.add(transaction);db.flush()
    sale=RetailSale(customer_token=token,transaction_id=transaction.id,total_amount=total,gross_profit=0,payment_method=data.payment_method,amount_paid=paid,source=data.source,created_at=sold_at)
    db.add(sale);db.flush();profit=Decimal('0')
    for item in data.items:
        p=catalog[item.product_id];cost=consume(db,p,item.quantity,sale_id=sale.id)
        line_total=money(Decimal(str(p.selling_price))*item.quantity);line_profit=money(Decimal(str(line_total))-Decimal(str(cost)))
        db.add(RetailSaleLine(sale_id=sale.id,product_id=p.id,product_name=p.name,variant=p.variant,quantity=item.quantity,unit_price=p.selling_price,unit_cost=money(Decimal(str(cost))/item.quantity),line_total=line_total,line_profit=line_profit))
        profit+=Decimal(str(line_profit))
    sale.gross_profit=transaction.gross_profit=money(profit);db.flush()
    emit(db,'retail.sale','Sale recorded',f'{len(data.items)} products; ₹{total:g}; payment {data.payment_method}. Synthetic ledger entry.',agent='merchant',data={'sale_id':sale.id,'transaction_id':transaction.id,'source':sale.source,'simulated':True})
    return sale_dict(db,sale)


def sale_dict(db,sale):
    lines=db.scalars(select(RetailSaleLine).where(RetailSaleLine.sale_id==sale.id).order_by(RetailSaleLine.product_name)).all()
    return {k:getattr(sale,k) for k in ('id','customer_token','transaction_id','total_amount','gross_profit','payment_method','amount_paid','source')}|{'outstanding':money(sale.total_amount-sale.amount_paid),'created_at':sale.created_at.isoformat(),'simulated':True,'items':[{k:getattr(x,k) for k in ('id','product_id','product_name','variant','quantity','unit_price','unit_cost','line_total','line_profit')} for x in lines]}


def sales(db,limit=100):
    rows=db.scalars(select(RetailSale).order_by(RetailSale.created_at.desc()).limit(limit)).all()
    return {'items':[sale_dict(db,s) for s in rows],'total':db.scalar(select(func.count(RetailSale.id))),'data_source':'Product-level synthetic sales. Older aggregate transactions do not contain product attribution.'}


def create_reorder(db,data):
    data=ReorderInput.model_validate(data)
    if len({x.product_id for x in data.items})!=len(data.items):raise HTTPException(422,'Combine duplicate products')
    items=[]
    for item in data.items:
        p=require_product(db,item.product_id)
        if p.supplier!=data.supplier:raise HTTPException(422,'All reordered products must belong to the selected supplier')
        items.append({'product_id':p.id,'product_name':p.name,'quantity':item.quantity,'unit_cost':p.purchase_price})
    row=SupplierReorder(supplier=data.supplier,items=items,estimated_cost=money(sum(x['quantity']*x['unit_cost'] for x in items)))
    db.add(row);db.flush();emit(db,'inventory.reorder','Supplier reorder drafted','Review with your supplier; no external order has been sent.',agent='merchant',data={'reorder_id':row.id})
    return reorder_dict(row)


def reorder_dict(row):
    return {'id':row.id,'supplier':row.supplier,'status':row.status,'items':row.items,'estimated_cost':row.estimated_cost,'created_at':row.created_at.isoformat(),'received_at':row.received_at.isoformat() if row.received_at else None,'external_order_sent':False}


def reorders(db):return {'items':[reorder_dict(r) for r in db.scalars(select(SupplierReorder).order_by(SupplierReorder.created_at.desc()))]}


def receive_reorder(db,id,confirmed=True):
    if not confirmed:raise HTTPException(422,'Confirm physical receipt before increasing stock')
    row=db.scalar(select(SupplierReorder).where(SupplierReorder.id==id).with_for_update())
    if not row:raise HTTPException(404,'Reorder not found')
    if row.status=='received':return reorder_dict(row)
    for item in sorted(row.items,key=lambda item:item['product_id']):
        add_batch(db,{'product_id':item['product_id'],'quantity':item['quantity'],'batch_number':'Reorder '+row.id[:8],'cost_price':item['unit_cost']},reason='Supplier reorder received')
    row.status='received';row.received_at=datetime.now(timezone.utc);db.flush()
    return reorder_dict(row)


def import_sales(db,raw):
    try:rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    except UnicodeDecodeError:raise HTTPException(422,'CSV must use UTF-8 encoding')
    if not rows or len(rows)>2000:raise HTTPException(422,'CSV must contain 1–2000 product lines')
    by_sku={p.sku:p.id for p in db.scalars(select(Product)) if p.sku}
    grouped={}
    for index,row in enumerate(rows,2):
        key=(row.get('invoice_id') or str(index)).strip()
        pid=(row.get('product_id') or by_sku.get(row.get('sku','')) or '').strip()
        try:
            quantity=int(row.get('quantity',''))
            item=SaleItem(product_id=pid,quantity=quantity)
            sold_at=datetime.fromisoformat(row['sold_at'].replace('Z','+00:00')) if row.get('sold_at') else None
            data={'customer_token':row.get('customer_token') or None,'payment_method':row.get('payment_method') or 'cash','sold_at':sold_at,'source':'csv-import'}
            if key not in grouped:grouped[key]={**data,'items':[]}
            elif any(grouped[key][k]!=v for k,v in data.items()):raise ValueError('Invoice fields must match on every line')
            grouped[key]['items'].append(item.model_dump())
        except (ValueError,TypeError) as error:raise HTTPException(422,f'CSV row {index}: {str(error)[:200]}')
    validated=[SaleInput.model_validate(group) for group in grouped.values()]
    # Every row is validated before any writes; the endpoint rolls back the
    # entire transaction if any later product/stock check fails.
    imported=[create_sale(db,item.model_dump()) for item in validated]
    return {'imported_sales':len(imported),'imported_lines':len(rows),'items':imported,'simulated':True}


def seed_retail_demo(db):
    """Create explicitly labelled product records, never infer old purchases."""
    if db.scalar(select(RetailSale.id).where(RetailSale.source=='synthetic-retail-seed').limit(1)):
        return {'status':'existing'}
    catalog=list(db.scalars(select(Product).where(Product.merchant_id=='sharma-kirana').order_by(Product.id)))
    if not catalog:return {'status':'empty'}
    tokens=list(db.scalars(select(CustomerToken.customer_token).where(CustomerToken.customer_token.like('PK-00%')).order_by(CustomerToken.customer_token).limit(15)))
    if not tokens:return {'status':'empty'}
    today=business_today()
    for index,p in enumerate(catalog):
        p.sku=p.sku or p.id
        base=f'8901000{index+1:05d}'
        check=(10-sum(int(d)*(1 if i%2==0 else 3) for i,d in enumerate(base))%10)%10
        p.barcode=p.barcode or base+str(check);p.variant=p.variant or p.unit
        ensure_opening_batch(db,p)
        # Split the existing opening stock, preserving the total balance.
        opening=db.scalar(select(StockBatch).where(StockBatch.product_id==p.id,StockBatch.quantity_remaining>0).order_by(StockBatch.received_at))
        if opening and index in (5,7,9) and opening.quantity_remaining>=6:
            opening.quantity_remaining-=6
            db.add(StockBatch(product_id=p.id,batch_number='Synthetic expiry example',quantity_remaining=6,cost_price=p.purchase_price,expires_on=today+timedelta(days={5:3,7:5,9:2}[index])))
        if index==9:p.reorder_point=max(p.reorder_point,p.available_stock-5)
    db.flush()
    count=0
    # 28 observed business dates support a transparent weekly demand baseline.
    # Historical examples consume the opening balance but do not touch absent
    # customers; only active sample customers are used.
    for day in range(27,-1,-1):
        choices=[catalog[0],catalog[6],catalog[8]] if day%2==0 else [catalog[2],catalog[4],catalog[9]]
        items=[]
        for p in choices:
            q=(2 if p.id in (catalog[0].id,catalog[6].id) else 1)
            if p.available_stock>=q:items.append({'product_id':p.id,'quantity':q})
        if not items:continue
        sold_at=business_day_start()-timedelta(days=day)+timedelta(hours=5+day%8)
        create_sale(db,{'items':items,'customer_token':tokens[day%len(tokens)],'payment_method':'credit' if day==1 else 'cash','amount_paid':0 if day==1 else None,'sold_at':sold_at,'source':'synthetic-retail-seed'})
        count+=1
    emit(db,'retail.seeded','Product-level demo ledger prepared',f'{count} explicitly synthetic receipts with actual line items. Legacy purchases were not attributed to products.',agent='system',data={'sales':count,'simulated':True})
    db.flush()
    return {'status':'seeded','sales':count}
