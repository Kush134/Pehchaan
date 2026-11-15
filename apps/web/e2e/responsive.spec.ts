import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

test("all workspace modules fit desktop, tablet, and phone widths", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const modules = [
    "dashboard",
    "comeback",
    "customers",
    "haggle",
    "agents",
    "firewall",
    "soundbox",
    "catalog",
    "ledger",
    "settings",
  ];
  const runtimeErrors: string[] = [];
  page.on("pageerror", (error) => runtimeErrors.push(error.message));
  const capture = process.env.PEHCHAAN_CAPTURE_LAYOUT === "1";
  const directory = resolve(process.cwd(), "../../.runtime/qa/blue-white");
  if (capture) await mkdir(directory, { recursive: true });
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    for (const sectionId of modules) {
      await page.goto(`/${sectionId}`);
      await expect(
        page.getByRole("main").getByRole("heading", { level: 1 }),
      ).toBeVisible();
      await page.evaluate(async () => {
        await document.fonts.ready;
      });
      await expect
        .poll(() => page.evaluate(() => document.documentElement.scrollWidth), {
          message: `${sectionId} page should fit ${width}px viewport`,
        })
        .toBeLessThanOrEqual(width + 1);
      if (capture && (width === 1440 || width === 390)) {
        await page.screenshot({
          path: resolve(directory, `${sectionId}-${width}.png`),
          fullPage: true,
        });
      }
    }
  }
  expect(runtimeErrors).toEqual([]);
});
