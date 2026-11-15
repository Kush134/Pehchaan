import { expect, test } from "@playwright/test";

test("simulated comeback call accepts once and automatically discounts a QR checkout", async ({ page, request }, testInfo) => {
  await page.goto("/");
  const creation = page.waitForResponse((response) => response.url().endsWith("/api/v1/telephony/demo-offer") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Try a simulated call", exact: true }).click();
  const response = await creation;
  expect(response.ok()).toBeTruthy();
  const invitation = await response.json();
  expect(invitation.call.provider).toBe("simulation");
  expect(invitation.call.accepted).toBe(false);
  const call = page.locator(`[data-call-id="${invitation.call.id}"]`);
  await expect(call).toContainText("Simulated call · no phone dialed");
  await call.getByRole("button", { name: "1 · Accept test offer", exact: true }).click();
  await expect(call).toContainText("Accepted · pressed 1");
  await expect(call.getByRole("button", { name: "1 · Accept test offer", exact: true })).toHaveCount(0);
  await call.getByRole("link", { name: "Try checkout · automatically apply offer" }).click();
  await expect(page).toHaveURL(/\/ledger#checkout/);
  const checkout = page.locator("#checkout");
  await expect(checkout.getByLabel("Customer", { exact: true })).toHaveValue(invitation.call.customer_token);

  // Merely accepting a call cannot bypass the offer's minimum basket.
  await checkout.getByLabel("Bill amount (₹)", { exact: true }).fill("199");
  const belowMinimum = page.waitForResponse((r) => r.url().endsWith("/api/v1/checkout/quote") && r.request().method() === "POST");
  await checkout.getByRole("button", { name: "Simulate QR scan", exact: true }).click();
  expect((await (await belowMinimum).json()).discount).toBe(0);
  await expect(checkout.getByRole("button", { name: "Pay ₹199 · simulated", exact: true })).toBeVisible();

  // Editing the amount invalidates the old preview; a new scan uses server pricing.
  await checkout.getByLabel("Bill amount (₹)", { exact: true }).fill("250");
  await expect(checkout.getByRole("button", { name: /^Pay / })).toHaveCount(0);
  const quotation = page.waitForResponse((r) => r.url().endsWith("/api/v1/checkout/quote") && r.request().method() === "POST");
  await checkout.getByRole("button", { name: "Simulate QR scan", exact: true }).click();
  const quote = await (await quotation).json();
  expect(quote.bill_amount).toBe(250);
  expect(quote.discount).toBe(20);
  expect(quote.payable_amount).toBe(230);
  expect(quote.simulated).toBe(true);
  await expect(checkout.getByRole("button", { name: "Pay ₹230 · simulated", exact: true })).toBeVisible();
  const payment = page.waitForResponse((r) => r.url().endsWith("/api/v1/checkout/pay") && r.request().method() === "POST");
  await checkout.getByRole("button", { name: "Pay ₹230 · simulated", exact: true }).click();
  const paidResponse = await payment;
  expect(paidResponse.ok()).toBeTruthy();
  const paid = await paidResponse.json();
  expect(paid.status).toBe("paid");
  expect(paid.payable_amount).toBe(230);
  await expect(checkout).toContainText("Simulated payment complete");
  await expect(checkout).toContainText("cannot be used again");
  await expect(checkout.getByRole("button", { name: /^Pay / })).toHaveCount(0);

  // A transport retry of the same confirmation returns its receipt, never a second charge.
  const before = await (await request.get("/api/v1/transactions?page_size=1")).json();
  const replay = await request.post("/api/v1/checkout/pay", { data: { quote_id: quote.id }, headers: { "Idempotency-Key": paidResponse.request().headers()["idempotency-key"] } });
  expect(replay.ok()).toBeTruthy();
  expect((await replay.json()).transaction_id).toBe(paid.transaction_id);
  const after = await (await request.get("/api/v1/transactions?page_size=1")).json();
  expect(after.total).toBe(before.total);
  await testInfo.attach("workflow-records", { body: JSON.stringify({ campaign_id: invitation.campaign.id, call_id: invitation.call.id, quote_id: quote.id, redeemed_offer_id: quote.offer_id, transaction_id: paid.transaction_id }, null, 2), contentType: "application/json" });
  await checkout.screenshot({ path: testInfo.outputPath("accepted-offer-checkout.png") });
});
