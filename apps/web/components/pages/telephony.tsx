"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Phone, PhoneCall, Radio, FlaskConical, ArrowRight, RefreshCw } from "lucide-react";
import { api, post } from "@/lib/api";
import { money } from "@/lib/utils";
import { useUI } from "@/store/ui";
import { Badge, Busy, Panel } from "../shared";
import { Button } from "../ui/button";
import "./telephony.css";

export type TelephonyStatus = {
  configured: boolean; enabled: boolean; provider: string; missing: string[];
  customer_name: string; masked_phone: string; customer_token: string;
  simulation_available: boolean; supports_dtmf: boolean; note?: string;
};
export type OfferCall = {
  id: string; campaign_id: string; customer_token: string; customer_name: string;
  masked_phone: string; status: string; accepted: boolean; offer_amount: number;
  minimum_bill: number; redeemed: boolean; provider: string; error: string | null; created_at: string;
  updated_at: string; script: string;
};
export const callStateLabel = (status: string) => ({
  queued: "Queued", dispatching: "Sending to call provider", submitted: "Submitted to call provider",
  ringing: "Ringing", connected: "Connected · awaiting keypress", accepted: "Accepted · pressed 1",
  declined: "Declined · pressed 2", completed: "Call ended · no acceptance", no_answer: "No answer",
  failed: "Call failed", unknown: "Delivery uncertain · check provider", blocked: "Calling setup required",
}[status] || status.replaceAll("_", " "));

