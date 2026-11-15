import base64
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.integrations.sarvam.provider import SarvamProvider,DocumentIntelligenceProvider,known_product_id


def client_mock():
    client=SimpleNamespace(chat=SimpleNamespace(completions=Mock()),
        speech_to_text=SimpleNamespace(transcribe=Mock()),text_to_speech=SimpleNamespace(convert=Mock()))
    return client


@pytest.mark.asyncio
async def test_official_chat_schema_and_no_exposed_reasoning():
    client=client_mock()
    client.chat.completions.return_value=SimpleNamespace(id='chat-123',choices=[SimpleNamespace(message=SimpleNamespace(content='{"action":"none"}',reasoning_content='PRIVATE'))])
    result=await SarvamProvider(client).chat([{'role':'user','content':'Explain customer decline.'}],structured=True)
    assert result['provider']=='sarvam' and not result['demo']
    assert result['text']=='{"action":"none"}' and 'PRIVATE' not in str(result)
    args=client.chat.completions.call_args.kwargs
    assert args['model']=='sarvam-105b' and args['reasoning_effort'] is None
    assert args['response_format']=={'type':'json_object'}


@pytest.mark.asyncio
async def test_speech_contracts_and_base64_audio():
    client=client_mock();content=b'RIFF-audio-test'
    client.text_to_speech.convert.return_value=SimpleNamespace(audios=[base64.b64encode(content).decode()])
    client.speech_to_text.transcribe.return_value=SimpleNamespace(transcript='नमस्कार',language_code='mr-IN',request_id='speech-123')
    provider=SarvamProvider(client)
    audio=await provider.synthesize('नमस्कार','mr-IN')
    assert base64.b64decode(audio['audio_base64'])==content
    args=client.text_to_speech.convert.call_args.kwargs
    assert args['model']=='bulbul:v4-flash' and args['language_code']=='mr-IN'
    assert 'speaker' not in args
    transcript=await provider.transcribe(content,'recording.wav','audio/wav','mr-IN')
    assert transcript['transcript']=='नमस्कार'
    assert client.speech_to_text.transcribe.call_args.kwargs['model']=='saaras:v4'


@pytest.mark.asyncio
async def test_provider_errors_are_explicit_no_fake_media():
    client=client_mock();client.chat.completions.side_effect=RuntimeError('secret API request')
    client.text_to_speech.convert.side_effect=RuntimeError('secret API request')
    client.speech_to_text.transcribe.side_effect=RuntimeError('secret API request')
    provider=SarvamProvider(client)
    text=await provider.chat([{'role':'user','content':'Hi'}]);audio=await provider.synthesize('Hi','hi-IN');stt=await provider.transcribe(b'audio','x.wav','audio/wav','hi-IN')
    assert all(r['demo'] and r['error'] and r['provider']=='demo' for r in (text,audio,stt))
    assert audio['audio_base64'] is None and stt['transcript']=='' and text['text']==''
    assert 'secret API request' not in str((text,audio,stt))


@pytest.mark.asyncio
async def test_document_sdk_extraction_requires_review():
    client=client_mock();client.doc_ai=SimpleNamespace(
        extract=Mock(return_value=SimpleNamespace(job_id='doc-123')),
        get_status=Mock(return_value=SimpleNamespace(status='completed')),
        get_results=Mock(return_value=SimpleNamespace(result={'items':[{'name':'Rice','quantity':5,'unit':'kg','price':85}]})))
    result=await DocumentIntelligenceProvider(SarvamProvider(client)).extract(b'%PDF-test','parchi.pdf','application/pdf','hi-IN')
    assert result['provider']=='sarvam' and result['review_required'] and not result['demo']
    assert result['items'][0]['product_id']=='rice'
    args=client.doc_ai.extract.call_args.kwargs
    assert isinstance(args['schema'],str) and args['file'][0][0]=='parchi.pdf'


def test_document_fallback_is_a_labelled_sample():
    result=DocumentIntelligenceProvider.demo('No provider configured')
    assert result['demo'] and result['review_required'] and 'not extracted' in result['notice']


def test_product_normalization_never_uses_line_position():
    assert known_product_id('Premium Tea')=='tea'
    assert known_product_id('Sunflower Oil')=='oil'
    assert known_product_id('Whole Wheat Atta')=='atta'
    assert known_product_id('Tata Salt') is None
    assert known_product_id('Tea and Rice bundle') is None
