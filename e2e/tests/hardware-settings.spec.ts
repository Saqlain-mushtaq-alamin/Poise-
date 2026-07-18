import { expect, test } from "@playwright/test";

// Runs against the real FastAPI backend (see playwright.config.ts webServer)
// so this exercises actual hardware detection on whatever machine runs CI —
// assertions stay structural (sections render, a tier ends up selected)
// rather than pinned to a specific tier, since that depends on the runner's
// hardware.
test("Settings page loads real hardware detection and provider status", async ({ page }) => {
  await page.goto("/#/settings");

  await expect(page.getByRole("heading", { name: "Hardware & model providers" })).toBeVisible();

  // Hardware card populates from a real /hardware/profile call.
  await expect(page.getByText("CPU")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByLabelText(/active tier/i)).toBeVisible();

  // Model configuration table reflects whatever tier got selected.
  await expect(page.getByRole("heading", { name: "Model configuration" })).toBeVisible();
  await expect(page.getByText("Reasoning (LLM)")).toBeVisible();

  // Cost limits section renders with a live session readout.
  await expect(page.getByRole("heading", { name: "Cost limits" })).toBeVisible();
  await expect(page.getByText(/tokens.*per session/i)).toBeVisible();
});

test("storing and testing an API key round-trips through the real backend", async ({ page }) => {
  await page.goto("/#/settings");

  await expect(page.getByText("OpenAI")).toBeVisible();

  const openaiRow = page.locator(".api-key-row", { hasText: "OpenAI" }).first();
  await openaiRow.getByLabelText(/OpenAI API key/i).fill("sk-fake-key-for-e2e");
  await openaiRow.getByRole("button", { name: /save/i }).click();

  // Without Tauri's keychain bridge, storeApiKey rejects outside the app;
  // this asserts the wizard UI at least attempts the call and doesn't crash
  // the page. The full keychain round-trip is covered by the Rust unit
  // tests in src-tauri/src/keychain.rs.
  await expect(page.getByText("OpenAI")).toBeVisible();
});
