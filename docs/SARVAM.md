# Sarvam integration

The backend uses the official `sarvamai` Python SDK (verified installed version `0.1.46`) and reads `SARVAM_API_KEY` from the ignored repository-root `.env`. No browser environment variable carries this credential. Restart the API after changing it.

Configured models:

```dotenv
SARVAM_CHAT_MODEL=sarvam-105b
SARVAM_FAST_MODEL=deepseekv4.1-flash-1017
SARVAM_STT_MODEL=saaras:v4
SARVAM_TTS_MODEL=bulbul:v4-flash
```

The optional fast model is retained as configuration; it is not required or called for deterministic arithmetic. The current V1 chat endpoint serves Sarvam models; open-weight models use V2 and would need a separate adapter if enabled. See the official [chat endpoint guide](https://docs.sarvam.ai/api/token-factory/chat-completions).

## Contracts verified on 14 November 2026

- **Chat:** `client.chat.completions(model, messages, temperature, max_tokens, reasoning_effort=None, response_format={"type":"json_object"})`. Response is a typed object; text is `choices[0].message.content`. `None` is explicitly serialized as JSON null to disable reasoning for short merchant responses. The string `"none"` is rejected by the deployed V1 API even though the broad schema lists it. A small token budget with reasoning enabled can return `content:null`; this is treated as an invalid provider result, never a success. The official [SDK metaprompt](https://docs.sarvam.ai/api-reference/metaprompt) documents the explicit-None behavior. No reasoning content is returned to the UI.
- **STT:** `client.speech_to_text.transcribe(file=(filename, BytesIO(content), mime), model="saaras:v4", language_code=..., mode="transcribe")`. Read `transcript`, `language_code`, `request_id`. The API accepts `hi-IN`, `mr-IN`, `en-IN`. See the official [REST reference](https://docs.sarvam.ai/api-reference/speech-to-text/transcribe). The server verifies the 30-second synchronous limit before a call.
- **TTS:** `client.text_to_speech.convert(text=..., language_code=..., model="bulbul:v4-flash", output_audio_codec="wav", speech_sample_rate=22050)`. `audios` is a list of base64 strings. Decode before playback. Speaker is omitted to use the documented v4 default; no guessed v3 voice ID is supplied. See [TTS REST](https://docs.sarvam.ai/api-reference/text-to-speech/convert).
- **Document extraction:** `client.doc_ai.extract(file=[(filename, BytesIO(content), mime)], schema=json.dumps(schema), output_format="json")`; poll `get_status(job_id=...)`, then `get_results(job_id=...).result`. The current endpoint and SDK have no `language` parameter for Extract; older how-to examples differ. The implementation follows the exact current [Extract Fields reference](https://docs.sarvam.ai/api-reference/doc-ai/job/extract). Valid source formats are PDF, PNG and JPEG; application-side validated WebP is converted to PNG. See [format limits](https://docs.sarvam.ai/api/api-guides-tutorials/document-intelligence/languages-formats-limits). Results always require user review.

## Genuine verification

Using the configured subscription, these real calls succeeded during implementation:

1. Sarvam-105B chat and structured JSON completion with `reasoning_effort=None`.
2. Bulbul v4 Flash Hindi synthesis of a short Sharma Kirana greeting.
3. Saaras v4 transcription of that Hindi audio.
4. Bulbul v4 Flash Marathi synthesis of a short merchant greeting.
5. Saaras v4 transcription of that Marathi audio.
6. Sarvam Vision Document Intelligence extraction from a synthetic rate-card PNG: Rice 5 kg at ₹85, Oil 2 l at ₹145, Tea 1 kg at ₹360, with all three lines and prices correctly returned and review required.
7. Real HTTP four-round negotiation across three seller agents; final eligible ₹36,708 bundle under ₹40,000. A Hindi voice change to ₹15 discount/₹250 minimum bill produced a genuine structured proposal, and separate merchant approval activated the internal campaign simulation.

No key or audio payload is logged in this document. Automated tests mock the official typed SDK response shapes and cover failures, base64 decoding, structured output, absence of reasoning exposure, and document result review.

Provider responses include `provider`, `demo`, and `error`. Missing keys, rate limits, invalid responses and unavailable entitlements never become fake successful Sarvam calls. Merchant text commands have a labelled deterministic fallback. STT returns an empty transcript on provider failure; TTS returns no audio. Document fallback is an explicitly labelled sample basket, not claimed OCR of the uploaded file.

Packing-photo inspection is a local human-review advisory only. Payment integration remains a local simulator and has no relationship to successful Sarvam requests.
