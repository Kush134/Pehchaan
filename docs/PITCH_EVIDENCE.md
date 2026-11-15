# Pehchaan: pitch evidence and claim boundaries

Research checked: **14 November 2026**. This is primary-source desk research, not completed merchant interviews or a measured product pilot. The video should present a working proof of concept and a testable company proposition.

## Exactly who we are building for

Our **chosen initial customer segment** is the owner of one independent, neighbourhood kirana in Wakad, Pune, with one to three staff, recurring local customers, a Paytm QR, and a preference for Hindi or Marathi. The owner handles the counter, customer follow-up and supplier purchases. These are product-focus choices, not survey findings about every kirana.

Eligibility also requires enough authorised, customer-linked purchase history to estimate an individual customer's usual buying pattern. A QR sticker alone does not establish that usable, stable customer identity is available. Cash purchases or purchases through other channels can make a customer appear absent; the owner must be able to review and correct the signal. Production data access, customer-contact permissions and tenant isolation remain future integration work.

**Problem hypothesis:** during counter work, the owner may overlook a regular whose visits have slowed, then struggle to choose an economical response and separately compare supplier quotes. We are testing whether a short, local-language, approval-led workflow makes those decisions easier.

## How often does the problem happen?

The proposed workflow is a daily opportunity check and a weekly review of regulars and campaign outcomes. Those are design choices; we have **not measured the frequency or severity of this problem in the initial segment**.

Customer-specific cadence matters. For example, a customer who usually buys every five days but has not visited for fifteen days may warrant review. That is an illustrative signal, not proof that the customer has switched shops or will respond to an offer. A retention signal cannot establish a lost sale by itself.

## What research supports the direction?

