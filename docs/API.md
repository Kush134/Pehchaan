# API reference

Base URL: `http://localhost:8000/api/v1`.

The generated [OpenAPI UI](http://localhost:8000/docs) is the authoritative request/schema reference for the running build. [Core frontend contract](API_CONTRACT.md) describes analytics, campaigns, catalogue, firewall, events and demo reset. [Workflow contract](WORKFLOWS_API.md) describes negotiation, voice, documents, orders and simulated payments.

Requests and responses use JSON except multipart uploads and SSE. Prices are INR. The API returns validated client errors rather than treating unavailable external providers as successful calls. Mutation clients should send a stable `Idempotency-Key` for retried operations. Keep a new key for each intentional operation.

## Core workflows

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Database, Redis, provider configuration and simulation status |
| GET | `/dashboard/summary?days=30` | Stored-data metrics, trends, segments and recommendation |
| GET | `/customers?segment=All&page=1&page_size=20` | Paginated pseudonymous customer metrics |
| GET | `/customers/segments` | Segment counts |
| GET | `/customers/at-risk` | Inactive regular cohort |
| GET, POST | `/campaigns` | List/create validated campaign proposals |
| POST | `/campaigns/{id}/launch` | Allocate and activate an internal experiment |
| POST | `/campaigns/{id}/simulate-redemptions` | Write synthetic redemption/purchase outcomes |
| POST | `/campaigns/{id}/stop` | Stop future campaign operations |
| GET, POST | `/catalog/products` | Merchant product list/create |
| PATCH, DELETE | `/catalog/products/{id}` | Edit/delete a merchant product |
| POST | `/catalog/import` | Validated CSV import |
| GET | `/transactions?page=1&page_size=20` | Synthetic transaction ledger |
| POST | `/firewall/validate` | Run a sandbox proposal through deterministic policy checks |
| GET | `/firewall/audit` | Public decision audit, without confidential floors |
| GET | `/agents/status` | Agent status based on real events/runs |
| GET | `/events?limit=30` | Persistent audit activity |
| GET | `/events/stream` | SSE with replay IDs and reconnect support |
| POST | `/demo/reset` | Recreate only the configured synthetic application dataset |

The sandbox firewall check does not authorize any financial operation. Consequential order/payment paths use stored session mandates, explicit approvals and signed/replay-protected policy validation. The local demo has a single merchant; a production deployment requires authenticated tenant and role enforcement.

## SSE

The browser opens an `EventSource` connection to `/api/v1/events/stream`. Each event carries a persistent ID and a JSON payload containing type, title, detail, agent, status, timestamp and structured metadata. On reconnect, the event ID allows replay. Polling `/events` is available for an inspection client. No hidden LLM reasoning is emitted.

## Uploads

CSV and document/image/audio endpoints enforce their supported types and limits. Audio recordings must be at most 30 seconds for synchronous STT. Extracted document content is advisory and must be reviewed before persistence. See the generated schema for multipart field names and accepted fields.
