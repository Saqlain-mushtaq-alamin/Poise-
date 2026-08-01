import { useEffect, useState } from "react";
import { scoringApi } from "../lib/scoringApi";
import type { SessionSummary } from "../types/scoring";

export function useHistory(mode?: string) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    scoringApi
      .getHistory({ mode })
      .then(setSessions)
      .finally(() => setLoading(false));
  }, [mode]);

  return { sessions, loading };
}
