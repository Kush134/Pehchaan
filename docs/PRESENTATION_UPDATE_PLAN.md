# Pehchaan presentation update plan

Reviewed source: `/Volumes/DevSSD/Downloads/Presentation 3.pdf`, all seven pages, visually inspected on 14 November 2026. This is a content review and complete replacement-copy plan; the original PDF has not been edited.

## Positioning for the current prototype

**Pehchaan - the Hindi/Marathi growth copilot for owner-run kiranas.**

**One sentence:** Pehchaan helps kirana owners understand customer purchase patterns, approve offers within their margins, and compare bulk deals within clear financial limits.

Primary customer: the owner of one independent kirana in Wakad, Pune, with a 1-3-person team, recurring neighbourhood customers, Hindi/Marathi preference and usable, consented customer-linked purchase history. This is the chosen initial segment, not a completed market study. The bulk buyer and seller are separate roles in the negotiation demonstration.

The implemented product is a browser merchant workspace. Its virtual Soundbox is a simulator with genuine configured Sarvam language/speech capabilities. Native Paytm hardware, Consumer App offers, production transaction feeds and real payment processing remain future integration work.

## What to change on the original seven pages

### Original page 1: cover and elevator pitch

Keep the Pehchaan name, Devanagari identity and blue/white palette. Replace the subtitle with **"The Hindi/Marathi growth copilot for owner-run kiranas."** Replace the long elevator paragraph with the one-sentence proposition above. Use an actual dashboard or customer-detail screenshot.

Remove or move to the roadmap: autonomous execution on existing Soundbox hardware; offers delivered inside the Paytm Consumer App; a spoken "Haan" unlocking cashback; "same hardware" deployment; 150+ daily beeps, 0% retained identity, and hypothetical recovered sales presented like observations. Update the submission-stage label to the actual current stage.

### Original page 2: problem statement

Split this into customer, recurring problem and illustrative economics slides. Describe the counter owner's decisions: which regular needs review, which offer is affordable, and which bulk quotation meets constraints. State daily checking and weekly reviews as workflow hypotheses awaiting field validation.

Remove unsupported universal or numerical claims: 14-hour shifts, 150+ beeps/day, 0% visibility, <2% retention action, 40% revenue concentration and 25-30% cash-flow decline. Do not attribute a smaller basket to quick commerce from store transaction history alone. Replace categorical claims that dashboards/CRM fail with a usability question the pilot can test.

### Original page 3: proposed solution

Replace the autonomous four-step hardware loop with **signal -> eligible proposal -> local-language review -> explicit approval -> feedback**. Add three core capabilities: Comeback, Voice Copilot, and Haggle with mandate guardrails.

Current evidence supports RFM/cadence/spend calculations, editable campaigns, margin checks, approval, A/B/control assignments and simulated redemptions. Remove implemented-sounding claims of nightly automation, a 15-minute quiet-hour trigger, the mathematically highest-ROI offer, native wallet cashback or exact verified attribution. These can appear as future ideas only if the team still intends to build them.

### Original page 4: technology and architecture

Replace AWS Bedrock/Claude/Bhashini and the four old specialist-agent boxes with the actual implementation: Next.js/React/TypeScript; FastAPI/Python/Pydantic; PostgreSQL/SQLAlchemy; Redis/SSE events; LangGraph negotiation; Sarvam language, speech and document adapters; deterministic Python financial policy checks.

Replace native Paytm webhooks, wallet settlement and hardware/WebSocket flows with current application boundaries. Describe HMAC signatures as policy-envelope integrity, rather than proof of anonymous customer identity or regulatory compliance. Remove blanket zero-PII and DPDP-compliant claims. Production identity, permissions, tenant isolation and authorised data integration remain deployment work.

### Original page 5: USP and competition

Remove "only Paytm can build," automatic identification of all customers, zero-UI hardware deployment and assumptions about competitors sharing phone numbers or failing. Give existing products credit for documented analytics, billing, ledger, language and loyalty capabilities.

