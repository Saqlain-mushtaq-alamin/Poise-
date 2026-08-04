import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ModelConfigCard } from "./ModelConfigCard";

describe("ModelConfigCard", () => {
  it("renders nothing when there's no model plan yet", () => {
    const { container } = render(<ModelConfigCard modelPlan={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders every role and its model", () => {
    render(
      <ModelConfigCard
        modelPlan={{ llm: "qwen2.5:14b", vlm: "qwen2-vl:7b", stt: "large-v3", tts: "xtts-v2", embedding: "nomic-embed-text" }}
      />
    );

    expect(screen.getByText(/qwen2\.5:14b/)).toBeInTheDocument();
    expect(screen.getByText("qwen2-vl:7b")).toBeInTheDocument();
    expect(screen.getByText("large-v3")).toBeInTheDocument();
  });

  it("shows a placeholder for a role with no model at this tier", () => {
    render(
      <ModelConfigCard
        modelPlan={{ llm: "qwen2.5:7b", vlm: null, stt: "small", tts: "piper", embedding: "nomic-embed-text" }}
      />
    );

    expect(screen.getByText(/not available at this tier/)).toBeInTheDocument();
  });
});
