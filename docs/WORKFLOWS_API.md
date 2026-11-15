# Workflow API

All paths use `/api/v1`. All stored business data is synthetic; every payment is a local simulation. Financial amounts are INR. Internal computations use `Decimal` and explicit paise rounding. No seller private price floor is returned by any of these routes.

## Negotiation

`GET /haggle/catalogue` returns the five supported product IDs (`rice`, `atta`, `oil`, `snacks`, `tea`), three public seller strategies, current available stock and the default basket. Seller policy floors are server-only.

`POST /haggle/sessions` accepts:

```json
{
  "requirement": "Groceries and snacks for an office event",
  "budget": 40000,
  "delivery_date": "2026-11-20",
  "items": [{"product_id": "rice", "quantity": 100}]
}
```

`items` and `delivery_date` are optional. Omission selects the seeded five-line basket and next Friday. IDs and quantities are validated; extracted text must be reviewed and mapped to supported catalogue product IDs. `Idempotency-Key` replays the same create response, and reuse with different data is rejected.

`GET /haggle/sessions` returns `{items: Session[]}`. `GET /haggle/sessions/{id}` returns one session. Session fields:

```text
id, status, requirement, budget, delivery_date, items,
round_number, quotes, rounds, best_deal, provider, provider_error,
active_node, elapsed_ms, created_at
```

States: `created`, `running`, `paused`, `awaiting_approval`, `no_deal`, `confirmed`, `cancelled`, `failed`.

`POST /haggle/sessions/{id}/start`, `/pause`, `/resume`, `/cancel`, `/reset` perform actual workflow control. Reset creates a new session from the prior basket; cancel is required before resetting an active run. Pause takes effect at the next graph stage, after any in-flight provider calls finish. Resume can restart a process-interrupted running session from its persisted round state. Cancelling a confirmed order is rejected; manage its simulation in the ledger instead.

The actual LangGraph graph executes parse → normalize → dispatch → initialize → collect seller quotes → buyer evaluation → counteroffer instructions → firewall validation; the conditional edge repeats through round four, then optimizes and waits for approvals. Three independent first-round Sarvam calls run concurrently; deterministic authorized concessions govern later rounds. The optimizer exhaustively compares product assignments (at most `3^5 = 243` for the supported basket), includes each used supplier's delivery charge, and filters stock, deadline, private pricing floors and buyer budget. No LLM performs price arithmetic or financial authorization.

Quote fields include `seller_id`, `seller_name`, `products`, `quantities`, `unit_prices`, `subtotal`, `delivery_cost`, `discounts`, `total_amount`, `delivery_date`, `validity`, `round_number`, `status`, `summary`, `validation`. Product fields include `product_id`, `name`, `quantity`, `unit`, `unit_price`, `total`; the selected bundle also binds `seller_id` and `seller_name` on each product.

`GET /haggle/sessions/{id}/events` is a reconnectable SSE stream with numeric event IDs. Supports `Last-Event-ID` or `?after=<id>`. Events show action summaries and structured decisions, never hidden model reasoning. Global `/events` also receives the same durable events.

`POST /haggle/sessions/{id}/confirm` requires both:

```json
{"merchant_approved": true, "buyer_confirmed": true}
```

This is an explicit local demo approval, not production authentication. The server locks the stored session and seller rows; verifies the stored HMAC mandate and expiry; rechecks the stored budget, current stock and delivery; validates a signed, expiring, nonce-protected action; reserves stock; and creates exactly one order per session. Repeated confirmation returns the existing order. Caller-supplied totals, budgets, seller floors and replacement deals are not accepted. The three post-approval LangGraph nodes execute order confirmation → simulated payment → final ledger update in one database transaction.

## Orders and payment simulation

`GET /orders` returns `{items: Order[]}`; `GET /orders/{id}` returns an order. Public fields:

```text
id, status, created_at, session_id, seller_name, items, subtotal,
delivery_cost, total_amount, delivery_date, payment_state,
simulated:true, merchant_approved, buyer_confirmed, packed,
delivery_confirmed, inspection, timeline, payment_notice
```

Each timeline item is `{state, detail, created_at}`. Order creation records `ORDER_CREATED` → `PAYMENT_INITIATED` → `AUTHORIZATION_SIMULATED` → `DELIVERY_CONFIRMATION_PENDING`. These are local ledger records, not Paytm responses.

