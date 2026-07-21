import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CoachingToast } from "./CoachingToast";

describe("CoachingToast", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders nothing when there's no tip", () => {
    const { container } = render(<CoachingToast tip={null} onDismiss={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the tip message", () => {
    render(
      <CoachingToast
        tip={{ category: "eye_contact", message: "Look at the camera lens.", severity: "gentle" }}
        onDismiss={vi.fn()}
      />
    );
    expect(screen.getByText("Look at the camera lens.")).toBeInTheDocument();
  });

  it("renders an exercise line when present", () => {
    render(
      <CoachingToast
        tip={{
          category: "breathing",
          message: "Slow down your breathing.",
          severity: "important",
          exercise: "Try 4-7-8 breathing.",
        }}
        onDismiss={vi.fn()}
      />
    );
    expect(screen.getByText("Try 4-7-8 breathing.")).toBeInTheDocument();
  });

  it("applies a severity-specific class", () => {
    render(
      <CoachingToast
        tip={{ category: "posture", message: "Sit up.", severity: "important" }}
        onDismiss={vi.fn()}
      />
    );
    expect(screen.getByRole("status")).toHaveClass("coaching-toast--important");
  });

  it("auto-dismisses after the configured duration", () => {
    const onDismiss = vi.fn();
    render(
      <CoachingToast
        tip={{ category: "eye_contact", message: "Look at the camera.", severity: "gentle" }}
        onDismiss={onDismiss}
        autoDismissMs={5000}
      />
    );

    expect(onDismiss).not.toHaveBeenCalled();
    vi.advanceTimersByTime(5000);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("does not fire onDismiss before the duration elapses", () => {
    const onDismiss = vi.fn();
    render(
      <CoachingToast
        tip={{ category: "eye_contact", message: "Look at the camera.", severity: "gentle" }}
        onDismiss={onDismiss}
        autoDismissMs={5000}
      />
    );

    vi.advanceTimersByTime(4000);
    expect(onDismiss).not.toHaveBeenCalled();
  });
});
