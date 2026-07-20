import { useEffect, useMemo, useRef, useState } from "react";

import { PoiseAPI } from "../lib/api";
import { getSidecarStatus, onSidecarStatusChange } from "../lib/ipc";
import type { SidecarStatus } from "../lib/types";

const POLL_INTERVAL_MS = 2000;

interface UseSidecarResult {
  status: SidecarStatus | null;
  api: PoiseAPI | null;
  isConnected: boolean;
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

    async function poll() {
      try {
        const next = await getSidecarStatus();
        if (mountedRef.current) setStatus(next);
      } catch {
        if (mountedRef.current) {
          setStatus((prev) =>
            prev ? { ...prev, status: "unhealthy" } : { port: 0, status: "unhealthy", uptime_seconds: 0, restart_count: 0 }
          );
        }
      }
    }

    onSidecarStatusChange((next) => {
      if (mountedRef.current) setStatus(next);
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
  const api = useMemo(() => (port ? new PoiseAPI(port) : null), [port]);

  return { status, api, isConnected: status?.status === "healthy" };
}
