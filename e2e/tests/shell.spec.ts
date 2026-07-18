import { expect, test } from "@playwright/test";

test("app launches, sidebar navigates, and theme toggles", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Poise" })).toBeVisible();

  await page.getByRole("link", { name: /Session History/i }).click();
  await expect(page.getByRole("heading", { name: "Session History" })).toBeVisible();

  await page.getByRole("link", { name: /Settings/i }).click();
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

  const html = page.locator("html");
  await expect(html).toHaveAttribute("data-theme", "dark");

  await page.getByRole("switch", { name: /Toggle dark theme/i }).click();
  await expect(html).toHaveAttribute("data-theme", "light");
});