Use this differentiation hypothesis: **"A kirana owner can move from a reviewed customer signal to an affordable, merchant-approved action in Hindi or Marathi, then inspect the outcome in the same workspace."** Add bounded negotiation and deterministic enforcement as supporting product strengths. Easier use and greater value than alternatives still require comparison with real merchants.

### Original page 6: impact and benefits

Replace 15-22% churn recovery, Rs 8,000-15,000 recovered sales, 10-second operation and underwriting improvements with an illustrative opportunity and proposed pilot metrics. Revenue divided by discount expense is not incremental profit or ROI. Discounts and software/service costs must be accounted for.

Show implemented order tracking with packing, explicit human delivery confirmation and simulated payment states. Do not claim native consumer rewards, real settlement or proved merchant growth.

### Original page 7: business model

Lead with proposed basic insights plus a paid workflow subscription. Treat Rs 49, 10% success fees, 50% brand funding and adoption/ARR calculations as unvalidated ideas; remove them from the main pitch unless a stated assumption and cost model justify them.

Do not imply signed brand sponsorship, Paytm distribution, access to the entire Soundbox base, automatic merchant acquisition or subscription billing already implemented. Performance fees need defensible incremental attribution; brand sponsorship can be a later experiment.

## Complete replacement presentation: 15 main slides

### 1. Pehchaan - the kirana growth copilot

**On-slide copy**

- The Hindi/Marathi growth copilot for owner-run kiranas
- Understand customer patterns. Approve affordable offers. Compare bulk deals within limits.
- Track 1: Merchant Growth AI | Team and presenter names

**Visual:** one real product screenshot, with the current blue/white identity.

**Speaker line:** "We are building an AI business partner for a specific neighbourhood shop owner who handles growth decisions while running the counter."

### 2. Our initial customer

**On-slide copy**

- One independent kirana in Wakad, Pune; 1-3-person team
- Recurring neighbourhood households; Hindi or Marathi preferred
- QR payments and usable, consented customer-linked purchase history
- Owner handles customer follow-up and purchasing without a growth analyst

**Visible qualification:** Chosen initial segment; merchant interviews and data eligibility still need validation.

**Speaker line:** "A QR sticker alone does not guarantee the history we need. We start with eligible shops and verify the data with the owner."

### 3. The recurring merchant decisions

**On-slide copy**

- Which regular's recorded visits or spending have slowed?
- What response fits the shop's budget and margin?
- Which bulk deal meets price, stock and delivery requirements?
- Designed for daily checks and weekly retention reviews

**Visible qualification:** Problem frequency is a pilot hypothesis, not a measured segment statistic.

**Example:** usual visit cadence 5 days; no recorded visit for 20 days -> review with the owner. This does not establish churn or purchases at a competitor.

### 4. An illustrative cost scenario

**On-slide copy**

- 10 regulars x 2 missed purchases/month x Rs 300 basket = **Rs 6,000 revenue potentially at risk/month**
- At an assumed 22% gross margin = **Rs 1,320 gross profit potentially at risk**, before offer costs
- Separate time scenario: 20 minutes/day x 26 days = **8h 40m/month**

**Required visible label:** Illustrative assumptions, not measured losses or promised savings.

**Speaker line:** "These numbers make the opportunity concrete. The pilot must measure the real baseline and the cost of any offer."

### 5. Existing alternatives and the workflow we are testing

**On-slide copy**

| Product/category | Documented capabilities |
| --- | --- |
| Paytm Payment Analytics | Customer trends, RFM and retention cohorts; payment-gateway product scope |
| Vyapar | Billing, inventory and business reports |
| Khatabook | Ledger, reminders and multiple languages |
| Loyalty platforms such as EasyRewardz | Rewards, segmentation, personalised engagement and AI assistance |

**Proposed gap:** a short, local-language workflow connecting an explainable signal to a margin-eligible action, explicit approval and controlled feedback for our chosen owner.

**Speaker line:** "We are testing the combination and ease of use. We are not claiming that analytics, rewards or AI tools are new."