[Bhattacharjee, Kumar, Verma and Maiti (1 July 2024)](https://www.mdpi.com/0718-1876/19/3/83) studied digitalisation using a survey of 285 kirana owners in Delhi, Kolkata, Bangalore, Hyderabad and Chennai. The survey was conducted in mid-2022. Cost, compatibility, ease of use and usefulness affected intention to digitalise. The authors also discuss affordable technology and vernacular access. This supports testing a simple, useful and affordable workflow; the sample does not establish current Pune churn, daily time spent, willingness to pay, or Pehchaan's impact.

The targeted source review did not establish a trustworthy published loss or task-time figure for this exact initial segment. Do not replace missing evidence with a national estimate or a vendor's case-study result.

## Economics: an illustrative scenario, not measured losses

Keep **“Illustrative assumptions — not merchant results”** visible during the calculation.

| Assumption or calculation | Result | What it means |
| --- | ---: | --- |
| 10 regulars × 2 missed purchases per month × ₹300 assumed basket | ₹6,000/month | Revenue potentially at risk in this example; neither verified lost sales nor recoverable revenue |
| ₹6,000 × 22% assumed gross margin | ₹1,320/month | Associated gross profit potentially at risk, before campaign costs and fixed costs; not net profit |
| 20 assumed minutes/day × 26 working days | 520 minutes = 8h 40m/month | Illustrative time spent on follow-up/quote tasks; not proven time savings |

These are different measures. Do not add them together as one financial loss. Twenty-two percent is an assumed margin, not an industry benchmark. A discount can reduce profit, so campaign evaluation must account for offer costs and purchases that would have happened anyway.

Safe narration: “Here is one scenario to make the opportunity concrete. Ten regulars missing two three-hundred-rupee purchases means six thousand rupees of monthly sales at risk. These are assumptions, and our pilot must measure the real baseline.”

## Existing solutions: give them credit

The comparison below describes documented capabilities. Public feature pages cannot prove that a competitor lacks a capability, nor that its product fails for kirana merchants.

| Alternative | What its official material already offers | Implication for our pitch |
| --- | --- | --- |
| [Paytm Payment Analytics](https://business.paytm.com/payment-analytics) | New/repeat/lost-customer trends, churn, retention cohorts and RFM segmentation, including at-risk groups. This page concerns online payment-gateway analytics. | Do not claim that retention analytics or RFM are new, or that every kirana QR merchant already receives this exact product. |
| [Paytm for Business](https://business.paytm.com/) | Payment tools, POS billing, m’Loyal loyalty/marketing, Ads, Mini Apps and WhatsApp-oriented tools are listed. | Do not describe Paytm as “only payments” or say that it has no growth tools. |
| [Vyapar feature list](https://vyaparapp.in/blog/vyapar-app-features/) and [low-stock guide](https://vyaparapp.in/guides/how-to-set-a-low-stock-alert-in-vyapar) | Billing, stock management, reports, unpaid-invoice tracking, reminders and UPI collection. Inventory can generate low-stock warnings and exportable reports after setup. | Do not claim that billing apps cannot manage inventory, report on a shop or trigger operational alerts. |
| [Khatabook](https://khatabook.com/en/) | Customer/transaction records, automatic payment reminders, reports and multiple languages. | Local-language access and reminders alone are not unique. Payment collection reminders are also different from our proposed missed-visit decision workflow. |
| [EasyRewardz retail solutions](https://easyrewardz.com/industries/consumer/) | Personalised loyalty/rewards, automated segmentation, campaign engagement, analytics, AI assistance and omnichannel messaging. | Do not claim that personalised offers, automated engagement or AI loyalty tools do not exist. |

**Our differentiation hypothesis:** a small-store owner can move from a reviewed customer signal to a merchant-approved, budget- and margin-constrained action in Hindi or Marathi, then inspect an experiment; the same workspace supports bounded supplier negotiation and deterministic financial checks. The combination and usability are what we are testing. We have not established market exclusivity or comparative superiority.

Suggested narration: “Payments, accounting and loyalty tools already solve important parts of this problem. Our focus is the owner’s next decision: whom to follow up with, what the shop can afford, and what must be approved before an action happens.”

## One product, three core capabilities

One-sentence proposition: **“Pehchaan helps owner-run kirana stores turn customer purchase patterns into approved comeback campaigns and safer bulk-purchase decisions, in Hindi or Marathi.”**

The three core prototype capabilities are:

1. **Recognise and test:** explain an overdue regular's purchase pattern, configure a comeback offer, allocate treatment/control groups and simulate redemptions.
2. **Converse and approve:** use Hindi/Marathi voice or text to review an action, then explicitly approve it. Language models propose; the merchant authorises.
3. **Negotiate within limits:** compare three simulated seller agents over four rounds, enforce deterministic financial mandates, inspect rejection reasons and confirm the chosen simulated order.

The catalog, ledger, settings, customer detail view and activity log support these capabilities. Avoid presenting every screen as a separate product.

For a focused demo, show two complete journeys: **bring back a regular** and **choose a bulk order within limits**. The mandate rejection is the trust moment inside the second journey. Voice approval is demonstrated inside the first journey. Keep the same shop owner and decision story throughout.

## Company and business model framing

Proposed model: a merchant software subscription with a basic insights tier and a paid workflow tier. Pricing, conversion, retention and willingness to pay are unvalidated; the prototype does not implement subscription billing. A Paytm integration or distribution partnership is a future route to investigate, not an existing affiliation.

The initial business test is whether measurable incremental gross profit and task-time benefits justify the merchant's fee after offer costs and service costs. Do not promise a specific ROI, claim paying customers, or use a hypothetical subscription as realised revenue.

## What is demonstrated and what remains to validate

The current repository demonstrates analytics, local-language assistance, reviewable proposals, experiment mechanics, negotiation and policy checks. Its seeded customers and transactions are synthetic. Customer messaging and Paytm authorisation/payment/settlement are not live; order/payment lifecycle events are simulated. Sarvam responses are genuine only when the configured service is available, with labelled fallback paths otherwise. A prototype UI recording is evidence of workflow implementation, not evidence of merchant growth.

Next validation work, **not work already completed**: interview the initial segment; measure a baseline of missed-visit review, existing tools and task time; confirm authorised data availability; run a consented pilot with an appropriate control; measure incremental purchases and gross profit net of incentives; test owner comprehension, approval errors, time spent and willingness to pay. This is what turns the current opportunity scenario into defensible customer and company evidence.

## Claims to remove from pitch copy

- “Every kirana loses ₹6,000,” “we save eight hours,” or “22% is the standard kirana margin.”
- “Paytm only processes payments,” “competitors have no retention intelligence,” or “existing solutions are failing.”
- “Our AI knows a customer has churned” when it has detected only a cadence deviation.
- “Recovered revenue” for synthetic campaign redemptions or an uncontrolled before/after comparison.
- “Live Paytm integration,” “autonomous real payments,” “paying merchants,” or “proven ROI.”

No verbatim excerpts from the web sources are used here. Each source's derived summary is deliberately short; keep additional source-derived video text within its applicable quotation and summarisation limits.
