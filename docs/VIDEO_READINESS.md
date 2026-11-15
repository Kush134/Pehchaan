# Walkthrough recording readiness

Read-only readiness audit: 14 November 2026. Both `http://localhost:3000/dashboard` and API health on port 8000 returned HTTP 200. PostgreSQL and Redis are connected, and the Sarvam subscription is configured. This does not guarantee every future provider request succeeds; retain provider/fallback labels visible in each captured result.

All ten routes opened at 1600×900 with no runtime exceptions or horizontal page overflow. The global `DEMO MODE` badge is absent. The application uses the current blue-and-white theme.

## Recording setup

- Use a fresh browser context at 1600×900 or 1920×1080, device scale 1. The app uses local storage for negotiation and voice-session continuity.
- Wait for the main heading and actual data, not `networkidle`: the event stream remains open by design.
- Prefer Playwright `getByRole` locators. Hidden streaming markup can briefly duplicate label-based matches during hydration.
- Await mutation HTTP responses or visible status changes before moving to the next chapter. Clicking alone does not await application-side asynchronous work.
- Screen video capture and voice-over mixing are separate tasks. Playwright `recordVideo` captures pixels; prepare and mix narration/audio separately.
- Optional clean sample reset belongs before recording, never during an active negotiation. Resetting is a real database mutation and is reserved for the recording owner.
- The UI includes real loading, success, policy-blocked, and approval states; record these rather than replacing them with staged success text.

## Stable route and control map

| Route | Reliable controls and facts to show |
|---|---|
| `/dashboard` | `button: Start walkthrough`; `select: Dashboard date range`; revenue/returning/at-risk/basket metrics; actual live events |
| `/customers` | `textbox: Search customer tokens`; `button: View customer PK-XXXX`; dialog heading `Customer PK-XXXX`; heading `Purchase history`; RFM/cadence/spend details and observed weekly cohorts |
| `/comeback` | `button: Create campaign`; dialog labels `Campaign name`, `Target segment`, `Offer amount (₹)`, `Minimum bill (₹)`; choose `At-Risk + Declining`; `button: Approve & launch campaign`; `button: Simulate redemptions`; show Control assignments and Preliminary results |
| `/soundbox` | `combobox: Assistant language`; `checkbox: Spoken responses`; `textbox: Merchant command`; `button: Send command`; `button: Approve action`; `button: New conversation`; microphone buttons `Start microphone recording` and `Stop recording` |
| `/haggle` | `textbox: Buyer requirement`; `button: Parse request`; text `Review parsed request`; spinbutton `Maximum budget (₹)`; `button: Upload parchi`; `button: Start negotiation`; `Pause`, `Resume`, `Cancel`; heading `Best eligible deal`; `button: Review & confirm order` |
| `/agents` | Actual React Flow network, execution timeline and agent registry; node click opens latest action; execution summaries are not hidden reasoning |
| `/firewall` | `spinbutton: Proposed amount (₹)` → 95000; `button: Run firewall check`; `.decision-result` shows BLOCKED and buyer-budget reason |
| `/ledger` | Order card `.utility-order` matched by uppercase first 8 ID characters; `Mark packed`; `Upload packing photo`; `Confirm delivery`; dialog checkbox then `Confirm demo delivery`; `Release simulated settlement`; `Import transactions`; `Export transactions` |
| `/catalog` | `Add product`; `Import catalogue`; catalogue dialog `Upload CSV`, `Photograph / document`, `CSV template`; every extracted line is editable before saving |
| `/settings` | `combobox: Default assistant language`; `button: Save language`; connection metadata; `Reset sample data` (do not click during the main recording) |

Order confirmation requires BOTH checkboxes: `I approve this order as the merchant.` and `I confirm the selected bundle as the buyer.` The submit button is `Confirm simulated order`. After it returns, the ledger begins at delivery-confirmation-pending and the payment timeline explicitly records the simulated authorization stage.

Parchi upload in Haggle uses `input[type=file]` accepting JPEG, PNG, PDF. Catalogue uploads additionally accept WebP. Packing-photo input has label `Upload packing photo` and accepts PNG/JPEG/WebP. Use a readable synthetic rate card, never real customer data or personal identifiers.

## Genuine recorded Hindi/Marathi speech

The checked-in `apps/web/e2e/voice-recording.spec.ts` is a tested pattern:

1. Request a known phrase from `/api/v1/voice/synthesize` with `hi-IN` or `mr-IN`.
2. Decode the base64 WAV and convert with FFmpeg to 48 kHz mono signed 16-bit PCM.
3. Launch Chromium with `--use-fake-ui-for-media-stream`, `--use-fake-device-for-media-stream`, and `--use-file-for-fake-audio-capture=/absolute/path.wav`.
4. Grant microphone permission in the context and click the actual microphone button.
5. Stop after the phrase duration (always below the 30-second provider limit).
6. Await actual `/voice/transcribe` and `/voice/chat` responses; inspect the displayed structured proposal and approve separately.

This uses synthetic speech as a test microphone input while exercising real MediaRecorder, upload validation, genuine STT and structured interpretation. Do not describe the fixture as a human merchant's recording.

## Truthful story and claims

- Current customer/transaction records are synthetic, campaign redemption outcomes are simulated, and payments do not move real money.
- Genuine Sarvam requests are server-side. When an external call fails, show its labelled fallback or re-record after resolving availability; do not claim a fake API success.
- Business model, pricing, rollout, and addressable-market statements should be presented as proposals or future plans, not existing customers/revenue/partnerships.
- RFM/cadence calculations and financial arithmetic are deterministic Python logic; Sarvam performs language, speech, document interpretation and bounded negotiation explanations.
- The API currently exposes single-merchant local demonstration roles, not production authentication or deployed tenant isolation.

## Verification during this audit

Strict TypeScript, ESLint, and seven Vitest tests passed. The initial full backend run found an invalid-quantity reconciliation regression: a model could replace explicit `0.5kg rice` with an invented 100 kg. The recording readiness agent was authorized to fix the reconciliation and extend the regression to zero and excessive quantities. The final backend suite passed all 62 tests. API port 8000 was restarted after confirming there were zero running or paused negotiations; health returned HTTP 200 with PostgreSQL and Redis connected. The latest deterministic reconciliation is now loaded.
