import { useCallback, useEffect, useState } from "react";
import { scoringApi } from "../lib/scoringApi";
import type { FusedReport } from "../types/scoring";

export function useSessionReport(sessionId: string) {
  const [report, setReport] = useState<FusedReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    (refresh = false) => {
      setLoading(true);
      setError(null);
      scoringApi
        .getReport(sessionId, refresh)
        .then(setReport)
        .catch((e) => setError(String(e)))
        .finally(() => setLoading(false));
    },
    [sessionId]
  );

  useEffect(() => load(), [load]);

  return { report, loading, error, refresh: () => load(true) };
}
