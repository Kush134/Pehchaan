"use client";
import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CreditCard, QrCode, ScanLine, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useUI } from "@/store/ui";
import { Badge, Busy, Panel } from "../shared";
import { Button } from "../ui/button";
import type { TelephonyStatus } from "./telephony";
import "./telephony.css";

const money = (amount: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(amount);

type CheckoutOffer = { id: string; customer_name: string; customer_token: string; offer_amount: number; minimum_bill: number; status: string; accepted: boolean; acceptance_source: string; redeemed: boolean };
export type CheckoutQuote = { id: string; customer_token: string; bill_amount: number; discount: number; payable_amount: number; offer_id: string | null; eligible: boolean; reason: string; simulated: true; status: "quoted" | "paid"; expires_at: string; transaction_id?: string };

export default function CheckoutPanel() {
  const client = useQueryClient();
  const notify = useUI((s) => s.notify);
  const [bill, setBill] = useState("250");
  const [selected, setSelected] = useState("");
  const [quote, setQuote] = useState<CheckoutQuote | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const paymentKey = useRef("");
  const status = useQuery({ queryKey: ["telephony-status"], queryFn: () => api<TelephonyStatus>("/telephony/status") });
  const offers = useQuery({ queryKey: ["checkout-offers"], queryFn: () => api<{ items: CheckoutOffer[] }>("/checkout/offers"), refetchInterval: 2000 });
  const customerToken = selected || status.data?.customer_token || offers.data?.items[0]?.customer_token || "";
  const customerOptions = [...new Map((offers.data?.items || []).map((offer) => [offer.customer_token, offer.customer_name])).entries()];
  if (status.data && !customerOptions.some(([token]) => token === status.data.customer_token)) customerOptions.unshift([status.data.customer_token, status.data.customer_name]);
  const accepted = offers.data?.items.some((offer) => offer.customer_token === customerToken && offer.accepted && !offer.redeemed);
  async function scan() {
    setBusy("scan"); setError(""); setQuote(null);
    try {
      const result = await api<CheckoutQuote>("/checkout/quote", { method: "POST", body: JSON.stringify({ customer_token: customerToken, bill_amount: Number(bill) }) });
      setQuote(result); paymentKey.current = crypto.randomUUID();
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(""); }
  }
  async function pay() {
    if (!quote || quote.status === "paid") return;
    setBusy("pay"); setError("");
    try {
      const result = await api<CheckoutQuote>("/checkout/pay", { method: "POST", body: JSON.stringify({ quote_id: quote.id }), headers: { "Idempotency-Key": paymentKey.current } });
      setQuote(result); await client.invalidateQueries();
      notify(`Simulated payment of ${money(result.payable_amount)} recorded.`);
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(""); }
  }
  function resetQuote() { setQuote(null); setError(""); }
  return <div id="checkout" style={{ scrollMarginTop: 25 }}><Panel title="Scan & pay with your accepted offer" subtitle="Simulated checkout · accepted offers apply automatically" action={<Badge tone="amber"><ShieldCheck size={12} />NO REAL MONEY MOVES</Badge>} className="telephony-panel">
    <div className="telephony-body checkout-grid">
      <div>
        <div className="checkout-fields">
          <label className="field"><span>Customer</span><select aria-label="Customer" value={customerToken} disabled={!!busy} onChange={(event) => { setSelected(event.target.value); resetQuote(); }}>{customerOptions.length ? customerOptions.map(([token, name]) => <option key={token} value={token}>{name} · {token}</option>) : <option value="">Loading customer…</option>}</select></label>
          <label className="field"><span>Bill amount (₹)</span><input type="number" min="1" max="100000" step="0.01" value={bill} disabled={!!busy} onChange={(event) => { setBill(event.target.value); resetQuote(); }} /></label>
        </div>
        <p className="checkout-note">{accepted ? "This customer has an accepted offer. Scan to check eligibility and apply the discount." : "Accept a comeback call first to unlock its offer. You can also scan to preview a bill without a discount."}</p>
        <div className="checkout-scan"><QrCode size={64} strokeWidth={1.4} /><div><strong>Sharma Kirana · demo checkout</strong><p>Use the button below to mimic scanning the store QR. The server checks your accepted offer and calculates the amount due.</p></div></div>
        <Button disabled={!!busy || !customerToken || !Number.isFinite(Number(bill)) || Number(bill) <= 0} onClick={() => void scan()}>{busy === "scan" ? <Busy>Checking offer…</Busy> : <><ScanLine size={15} />{quote?.status === "paid" ? "Start another simulated checkout" : "Simulate QR scan"}</>}</Button>
        {(error || status.error || offers.error) && <p className="telephony-error" role="alert">{error || status.error?.message || offers.error?.message}</p>}
      </div>
      <div aria-live="polite">
        {quote ? <div className={quote.status === "paid" ? "checkout-receipt" : ""}>
          {quote.status === "paid" && <strong><CheckCircle2 size={20} />Simulated payment complete</strong>}
          <dl className="checkout-totals"><div><dt>Bill total</dt><dd>{money(quote.bill_amount)}</dd></div><div className={quote.discount ? "checkout-discount" : ""}><dt>Accepted offer discount</dt><dd>−{money(quote.discount)}</dd></div><div><dt>{quote.status === "paid" ? "Paid in simulation" : "Amount to pay"}</dt><dd>{money(quote.payable_amount)}</dd></div></dl>
          <p className="checkout-note">{quote.reason}</p>
          {quote.status === "paid" ? <p className="checkout-note">Saved to the transaction ledger. {quote.discount > 0 ? "This offer has been redeemed and cannot be used again." : "No discount was redeemed."}{quote.transaction_id && <><br /><span className="mono">Transaction {quote.transaction_id.slice(0, 12)}</span></>}</p> : <><Button disabled={!!busy} onClick={() => void pay()}>{busy === "pay" ? <Busy>Recording payment…</Busy> : <><CreditCard size={15} />Pay {money(quote.payable_amount)} · simulated</>}</Button><p className="checkout-note">The offer and campaign budget are checked again before recording payment. If your offer changes, scan again.</p></>}
        </div> : <div className="checkout-empty"><CreditCard size={32} /><strong>Your final amount appears here</strong><p>A ₹250 bill with an accepted ₹20 offer becomes ₹230. Scan, review the discount, then confirm a simulated payment.</p></div>}
      </div>
    </div>
  </Panel></div>;
}
