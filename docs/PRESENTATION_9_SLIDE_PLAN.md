# Pehchaan: final nine-slide presentation plan

This plan supersedes the earlier 15-slide recommendation. Keep and rewrite all seven original pages. Add only an economics slide and a prototype-demo slide. The original PDF is not edited.

| Final slide | Source |
| --- | --- |
| 1. Pehchaan: the kirana growth copilot | Original 1 |
| 2. Our merchant and the recurring problem | Original 2 |
| 3. An illustrative monthly cost | New |
| 4. One product, three core capabilities | Original 3 |
| 5. The working prototype demo | New |
| 6. Actual architecture and POC status | Original 4 |
| 7. Existing alternatives and our difference | Original 5 |
| 8. Measuring merchant value | Original 6 |
| 9. Proposed business model and next step | Original 7 |

## 1. Pehchaan: the kirana growth copilot (original 1)

Keep the brand, Devanagari identity and navy/cyan/white palette.

**Replace subtitle:** The Hindi/Marathi growth copilot for owner-run kiranas.

**One sentence:** Pehchaan helps kirana owners understand customer purchase patterns, approve offers within their margins, and compare bulk deals within clear financial limits.

Use a real dashboard screenshot. Remove implemented-sounding native Soundbox deployment, Consumer App cashback and one-word payment activation. Add the team and correct submission stage.

## 2. Our merchant and the recurring problem (original 2)

**Copy:**

- Initial segment: one owner-operated kirana in Wakad, Pune; 1-3-person team; Hindi/Marathi preference.
- Owner serves recurring local households and handles customer follow-up and purchasing.
- Decisions: which regular slowed down, which offer is affordable, and which bulk deal satisfies constraints?
- Designed for daily checks and weekly reviews; actual frequency remains to validate.

Small qualification: the workflow needs usable, consented customer-linked history; a QR sticker alone is insufficient.

Remove unsupported figures for beeps, visibility, retention adoption, shifts and cash-flow decline. Recorded absence or smaller baskets do not establish quick-commerce switching.

## 3. An illustrative monthly cost (new)

**Copy:**

- 10 regulars x 2 missed purchases x Rs 300 = Rs 6,000 revenue potentially at risk/month.
- At an assumed 22% gross margin: Rs 1,320 gross profit potentially at risk, before offer costs.
- Separate time scenario: 20 minutes x 26 days = 8h 40m/month.

Keep visible: **Illustrative assumptions, not measured losses or promised savings.** Do not add time and money as one loss or claim all at-risk revenue can be recovered.

## 4. One product, three core capabilities (original 3)

**Copy:**

1. Comeback: customer history/RFM/cadence, eligible offers, merchant approval and A/B/control evaluation.
2. Voice Copilot: Hindi/Marathi speech or text, structured proposals, separate approval and saved conversations.
3. Haggle with guardrails: reviewed bulk requirements, three seller agents, up to four rounds and bounded deal selection.

Supporting tools: dashboard, catalogue/documents, CSV import/export, order ledger and audit history.

Workflow: **Signal -> eligible proposal -> review -> approval -> feedback.**

Remove highest-ROI guarantees, quiet-hour automation, live cashback and exact verified attribution as current capabilities. Label any retained future ideas as roadmap items.

## 5. The working prototype demo (new)

Use three real screenshots or a short embedded recording:

- Comeback: inspect one customer and prepare the Rs 15 off / Rs 250 minimum-bill offer; show control allocation and simulated outcomes.
- Voice: a Hindi/Marathi request becomes a reviewable proposal, followed by explicit approval.
- Haggle: review a grocery requirement, compare three seeded sellers and reject Rs 95,000 against a Rs 40,000 buyer budget.

Finish the third flow with merchant + buyer confirmation and the order ledger: simulated authorisation -> packed -> human delivery confirmation -> simulated settlement.

Keep visible: synthetic records, simulated sellers/payments, browser Soundbox simulator. The current bulk fixture uses an office/event buyer against wholesale catalogues; it is not an onboarded marketplace of real kiranas.

## 6. Actual architecture and POC status (original 4)

**Copy:**

- Next.js/React/TypeScript interface -> FastAPI/Python -> PostgreSQL/SQLAlchemy.
- LangGraph for bounded negotiation; Redis/SSE for application events.
- Sarvam for language, speech and document interpretation.
- Deterministic Python arithmetic/policy checks and explicit human approvals.

**Explain:** AI interprets; Python calculates and validates; people authorise.

Replace Bedrock/Claude/Bhashini, native Paytm rails and hardware/WebSocket diagrams. HMAC protects policy-envelope integrity; it does not establish universal anonymity or compliance.

Footer: working local POC; genuine configured AI calls with labelled fallbacks; synthetic merchant records; simulated outcomes/payments. Authorised live integrations, identity and tenant controls remain production work.

## 7. Existing alternatives and our difference (original 5)

**Fair comparison:**

- Paytm Payment Analytics: customer trends, RFM and cohorts, in its payment-gateway product scope.
- Vyapar: billing, inventory and reports.
- Khatabook: ledger, reminders and multiple languages.
- Loyalty platforms such as EasyRewardz: rewards, segmentation, personalised engagement and AI assistance.

**Our differentiation hypothesis:** a small-store owner can move from an explained signal to a margin-eligible action, review it in Hindi/Marathi, approve it, and inspect feedback in one workspace.

Remove exclusivity, "100% automatic," blanket competitor-failure and proven-superiority claims. Financial security should be described as a deterministic mandate firewall, not complete AI cybersecurity.

Sources: https://business.paytm.com/payment-analytics ; https://vyaparapp.in/blog/vyapar-app-features/ ; https://khatabook.com/en/ ; https://easyrewardz.com/industries/consumer/

## 8. Measuring merchant value (original 6)

**Copy:**

- Dashboard: recorded sales, returning/at-risk customers and basket trends.
- Campaigns: returns, redemption/discount costs, control comparisons and preliminary contribution estimates.
- Operations: bulk orders, fulfilment, policy decisions and simulated payment status.
- Proposed pilot: 10 eligible kiranas over four weeks, measuring baseline time, return visits, offer costs, contribution profit and willingness to pay.

Remove unmeasured recovery rates, recovered revenue, verified ROI, 10-second workflow and underwriting benefits. Sales divided by discount is not incremental profit. Call current customer returns and campaign results synthetic observations, not real-world impact or causal recovery. A short pilot may establish feasibility without proving long-term ROI.

## 9. Proposed business model and next step (original 7)

**Copy:**

- Basic insights as the entry tier; paid subscription for advanced workflows.
- Validate pricing against owner time and contribution profit after incentives.
- Account for AI calls, infrastructure, onboarding and support.
- Initial acquisition test: hands-on onboarding of eligible shops in one neighbourhood.

Do not present Rs 49, a 10% success fee, 50% brand funding, adoption/ARR or Paytm distribution as validated. Move optional success-fee and sponsorship ideas out of the main deck. Billing, partnerships and prices remain unimplemented/unvalidated.

**Ask:** eligible merchant pilots and guidance on authorised data/payment integration.

**Closing:** Pehchaan helps the neighbourhood kirana turn a customer signal into an approved action.

## Presentation rules

- Nine slides total; no extra cover, thank-you or appendix page.
- Keep one purpose per slide and use real product screenshots.
- Keep the cost assumptions, synthetic-data labels and simulated-payment labels visible.
- Show three hero capabilities; discuss supporting screens when asked.
- Use source notes for competitor claims; never turn future integration into implemented capability.
