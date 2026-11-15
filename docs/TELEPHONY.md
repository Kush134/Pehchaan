# Comeback calls and automatic demo checkout

The application connects the merchant's approved campaign to a persistent customer call, a customer acceptance, and a single-use checkout discount. The allowlisted demo recipient is Kush, mapped through `TELEPHONY_DEMO_CUSTOMER_TOKEN` to a pseudonymous customer (`PK-0036` by default). This workspace maps Kush to an existing inactive regular, `PK-0037`, so the spoken suggestion reflects actual stored history. No purchase dates were changed. The phone number lives only in server settings and is masked in dashboard responses.

## Try the complete local flow

1. Run `make migrate`, then start `make api` and `make web`.
2. In Comeback Agent, choose **Try a simulated call**. This explicitly creates a local simulation. It does not ring a phone or consume telephony credits.
3. Choose **1 · Accept test offer**. The dashboard shows acceptance and its simulation source. The decline and no-answer controls exercise the other outcomes.
4. In the demo checkout, scan a bill of ₹250. An accepted ₹20 offer with a ₹200 minimum produces ₹230 payable. Confirm the simulated payment; the ledger stores ₹230 and the discount can be used only once.

The ₹250 bill, payment and ledger remain simulations even when offer acceptance comes from a real phone call. No UPI payment or real transfer is initiated.

## Enable a real press-1 call

Sarvam's standard speech API key generates audio, but cannot by itself place a PSTN phone call. The implemented keypad path uses **Twilio Programmable Voice + Sarvam speech**. Twilio places the call and collects DTMF using `<Gather input="dtmf" numDigits="1">`; the announcement played inside that Gather is a WAV synthesized with the existing Sarvam subscription.

Set these values in the ignored root `.env`, using the corresponding provider account values:

```dotenv
TELEPHONY_ENABLED=true
TELEPHONY_PROVIDER=twilio
TELEPHONY_DEMO_PHONE=+15005550006
TELEPHONY_DEMO_CUSTOMER_NAME=Kush
TELEPHONY_DEMO_CUSTOMER_TOKEN=PK-0036
TELEPHONY_PUBLIC_BASE_URL=https://YOUR_PUBLIC_API_HOST
TELEPHONY_WEBHOOK_SECRET=YOUR_SEPARATE_PERSISTENT_RANDOM_SECRET
TWILIO_ACCOUNT_SID=YOUR_ACCOUNT_SID
TWILIO_AUTH_TOKEN=YOUR_AUTH_TOKEN
# Optional preferred credentials for outbound REST requests:
TWILIO_API_KEY_SID=YOUR_API_KEY_SID
TWILIO_API_KEY_SECRET=YOUR_API_KEY_SECRET
TWILIO_FROM_NUMBER=YOUR_VOICE_ENABLED_TWILIO_NUMBER
SARVAM_API_KEY=YOUR_EXISTING_SPEECH_KEY
```

When both API-key entries are supplied, outbound REST calls authenticate with the API key SID and secret. If both are blank, the account SID and Auth Token are used. Supplying only one API-key entry blocks calling with an actionable missing-setting message. Keep `TWILIO_AUTH_TOKEN` configured in either case: Twilio signs keypad and status webhooks with that account token, independently of REST authentication.

Generate the webhook secret once with `python3 -c 'import secrets; print(secrets.token_hex(32))'`. Keep it stable across restarts. `TELEPHONY_PUBLIC_BASE_URL` must forward public HTTPS requests to the **callback gateway on port 8010** (or the corresponding deployed callback service), preserving `/api/v1/...` paths. A localhost URL is not reachable by the calling provider. A development HTTPS tunnel can provide this URL. Do not put provider credentials in browser settings or `NEXT_PUBLIC_*` variables.

