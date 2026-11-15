# Soundbox merchant workspace

Soundbox combines the merchant conversation with five working tool tabs:

- **Business overview:** last-seven-day revenue and itemized best sellers, expiring batches, low stock, and evidence → explanation → action → expected benefit.
- **Record a sale:** quick-click product/variant cart, Hindi/Hinglish voice proposals, barcode/QR lookup and supported-browser camera decoding, CSV/POS import/export, invoices and WhatsApp receipt drafts.
- **Inventory & expiry:** batch receipts, expiry dates, first-expiry-first-out consumption, stock corrections/write-offs, SKU/barcode/variant profiles, reorder thresholds, supplier drafts and explicit physical-receipt confirmation.
- **Udhar khata:** credit sales, oldest-invoice-first repayment allocation, persistent outstanding balances and reviewable WhatsApp reminder drafts.
- **Reports & expenses:** recorded operating costs, an explained business-health heuristic, a bounded linear revenue forecast with a rolling error estimate, peak transaction hours, same-basket product combinations and daily summaries.

Say “2 kilo chawal aur 1 packet biscuit becha” to prepare a sale. Review its product names, variants, units and prices, then say “Haan” or use Approve. Ambiguous products and incompatible spoken units require clarification; no stock changes until approval. Whole quantities represent the catalogue unit, including a 5 kg bag when that is the SKU unit.

Ask “Pichle hafte sabse zyada kya bika?”, “Kaun sa maal expire hone wala hai?”, “Business health score”, or “Aaj ki business summary”. These answers use stored product lines, batches, costs and expenses and continue without an LLM. The separate 28-day itemized sample is explicitly synthetic; legacy total-only bills are never attributed to invented products. Waiting times are unavailable because arrival/service timestamps are not recorded.

WhatsApp buttons prepare text and open a reviewable WhatsApp draft. They do not claim an automatic send. SMS delivery, customer acceptance through an offer link, and one-time checkout redemption are separate states. The local SMS preview never sends a message and cannot accept a real notification.

The “Demo response” badge was removed from the merchant conversation. Provider errors remain actionable, and synthetic financial records retain their labels.
