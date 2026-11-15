from datetime import date
from typing import Literal
from pydantic import BaseModel,Field,ConfigDict,model_validator

class CampaignCreate(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    name: str=Field(min_length=3,max_length=100)
    target_segment: Literal['All','All Customers','At-Risk + Declining','Champions','Loyal Customers','Potential Loyalists','New Customers','At-Risk Customers','Lost Customers','Declining Customers']='At-Risk Customers'
    offer_amount: float=Field(gt=0,le=5000)
    minimum_bill: float=Field(gt=0,le=100000)
    start_date: date
    end_date: date
    budget: float=Field(gt=0,le=1000000)
    max_customers: int=Field(ge=1,le=100)
    language: Literal['hi-IN','mr-IN','en-IN','Hindi','Marathi','English']='hi-IN'
    ab_test: bool=True
    @model_validator(mode='after')
    def dates(self):
        if self.end_date<self.start_date: raise ValueError('End date must be after start date')
        return self

class ProductWrite(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    name: str=Field(min_length=2,max_length=120)
    category: str=Field(min_length=2,max_length=60)
    unit: str=Field(min_length=1,max_length=30)
    selling_price: float=Field(gt=0,le=1000000)
    available_stock: int=Field(ge=0,le=10000000)
    purchase_price: float=Field(ge=0,le=1000000)
    minimum_selling_price: float=Field(gt=0,le=1000000)
    supplier: str=Field(default='Local supplier',max_length=120)
    @model_validator(mode='after')
    def margins(self):
        if self.selling_price<self.minimum_selling_price: raise ValueError('Selling price is below merchant minimum')
        if self.minimum_selling_price<self.purchase_price: raise ValueError('Minimum selling price must cover purchase price')
        return self

class FirewallProposal(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    amount:float=Field(gt=0,le=100000000)
    budget:float=Field(default=40000,gt=0,le=100000000)
    seller_id:str='seller-a'
    round_number:int=Field(default=1,ge=0,le=100)
    operation:str='quote'
    merchant_approved:bool=False
    buyer_confirmed:bool=False
    quantity_available:bool=True
    delivery_feasible:bool=True
    discount_percent:float=Field(default=0,ge=0,le=100)
    nonce:str|None=Field(default=None,max_length=120)
    expiry:str|None=None
    signature:str|None=None
