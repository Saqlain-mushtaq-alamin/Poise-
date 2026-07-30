import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ConfidenceCalibration } from "../../../../contracts/types/motivation";
import { motivationApi } from "../../lib/motivationApi";
import "./motivation.css";

const TREND_LABEL: Record<ConfidenceCalibration["calibration_trend"], string> = {
  under_confident: "You tend to underrate yourself",
  over_confident: "You tend to overrate yourself",
  well_calibrated: "Well calibrated",
};

export function CalibrationChart() {
  const [data, setData] = useState<ConfidenceCalibration | null>(null);

  useEffect(() => {
    motivationApi.getCalibration().then(setData).catch(() => setData(null));
  }, []);

  if (!data) return null;

  if (data.historical_gaps.length === 0) {
    return (
      <div className="mv-card">
        <p className="mv-card-title">🪞 Confidence calibration</p>
        <div className="mv-empty-state">{data.insight}</div>
      </div>
    );
  }

  const chartData = data.historical_gaps.map((gap, i) => ({
    session: `S${i + 1}`,
    gap: Number(gap.toFixed(1)),
  }));

  return (
    <div className="mv-card">
      <p className="mv-card-title">🪞 Confidence calibration — {TREND_LABEL[data.calibration_trend]}</p>
      <div style={{ height: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid stroke="var(--color-surface)" strokeDasharray="3 3" />
            <XAxis dataKey="session" stroke="var(--color-text-muted)" fontSize={12} />
            <YAxis stroke="var(--color-text-muted)" fontSize={12} />
            <Tooltip
              contentStyle={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-surface)" }}
              formatter={(v: number) => [`${v > 0 ? "+" : ""}${v}`, "Self-rating minus actual (÷10)"]}
            />
            <Legend />
            <Line type="monotone" dataKey="gap" name="Calibration gap" stroke="var(--color-accent-primary)" strokeWidth={2} dot={{ r: 4 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p style={{ fontSize: 13, color: "var(--color-text-secondary)", marginTop: "var(--space-3)" }}>{data.insight}</p>
    </div>
  );
}