export default function TelephonyPanel({ campaignId, compact = false, offerAmount = 20, minimumBill = 200 }: { campaignId?: string; compact?: boolean; offerAmount?: number; minimumBill?: number }) {
  const client = useQueryClient();
  const notify = useUI((s) => s.notify);
  const [busy, setBusy] = useState("");
  const [actionError, setActionError] = useState("");
  const [focusedCallId, setFocusedCallId] = useState("");
  const status = useQuery({ queryKey: ["telephony-status"], queryFn: () => api<TelephonyStatus>("/telephony/status"), refetchInterval: 15000 });
  const calls = useQuery({ queryKey: ["telephony-calls"], queryFn: () => api<{ items: OfferCall[]; total: number }>("/telephony/calls"), refetchInterval: 2000 });
  async function send(simulate: boolean) {
    setBusy(simulate ? "simulate" : "call"); setActionError("");
    try {
      const result = campaignId && !simulate
        ? { call: await post<OfferCall>(`/campaigns/${campaignId}/notify`) }
        : await post<{ call: OfferCall }>("/telephony/demo-offer", { simulate });
      setFocusedCallId(result.call.id);
      await client.invalidateQueries();
      if (result.call.error) setActionError(result.call.error);
      else notify(simulate ? "Test call created. Use the test keypad below to respond." : "Call requested. Watch its live status below.");
    } catch (error) { setActionError((error as Error).message); }
    finally { setBusy(""); }
  }
  async function press(call: OfferCall, digit: "1" | "2" | "no_answer") {
    setBusy(call.id); setActionError("");
    try {
      await post(`/telephony/calls/${call.id}/simulate`, digit === "no_answer" ? { status: "no_answer" } : { digit });
      await client.invalidateQueries();
      notify(digit === "1" ? "Test offer accepted. Try a simulated checkout." : digit === "2" ? "Test offer declined." : "Test call marked no answer.");
    } catch (error) { setActionError((error as Error).message); }
    finally { setBusy(""); }
  }
  const keypadReady = status.data?.configured && status.data.supports_dtmf;
  const providerName = status.data?.provider === "twilio" ? "Twilio + Sarvam voice" : "Sarvam";
  const visible = (calls.data?.items || []).filter((call) => !campaignId || call.campaign_id === campaignId || call.id === focusedCallId).slice(0, compact ? 3 : 5);
  const loading = status.isPending || calls.isPending;
  const error = status.error || calls.error;
  return <Panel title="Call, accept, come back" subtitle="A phone invitation with live offer acceptance" action={<Badge tone={keypadReady ? "green" : "amber"}><Radio size={12} />{keypadReady ? "CALLING READY" : status.data?.configured ? "KEYPAD UNAVAILABLE" : "SETUP PENDING"}</Badge>} className="telephony-panel">
    <div className="telephony-body">
      <div className="telephony-invitation">
        <span className="telephony-phone-icon"><PhoneCall size={22} /></span>
        <div><strong>{status.data?.customer_name || "Kush"} · {status.data?.masked_phone || "Your test number"}</strong><p>{campaignId ? "Send this campaign’s offer to your test number." : "₹20 off a bill of ₹200 or more. One invitation, one accepted offer."}</p></div>
      </div>
      <blockquote className="telephony-script">“Hi Kush! You haven’t visited our kirana store recently. Get {money(offerAmount)} off an order of {money(minimumBill)} or more. To accept the offer, press 1.”</blockquote>
      <div className="telephony-actions">
        <Button disabled={!!busy || !keypadReady} onClick={() => void send(false)}><Phone size={14} />{busy === "call" ? <Busy>Requesting call…</Busy> : campaignId ? "Send notification · call Kush" : "Start ₹20 campaign & call Kush"}</Button>
        <Button variant="secondary" disabled={!!busy || loading} onClick={() => void send(true)}><FlaskConical size={14} />{busy === "simulate" ? "Creating test…" : "Try a simulated call"}</Button>
      </div>
      {status.data?.configured && !status.data.supports_dtmf && <p className="checkout-note">Keypad acceptance is unavailable on native Sarvam calls. Choose the Twilio + Sarvam route in calling settings for the press 1 flow. You can try the complete flow with a simulated call below.</p>}
      {status.data && !status.data.configured && <details className="telephony-setup"><summary>Connect phone calling to ring your phone</summary><p>Your speech key powers Soundbox. Phone calls also need a connected telephony provider, an outbound number, and a public callback URL. The configured route is {providerName}. Add the missing settings to the root .env and restart the API.</p><p className="mono">{status.data.missing.join(" · ")}</p><p>Setup guide: docs/TELEPHONY.md. The test call below works while you connect calling.</p></details>}
      {(actionError || error) && <div className="telephony-error" role="alert">{actionError || error?.message}<Button size="sm" variant="ghost" onClick={() => { void status.refetch(); void calls.refetch(); }}><RefreshCw size={12} />Refresh</Button></div>}
      <div className="telephony-call-list" aria-live="polite" aria-atomic="false">
        {loading ? <p className="telephony-muted">Loading call activity…</p> : visible.length === 0 ? <p className="telephony-muted">No calls yet. Start an invitation to see ringing, acceptance, and redemption here.</p> : visible.map((call) => <article className="telephony-call" data-call-id={call.id} key={call.id}>
          <div className="telephony-call-heading"><div><strong>{call.customer_name}</strong><span>{money(call.offer_amount)} off · {money(call.minimum_bill)} minimum</span></div><Badge tone={call.accepted ? "green" : ["failed", "blocked", "declined"].includes(call.status) ? "amber" : "default"}>{call.accepted && <CheckCircle2 size={12} />}{call.redeemed ? "Redeemed · payment simulated" : callStateLabel(call.status)}</Badge></div>
          <div className="telephony-call-meta"><span>{call.provider === "simulation" ? "Simulated call · no phone dialed" : call.provider === "twilio" ? "Twilio phone call · Sarvam voice" : "Sarvam phone call"}</span><time>{new Date(call.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</time></div>
          {call.error && <p className="telephony-call-error">{call.error}</p>}
          {call.provider === "simulation" && ["queued", "submitted", "ringing", "connected"].includes(call.status) && <div className="telephony-test-keypad"><span>Test keypad</span><Button size="sm" disabled={!!busy} onClick={() => void press(call, "1")}>1 · Accept test offer</Button><Button size="sm" variant="secondary" disabled={!!busy} onClick={() => void press(call, "2")}>2 · Decline</Button><Button size="sm" variant="ghost" disabled={!!busy} onClick={() => void press(call, "no_answer")}>No answer</Button></div>}
          {call.accepted && !call.redeemed && <Link href="/ledger#checkout" className="text-link">Try checkout · automatically apply offer <ArrowRight size={13} /></Link>}
        </article>)}
      </div>
    </div>
  </Panel>;
}
