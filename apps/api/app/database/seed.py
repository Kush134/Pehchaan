"""Reproducible, pseudonymous synthetic merchant data; never real payment history."""
from datetime import datetime,timezone,timedelta
import csv
import random
import os
from pathlib import Path
from sqlalchemy import select,func
from app.database.session import Base,engine,SessionLocal
from app.core.clock import business_day_start,business_today
from app.models import Merchant,CustomerToken,Transaction,Product,Inventory,CustomerMetric,Seller,Buyer
from app.analytics.customers import refresh_metrics
from app.services.events import emit
from app.services.campaigns import create_campaign,launch_campaign,simulate_campaign

CATALOG=[('Basmati Rice','Grains','kg',95,320,72,80,'Sharma Wholesale Mart'),('Aashirvaad Atta','Grains','5 kg bag',265,90,221,235,'Pune Grocery Distributors'),('Toor Dal','Pulses','kg',155,180,126,135,'Sai General Suppliers'),('Sunflower Oil','Cooking oil','litre',145,240,119,128,'Pune Grocery Distributors'),('Tata Salt','Essentials','kg',28,400,22,25,'Sharma Wholesale Mart'),('Sugar','Essentials','kg',46,350,37,40,'Sai General Suppliers'),('Parle-G Biscuits','Snacks','packet',10,1200,7.5,8.5,'Sharma Wholesale Mart'),('Masala Chai','Beverages','250 g',135,160,103,115,'Pune Grocery Distributors'),('Poha','Grains','kg',65,160,49,55,'Sai General Suppliers'),('Dry Fruit Mix','Snacks','250 g',230,75,175,195,'Sharma Wholesale Mart'),('Dishwash Bar','Household','200 g',25,250,18,21,'Sai General Suppliers'),('Turmeric Powder','Spices','100 g',42,180,30,35,'Pune Grocery Distributors')]

def seed_demo(db, reset=False):
    if reset:
        for table in reversed(Base.metadata.sorted_tables): db.execute(table.delete())
        db.flush()
    if db.get(Merchant,'sharma-kirana'): return {'status':'existing','customers':100,'transactions':len(db.scalars(select(Transaction)).all())}
    rng=random.Random(42)
    reference=business_day_start()
    db.add(Merchant(id='sharma-kirana',name='Sharma Kirana Store',location='Wakad, Pune, Maharashtra',category='Kirana / Grocery'))
    db.flush()
    transactions=[]
    for index in range(100):
        token=f'PK-{index+1:04d}'
        db.add(CustomerToken(customer_token=token,merchant_id='sharma-kirana',created_at=reference-timedelta(days=90)))
        db.flush()
        if index<15: days=range(0,90,3); base=510
        elif index<35: days=range(index%4,90,5); base=320
        elif index<52: days=range(18+index%4,90,4); base=370
        elif index<67: days=list(range(index%3,30,13))+list(range(31,90,3)); base=390
        elif index<77: days=range(41+index%3,90,6); base=300
        elif index<87: days=[index%10+1]; base=240
        else: days=range(index%7,65,9); base=275
        for day in days:
            amount=round(max(65,rng.gauss(base,base*.22)),2)
            if 52<=index<67 and day<30: amount=round(amount*.65,2)
            transactions.append(Transaction(merchant_id='sharma-kirana',customer_token=token,amount=amount,gross_profit=round(amount*.22,2),category=rng.choices(['Grains','Pulses','Snacks','Beverages','Essentials','Household'],[28,16,20,10,18,8])[0],created_at=reference-timedelta(days=day,hours=rng.randrange(0,8)),simulated=True))
    db.add_all(transactions)
    for index,row in enumerate(CATALOG):
        name,category,unit,price,stock,purchase,minimum,supplier=row
        product=Product(id=f'PRD-{index+1:03d}',merchant_id='sharma-kirana',name=name,category=category,unit=unit,selling_price=price,available_stock=stock,purchase_price=purchase,minimum_selling_price=minimum,supplier=supplier)
        db.add(product); db.flush(); db.add(Inventory(product_id=product.id,quantity=stock))
    db.add(Buyer(id='buyer-demo',status='active',payload={'name':'Pune Office Collective','budget':40000}))
    for id,name in [('seller-a','Sharma Wholesale Mart'),('seller-b','Pune Grocery Distributors'),('seller-c','Sai General Suppliers')]: db.add(Seller(id=id,status='active',payload={'name':name}))
    db.flush(); refresh_metrics(db)
    today=business_today()
    campaign=create_campaign(db,{'name':'Neighbourhood favourites','target_segment':'All','offer_amount':15,'minimum_bill':250,'start_date':today.isoformat(),'end_date':(today+timedelta(days=7)).isoformat(),'budget':1000,'max_customers':45,'language':'hi-IN','ab_test':True})
    launch_campaign(db,campaign['id']); simulate_campaign(db,campaign['id']); refresh_metrics(db)
    emit(db,'analytics.updated','Customer segments updated','100 pseudonymous customers analysed from 90 days of synthetic purchases.',agent='customer-intelligence',data={'customers':100,'seed':42})
    emit(db,'system.ready','Pehchaan is ready','Synthetic merchant workspace initialized. Payment provider is simulated.',agent='system')
    db.flush()
    # Portable sample transaction CSV for manual import demonstrations.
    if not os.environ.get('VERCEL'):
        sample=Path(__file__).resolve().parents[4]/'data'/'sample-transactions.csv'
        sample.parent.mkdir(exist_ok=True)
        with sample.open('w',newline='') as file:
            writer=csv.writer(file);writer.writerow(['customer_token','amount','category','created_at'])
            for tx in transactions[:30]: writer.writerow([tx.customer_token,tx.amount,tx.category,tx.created_at.isoformat()])
    return {'status':'reset' if reset else 'seeded','customers':100,'transactions':db.scalar(select(func.count(Transaction.id)))}

if __name__=='__main__':
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        result=seed_demo(db); db.commit(); print(result)