**Twilio trial accounts:** the current Voice trial supports custom TwiML, including `<Gather>` with keypad input and an action URL, nested `<Play>` with an external audio URL, and `<Say>`. This offer flow uses those supported verbs; a paid upgrade is not automatically required merely because it uses a personalized announcement. Trial limits still apply: verified recipients, calls within the sign-up country, a 75-minute quota, and a 10-minute per-call limit. Follow the API request shown by the Console for the account’s trial experience and use the returned provider error to diagnose any restriction. See [Twilio custom TwiML trial support](https://www.twilio.com/docs/usage/trials/try-out-voice#custom-twiml-during-trial).

The new **Try out Voice** flow supplies a shared Twilio-owned trial caller number, which can vary by product and recipient. It is not a dedicated number provisioned to the account. Use the **From** number shown alongside the selected **To** recipient in that flow. An empty account-owned phone-number list does not, by itself, show that trial setup is incomplete. After upgrading, purchase a dedicated voice-enabled number and update `TWILIO_FROM_NUMBER`; the shared trial caller number is not retained. See [Twilio trial numbers](https://www.twilio.com/docs/usage/trials#twilio-trial-numbers).

Restart the API after changing `.env`. `GET /api/v1/telephony/status` and the calling panel show exactly which configuration entries are still missing. Provider calling permissions, destination verification for trial accounts, balance and destination geographic permissions must also allow the call. The application reports provider rejection and uncertain network outcomes honestly.

When **Send notification**, **Start campaign**, or an approved Soundbox comeback proposal is executed, only the configured recipient receives one outbound call per campaign. The spoken announcement is:

> Hi Kush! You have not visited Sharma Kirana Store recently. We have an offer: 20 rupees off an order of 200 rupees or more. To accept this offer, press 1. To decline, press 2.

The Twilio callback endpoints are generated automatically when the call is created; no Twilio Console webhook entry is needed for these outbound calls. The provider's `X-Twilio-Signature` is verified against the configured public URL and all posted form fields. Account, call identifier and destination must match the persisted call. Unauthenticated and mismatched callbacks cannot accept an offer. The Sarvam-generated announcement is served through an unguessable signed audio capability URL.

## Local HTTPS callbacks without exposing merchant controls

Run `make telephony-gateway` in one terminal and `make telephony-tunnel` in another. The tunnel helper uses `cloudflared` from PATH or `.runtime/bin/cloudflared`. Copy its generated HTTPS URL into `TELEPHONY_PUBLIC_BASE_URL` in root `.env`, then restart the API and callback gateway. Keep both processes running while testing calls. Quick Tunnel URLs are temporary and must be updated after the tunnel restarts.

This tunnel forwards port **8010**, which exposes only signed provider callbacks, protected announcement audio and `/health`. It does not expose campaign creation, call submission, checkout, customer records or API documentation. The web app and merchant API continue running on ports 3000 and 8000.

## Native Sarvam Voice Agents adapter

`TELEPHONY_PROVIDER=sarvam` uses the documented instant-outbound endpoint:

```text
POST https://apps.sarvam.ai/api/outbounds/v1/orgs/{org_id}/workspaces/{workspace_id}/outbounds
X-API-Key: <VOICE_AGENTS_WORKSPACE_KEY>
```

This needs a separate Voice Agents workspace, a committed agent, telephony connection and outbound phone number, plus the `SARVAM_VOICE_*` entries in `.env.example`. The request supplies the customer/offer variables and initial greeting. Its authenticated completion webhook updates call connectivity only.

**Native Sarvam Voice Agents does not supply general keypad input today.** Its official run-time documentation says DTMF is planned. The adapter therefore never interprets an agent variable or an LLM transcript as a verified press 1. Use the implemented Twilio path for literal keypad acceptance. No custom bridge code is required for Twilio.

## API and persistence

- `GET /api/v1/telephony/status`: safe readiness checklist and masked recipient.
- `GET /api/v1/telephony/calls`: persistent calls, acceptance source and errors.
- `POST /api/v1/telephony/demo-offer` with `{"simulate":false}`: create the ₹20/₹200 single-recipient campaign and submit its call. `{"simulate":true}` creates the explicit local simulator. Supports `Idempotency-Key`.
- `POST /api/v1/campaigns/{id}/notify` with `{}`: submit the existing campaign's one-recipient call. Repeating it returns the same call; it never redials an uncertain or submitted call.
- `POST /api/v1/telephony/calls/{id}/simulate` with `{"digit":"1"}`, `{"digit":"2"}` or `{"status":"no_answer"}`: simulator calls only. A real call cannot be converted into a simulated acceptance.

Call dispatch atomically claims and commits the record before making any provider request. Provider timeouts become `unknown`, with no automatic retries that might produce duplicate calls. An interrupted `dispatching` record likewise needs provider-log reconciliation; creating a new campaign should only follow that check. A blocked record can be submitted after its missing configuration is supplied. Accepted and declined outcomes are stable; a verified digit arriving after a completed callback can still finalize acceptance, handling callbacks that arrive out of order.

Explicitly contacted customers receive a `Phone` campaign assignment and are removed from any randomized holdout. The campaign budget reserves the offer before dialing. A previously redeemed assignment cannot receive another discount. Phone assignments are not randomized experiment evidence.

## Official contracts checked during implementation

- [Twilio REST authentication](https://www.twilio.com/docs/usage/requests-to-twilio)
- [Twilio Call resource](https://www.twilio.com/docs/voice/api/call-resource)
- [Twilio Gather and DTMF input](https://www.twilio.com/docs/voice/twiml/gather)
- [Twilio request signing](https://www.twilio.com/docs/usage/security)
- [Sarvam instant outbound request](https://docs.sarvam.ai/voice-agents/api/instant-outbound/create)
- [Sarvam instant outbound completion webhook](https://docs.sarvam.ai/voice-agents/api/instant-outbound/webhook-payload)
- [Sarvam run-time and DTMF availability](https://docs.sarvam.ai/voice-agents/build/run-time)
