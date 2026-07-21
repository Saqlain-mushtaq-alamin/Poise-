import { expect, test } from "@playwright/test";

// Uses Chromium's fake media stream (see playwright.config.ts launchOptions)
// so this runs headlessly without a real mic — the synthetic device still
// exercises getUserMedia, the AudioWorklet, and the volume meter for real.
test("Audio settings render, list a fake mic, and a transcribe test can be started", async ({
  page,
}) => {
  await page.goto("/#/settings");

  await expect(page.getByRole("heading", { name: "Voice" })).toBeVisible();
  await expect(page.getByLabelText(/microphone/i)).toBeVisible({ timeout: 10_000 });

  // Chromium's fake device shows up as "fake_device_0audio" or similar.
  const micOptions = await page.getByLabelText(/microphone/i).locator("option").count();
  expect(micOptions).toBeGreaterThan(1); // "System default" + at least the fake device

  await expect(page.getByRole("heading", { name: "Model configuration" })).toBeVisible();
});

test("clicking the transcribe test button starts capturing (fake mic)", async ({ page }) => {
  await page.goto("/#/settings");

  const testButton = page.getByRole("button", { name: /say something and see it transcribed/i });
  await expect(testButton).toBeVisible();
  await testButton.click();

  // With no real Whisper model available server-side, this should surface
  // the graceful "model not available" error rather than hang silently —
  // see backend/app/services/stt.py's ModelNotAvailableError.
  await expect(page.getByText(/not available/i)).toBeVisible({ timeout: 10_000 });
});
