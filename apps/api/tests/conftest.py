import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.database.session import Base
from app import models

@pytest.fixture
def db():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as session:yield session
    engine.dispose()

@pytest.fixture
def seeded(db):
    from app.database.seed import seed_demo
    seed_demo(db);db.commit();return db

@pytest.fixture
def client(seeded,monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.config import settings
    from app.database.session import get_db
    monkeypatch.setattr(settings,'auto_seed',False)
    def override():yield seeded
    app.dependency_overrides[get_db]=override
    with TestClient(app,raise_server_exceptions=True) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def isolate_telephony_configuration(monkeypatch):
    """Tests never dial a phone or inherit a developer's live recipient config."""
    from app.core.config import settings
    monkeypatch.setattr(settings, 'notification_channel', 'call')
    monkeypatch.setattr(settings, 'sms_enabled', False)
    monkeypatch.setattr(settings, 'telephony_enabled', False)
    monkeypatch.setattr(settings, 'telephony_provider', 'twilio')
    monkeypatch.setattr(settings, 'telephony_demo_customer_token', 'PK-0036')
    monkeypatch.setattr(settings, 'telephony_demo_customer_name', 'Kush')
    monkeypatch.setattr(settings, 'telephony_demo_phone', '+15005550006')
