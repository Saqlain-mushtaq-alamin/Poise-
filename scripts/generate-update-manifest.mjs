#!/usr/bin/env node
// scripts/generate-update-manifest.mjs
// Phase 9.4 — builds the static update-manifest.json consumed by
// @tauri-apps/plugin-updater from a published GitHub Release's assets.
// Usage: node scripts/generate-update-manifest.mjs v1.1.0
//
// Requires GITHUB_TOKEN and GITHUB_REPOSITORY env vars (both provided
// automatically inside GitHub Actions).

import { mkdir, writeFile } from "node:fs/promises";

const tag = process.argv[2];
if (!tag) {
  console.error("Usage: generate-update-manifest.mjs <tag>");
  process.exit(1);
}

const repo = process.env.GITHUB_REPOSITORY; // e.g. "saqlain/poise"
const token = process.env.GITHUB_TOKEN;
const version = tag.replace(/^v/, "");

const res = await fetch(`https://api.github.com/repos/${repo}/releases/tags/${tag}`, {
  headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
});
if (!res.ok) {
  throw new Error(`Failed to fetch release ${tag}: ${res.status} ${await res.text()}`);
}
const release = await res.json();

// Tauri's updater expects a platform key per target, each pointing at the
// signed bundle + its detached .sig signature (produced by tauri-action
// when TAURI_SIGNING_PRIVATE_KEY is set).
const PLATFORM_ASSET_PATTERNS = {
  "windows-x86_64": /_x64-setup\.nsis\.zip$/,
  "darwin-aarch64": /aarch64\.app\.tar\.gz$/,
  "darwin-x86_64": /x64\.app\.tar\.gz$/,
  "linux-x86_64": /amd64\.AppImage\.tar\.gz$/,
};

const assets = release.assets ?? [];
const platforms = {};

for (const [platformKey, pattern] of Object.entries(PLATFORM_ASSET_PATTERNS)) {
  const bundleAsset = assets.find((a) => pattern.test(a.name));
  const sigAsset = assets.find((a) => pattern.test(a.name.replace(/\.sig$/, "")) && a.name.endsWith(".sig"));
  if (!bundleAsset) {
    console.warn(`No asset matched for ${platformKey}, skipping`);
    continue;
  }
  let signature = "";
  if (sigAsset) {
    const sigRes = await fetch(sigAsset.browser_download_url);
    signature = (await sigRes.text()).trim();
  }
  platforms[platformKey] = { url: bundleAsset.browser_download_url, signature };
}

const manifest = {
  version,
  notes: release.body?.slice(0, 2000) ?? "See release notes on GitHub.",
  pub_date: new Date().toISOString(),
  platforms,
};

await mkdir("gh-pages-out", { recursive: true });
await writeFile("gh-pages-out/update-manifest.json", JSON.stringify(manifest, null, 2));
console.log("Wrote gh-pages-out/update-manifest.json for version", version);
