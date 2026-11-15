import { expect, test } from "@playwright/test";

test("customer filtering searches stored pseudonymous profiles", async ({
  page,
  request,
}) => {
  const response = await request.get("/api/v1/customers?page_size=1");
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  const token: string = data.items[0].customer_token;
  await page.goto("/customers");
  await page
    .getByRole("textbox", { name: "Search customer tokens" })
    .fill(token);
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText(token);
  await page
    .getByRole("textbox", { name: "Search customer tokens" })
    .fill("no-such-customer-xyz");
  await expect(
    page.getByRole("heading", { name: "No customers match this filter" }),
  ).toBeVisible();
});

test("catalogue add, edit and delete persist through the API", async ({
  page,
  request,
}) => {
  const name = `Browser test dal ${Date.now()}`;
  await page.goto("/catalog");
  await page.getByRole("button", { name: "Add product", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Product name", { exact: true }).fill(name);
  await dialog.getByLabel("Category", { exact: true }).fill("Pulses");
  await dialog.getByLabel("Unit", { exact: true }).fill("kg");
  await dialog
    .getByLabel("Supplier", { exact: true })
    .fill("Synthetic test supplier");
  await dialog.getByLabel("Selling price (₹)", { exact: true }).fill("145");
  await dialog.getByLabel("Available stock", { exact: true }).fill("80");
  await dialog.getByLabel("Purchase cost (₹)", { exact: true }).fill("115");
  await dialog
    .getByLabel("Minimum selling price (₹)", { exact: true })
    .fill("125");
  await dialog
    .getByRole("button", { name: "Add product", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await page.getByRole("textbox", { name: "Search products" }).fill(name);
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.getByRole("button", { name: `Edit ${name}`, exact: true }).click();
  await dialog.getByLabel("Selling price (₹)", { exact: true }).fill("149");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toHaveCount(0);
  const products = await (await request.get("/api/v1/catalog/products")).json();
  expect(
    products.find((p: { name: string }) => p.name === name).selling_price,
  ).toBe(149);
  await page
    .getByRole("button", { name: `Delete ${name}`, exact: true })
    .click();
  await dialog
    .getByRole("button", { name: "Delete product", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "No matching products" }),
  ).toBeVisible();
});

test("campaign creation, explicit launch and simulation write assigned outcomes", async ({
  page,
}) => {
  await page.goto("/comeback");
  await page
    .getByRole("button", { name: "Create campaign", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Campaign name")
    .fill(`Browser comeback ${Date.now()}`);
  await dialog.getByLabel("Offer amount (₹)").fill("15");
  await dialog.getByLabel("Minimum bill (₹)").fill("250");
  await dialog.getByLabel("Target segment").selectOption("At-Risk + Declining");
  const creation = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/campaigns") && r.request().method() === "POST",
  );
  await dialog
    .getByRole("button", { name: "Create campaign", exact: true })
    .click();
  const createdResponse = await creation;
  expect(createdResponse.ok()).toBeTruthy();
  const created = await createdResponse.json();
  expect(created.status).toBe("draft");
  await expect(dialog).toHaveCount(0);
  const launch = page.waitForResponse((r) =>
    r.url().includes(`/campaigns/${created.id}/launch`),
  );
  await page.getByRole("button", { name: "Approve & launch campaign" }).click();
  const campaign = await (await launch).json();
  expect(campaign.stats.allocated).toBeGreaterThan(0);
  expect(
    campaign.assignments.some(
      (a: { variant: string }) => a.variant === "Control",
    ),
  ).toBeTruthy();
  const simulation = page.waitForResponse((r) =>
    r.url().includes(`/campaigns/${created.id}/simulate-redemptions`),
  );
  await page
    .getByRole("button", { name: "Simulate redemptions", exact: true })
    .click();
  const result = await (await simulation).json();
  expect(result.stats.redeemed).toBeGreaterThan(0);
  expect(result.stats.discount_expense).toBeLessThanOrEqual(result.budget);
  await expect(
    page.getByText("Preliminary results.", { exact: false }),
  ).toBeVisible();
});

test("text voice fallback proposes a change and waits for explicit approval", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await page.goto("/soundbox");
  await page.getByRole("checkbox", { name: "Spoken responses" }).uncheck();
  await page
    .getByRole("textbox", { name: "Merchant command" })
    .fill(
      "Create a retention campaign with ₹15 discount and ₹250 minimum bill.",
    );
  const proposalResponse = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/voice/chat") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Send command", exact: true }).click();
  const proposal = await (await proposalResponse).json();
  expect(proposal.proposal.status).toBe("pending_approval");
  await expect(
    page.getByRole("button", { name: "Approve action" }),
  ).toBeVisible({ timeout: 60_000 });
  const approvalResponse = page.waitForResponse((r) =>
    r.url().endsWith("/api/v1/voice/approve"),
  );
  await page.getByRole("button", { name: "Approve action" }).click();
  const approval = await (await approvalResponse).json();
  expect(approval.status).toBe("approved");
  expect(approval.campaign.status).toBe("active");
  await expect(
    page.getByRole("button", { name: "Approve action" }),
  ).toHaveCount(0);
});

test("rogue bid is blocked by the buyer budget rule", async ({ page }) => {
  await page.goto("/firewall");
  await page
    .getByRole("spinbutton", { name: "Proposed amount (₹)" })
    .fill("95000");
  const response = page.waitForResponse((r) =>
    r.url().endsWith("/api/v1/firewall/validate"),
  );
  await page.getByRole("button", { name: "Run firewall check" }).click();
  const result = await (await response).json();
  expect(result.status).toBe("BLOCKED");
  expect(
    result.rules.find((r: { rule: string }) => r.rule === "BUYER_BUDGET")
      .passed,
  ).toBe(false);
  await expect(page.locator(".decision-result")).toContainText("BLOCKED");
  await expect(page.locator(".decision-result")).toContainText(
    "authorized buyer budget",
  );
  await expect(page.locator(".decision-result")).toHaveClass(/blocked/);
});

test("four-round negotiation creates a confirmed order and simulated payment lifecycle", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  await page.goto("/haggle");
  await page.evaluate(() => localStorage.removeItem("pehchaan-session"));
  await page.reload();
  const creation = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/haggle/sessions") &&
      r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Start negotiation", exact: true })
    .click();
  const session = await (await creation).json();
  expect(session.budget).toBe(40000);
  await expect(
    page.getByRole("button", { name: "Pause", exact: true }),
  ).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Resume", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Resume", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Best eligible deal", exact: true }),
  ).toBeVisible({ timeout: 80_000 });
  const completed = await (
    await request.get(`/api/v1/haggle/sessions/${session.id}`)
  ).json();
  expect(completed.round_number).toBe(4);
  expect(completed.rounds).toHaveLength(4);
  expect(completed.best_deal.total_amount).toBeLessThanOrEqual(
    completed.budget,
  );
  expect(JSON.stringify(completed)).not.toMatch(
    /minimum_price|private_floor|floor_price/,
  );
  await page.getByRole("button", { name: "Review & confirm order" }).click();
  const dialog = page.getByRole("dialog");
  const confirm = dialog.getByRole("button", {
    name: "Confirm simulated order",
  });
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel("I approve this order as the merchant.").check();
  await expect(confirm).toBeDisabled();
  await dialog
    .getByLabel("I confirm the selected bundle as the buyer.")
    .check();
  const confirmation = page.waitForResponse((r) =>
    r.url().endsWith(`/haggle/sessions/${session.id}/confirm`),
  );
  await confirm.click();
  const order = await (await confirmation).json();
  expect(order.payment_state).toBe("DELIVERY_CONFIRMATION_PENDING");
  await expect(dialog).toHaveCount(0);
  await page.getByRole("link", { name: "View simulated order" }).click();
  const orderCard = page
    .locator(".utility-order")
    .filter({ hasText: order.id.slice(0, 8).toUpperCase() });
  await orderCard.getByRole("button", { name: "Mark packed" }).click();
  await orderCard
    .getByRole("button", { name: "Confirm delivery", exact: true })
    .click();
  await page.getByRole("dialog").getByRole("checkbox").check();
  await page
    .getByRole("button", { name: "Confirm demo delivery", exact: true })
    .click();
  await orderCard
    .getByRole("button", { name: "Release simulated settlement" })
    .click();
  await expect(orderCard).toContainText("Released simulated");
  const persisted = await (
    await request.get(`/api/v1/orders/${order.id}`)
  ).json();
  expect(persisted.payment_state).toBe("RELEASED_SIMULATED");
  expect(persisted.simulated).toBe(true);
});

