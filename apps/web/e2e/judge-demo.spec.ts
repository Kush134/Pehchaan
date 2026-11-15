import { expect, test } from "@playwright/test";

test("judge walkthrough runs connected campaigns, negotiation, and firewall actions", async ({
  page,
  request,
}) => {
  test.setTimeout(150_000);
  await page.goto("/dashboard");
  await page
    .getByRole("button", { name: "Start walkthrough", exact: true })
    .click();
  const guide = page.locator(".judge-demo");
  await expect(guide).toContainText("The disappearing regulars");
  await expect(page).toHaveURL(/\/customers$/);
  await guide
    .getByRole("button", { name: "Show comeback opportunity" })
    .click();
  await expect(page).toHaveURL(/\/comeback$/);
  const campaignResponse = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/campaigns") && r.request().method() === "POST",
  );
  await guide.getByRole("button", { name: "Approve demo campaign" }).click();
  const campaign = await (await campaignResponse).json();
  await expect(page).toHaveURL(/\/soundbox$/);
  const campaigns = await (await request.get("/api/v1/campaigns")).json();
  const launched = campaigns.find((c: { id: string }) => c.id === campaign.id);
  expect(launched.status).toBe("active");
  expect(launched.assignments.length).toBeGreaterThan(0);
  expect(launched.stats.redeemed).toBeGreaterThan(0);
  const creation = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/haggle/sessions") &&
      r.request().method() === "POST",
  );
  await guide.getByRole("button", { name: "Start live negotiation" }).click();
  const session = await (await creation).json();
  await expect(page).toHaveURL(/\/haggle$/);
  await guide
    .getByRole("button", { name: "Test the mandate firewall" })
    .click();
  await expect(page).toHaveURL(/\/firewall$/);
  const firewall = page.waitForResponse((r) =>
    r.url().endsWith("/api/v1/firewall/validate"),
  );
  await guide.getByRole("button", { name: "Block rogue proposal" }).click();
  expect((await (await firewall).json()).status).toBe("BLOCKED");
  await expect(page).toHaveURL(/\/haggle$/);
  await expect(
    page.getByRole("heading", { name: "Best eligible deal", exact: true }),
  ).toBeVisible({ timeout: 90_000 });
  const completed = await (
    await request.get(`/api/v1/haggle/sessions/${session.id}`)
  ).json();
  expect(completed.rounds).toHaveLength(4);
  expect(completed.status).toBe("awaiting_approval");
  const orders = await (await request.get("/api/v1/orders")).json();
  expect(
    orders.items.some(
      (o: { session_id?: string }) => o.session_id === session.id,
    ),
  ).toBe(false);
  await guide.getByRole("button", { name: "Open simulated ledger" }).click();
  await expect(page).toHaveURL(/\/ledger$/);
  await guide.getByRole("button", { name: "Finish walkthrough" }).click();
  await expect(guide).toHaveCount(0);
  await expect(page).toHaveURL(/\/dashboard$/);
});
