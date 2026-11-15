import { expect, test } from "@playwright/test";

test("dashboard loads stored merchant data and every navigation module opens", async ({
  page,
}) => {
  await page.goto("/dashboard");
  await expect(page.getByText("Sharma Kirana Store").first()).toBeVisible();
  await expect(
    page.getByRole("main").getByRole("heading", { level: 1 }),
  ).toBeVisible();
  await expect(
    page.locator(".topbar").getByText("DEMO MODE", { exact: true }),
  ).toHaveCount(0);
  const palette = await page.evaluate(() => {
    const rgb = (value: string) =>
      (value.match(/\d+(?:\.\d+)?/g) || []).slice(0, 3).map(Number);
    const primary = document.querySelector<HTMLButtonElement>(
      ".page-actions .btn-primary",
    );
    return {
      background: rgb(getComputedStyle(document.body).backgroundColor),
      action: primary ? rgb(getComputedStyle(primary).backgroundColor) : [],
      scheme: getComputedStyle(document.documentElement).colorScheme,
    };
  });
  expect(palette.background.every((channel) => channel >= 230)).toBe(true);
  expect(palette.action[2]).toBeGreaterThan(palette.action[0] + 40);
  expect(palette.scheme).toContain("light");
  const modules = [
    ["Comeback Engine", "/comeback"],
    ["Customer Intelligence", "/customers"],
    ["Haggle Arena", "/haggle"],
    ["Agent Command Center", "/agents"],
    ["Mandate Firewall", "/firewall"],
    ["Soundbox Simulator", "/soundbox"],
    ["Product Catalogue", "/catalog"],
    ["Transaction Ledger", "/ledger"],
    ["Settings", "/settings"],
  ] as const;
  for (const [name, path] of modules) {
    await page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("link", { name: new RegExp(`^${name}`) })
      .click();
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await expect(
      page.getByRole("main").getByRole("heading", { level: 1 }),
    ).toBeVisible();
    await expect(
      page.getByText("Couldn’t reach the workspace", { exact: true }),
    ).toHaveCount(0);
  }
});

test("network failures produce a recoverable error state", async ({ page }) => {
  await page.route("**/api/v1/dashboard/summary**", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Deliberate browser-test outage" }),
    }),
  );
  await page.goto("/dashboard");
  await expect(
    page.getByRole("heading", { name: "Couldn’t reach the workspace" }),
  ).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Try again" })).toBeEnabled();
  await page.unroute("**/api/v1/dashboard/summary**");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByRole("heading", { name: "Couldn’t reach the workspace" }),
  ).toHaveCount(0, { timeout: 20_000 });
});

test("demo reset restores the seeded customer count through a real endpoint", async ({
  page,
}) => {
  await page.goto("/settings");
  await page
    .getByRole("button", { name: "Reset sample data", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: "Reset sample data?" }),
  ).toBeVisible();
  const reset = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/demo/reset") &&
      response.request().method() === "POST",
  );
  await dialog
    .getByRole("button", { name: "Reset sample data", exact: true })
    .click();
  const response = await reset;
  expect(response.ok()).toBeTruthy();
  expect((await response.json()).customers).toBe(100);
  await expect(dialog).toHaveCount(0);
});

test("phone catalogue scrolls its table without widening the page", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/catalog");
  await expect(
    page.getByRole("heading", { name: "Merchant inventory" }),
  ).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
    .toBe(390);
  const table = page.locator(".table-wrap").first();
  expect(await table.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(
    true,
  );
  await table.evaluate((el) => {
    el.scrollLeft = el.scrollWidth;
  });
  await expect(
    table.getByRole("button", { name: /^Edit / }).first(),
  ).toBeInViewport();
});
