import { useEffect, useMemo, useRef, useState } from "react";

import { api as sharedApi, PoiseAPI } from "../lib/api";
import { getSidecarStatus, isTauri, onSidecarStatusChange } from "../lib/ipc";
import type { SidecarStatus } from "../lib/types";

const POLL_INTERVAL_MS = 2000;
// Ports to probe when Tauri can't find the sidecar binary (dev mode).
const DEV_FALLBACK_PORTS = [8000, 8001, 8080, 54500, 5000];

interface UseSidecarResult {
  status: SidecarStatus | null;
  api: PoiseAPI | null;
  isConnected: boolean;
}

/** Probe a candidate port via the /health endpoint and return the port number
 * if healthy, or null if not reachable. */
async function probeDevPort(port: number): Promise<number | null> {
  try {
    const res = await fetch(`http://127.0.0.1:${port}/health`, {
      signal: AbortSignal.timeout(1000),
    });
    if (res.ok) return port;
  } catch {
    // not reachable
  }
  return null;
}

/** Tracks sidecar health (via push events when available, falling back to
 * polling) and hands back a ready-to-use PoiseAPI client once a port is
 * known. Components should treat `api` as possibly null until connected. */
export function useSidecar(): UseSidecarResult {
  const [status, setStatus] = useState<SidecarStatus | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    let unsubscribe: (() => void) | undefined;

    async function discoverDevPort(): Promise<number | null> {
      for (const port of DEV_FALLBACK_PORTS) {
        const found = await probeDevPort(port);
        if (found !== null) return found;
      }
      return null;
    }

    async function poll() {
      try {
        const next = await getSidecarStatus();
        if (!mountedRef.current) return;

        // In Tauri dev mode the sidecar binary isn't bundled, so the Rust
        // side reports port=0. Fall back to probing well-known dev ports.
        if (next?.port === 0 && isTauri) {
          const devPort = await discoverDevPort();
          if (devPort && mountedRef.current) {
            const syntheticStatus: SidecarStatus = {
              port: devPort,
              status: "healthy",
              uptime_seconds: 0,
              restart_count: 0,
            };
            setStatus(syntheticStatus);
            sharedApi.setPort(devPort);
            return;
          }
        }

        setStatus(next);
        if (next?.port) sharedApi.setPort(next.port);
      } catch {
        if (mountedRef.current) {
          setStatus((prev) =>
            prev ? { ...prev, status: "unhealthy" } : { port: 0, status: "unhealthy", uptime_seconds: 0, restart_count: 0 }
          );
        }
      }
    }

    onSidecarStatusChange((next) => {
      if (mountedRef.current) {
        setStatus(next);
        if (next?.port) sharedApi.setPort(next.port);
      }
    }).then((fn) => {
      unsubscribe = fn;
    });

    poll();
    const pollId = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      mountedRef.current = false;
      clearInterval(pollId);
      unsubscribe?.();
    };
  }, []);

  const port = status?.port;
  const api = useMemo(() => {
    if (port) {
      sharedApi.setPort(port);
      return sharedApi;
    }
    return null;
  }, [port]);

  return { status, api, isConnected: status?.status === "healthy" };
}
