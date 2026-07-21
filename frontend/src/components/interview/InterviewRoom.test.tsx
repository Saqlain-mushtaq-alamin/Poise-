import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { InterviewRoom } from "./InterviewRoom";

describe("InterviewRoom", () => {
  it("shows the completion message when isComplete is true", () => {
    render(
      <InterviewRoom
        currentMessage={null}
        lastFeedback={null}
        isComplete={true}
        busy={false}
        machineState="completed"
        onSubmitWarmUp={vi.fn()}
        onSubmitAnswer={vi.fn()}
        onEnd={vi.fn()}
      />
    );

    expect(screen.getByText("Interview complete")).toBeInTheDocument();
  });

  it("renders the current message and feedback", () => {
    render(
      <InterviewRoom
        currentMessage="Tell me about yourself."
        lastFeedback={{ score: 0.8, feedback: "Good detail.", reaction: "Nice." }}
        isComplete={false}
        busy={false}
        machineState={JSON.stringify({ inProgress: "listening" })}
        onSubmitWarmUp={vi.fn()}
        onSubmitAnswer={vi.fn()}
        onEnd={vi.fn()}
      />
    );

    expect(screen.getByText("Tell me about yourself.")).toBeInTheDocument();
    expect(screen.getByText(/Good detail\./)).toBeInTheDocument();
    expect(screen.getByText("Nice.")).toBeInTheDocument();
  });

  it("calls onSubmitAnswer (not onSubmitWarmUp) when not in warm-up", () => {
    const onSubmitAnswer = vi.fn();
    const onSubmitWarmUp = vi.fn();
    render(
      <InterviewRoom
        currentMessage="Q1?"
        lastFeedback={null}
        isComplete={false}
        busy={false}
        machineState={JSON.stringify({ inProgress: "listening" })}
        onSubmitWarmUp={onSubmitWarmUp}
        onSubmitAnswer={onSubmitAnswer}
        onEnd={vi.fn()}
      />
    );

    fireEvent.change(screen.getByLabelText(/your response/i), { target: { value: "My answer" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(onSubmitAnswer).toHaveBeenCalledWith("My answer");
    expect(onSubmitWarmUp).not.toHaveBeenCalled();
  });

  it("calls onSubmitWarmUp during warmUp state", () => {
    const onSubmitWarmUp = vi.fn();
    render(
      <InterviewRoom
        currentMessage="Hi there!"
        lastFeedback={null}
        isComplete={false}
        busy={false}
        machineState="warmUp"
        onSubmitWarmUp={onSubmitWarmUp}
        onSubmitAnswer={vi.fn()}
        onEnd={vi.fn()}
      />
    );

    fireEvent.change(screen.getByLabelText(/your response/i), { target: { value: "Doing well!" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(onSubmitWarmUp).toHaveBeenCalledWith("Doing well!");
  });

  it("clears the draft after sending", () => {
    render(
      <InterviewRoom
        currentMessage="Q1?"
        lastFeedback={null}
        isComplete={false}
        busy={false}
        machineState={JSON.stringify({ inProgress: "listening" })}
        onSubmitWarmUp={vi.fn()}
        onSubmitAnswer={vi.fn()}
        onEnd={vi.fn()}
      />
    );

    const textarea = screen.getByLabelText(/your response/i) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "My answer" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(textarea.value).toBe("");
  });

  it("does not send an empty draft", () => {
    const onSubmitAnswer = vi.fn();
    render(
      <InterviewRoom
        currentMessage="Q1?"
        lastFeedback={null}
        isComplete={false}
        busy={false}
        machineState={JSON.stringify({ inProgress: "listening" })}
        onSubmitWarmUp={vi.fn()}
        onSubmitAnswer={onSubmitAnswer}
        onEnd={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    expect(onSubmitAnswer).not.toHaveBeenCalled();
  });

  it("calls onEnd when End interview is clicked", () => {
    const onEnd = vi.fn();
    render(
      <InterviewRoom
        currentMessage="Q1?"
        lastFeedback={null}
        isComplete={false}
        busy={false}
        machineState={JSON.stringify({ inProgress: "listening" })}
        onSubmitWarmUp={vi.fn()}
        onSubmitAnswer={vi.fn()}
        onEnd={onEnd}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /end interview/i }));
    expect(onEnd).toHaveBeenCalled();
  });

  it("disables the send button while busy", () => {
    render(
      <InterviewRoom
        currentMessage="Q1?"
        lastFeedback={null}
        isComplete={false}
        busy={true}
        machineState={JSON.stringify({ inProgress: "listening" })}
        onSubmitWarmUp={vi.fn()}
        onSubmitAnswer={vi.fn()}
        onEnd={vi.fn()}
      />
    );

    expect(screen.getByRole("button", { name: /sending/i })).toBeDisabled();
  });
});
