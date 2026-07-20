import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as ipc from "../lib/ipc";
import { useSidecar } from "./useSidecar";

describe("useSidecar", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("parses a healthy sidecar status from the IPC layer", async () => {
    vi.spyOn(ipc, "getSidecarStatus").mockResolvedValue({
      port: 12345,
      status: "healthy",
      uptime_seconds: 10,
      restart_count: 0,
    });
    vi.spyOn(ipc, "onSidecarStatusChange").mockResolvedValue(() => {});

    const { result } = renderHook(() => useSidecar());

    await waitFor(() => expect(result.current.isConnected).toBe(true));

    expect(result.current.status?.port).toBe(12345);
    expect(result.current.api).not.toBeNull();
  });

  it("marks the connection unhealthy when the IPC call fails", async () => {
    vi.spyOn(ipc, "getSidecarStatus").mockRejectedValue(new Error("no sidecar"));
    vi.spyOn(ipc, "onSidecarStatusChange").mockResolvedValue(() => {});

    const { result } = renderHook(() => useSidecar());

    await waitFor(() => expect(result.current.status?.status).toBe("unhealthy"));
    expect(result.current.isConnected).toBe(false);
  });
});
