import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CheckoutPanel from "../components/pages/checkout";

let container: HTMLDivElement;
let root: Root;
let client: QueryClient;
const quote = { id: "quote-1", customer_token: "PK-0036", bill_amount: 250, discount: 20, payable_amount: 230, offer_id: "call-1", eligible: true, reason: "Accepted offer applied.", simulated: true, status: "quoted", expires_at: "2099-01-01T00:00:00Z" };
let paymentAttempts: RequestInit[];
let rejectFirstPayment: boolean;
function button(label: string) {
  const target = [...container.querySelectorAll("button")].find((node) => node.textContent?.includes(label));
  if (!target) throw new Error(`Missing button ${label}: ${container.textContent}`);
  return target;
}
async function click(label: string) {
  await act(async () => { button(label).click(); });
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 5)); });
}

beforeEach(async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  paymentAttempts = []; rejectFirstPayment = false;
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    let body: unknown;
    if (url.endsWith("/telephony/status")) body = { customer_name: "Kush", customer_token: "PK-0036" };
    else if (url.endsWith("/checkout/offers")) body = { items: [{ id: "call-1", customer_name: "Kush", customer_token: "PK-0036", accepted: true, redeemed: false }] };
    else if (url.endsWith("/checkout/quote")) body = quote;
    else if (url.endsWith("/checkout/pay")) {
      paymentAttempts.push(options!);
      if (rejectFirstPayment && paymentAttempts.length === 1) return new Response(JSON.stringify({ detail: "Temporary failure. Please retry." }), { status: 503 });
      body = { ...quote, status: "paid", transaction_id: "transaction-1" };
    } else throw new Error(`Unexpected request: ${url}`);
    return new Response(JSON.stringify(body));
  }));
  container = document.createElement("div"); document.body.appendChild(container);
  root = createRoot(container);
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  await act(async () => { root.render(<QueryClientProvider client={client}><CheckoutPanel /></QueryClientProvider>); });
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 10)); });
});
afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove(); vi.unstubAllGlobals(); });

describe("accepted-offer checkout", () => {
  it("previews the server discount and charges the net amount only after confirmation", async () => {
    expect(container.textContent).not.toContain("Simulated payment complete");
    await click("Simulate QR scan");
    expect(button("Pay ₹230").textContent).toContain("simulated");
    expect(paymentAttempts).toHaveLength(0);
    await click("Pay ₹230");
    expect(JSON.parse(paymentAttempts[0].body as string)).toEqual({ quote_id: "quote-1" });
    expect(container.textContent).toContain("Simulated payment complete");
    expect(container.textContent).toContain("cannot be used again");
    expect(container.querySelectorAll("button").length).toBe(1);
  });
  it("uses the same payment key when retrying a failed confirmation", async () => {
    rejectFirstPayment = true;
    await click("Simulate QR scan"); await click("Pay ₹230");
    expect(container.textContent).toContain("Temporary failure");
    expect(container.textContent).not.toContain("Simulated payment complete");
    await click("Pay ₹230");
    expect(paymentAttempts).toHaveLength(2);
    expect(new Headers(paymentAttempts[0].headers).get("Idempotency-Key")).toBe(new Headers(paymentAttempts[1].headers).get("Idempotency-Key"));
    expect(container.textContent).toContain("Simulated payment complete");
  });
});
