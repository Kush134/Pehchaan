# Three-minute judge walkthrough

Open `http://localhost:3000`. Every payment and transaction shown is synthetic. A blue provider indicator identifies whether Sarvam is configured; missing access uses an explicitly labelled deterministic demo response.

Before presenting, open Settings and use **Reset sample data** once if a clean run is needed. This deletes only the configured application's synthetic records. Check `/api/v1/health` and try your microphone in Soundbox Simulator before the audience arrives. Grant microphone access to localhost. Keep utterances under 30 seconds.

## 0:00–0:25 · A merchant losing regulars

Open **Overview** for Sharma Kirana Store, Wakad, Pune. Explain:

> “Paytm helps merchants receive payments. Pehchaan helps merchants earn their next payment.”

Point to at-risk regulars, the stored revenue chart, and the recommendation. Open **Customer Intelligence**, open a customer token, and show its cadence, RFM profile, risk, spend changes, and purchase history. These are patterns in this merchant's records; the app does not infer competitor purchases.

## 0:25–1:15 · Bring customers back

Open **Comeback Engine**. Create a ₹15 discount with a ₹250 minimum bill, a finite budget, and an A/B experiment including a control. Inspect the proposal and launch it. Click **Simulate redemptions** to write synthetic purchases; show conversion, discount cost, and the preliminary incremental-profit estimate.

Open **Soundbox Simulator**, choose Hindi or Marathi, press the microphone, and say:

> “पंद्रह रुपये डिस्काउंट रखो और मिनिमम बिल ढाई सौ रुपये करो।”

or:

> “पंधरा रुपये सूट ठेवा आणि किमान बिल अडीचशे रुपये करा.”

Review the transcription and structured proposal. Explicitly select **Approve action**. Play the response when Sarvam TTS is available. If microphone/API access is unavailable, enter the same command in the text box; point to the demo/provider label. Do not imply that a fallback transcript came from speech recognition.

## 1:15–2:10 · Let agents negotiate

Open **Haggle Arena**. Use the seeded grocery request with a ₹40,000 budget and a feasible delivery date, or type a request and choose **Parse request** to prepare an editable basket. Review it before starting. Start negotiation. Show the Buyer Agent and three distinct sellers in the event timeline and four-round quote comparison. Pause and resume if useful. Open **Agent Command Center** briefly to show the same run's events and graph.

Inspect **Best eligible deal**. Explain that the deterministic optimizer checks stock, delivery, budget, and private seller mandates. Quotes do not expose seller floors. Approve as merchant and confirm as buyer only when ready to create the simulated order.

## 2:10–2:35 · Block a rogue bid

Open **Mandate Firewall**. Submit ₹95,000 against the ₹40,000 buyer budget. Run the check. Point to **BLOCKED** and the budget rule. Test a below-floor offer if desired; the rejection is generic and reveals no floor. An eligible proposal still needs the specified approvals.

## 2:35–3:00 · Close the loop

Open **Transaction Ledger**. Inspect the confirmed synthetic bulk order, simulated authorization, packing and human delivery confirmation stages. Advance through the allowed lifecycle controls and see the ledger event update. No real Paytm authorization, escrow, or transfer occurs.

Return to **Overview** to see stored workflow outcomes and the live activity feed. End with:

> “PEHCHAAN — More returning customers. Better negotiated deals. Smarter merchants.”

## Built-in guide

**Start walkthrough** in Overview opens the in-product guide. Its scenes navigate the same working modules; complete the real workflow controls rather than treating the guide as disconnected animation. The manual sequence above remains available for a presenter-controlled pace.

## Further workspace checks

- Reload Soundbox after a command to show restored conversation history and the same pending proposal. It remains unexecuted until explicit approval.
- Save Marathi or Hindi as the default assistant language in Settings, then open a new conversation.
- In the ledger, download the transaction template, import a reviewed pseudonymous CSV, and export the stored transactions.
- The top bar uses the blue-and-white merchant theme without a global Demo Mode badge. Synthetic data, simulated payments, and unavailable-provider responses retain their own labels.
