import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { CostEstimate } from "../../lib/types";
import { CostLimitSlider } from "./CostLimitSlider";

const estimate: CostEstimate = {
  input_tokens: 1000,
  output_tokens: 500,
  total_tokens: 1500,
  estimated_cost_usd: 0.05,
  soft_cap_tokens: 50000,
  soft_cap_usd: 2.0,
  cap_warning: false,
};

describe("CostLimitSlider", () => {
  it("shows the current session usage", () => {
    render(<CostLimitSlider costEstimate={estimate} onChange={vi.fn()} />);
    expect(screen.getByText(/1,500 tokens/)).toBeInTheDocument();
  });

  it("flags the cap-warning state visually", () => {
    render(<CostLimitSlider costEstimate={{ ...estimate, cap_warning: true }} onChange={vi.fn()} />);
    expect(screen.getByText(/approaching your cap/)).toBeInTheDocument();
  });

  it("commits the new cap on release, not on every drag tick", () => {
    const onChange = vi.fn();
    render(<CostLimitSlider costEstimate={estimate} onChange={onChange} />);

    const slider = screen.getByLabelText(/tokens.*per session/i) as HTMLInputElement;
    fireEvent.change(slider, { target: { value: "100000" } });
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.mouseUp(slider);
    expect(onChange).toHaveBeenCalledWith(100000, expect.any(Number));
  });
});
