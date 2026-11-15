# Validation record

Native verification on 14 November 2026 used PostgreSQL 17, Redis on localhost:6380, Python 3.12, Node 20.19, and Chromium. The application is a single-merchant local proof of concept, with synthetic customers and simulated payments.

## Functional and integration checks

- Backend: 62 Pytest tests passed; Alembic migrations applied against PostgreSQL.
- Frontend: seven Vitest request-boundary tests passed; strict TypeScript and ESLint passed with no warnings.
- The optimized Next.js production build passed and its standalone server was started successfully.
- Playwright: 14 browser integration tests, including the phone catalogue regression.
- Browser coverage includes dashboard/navigation, recoverable outages, customer filtering, catalogue CRUD, campaign creation/approval/control allocation/redemptions, genuine voice proposals, firewall rejection, pause/resume and four-round negotiation, dual order approval, human delivery confirmation, simulated release, and demo reset.
- A connected judge-guide test verifies that its scenes execute real campaign, negotiation, and firewall endpoints.
- Hindi and Marathi browser audio tests generate known speech fixtures through the genuine Sarvam TTS adapter, feed them through Chromium's test microphone and MediaRecorder, upload the recording to genuine STT, and verify a structured proposal without executing it before approval. The test microphone is synthetic test input, not a claim about a person's recording.
- Genuine Sarvam chat, Hindi/Marathi TTS and STT, and Document Intelligence extraction were verified with the supplied subscription. Provider errors and local fallbacks remain explicitly labelled. See [Sarvam contracts](SARVAM.md).
- npm audit: zero known vulnerabilities after the development-tool dependency override. Source secret scan passed; root `.env` is ignored and mode 0600. No subscription key is in frontend source.

## Browser layout

A read-only sweep visits all ten modules at widths 1440, 1024, 768 and 390. No browser runtime exceptions were observed; the corrected catalogue was rechecked at all four widths without page overflow. It identified and corrected an absolutely positioned accessibility label escaping the catalogue table's scroll container; a phone-specific regression test covers this case. Tables remain horizontally scrollable within their panels.

Geist is self-hosted through Next's local-font support. Desktop/mobile screenshots are available in the local ignored `.runtime/qa/final/` directory.

## Visual-skill checker

`GATE: FAIL 23 (round 2 of 3)` was the initial midnight-theme marketing-layout checker result. It is **not** a passed gate. The user explicitly requested a working multi-module command center and rejected a landing page or giant hero, so the application intentionally preserves its sidebar, dense dashboard panels, differently sized data figures, and compact footer. The checker expects full-screen marketing sections, a full-screen hero, one heading per section, one heading scale, centered viewport margins, an animated marketing moment, and a `.wrap` container; these rules conflict with the requested application layout. It also misclassified a real audit-event explanation as an image caption. Its color-contrast and keyboard-focus findings were addressed, and a real mobile overflow issue was corrected through browser inspection. No checker files were modified or findings hidden.

The user subsequently requested a Paytm-inspired blue-and-white theme and removal of the global Demo Mode badge. The current interface uses light surfaces, navy text, blue/cyan actions, Geist typography, restrained Motion transitions, and real Recharts/React Flow application visuals. Operation-specific synthetic-data, simulated-payment, and provider-fallback labels remain visible. Its copy is operational and merchant-specific. All customer and transaction figures come from the seeded database. No stock photography, testimonials, or external customer claims are used.

## Execution limits

Docker Compose YAML and the container definitions are supplied, but Docker execution was not verified: this machine has no running Docker daemon or Compose v2 plugin. Native PostgreSQL/Redis execution was verified. Paytm remains disabled; packing-image inspection is a local human-review advisory. Production authentication, tenant isolation and deployment hardening remain outside this local hackathon proof of concept.
