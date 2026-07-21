import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConfidenceOverlay } from "./ConfidenceOverlay";

describe("ConfidenceOverlay", () => {
  it("shows the rounded score", () => {
    render(
      <ConfidenceOverlay
        score={72.6}
        eyeContactRatio={0.8}
        expression="neutral"
        visible={true}
        onToggleVisible={vi.fn()}
      />
    );
    expect(screen.getByText("73")).toBeInTheDocument();
  });

  it("shows eye contact and expression indicators", () => {
    render(
      <ConfidenceOverlay
        score={80}
        eyeContactRatio={0.65}
        expression="happy"
        visible={true}
        onToggleVisible={vi.fn()}
      />
    );
    expect(screen.getByText(/65%/)).toBeInTheDocument();
    expect(screen.getByText(/happy/)).toBeInTheDocument();
  });

  it("shows a gesture indicator only when provided", () => {
    const { rerender } = render(
      <ConfidenceOverlay
        score={80}
        eyeContactRatio={0.65}
        expression="neutral"
        visible={true}
        onToggleVisible={vi.fn()}
      />
    );
    expect(screen.queryByTitle(/posture/i)).not.toBeInTheDocument();

    rerender(
      <ConfidenceOverlay
        score={80}
        eyeContactRatio={0.65}
        expression="neutral"
        gestureAssessment="natural"
        visible={true}
        onToggleVisible={vi.fn()}
      />
    );
    expect(screen.getByTitle(/posture/i)).toBeInTheDocument();
  });

  it("clamps an out-of-range score into the meter", () => {
    render(
      <ConfidenceOverlay
        score={150}
        eyeContactRatio={0.5}
        expression="neutral"
        visible={true}
        onToggleVisible={vi.fn()}
      />
    );
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuenow", "100");
  });

  it("minimizing hides the indicators but keeps the gauge", () => {
    render(
      <ConfidenceOverlay
        score={80}
        eyeContactRatio={0.65}
        expression="neutral"
        visible={true}
        onToggleVisible={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /minimize/i }));
    expect(screen.queryByText(/65%/)).not.toBeInTheDocument();
    expect(screen.getByText("80")).toBeInTheDocument();
  });

  it("renders a reopen button instead of the gauge when not visible", () => {
    const onToggleVisible = vi.fn();
    render(
      <ConfidenceOverlay
        score={80}
        eyeContactRatio={0.65}
        expression="neutral"
        visible={false}
        onToggleVisible={onToggleVisible}
      />
    );

    const reopenButton = screen.getByRole("button", { name: /show confidence overlay/i });
    fireEvent.click(reopenButton);
    expect(onToggleVisible).toHaveBeenCalled();
  });

  it("calls onToggleVisible when the hide (x) button is clicked", () => {
    const onToggleVisible = vi.fn();
    render(
      <ConfidenceOverlay
        score={80}
        eyeContactRatio={0.65}
        expression="neutral"
        visible={true}
        onToggleVisible={onToggleVisible}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /hide confidence overlay/i }));
    expect(onToggleVisible).toHaveBeenCalled();
  });
});
