import { useEffect, useState } from "react";
import { scoringApi } from "../lib/scoringApi";
import type { ReadinessVerdict, TrendData } from "../types/scoring";

export function useTrends(mode?: string) {
  const [trends, setTrends] = useState<TrendData | null>(null);
  const [readiness, setReadiness] = useState<ReadinessVerdict | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([scoringApi.getTrends({ mode }), scoringApi.getReadiness({ mode })])
      .then(([t, r]) => {
        setTrends(t);
        setReadiness(r);
      })
      .finally(() => setLoading(false));
  }, [mode]);

  return { trends, readiness, loading };
}
