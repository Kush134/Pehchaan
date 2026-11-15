def test_dashboard_from_database(client):
    response=client.get('/api/v1/dashboard/summary')
    assert response.status_code==200
    body=response.json()
    assert body['metrics']['revenue']>0 and len(body['revenue_trend'])==30
    assert sum(s['count'] for s in body['segments'])==100
    assert body['recommendation']['projection'] is True
    assert body['metrics']['incremental_gross_profit']==0

def test_catalog_private_cost_requires_merchant_role(client):
    assert client.get('/api/v1/catalog/products',headers={'X-Demo-Role':'buyer'}).status_code==403
    response=client.get('/api/v1/catalog/products')
    assert response.status_code==200 and len(response.json())==12

def test_catalog_upload_validation(client):
    bad=client.post('/api/v1/catalog/import',files={'file':('x.exe',b'hello','application/octet-stream')})
    assert bad.status_code==422
    bad=client.post('/api/v1/catalog/import',files={'file':('catalog.csv',b'name,selling_price\nTest,-100','text/csv')})
    assert bad.status_code==422

def test_customer_search_pagination(client):
    response=client.get('/api/v1/customers?page=2&page_size=10').json()
    assert len(response['items'])==10 and response['total']==100
    assert client.get('/api/v1/customers?search=PK-0001').json()['total']==1

def test_api_money_rejects_nan_and_invalid_campaign(client):
    response=client.post('/api/v1/firewall/validate',content='{"amount":NaN}',headers={'Content-Type':'application/json'})
    assert response.status_code==422
    assert client.post('/api/v1/campaigns',json={'name':'x'}).status_code==422

def test_transaction_csv_import_replay_safe(client):
    content=b'customer_token,amount,category,created_at\nPK-0001,125.50,Grocery,2026-11-01T10:00:00+00:00\n'
    first=client.post('/api/v1/transactions/import',files={'file':('transactions.csv',content,'text/csv')})
    assert first.status_code==200 and first.json()['imported']==1
    count=client.get('/api/v1/transactions').json()['total']
    second=client.post('/api/v1/transactions/import',files={'file':('transactions.csv',content,'text/csv')})
    assert second.status_code==200 and client.get('/api/v1/transactions').json()['total']==count
    invalid=client.post('/api/v1/transactions/import',files={'file':('transactions.csv',content.replace(b'PK-0001',b'upi-real-id'),'text/csv')})
    assert invalid.status_code==422


def test_reset_and_agent_telemetry_have_real_data(client):
    response=client.post('/api/v1/demo/reset',json={})
    assert response.status_code==200 and response.json()['customers']==100
    assert response.json()['transactions']==client.get('/api/v1/transactions').json()['total']
    agents=client.get('/api/v1/agents/status').json()['agents']
    assert len(agents)==11 and all('duration_ms' in agent for agent in agents)


def test_redis_health_does_not_claim_unavailable_service(monkeypatch):
    from app.services import events
    class Offline:
        def ping(self):raise ConnectionError('offline')
    monkeypatch.setattr(events,'_redis',Offline())
    monkeypatch.setattr(events,'_redis_available',True)
    assert events.redis_status()=='database_polling_fallback'
