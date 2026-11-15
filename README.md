# PEHCHAAN · पहचान

**Paytm helps merchants receive payments. Pehchaan helps merchants earn their next payment.**

A working merchant-growth proof of concept: customer intelligence, reproducible comeback experiments, a four-round LangGraph procurement negotiation, deterministic financial mandates, a Hindi/Marathi voice assistant, and a clearly labelled simulated order/payment ledger. Built for the synthetic **Sharma Kirana Store · Wakad, Pune**.

All customers are pseudonymous. All transactions and payments are demonstration records. Campaign outreach is simulated by default; when explicitly configured, approved campaigns can call the single allowlisted test recipient through Twilio with Sarvam-generated speech. No real money moves.

The interface uses a Paytm-inspired blue-and-white theme. The global Demo Mode badge is removed; payment simulations, synthetic data, and unavailable-provider fallback results retain their own explicit labels. Pehchaan remains an independent proof of concept.

The workspace also supports saved voice conversations, customer purchase-history details, reviewable natural-language buyer requests, and transaction CSV import/export. Every proposed financial action still requires the corresponding approvals.

## Run locally

Prerequisites: Node.js 20.19+ (22 recommended), npm, Python 3.12+, and [uv](https://docs.astral.sh/uv/). Install FFmpeg (`brew install ffmpeg` on macOS) to validate browser WebM/MP4 recordings. PostgreSQL 17 and Redis are recommended; SQLite and durable database event polling support an offline laptop demo.

From the repository root:

```sh
test -f .env || cp .env.example .env
python3 -c 'import secrets; print(secrets.token_hex(32))'
# Paste that generated value into POLICY_SIGNING_SECRET in .env.
make setup
make migrate
make seed
```

The development command uses Next.js with Webpack for the local preview.

Start two terminals:

```sh
make api
```

```sh
make web
```

For a production-mode local web server, run `make build` and then `npm run start --workspace apps/web` instead of `make web`; keep the API running.

Open [Pehchaan](http://localhost:3000) and [API documentation](http://localhost:8000/docs). Health: [GET /api/v1/health](http://localhost:8000/api/v1/health).

The seeded dataset contains 100 pseudonymous customers and 90 days of varied purchase patterns. Metrics and charts aggregate stored records. **Reset sample data** reconstructs the synthetic scenario. Do not configure this demo against a production merchant database.

### Comeback calls and accepted-offer checkout

The dashboard, Comeback Agent and Soundbox now include **Call, accept, come back**. Choose **Try a simulated call**, then **1 · Accept test offer**. Go to **Transaction Ledger → Scan & pay**, simulate a ₹250 QR scan, and confirm the ₹230 simulated payment. An accepted ₹20 offer requires a bill of at least ₹200 and is redeemable once. Call acceptance, decline and redemption persist and update live.

In Soundbox, ask **“Who has not visited in 14 days?”** (or the Hindi/Marathi prompt). It proposes outreach from actual stored purchase dates. Say **“Haan”** to approve the current offer. A live call requires phone-provider configuration; unavailable calling is shown honestly and never replaced with a pretend phone call. The standard Sarvam speech key alone cannot dial a phone. [Telephony setup and API guide](docs/TELEPHONY.md) covers Twilio + Sarvam, signed keypad callbacks and the optional native Sarvam outbound adapter.

### Workspace tools

- Open a customer token in **Customer Intelligence** to inspect its stored RFM profile, visit cadence, spend decline explanation, and purchase history.
- In **Transaction Ledger**, import a transaction CSV using known pseudonymous customer tokens or export the stored ledger. The downloadable template shows the accepted columns. Imports validate amounts and timestamps and recalculate customer intelligence; imported records are labelled synthetic.
- In **Haggle Arena**, enter a natural-language basket and choose **Parse request**. Review the extracted products, quantities, budget, and delivery date before choosing **Start negotiation**. Parsing alone creates no negotiation, order, or payment.
- **Soundbox Simulator** saves the active conversation in this browser and restores messages and unexpired pending proposals after a reload. **New conversation** starts a fresh view without executing or deleting the prior proposal.
- Set **Default assistant language** in Settings and choose **Save language**. New conversations use that preference; saved conversations restore their own language.

### PostgreSQL and Redis

For an existing local PostgreSQL service:

```sh
createdb pehchaan
```

Set `DATABASE_URL=postgresql+psycopg://YOUR_LOCAL_ROLE@localhost:5432/pehchaan` in root `.env`, then run `make migrate` and `make seed`. A PostgreSQL URL requires the installed Psycopg driver supplied in API requirements. Without an explicit database URL the API supports a local SQLite database.

Optional Redis:

```sh
redis-server --bind 127.0.0.1 --port 6380
```

Set `REDIS_URL=redis://127.0.0.1:6380/0` and restart the API. Redis health is reported honestly; persistent audit events remain in the database. In this workspace an isolated PostgreSQL database and Redis on port 6380 were prepared for verification.

### Docker Compose

Requires Docker Engine/Desktop with Compose v2. Set a persistent `POLICY_SIGNING_SECRET` in `.env` using the generation command above before starting; keep it unchanged across restarts so stored mandates remain verifiable. The default local demo password is suitable only for these loopback-published development services. Change `POSTGRES_PASSWORD` for another environment.

```sh
test -f .env || cp .env.example .env
make up
```

The stack includes PostgreSQL, Redis, API migrations, automatic seed, and the Next.js production build. Ports are bound to localhost: web3000, API8000, PostgreSQL5433, Redis6380. Do not start the native servers on the same ports while using Compose.

```sh
make down
```

This preserves database volumes. `docker compose -f infra/docker-compose.yml down -v` intentionally deletes the Docker demo data.

## Configure Sarvam

Only the FastAPI process reads subscription credentials. Add your key to the ignored **root `.env`** and restart `make api`:

```dotenv
SARVAM_API_KEY=your_subscription_key
SARVAM_CHAT_MODEL=sarvam-105b
SARVAM_FAST_MODEL=deepseekv4.1-flash-1017
SARVAM_STT_MODEL=saaras:v4
SARVAM_TTS_MODEL=bulbul:v4-flash
```

These are the requested configurable model identifiers. Your account must have access to the selected models. An unavailable model, denied subscription, timeout or rate limit is surfaced as a provider-unavailable/demo result, never a fake successful API call. See the Sarvam adapter notes in [workflow API](docs/WORKFLOWS_API.md) for the official contracts verified during implementation and model limitations.

Use **Soundbox Simulator** with Hindi, Marathi or English. Microphone recording requires localhost or HTTPS and browser permission. Recordings stop with a little headroom below the 30-second provider limit. The flow is recording → validated upload → STT → automatic interpretation → action proposal → explicit merchant approval → execution → optional synthesized response. If the microphone or provider is unavailable, use the text command input. Deterministic fallback responses are visibly labelled. Without a key, genuine STT and Sarvam synthesized voice are unavailable; text workflows remain usable.

Never put a key in `NEXT_PUBLIC_*`, the browser, a screenshot, or a committed file.

## Judge walkthrough

Select **Start walkthrough** on Overview. The built-in guide navigates the working modules. The full three-minute presenter script is in [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

1. Inspect at-risk regulars and their cadence in Customer Intelligence.
2. Create a ₹15 discount with a ₹250 minimum bill; allocate a treatment/control experiment and simulate redemptions.
3. Change an offer through Hindi/Marathi voice or text and explicitly approve the proposed action.
4. Start Haggle Arena under a ₹40,000 budget. Watch three seller agents negotiate through four rounds. Inspect the best eligible bundle.
5. Run a rogue ₹95,000 proposal through Mandate Firewall and see deterministic rejection.
6. Approve and confirm the selected order, then advance the simulated packing/delivery/settlement lifecycle in the ledger.

The Command Center displays actual action events and execution summaries. It does not display private chain-of-thought.

## Validation commands

```sh
make test-api
make test-web
make check
make build
# Browser tests expect API8000 and web3000 already running.
npx playwright install chromium
make e2e
```

Pytest covers customer analytics, campaign limits, signing/replay, firewall constraints, LangGraph negotiation, payment transitions, provider adapters and upload handling. Vitest and Playwright cover client behavior and cross-module flows. Exact coverage is defined by the checked-in tests. Docker build execution depends on a running Docker daemon and Compose v2; the native PostgreSQL path can be tested independently.

## Application structure

```text
apps/web/        Next.js App Router · React · strict TypeScript · Tailwind
                 Radix/shadcn-style components · Motion · Recharts
                 TanStack Query/Table · Zustand · React Flow
apps/api/        FastAPI · Pydantic v2 · SQLAlchemy · Alembic
                 RFM/cadence analytics · deterministic mandates
                 LangGraph · Sarvam and payment provider interfaces
infra/           PostgreSQL + Redis + API + web Docker Compose
data/            Synthetic transaction CSV import example
docs/            API contracts · architecture · judge script
```

[Validation and limits](docs/VALIDATION.md) · [Architecture](docs/ARCHITECTURE.md) · [Core API contract](docs/API_CONTRACT.md) · [Workflow API](docs/WORKFLOWS_API.md)

## Integration boundaries

- **Telephony:** Twilio handles outbound calling and literal press-1 DTMF; Sarvam generates the offer announcement. Calls require an enabled provider account and public HTTPS callbacks. Local simulated calls are labelled and cannot accept a real call.
- **Sarvam:** genuine backend requests when configured and permitted by the subscription. Live chat, Hindi/Marathi speech synthesis, Hindi/Marathi speech recognition, and rate-card document extraction were verified with the configured subscription; keys remain server-side.
- **Paytm:** disabled. The payment provider records synthetic lifecycle events only. No real Paytm authorization, UPI transaction, escrow or settlement is claimed.
- **Documents:** extraction is advisory, reviewable, and labelled by provider availability. The local fallback is demo content, not a claim of successful Sarvam OCR.
- **Customers:** synthetic tokens; one server-side test contact can be mapped to Kush for explicitly enabled offer calls. Other seeded customers have no phone numbers. Campaign simulation sends no messages.
- **Authentication:** single-merchant localhost proof of concept. Production identity, tenant isolation, deployed role enforcement, TLS, quotas and operational controls must be added before exposing this to real merchants.

Confidential seller floors stay on the server. Financial checks are deterministic and separate from the language model. An eligible quote is pending approval; the LLM cannot authorize a payment.
