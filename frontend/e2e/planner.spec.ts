import { test, expect } from "@playwright/test";
import path from "node:path";

test.describe("RouteLedger planner", () => {
  test("short preset generates map and log", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("RouteLedger")).toBeVisible();
    await page.getByRole("button", { name: /Short route/i }).click();
    await page.getByRole("button", { name: /Generate trip plan/i }).click();
    await expect(page.getByText(/Within modeled limits|Distance/i).first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/mi/i).first()).toBeVisible();
    await page.getByRole("button", { name: "Daily logs" }).click();
    await expect(page.getByRole("img", { name: /Driver daily log/i }).first()).toBeVisible();
  });

  for (const width of [375, 768, 1024, 1440]) {
    test(`layout at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/");
      await page.getByRole("button", { name: /Short route/i }).click();
      await page.getByRole("button", { name: /Generate trip plan/i }).click();
      await expect(page.getByText(/Within modeled limits/i)).toBeVisible({ timeout: 30_000 });
      await page.screenshot({
        path: path.join("e2e", "screenshots", `plan-${width}.png`),
        fullPage: true,
      });
      const overflowPx = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      );
      expect(overflowPx).toBeLessThanOrEqual(width < 400 ? 8 : 2);
    });
  }
});