**Sources:** [Paytm](https://business.paytm.com/payment-analytics), [Vyapar](https://vyaparapp.in/blog/vyapar-app-features/), [Khatabook](https://khatabook.com/en/), [EasyRewardz](https://easyrewardz.com/industries/consumer/).

### 6. One product, three core capabilities

**On-slide copy**

1. **Comeback:** explain customer signals, prepare eligible offers and compare outcomes
2. **Voice Copilot:** discuss and review actions in Hindi or Marathi, with separate approval
3. **Haggle with guardrails:** compare seller-agent quotes within financial and fulfilment limits

**Supporting layer:** analytics, dashboard, catalogue, imports, order ledger and audit trail.

**Speaker line:** "There are three things to remember; the supporting screens make those workflows usable."

### 7. Demo 1 - recognise a regular and prepare a comeback

**On-slide copy**

- Inspect purchase history, RFM, personal visit cadence and spending changes
- Edit the audience, offer, minimum bill and budget
- Check margin eligibility and approve the campaign
- Compare A/B variants with a control; inspect simulated redemptions and discount expense

**Visual:** customer-detail screenshot and one campaign view.

**Speaker line:** "The metric explains why the owner should review a customer; it does not automatically prove that the customer is lost."

### 8. Demo 2 - review an action in Hindi or Marathi

**On-slide copy**

- Speak or type a merchant request
- Sarvam transcribes/interprets it into a structured proposal
- Review the proposal and approve separately
- Resume saved conversations; use text when voice is inconvenient

**Visible qualification:** Browser Soundbox simulator; no deployment on Paytm hardware.

**Speaker line:** "The language model prepares the proposal. The owner retains approval authority."

### 9. Demo 3 - negotiate a bulk requirement

**On-slide copy**

- Upload a grocery list/parchi or type a bulk requirement
- Review products, quantities, budget and delivery date
- Compare three seeded seller agents through up to four rounds
- Review the eligible bundle; pause, resume or cancel; confirm explicitly

**Visible qualification:** Simulated counterparties, not a live network of participating shops.

**Speaker line:** "The current fixture is an office/event bulk-buyer request against wholesale catalogues. It demonstrates controlled procurement; a merchant bulk-sales marketplace would require separate onboarding and validation."

### 10. Financial guardrails and order completion

**On-slide copy**

- Independent Python rules check buyer budget, private seller floor, stock and delivery
- A Rs 95,000 proposal against a Rs 40,000 buyer budget is rejected
- Order confirmation requires merchant approval and buyer confirmation
- Simulated authorisation -> packing -> human delivery confirmation -> simulated settlement release

**Speaker line:** "A language model cannot override these policy checks. Packing images support review; they do not prove delivery or authorise payment."

**Visible qualification:** Payment simulation; no real Paytm or UPI money movement. This is a mandate firewall, not a claim of complete cybersecurity.

### 11. Business performance and campaign evidence

**On-slide copy**

- Track sales, returning/at-risk customers and average basket from stored records
- Inspect campaign returns, redemptions and discount expense
- Review bulk orders, fulfilment and simulated payment status
- Separate observed outcomes from preliminary estimates of incremental profit

**Visual:** actual dashboard or campaign-result screenshot.

**Speaker line:** "A returning customer is an observation. Claiming that our campaign caused the return needs a control and sufficient evidence. Current outcomes are synthetic."

### 12. How the working POC is built

**On-slide copy**

- **Interface:** Next.js, React and TypeScript
- **Application/data:** FastAPI, Python, PostgreSQL and SQLAlchemy
- **Workflows/events:** LangGraph, Redis and SSE
- **AI:** Sarvam language, speech and document interpretation
- **Authority:** deterministic arithmetic, mandate checks and human approvals

**Short status line:** Working local POC; synthetic merchant records; simulated campaigns/payments; genuine configured AI calls with labelled fallback paths.

**Speaker line:** "AI handles interpretation; Python calculates and enforces financial constraints; the owner authorises actions."

### 13. Why this workflow could be useful

**On-slide copy**

- Explain the customer signal before recommending action
- Check affordability before approval
- Offer Hindi/Marathi access with saved context
- Connect actions, policy decisions and outcome review in one workspace

**Single workflow line:** Signal -> eligible proposal -> local-language review -> approval -> feedback.

**Visible qualification:** Differentiation hypothesis; comparative usability and merchant value remain to validate.

### 14. Proposed business model

**On-slide copy**

- Basic customer insights as the entry tier
- Paid merchant-growth subscription for advanced workflows
- Test willingness to pay against owner time and contribution profit after incentives
- Model service costs: language/speech calls, infrastructure, onboarding and support

**Speaker line:** "We will validate pricing through usage and value. Paytm distribution, brand sponsorship and performance fees are possible future experiments, not current agreements."

**Visible qualification:** Proposed model; billing, prices and commercial partnerships are unimplemented/unvalidated.

### 15. Validation plan and closing

**On-slide copy**

- Proposed pilot: **10 eligible kiranas, 4 weeks**
- Verify permissions and baseline workflow time before intervention
- Measure return visits, discount expense, contribution profit and owner task time with appropriate controls
- Test owner comprehension and willingness to pay

**Closing:** "Pehchaan helps the neighbourhood kirana turn a customer signal into an approved action."

**Ask:** access to eligible merchant pilots and guidance for authorised data/payment integration.

**Visible qualification:** Proposed validation, not existing traction. A short pilot may establish feasibility without proving long-term ROI.

## Appendices

### A. Supporting features already in the prototype

- Customer detail, purchase history, RFM/cadence/spend indicators and weekly cohorts
- Editable campaigns, control groups, simulated redemption records and contribution estimates
- Natural-language bulk requirements and reviewable parchi/document extraction
- Product catalogue CRUD/import and editable extracted lines
- Transaction CSV template/import/export and duplicate protection
- Hindi/Marathi voice, text fallback, saved conversations and language preference
- Agent graph, execution summaries, policy decisions and persistent audit activity
- Order, packing, human delivery confirmation and simulated settlement ledger

### B. Current boundaries and production roadmap

- No native Soundbox deployment or Consumer App cashback distribution
- No real customer messaging, payment processing or production Paytm integration
- No onboarded marketplace of real sellers, paying customers or completed merchant pilot
- Add authenticated identities, tenant/role controls and authorised data access before production
- Evaluate data coverage, customer permissions, reliability, provider cost and merchant usability

### C. Sources and assumptions

- The original seven-page PDF is the source of the old presentation claims, not proof of those claims.
- Feature implementation: `docs/ARCHITECTURE.md`; actual UI recordings in the walkthrough artifacts.
- Claim boundaries: `docs/PITCH_EVIDENCE.md`; coherent narration: `docs/PITCH_STORY.md`.
- Primary merchant-digitisation study: [Bhattacharjee et al., 2024](https://www.mdpi.com/0718-1876/19/3/83), 285 owners in five metros, survey in mid-2022. Supports testing cost/usefulness/ease of use; does not establish present Pune losses or Pehchaan impact.
- Competitor sources are linked on slide 5. Public feature pages establish documented capabilities, not the absence of other features.
- All opportunity calculations, pricing, adoption and pilot assumptions must be labelled.

## If the submission is capped at seven slides

1. Product and exact initial customer
2. Recurring problem and illustrative cost
3. Three core capabilities and connected decision workflow
4. Actual architecture, financial guardrails and POC status
5. Fair alternatives and differentiation hypothesis
6. Demo evidence, order lifecycle and proposed pilot metrics
7. Proposed business model, go-to-market test and closing ask

Keep detailed features and source tables in an appendix only if the submission rules allow one. Do not cram the 15-slide copy into seven pages.

## Demo priorities

Show the three capabilities using the same story: review a slowed regular and prepare an eligible campaign; use Hindi/Marathi to review a proposal; compare a bulk basket and reject a proposal outside the budget. Show people approving actions, then the simulated order/payment record. Use the existing pitch video for the narrative and the full walkthrough when a judge asks about supporting screens.

## Visual changes

Preserve navy, cyan and white. Use actual product screenshots in place of future hardware or wallet illustrations. Give each page one purpose and keep most to 3-4 concise points. Put implementation details and definitions in notes/appendix. Keep assumptions visible next to financial figures, and simulation labels next to POC outcomes. Add citations in speaker notes and visible source labels where a comparison or quantitative claim needs them.
