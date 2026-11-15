from functools import lru_cache
from pathlib import Path
import secrets
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / '.env'), extra='ignore')
    database_url: str = 'sqlite:///' + str(ROOT / 'pehchaan.db')
    @field_validator('database_url',mode='before')
    @classmethod
    def normalize_postgres(cls,value):
        if isinstance(value,str):
            if value.startswith('postgres://'):return value.replace('postgres://','postgresql+psycopg://',1)
            if value.startswith('postgresql://'):return value.replace('postgresql://','postgresql+psycopg://',1)
        return value
    redis_url: str = ''
    sarvam_api_key: str = ''
    sarvam_chat_model: str = 'sarvam-105b'
    sarvam_fast_model: str = 'deepseekv4.1-flash-1017'
    sarvam_stt_model: str = 'saaras:v4'
    sarvam_tts_model: str = 'bulbul:v4-flash'
    policy_signing_secret: str = ''
    cors_origins: str = 'http://localhost:3000,http://127.0.0.1:3000'
    demo_mode: bool = True
    auto_seed: bool = True
    max_upload_bytes: int = 10 * 1024 * 1024
    api_timeout_seconds: float = 30.0
    notification_channel: str = 'sms'
    sms_enabled: bool = False
    twilio_sms_from_number: str = ''
    twilio_messaging_service_sid: str = ''
    twilio_sms_trial: bool = True
    telephony_enabled: bool = False
    telephony_provider: str = 'twilio'
    telephony_demo_phone: str = ''
    telephony_demo_customer_name: str = 'Kush'
    telephony_demo_customer_token: str = 'PK-0036'
    telephony_public_base_url: str = ''
    telephony_webhook_secret: str = ''
    twilio_account_sid: str = ''
    twilio_auth_token: str = ''
    twilio_api_key_sid: str = ''
    twilio_api_key_secret: str = ''
    twilio_from_number: str = ''
    sarvam_voice_api_key: str = ''
    sarvam_voice_org_id: str = ''
    sarvam_voice_workspace_id: str = ''
    sarvam_voice_app_id: str = ''
    sarvam_voice_app_version: int = 1
    sarvam_voice_connection_id: str = ''
    sarvam_voice_agent_phone: str = ''

@lru_cache
def get_settings():
    return Settings()

settings = get_settings()
# No hard-coded signing secret: generated once per process unless configured.
signing_secret = settings.policy_signing_secret or secrets.token_hex(32)
