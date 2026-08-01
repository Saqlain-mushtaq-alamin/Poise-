// frontend/src/hooks/useAutoUpdater.ts
// Phase 9.4 — Auto-Updater
//
// npm install @tauri-apps/plugin-updater @tauri-apps/plugin-process
// Requires the `updater` and `process` capabilities in
// src-tauri/capabilities/default.json (see that file in this bundle).

import { useCallback, useEffect, useState } from "react";
import { check, type Update } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";

export type UpdaterPhase = "idle" | "checking" | "available" | "downloading" | "ready" | "error" | "none";

export interface UpdaterState {
  phase: UpdaterPhase;
  version?: string;
  notes?: string;
  progress: number; // 0-100
  error?: string;
}

export function useAutoUpdater(checkOnMount = true) {
  const [state, setState] = useState<UpdaterState>({ phase: "idle", progress: 0 });
  const [pendingUpdate, setPendingUpdate] = useState<Update | null>(null);

  const checkForUpdate = useCallback(async () => {
    setState((s) => ({ ...s, phase: "checking" }));
    try {
      const update = await check();
      if (update) {
        setPendingUpdate(update);
        setState({ phase: "available", version: update.version, notes: update.body, progress: 0 });
      } else {
        setState({ phase: "none", progress: 0 });
      }
    } catch (err) {
      setState({ phase: "error", progress: 0, error: err instanceof Error ? err.message : String(err) });
    }
  }, []);

  const installUpdate = useCallback(async () => {
    if (!pendingUpdate) return;
    setState((s) => ({ ...s, phase: "downloading", progress: 0 }));

    let downloaded = 0;
    let total = 0;

    try {
      await pendingUpdate.downloadAndInstall((event) => {
        switch (event.event) {
          case "Started":
            total = event.data.contentLength ?? 0;
            break;
          case "Progress":
            downloaded += event.data.chunkLength;
            setState((s) => ({
              ...s,
              progress: total > 0 ? Math.round((downloaded / total) * 100) : s.progress,
            }));
            break;
          case "Finished":
            setState((s) => ({ ...s, phase: "ready", progress: 100 }));
            break;
        }
      });
    } catch (err) {
      setState({ phase: "error", progress: 0, error: err instanceof Error ? err.message : String(err) });
    }
  }, [pendingUpdate]);

  const restartToApply = useCallback(async () => {
    await relaunch();
  }, []);

  // Non-blocking check on app start, per Phase 9.4 spec.
  useEffect(() => {
    if (checkOnMount) {
      void checkForUpdate();
    }
  }, [checkOnMount, checkForUpdate]);

  return { state, checkForUpdate, installUpdate, restartToApply };
}
