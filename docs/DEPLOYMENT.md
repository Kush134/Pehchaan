# GitHub and Vercel deployment

The repository contains a Next.js frontend in `apps/web` and a FastAPI backend in `apps/api`. They deploy as separate Vercel projects so a Services beta enrollment is not required. The frontend forwards `/api/*` to the API project through its server-side `API_INTERNAL_URL` setting.

The backend uses managed PostgreSQL (Neon). Local SQLite and localhost PostgreSQL URLs must not be used in production. Plain `postgres://` and `postgresql://` connection strings are normalized to the installed Psycopg driver. Run Alembic migrations before promoting a backend deployment, and seed the synthetic merchant once; set `AUTO_SEED=false` after initialization.

## Required API environment

- `DATABASE_URL`: managed PostgreSQL connection string injected by Neon.
- `POLICY_SIGNING_SECRET`: persistent random server-side signing secret.
- `AUTO_SEED=false`, `DEMO_MODE=true`, `NOTIFICATION_CHANNEL=sms`.
- `SARVAM_API_KEY` and the configured Sarvam model names for actual speech services.
- Twilio account/API credentials, a persistent `TELEPHONY_WEBHOOK_SECRET`, and an SMS-capable sender or Messaging Service for SMS. Keep `TELEPHONY_ENABLED=false` for the SMS workflow. Current Twilio trials permit predefined SMS templates, so custom offer SMS requires the appropriate account access and sender. Never set `TWILIO_SMS_TRIAL=false` unless the account can actually send custom messages.
- `TELEPHONY_PUBLIC_BASE_URL`: the deployed API origin for signed status callbacks and offer links. A local development tunnel is not used in production.

## Required web environment

Set `API_INTERNAL_URL` to the API deployment origin. It is a server variable; no subscription credential belongs in `NEXT_PUBLIC_*`.

## Commands

```sh
make check
make test-api
make test-web
make build
# Link each project before deploying it.
vercel --prod
```

The deploy excludes `.env` files, `.venv`, `.runtime`, local recordings, build directories and test artifacts. The app manifest and service worker support installation and cached screens. Business API snapshots are available for up to 24 hours when the network is unavailable and display their fetch time; stock and payment writes are never silently replayed.

This remains the documented single-merchant proof of concept. Records, credit entries and checkout payments are synthetic. Production identity, tenant boundaries and operational controls are separate from the deployment itself.
