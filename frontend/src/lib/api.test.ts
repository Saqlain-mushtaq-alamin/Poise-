import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, PoiseAPI } from "./api";

describe("PoiseAPI", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("builds requests against the sidecar's localhost port", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok", version: "0.1.0", database: "connected", uptime_seconds: 1 }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const api = new PoiseAPI(54321);
    const health = await api.health();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:54321/health",
      expect.objectContaining({ method: "GET" })
    );
    expect(health.status).toBe("ok");
  });

  it("sends a JSON body and content-type header for PUT requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ value: "dark" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const api = new PoiseAPI(54321);
    await api.putSetting("theme", "dark");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:54321/settings/theme",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ value: "dark" }),
        headers: { "Content-Type": "application/json" },
      })
    );
  });

  it("throws an ApiError with the status code on a non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) })
    );

    const api = new PoiseAPI(54321);
    await expect(api.health()).rejects.toMatchObject(
      new ApiError("GET /health failed with 500", 500)
    );
  });

  it("wraps a network failure in an ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    const api = new PoiseAPI(54321);
    await expect(api.health()).rejects.toBeInstanceOf(ApiError);
  });
});