- `POST /orders/{id}/packed` records merchant packing.
- `POST /orders/{id}/inspection`, multipart `file`, validates an image and stores an advisory. It reports image decodability and dimensions only. It does not certify contents, delivery or quantity and cannot authorize settlement.
- `POST /orders/{id}/delivery-confirm` with `{"confirmed":true}` records human confirmation after packing and moves to `SETTLEMENT_ELIGIBLE`.
- `POST /orders/{id}/release` moves a human-confirmed order to `RELEASED_SIMULATED`.
- `POST /orders/{id}/void` moves an unreleased order to `VOIDED_SIMULATED` and restores reserved stock. A voided order cannot be delivered or released.

Transitions are naturally idempotent. Stored order approvals and signed server mandates are validated for payment and settlement actions. `/payments/simulate` rejects arbitrary requests; simulation is created only through an eligible, confirmed order. `PaymentProvider` is an interface; `SimulatedPaymentProvider` is the only implemented provider. No network request, real authorization, escrow or fund transfer occurs.

## Voice

`POST /voice/chat` accepts `{text, language, session_id?}`; language is `hi-IN`, `mr-IN` or `en-IN`. It returns `{session_id, transcript, response, proposal, provider, demo, error, messages}`.

The backend calls Sarvam-105B for a structured intent, validates it with Pydantic, applies deterministic campaign margin constraints and prepares a reviewable proposal. Action responses are deterministic localized copy so an LLM cannot claim an unapproved action already executed. Consultation context includes merchant aggregates only; customer pseudonyms and private seller policies are not sent. A missing or failed provider uses labelled deterministic interpretation.

Supported proposal actions: `create_campaign`, `stop_campaign`, `start_negotiation`. Proposal fields: `{id, action, parameters, status:'pending_approval', expires_at}`. New offer changes replace the previous pending proposal; approval of a stale proposal ID is rejected. A text "yes" alone cannot bypass the approval endpoint.

`POST /voice/approve` accepts `{session_id, proposal_id, approved}`. Approving executes the exact stored unexpired proposal and records the result; repeated approval returns the same result. Rejecting executes nothing. Campaign approval creates and launches an internal simulation only; no customer communication is sent. `GET /voice/history?session_id=...` returns persisted messages and the current proposal.

`POST /voice/transcribe`, multipart `file`, `language`, `duration_seconds`, validates the audio encoding and independently measures duration with `ffprobe`/`ffmpeg` before calling Saaras. Maximum 30 seconds and 10 MB. Browser WebM without duration metadata is decoded to count samples. Temporary audio files are immediately removed. WAV can be validated without ffmpeg; other formats require it. Return shape `{transcript,language_code,request_id?,provider,demo,error,duration_seconds}`. Missing-provider transcription is empty with an explicit error; no invented transcript is returned.

`POST /voice/synthesize` accepts `{text,language}` (up to 2500 characters). It calls Bulbul v4 Flash, validates and decodes the SDK base64 audio, and returns `{audio_base64,mime_type:'audio/wav',provider,demo,error}`. The browser decodes it to a playable Blob. Failed synthesis returns no audio; no synthetic success is claimed.

## Documents

`POST /documents/extract`, multipart `file`, optional `language`, accepts a validated PDF, JPEG, PNG or WebP up to 10 MB; WebP is converted to PNG for the documented provider format. The current `doc_ai.extract` SDK contract automatically handles document languages and accepts a JSON-string schema. The adapter submits, polls boundedly and fetches structured `result.items`.

Return: `{items:[{name,quantity,unit,price,product_id?}],provider,demo,error,review_required:true,notice?}`. Provider errors or missing credentials return a clearly labelled sample basket that was **not extracted from the upload**. No catalogue entries or orders are automatically published. Packing photos use a separate local advisory and never call this sample an image verification.

## Operational limits

The API applies conservative provider timeouts and a single retry for rate-limit/transient errors; expensive endpoints have per-process limits. Uploads have actual encoding validation and size limits. Backend credentials never enter browser payloads. Read `SARVAM.md` for verified official contracts and live verification results. Role headers are a local demonstration aid; production identity, durable distributed workers and authorized Paytm integration remain deployment work.
