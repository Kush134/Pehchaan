"""Server-only Sarvam adapter. Failed external calls never become fake successes.

Contracts verified against docs.sarvam.ai on 2026-11-14; see docs/SARVAM.md.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import re
from typing import Any, Protocol

import httpx
from sarvamai import SarvamAI

from app.core.config import settings


def known_product_id(name: str) -> str | None:
    """Only attach known catalogue identities; never map an OCR line by position."""
    normalized=' '.join(name.lower().split())
    synonyms={
        'rice':r'\brice\b|चावल|तांदूळ|तांदुळ',
        'atta':r'\batta\b|\bwheat flour\b|आटा|पीठ',
        'oil':r'\boil\b|तेल',
        'snacks':r'\bsnacks?\b|\bnamkeen\b|नमकीन|फरसाण',
        'tea':r'\btea\b|चाय|चहा',
    }
    matches=[key for key,pattern in synonyms.items() if re.search(pattern,normalized)]
    return matches[0] if len(matches)==1 else None


class ChatProvider(Protocol):
    async def chat(self, messages: list[dict], *, structured: bool = False) -> dict: ...


def failure(exc: Exception | None = None) -> dict:
    # Never return raw provider errors: they can contain a request or credential.
    status = getattr(exc, 'status_code', None)
    description = 'Sarvam API key is not configured.' if exc is None else (
        f'Sarvam provider unavailable (HTTP {status}).' if status else 'Sarvam provider timed out or returned an invalid response.'
    )
    return {'provider': 'demo', 'demo': True, 'error': description}


class SarvamProvider:
    def __init__(self, client: Any = None):
        self.client = client
        if client is None and settings.sarvam_api_key:
            self.client = SarvamAI(
                api_subscription_key=settings.sarvam_api_key,
                timeout=min(settings.api_timeout_seconds, 25),
            )

    async def _call(self, fn, **kwargs):
        for attempt in range(2):
            try:
                return await asyncio.wait_for(asyncio.to_thread(fn, **kwargs), timeout=min(settings.api_timeout_seconds, 25) + 2)
            except Exception as exc:
                if attempt == 0 and (getattr(exc, 'status_code', None) in (429, 502, 503, 504) or isinstance(exc, (TimeoutError, httpx.TimeoutException))):
                    await asyncio.sleep(.4)
                    continue
                raise

    async def chat(self, messages: list[dict], *, structured: bool = False) -> dict:
        if self.client is None:
            return {'text': '', **failure()}
        try:
            # Explicit JSON null disables reasoning on the live v1 deployment.
            # The string 'none' is documented but rejected by that deployment.
            kwargs = dict(model=settings.sarvam_chat_model, messages=messages, temperature=.2, max_tokens=1200, reasoning_effort=None)
            if structured:
                kwargs['response_format'] = {'type': 'json_object'}
            result = await self._call(self.client.chat.completions, **kwargs)
            text = result.choices[0].message.content
            if not isinstance(text, str) or not text.strip():
                raise ValueError('Empty completion')
            return {'text': text, 'provider': 'sarvam', 'demo': False, 'error': None, 'request_id': getattr(result, 'id', None)}
        except Exception as exc:
            return {'text': '', **failure(exc)}

    async def transcribe(self, content: bytes, filename: str, content_type: str, language: str) -> dict:
        if self.client is None:
            return {'transcript': '', 'language_code': language, **failure()}
        try:
            result = await self._call(self.client.speech_to_text.transcribe,
                file=(filename, io.BytesIO(content), content_type), model=settings.sarvam_stt_model,
                language_code=language, mode='transcribe')
            return {'transcript': result.transcript, 'language_code': result.language_code,
                    'request_id': result.request_id, 'provider': 'sarvam', 'demo': False, 'error': None}
        except Exception as exc:
            return {'transcript': '', 'language_code': language, **failure(exc)}

    async def synthesize(self, text: str, language: str) -> dict:
        if self.client is None:
            return {'audio_base64': None, 'mime_type': 'audio/wav', **failure()}
        try:
            # The documented v4 persona default is used; v3 short speaker names are incompatible.
            result = await self._call(self.client.text_to_speech.convert,
                text=text, language_code=language, model=settings.sarvam_tts_model,
                output_audio_codec='wav', speech_sample_rate=22050)
            if not result.audios:
                raise ValueError('No audio returned')
            decoded = base64.b64decode(result.audios[0], validate=True)
            if not decoded:
                raise ValueError('Empty audio returned')
            return {'audio_base64': base64.b64encode(decoded).decode('ascii'), 'mime_type': 'audio/wav',
                    'provider': 'sarvam', 'demo': False, 'error': None}
        except Exception as exc:
            return {'audio_base64': None, 'mime_type': 'audio/wav', **failure(exc)}


class DocumentIntelligenceProvider:
    SCHEMA = {
        'type': 'object', 'properties': {
            'items': {'type': 'array', 'description': 'Product lines in the grocery list or rate card, preserving every quantity and INR unit price.',
                'items': {'type': 'object', 'properties': {
                    'name': {'type': 'string', 'description': 'Product name exactly as written.'},
                    'quantity': {'type': 'number', 'description': 'Requested quantity, or 1 for a rate card.'},
                    'unit': {'type': 'string', 'description': 'Unit such as kg, l or pack.'},
                    'price': {'type': 'number', 'description': 'INR unit selling price if present, otherwise 0.'},
                }}},
        },
    }

    def __init__(self, provider: SarvamProvider | None = None):
        self.provider = provider or SarvamProvider()

    async def extract(self, content: bytes, filename: str, content_type: str, language: str) -> dict:
        if self.provider.client is None:
            return self.demo(failure()['error'])
        try:
            client = self.provider.client
            if not hasattr(client, 'doc_ai'):
                raise RuntimeError('Upgrade official sarvamai SDK for doc_ai')
            # Current endpoint/SDK auto-detect document language. Unlike older
            # how-to examples, extract() has no language parameter (SDK 0.1.46).
            if content_type=='image/webp':
                from PIL import Image
                converted=io.BytesIO()
                with Image.open(io.BytesIO(content)) as image: image.convert('RGB').save(converted,format='PNG')
                content=converted.getvalue();filename='document.png';content_type='image/png'
            job = await self.provider._call(client.doc_ai.extract,
                file=[(filename, io.BytesIO(content), content_type)], schema=json.dumps(self.SCHEMA),
                output_format='json')
            # Bounded job polling. Long-running jobs can be retried; no infinite request.
            for _ in range(12):
                status = await self.provider._call(client.doc_ai.get_status, job_id=job.job_id)
                if status.status.lower() in {'completed', 'partially_completed'}:
                    result = await self.provider._call(client.doc_ai.get_results, job_id=job.job_id)
                    fields = result.result
                    if hasattr(fields, 'model_dump'):
                        fields = fields.model_dump()
                    if not isinstance(fields, dict):
                        raise ValueError('Unexpected document extraction schema')
                    items = fields.get('items', [])
                    if not isinstance(items, list):
                        raise ValueError('Unexpected product list')
                    reviewed=[]
                    for item in items[:100]:
                        if not isinstance(item,dict) or not isinstance(item.get('name'),str):
                            raise ValueError('Invalid extracted product line')
                        product_id=known_product_id(item['name'])
                        reviewed.append({**item,**({'product_id':product_id} if product_id else {})})
                    return {'items': reviewed, 'provider': 'sarvam', 'demo': False, 'error': None,
                            'review_required': True, 'job_id': job.job_id, 'status': status.status}
                if status.status.lower() in {'failed', 'rejected'}:
                    raise RuntimeError('Document job rejected')
                await asyncio.sleep(2)
            return {'items': [], 'provider': 'sarvam', 'demo': False, 'review_required': True,
                    'job_id': job.job_id, 'error': 'Document job is still processing. Review and retry later.', 'status': 'processing'}
        except Exception as exc:
            return self.demo(failure(exc)['error'])

    @staticmethod
    def demo(error: str) -> dict:
        return {'items': [
            {'name': 'Basmati Rice', 'product_id': 'rice', 'quantity': 100, 'unit': 'kg', 'price': 85},
            {'name': 'Whole Wheat Atta', 'product_id': 'atta', 'quantity': 100, 'unit': 'kg', 'price': 46},
            {'name': 'Sunflower Oil', 'product_id': 'oil', 'quantity': 80, 'unit': 'l', 'price': 145},
            {'name': 'Assorted Snacks', 'product_id': 'snacks', 'quantity': 200, 'unit': 'pack', 'price': 38},
            {'name': 'Premium Tea', 'product_id': 'tea', 'quantity': 20, 'unit': 'kg', 'price': 360},
        ], 'provider': 'demo', 'demo': True, 'review_required': True,
            'error': error, 'notice': 'DEMO SAMPLE. These lines were not extracted from your file. Review and edit every line before use.'}
