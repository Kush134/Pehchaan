import hashlib
from datetime import datetime,timezone
from typing import Literal
from fastapi import APIRouter,Depends,Request,Query,UploadFile,File,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from app.api.core import merchant_role,mutate,csv_download
from app.database.session import get_db
from app.models import Product,Inventory
from app.models.retail import RetailSale,RetailSaleLine,StockMovement
from app.schemas.core import ProductWrite
from app.services import retail

router=APIRouter(prefix='/business',dependencies=[Depends(merchant_role)])

class ProductInput(ProductWrite):
    sku:str=Field(default='',max_length=100)
    barcode:str=Field(default='',max_length=100)
    variant:str=Field(default='Standard',min_length=1,max_length=100)
    reorder_point:int=Field(default=20,ge=0,le=10000000)

class ProductProfile(BaseModel):
    model_config=ConfigDict(extra='forbid')
    sku:str|None=Field(default=None,max_length=100)
    barcode:str|None=Field(default=None,max_length=100)
    variant:str|None=Field(default=None,min_length=1,max_length=100)
    reorder_point:int|None=Field(default=None,ge=0,le=10000000)

class ReceiveInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed:bool=False

@router.get('/products')
def products(db=Depends(get_db)):return retail.products(db)

@router.post('/products')
def product_create(data:ProductInput,request:Request,db=Depends(get_db)):
    def run():
        body=data.model_dump()
        if body['barcode'] and db.scalar(select(Product.id).where(Product.barcode==body['barcode'])):raise HTTPException(409,'Barcode already belongs to a product')
        if body['sku'] and db.scalar(select(Product.id).where(Product.sku==body['sku'])):raise HTTPException(409,'SKU already belongs to a product')
        row=Product(merchant_id='sharma-kirana',**body);db.add(row);db.flush()
        if not row.sku:row.sku=row.id
        db.add(Inventory(product_id=row.id,quantity=row.available_stock));retail.ensure_opening_batch(db,row);db.flush()
        return next(p for p in retail.products(db)['items'] if p['id']==row.id)
    return mutate(db,request,data.model_dump(),run)

@router.patch('/products/{id}')
def product_profile(id:str,data:ProductProfile,request:Request,db=Depends(get_db)):
    changes=data.model_dump(exclude_none=True)
    def run():
        row=retail.require_product(db,id,lock=True)
        for name,value in changes.items():
            if name in ('barcode','sku') and value and db.scalar(select(Product.id).where(getattr(Product,name)==value,Product.id!=id)):raise HTTPException(409,f'{name.upper()} already belongs to another product')
            setattr(row,name,value)
        db.flush();return next(p for p in retail.products(db)['items'] if p['id']==id)
    return mutate(db,request,changes,run)

@router.get('/batches')
def batches(db=Depends(get_db)):return retail.batches(db)

@router.post('/batches')
def add_batch(data:retail.BatchInput,request:Request,db=Depends(get_db)):
    return mutate(db,request,data.model_dump(mode='json'),lambda:retail.add_batch(db,data.model_dump()))

@router.post('/stock-adjustments')
def adjust_stock(data:retail.AdjustmentInput,request:Request,db=Depends(get_db)):
    return mutate(db,request,data.model_dump(),lambda:retail.adjust_stock(db,data.model_dump()))

@router.get('/stock-movements')
def stock_movements(limit:int=Query(100,ge=1,le=500),db=Depends(get_db)):
    rows=db.scalars(select(StockMovement).order_by(StockMovement.created_at.desc()).limit(limit)).all()
    return {'items':[{k:getattr(r,k) for k in ('id','product_id','batch_id','sale_id','quantity_delta','reason')}|{'created_at':r.created_at.isoformat()} for r in rows]}

@router.get('/sales')
def sales(limit:int=Query(100,ge=1,le=500),db=Depends(get_db)):return retail.sales(db,limit)

@router.post('/sales')
def create_sale(data:retail.SaleInput,request:Request,db=Depends(get_db)):
    def run():
        result=retail.create_sale(db,data.model_dump())
        from app.analytics.customers import refresh_metrics
        refresh_metrics(db);return result
    return mutate(db,request,data.model_dump(mode='json'),run)

@router.get('/sales/template')
def template(db=Depends(get_db)):
    p=db.scalar(select(Product).order_by(Product.id))
    if not p:raise HTTPException(409,'Add products before downloading a sales template')
    return csv_download('product-sales-template.csv',['invoice_id','product_id','sku','quantity','sold_at','customer_token','payment_method'],[('POS-001',p.id,p.sku,1,datetime.now(timezone.utc).isoformat(),'','cash')])

@router.get('/sales/export')
def export(db=Depends(get_db)):
    rows=db.execute(select(RetailSaleLine,RetailSale).join(RetailSale,RetailSale.id==RetailSaleLine.sale_id).order_by(RetailSale.created_at.desc())).all()
    return csv_download('product-sales.csv',['invoice_id','product_id','product_name','variant','quantity','unit_price','line_total','sold_at','customer_token','payment_method','source'],[(s.id,l.product_id,l.product_name,l.variant,l.quantity,l.unit_price,l.line_total,s.created_at.isoformat(),s.customer_token,s.payment_method,s.source) for l,s in rows])

@router.post('/sales/import')
async def import_sales(request:Request,file:UploadFile=File(...),db=Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith('.csv'):raise HTTPException(422,'Choose a CSV file')
    raw=await file.read(4*1024*1024+1)
    if len(raw)>4*1024*1024:raise HTTPException(413,'Sales CSV must be under 4 MB')
    def run():
        result=retail.import_sales(db,raw)
        from app.analytics.customers import refresh_metrics
        refresh_metrics(db);return result
    return mutate(db,request,{'sha256':hashlib.sha256(raw).hexdigest()},run)

@router.get('/reorders')
def reorders(db=Depends(get_db)):return retail.reorders(db)

@router.post('/reorders')
def create_reorder(data:retail.ReorderInput,request:Request,db=Depends(get_db)):
    return mutate(db,request,data.model_dump(),lambda:retail.create_reorder(db,data.model_dump()))

@router.post('/reorders/{id}/receive')
def receive_reorder(id:str,data:ReceiveInput,request:Request,db=Depends(get_db)):
    return mutate(db,request,data.model_dump(),lambda:retail.receive_reorder(db,id,data.confirmed))
