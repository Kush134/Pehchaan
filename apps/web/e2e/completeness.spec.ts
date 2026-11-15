import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("customer details expose the stored RFM profile and purchase history", async ({
  page,
  request,
}) => {
  const directory = await (
    await request.get("/api/v1/customers?page_size=1")
  ).json();
  const token: string = directory.items[0].customer_token;
  await page.goto("/customers");
  await page
    .getByRole("textbox", { name: "Search customer tokens" })
    .fill(token);
  const detailResponse = page.waitForResponse((response) =>
    response.url().endsWith(`/api/v1/customers/${token}`),
  );
  await page
    .getByRole("button", { name: `View customer ${token}`, exact: true })
    .click();
  const detail = await (await detailResponse).json();
  expect(detail.customer.customer_token).toBe(token);
  expect(detail.rfm.frequency).toBeGreaterThan(0);
  expect(detail.rfm.monetary).toBeGreaterThan(0);
  expect(detail.transactions.length).toBeGreaterThan(0);
  expect(JSON.stringify(detail)).not.toMatch(/"(?:phone|upi_id|email)"\s*:/i);
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: `Customer ${token}`, exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("heading", { name: "Purchase history", exact: true }),
  ).toBeVisible();
  await expect(dialog).toContainText(detail.insights.description);
});

test("transaction CSV import and export operate on the stored ledger", async ({
  page,
  request,
}) => {
  const directory = await (
    await request.get("/api/v1/customers?page_size=1")
  ).json();
  const token: string = directory.items[0].customer_token;
  const category = `BrowserCSV-${Date.now()}`;
  const csv = `customer_token,amount,category,created_at\n${token},321.45,${category},${new Date().toISOString()}\n`;
  const before = await (
    await request.get("/api/v1/transactions?page_size=1")
  ).json();
  await page.goto("/ledger");
  await page
    .getByRole("button", { name: "Import transactions", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", {
      name: "Import merchant transactions",
      exact: true,
    }),
  ).toBeVisible();
  const templateDownload = page.waitForEvent("download");
  await dialog
    .getByRole("button", { name: "Download transaction template", exact: true })
    .click();
  const template = await templateDownload;
  const templatePath = await template.path();
  expect(templatePath).not.toBeNull();
  expect(await readFile(templatePath!, "utf8")).toContain(
    "customer_token,amount,category,created_at",
  );
  await dialog
    .getByLabel("Transaction CSV file", { exact: true })
    .setInputFiles({
      name: "browser-transactions.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(csv),
    });
  const importedResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/transactions/import") &&
      response.request().method() === "POST",
  );
  await dialog.getByRole("button", { name: "Import CSV", exact: true }).click();
  const imported = await (await importedResponse).json();
  expect(imported.imported).toBe(1);
  expect(imported.simulated).toBe(true);
  await expect(dialog).toHaveCount(0);
  const after = await (
    await request.get("/api/v1/transactions?page_size=1")
  ).json();
  expect(after.total).toBe(before.total + 1);
  const exportDownload = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Export transactions", exact: true })
    .click();
  const exported = await exportDownload;
  const exportedPath = await exported.path();
  expect(exportedPath).not.toBeNull();
  const exportedCSV = await readFile(exportedPath!, "utf8");
  expect(exportedCSV).toContain(category);
  expect(exportedCSV).toContain("321.45");
});

test("a parsed buyer request remains reviewable without starting a negotiation", async ({
  page,
  request,
}) => {
  test.setTimeout(90_000);
  const before = await (await request.get("/api/v1/haggle/sessions")).json();
  await page.goto("/haggle");
  await page.evaluate(() => localStorage.removeItem("pehchaan-session"));
  await page.reload();
  await page
    .getByRole("textbox", { name: "Buyer requirement", exact: true })
    .fill(
      "I need 25 kg rice and 10 litres sunflower oil for an office event. Maximum total budget INR 12000. Deliver within 7 days.",
    );
  const parsedResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/haggle/parse-requirement") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Parse request", exact: true })
    .click();
  const parsed = await (await parsedResponse).json();
  expect(parsed.review_required).toBe(true);
  expect(parsed.status).toMatch(/parsed|partial/);
  expect(parsed.budget).toBe(12000);
  expect(
    parsed.items.find(
      (item: { product_id: string }) => item.product_id === "rice",
    ).quantity,
  ).toBe(25);
  expect(
    parsed.items.find(
      (item: { product_id: string }) => item.product_id === "oil",
    ).quantity,
  ).toBe(10);
  await expect(
    page.getByText("Review parsed request", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("spinbutton", { name: "Maximum budget (₹)", exact: true }),
  ).toHaveValue("12000");
  const after = await (await request.get("/api/v1/haggle/sessions")).json();
  expect(after.items.map((session: { id: string }) => session.id)).toEqual(
    before.items.map((session: { id: string }) => session.id),
  );
  await expect(
    page.getByRole("button", { name: "Start negotiation", exact: true }),
  ).toBeEnabled();
});

test("voice history restores a pending proposal and a new conversation does not execute it", async ({
  page,
  request,
}) => {
  await page.goto("/soundbox");
  await page.getByRole("checkbox", { name: "Spoken responses" }).uncheck();
  await page
    .getByRole("textbox", { name: "Merchant command" })
    .fill(
      "Create a retention campaign with 15 rupees discount and a 250 rupees minimum bill.",
    );
  const chatResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/voice/chat") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Send command", exact: true }).click();
  const chat = await (await chatResponse).json();
  expect(chat.proposal.status).toBe("pending_approval");
  const before = await (await request.get("/api/v1/campaigns")).json();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Approve action", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".conversation-messages")).toContainText(
    chat.transcript,
  );
  expect(
    await page.evaluate(() => localStorage.getItem("pehchaan-voice")),
  ).toBe(chat.session_id);
  await page
    .getByRole("button", { name: "New conversation", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Approve action", exact: true }),
  ).toHaveCount(0);
  const after = await (await request.get("/api/v1/campaigns")).json();
  expect(after.length).toBe(before.length);
  const saved = await (
    await request.get(`/api/v1/voice/history?session_id=${chat.session_id}`)
  ).json();
  expect(saved.messages.length).toBeGreaterThanOrEqual(2);
  expect(saved.proposal.status).toBe("pending_approval");
});

test("merchant language preference persists and initializes new conversations", async ({
  page,
  request,
}) => {
  const before = await (
    await request.get("/api/v1/settings/integrations")
  ).json();
  const chosen = before.merchant_language === "mr-IN" ? "en-IN" : "mr-IN";
  try {
    await page.goto("/settings");
    await page
      .getByRole("combobox", {
        name: "Default assistant language",
        exact: true,
      })
      .selectOption(chosen);
    const savedResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/settings/merchant") &&
        response.request().method() === "PATCH",
    );
    await page
      .getByRole("button", { name: "Save language", exact: true })
      .click();
    expect((await (await savedResponse).json()).language).toBe(chosen);
    await expect(page.getByRole("status")).toContainText(
      "Default language saved",
    );
    await page.reload();
    await expect(
      page.getByRole("combobox", {
        name: "Default assistant language",
        exact: true,
      }),
    ).toHaveValue(chosen);
    await page.goto("/soundbox");
    await expect(
      page.getByRole("combobox", { name: "Assistant language" }),
    ).toHaveValue(chosen);
  } finally {
    await request.patch("/api/v1/settings/merchant", {
      data: { language: before.merchant_language },
    });
  }
});