test("voice-approved bulk negotiation is reachable from the Soundbox", async ({
  page,
  request,
}) => {
  await page.goto("/soundbox");
  await page.getByRole("checkbox", { name: "Spoken responses" }).uncheck();
  await page
    .getByRole("textbox", { name: "Merchant command" })
    .fill("Start bulk negotiation for an office grocery event.");
  await page.getByRole("button", { name: "Send command", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Approve action" }),
  ).toBeVisible();
  const confirmation = page.waitForResponse((r) =>
    r.url().endsWith("/api/v1/voice/approve"),
  );
  await page.getByRole("button", { name: "Approve action" }).click();
  const response = await (await confirmation).json();
  expect(response.action).toBe("start_negotiation");
  await page.getByRole("link", { name: "View live negotiation" }).click();
  await expect(page).toHaveURL(/\/haggle$/);
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem("pehchaan-session")))
    .toBe(response.session_id);
  await expect(
    page.getByRole("button", { name: "Cancel", exact: true }),
  ).toBeVisible();
  const cancelled = page.waitForResponse(
    (r) =>
      r.url().endsWith(`/haggle/sessions/${response.session_id}/cancel`) &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  expect((await cancelled).ok()).toBeTruthy();
  const session = await (
    await request.get(`/api/v1/haggle/sessions/${response.session_id}`)
  ).json();
  expect(session.status).toBe("cancelled");
});
