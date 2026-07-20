import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiKeyManager } from "./ApiKeyManager";

describe("ApiKeyManager", () => {
  it("shows a configured badge only for providers with a stored key", () => {
    render(
      <ApiKeyManager
        configuredProviders={["openai"]}
        onStore={vi.fn()}
        onDelete={vi.fn()}
        onTest={vi.fn()}
      />
    );

    const openaiRow = screen.getByText("OpenAI").closest(".api-key-row") as HTMLElement;
    expect(within(openaiRow).getByText("Configured")).toBeInTheDocument();

    const anthropicRow = screen.getByText("Anthropic").closest(".api-key-row") as HTMLElement;
    expect(within(anthropicRow).getByText("Not configured")).toBeInTheDocument();
  });

  it("calls onStore with the entered key when Save is clicked", async () => {
    const onStore = vi.fn().mockResolvedValue(undefined);
    render(
      <ApiKeyManager configuredProviders={[]} onStore={onStore} onDelete={vi.fn()} onTest={vi.fn()} />
    );

    const openaiRow = screen.getByText("OpenAI").closest(".api-key-row") as HTMLElement;
    const input = within(openaiRow).getByLabelText(/OpenAI API key/i);
    fireEvent.change(input, { target: { value: "sk-test-123" } });
    fireEvent.click(within(openaiRow).getByRole("button", { name: /save/i }));

    await waitFor(() => expect(onStore).toHaveBeenCalledWith("openai", "sk-test-123", undefined));
  });

  it("calls onTest and renders a success result", async () => {
    const onTest = vi.fn().mockResolvedValue({
      provider: "openai",
      success: true,
      latency_ms: 120,
      models_available: 5,
    });
    render(
      <ApiKeyManager configuredProviders={[]} onStore={vi.fn()} onDelete={vi.fn()} onTest={onTest} />
    );

    const openaiRow = screen.getByText("OpenAI").closest(".api-key-row") as HTMLElement;
    fireEvent.click(within(openaiRow).getByRole("button", { name: /test connection/i }));

    await waitFor(() => expect(within(openaiRow).getByText(/Connected/)).toBeInTheDocument());
    expect(onTest).toHaveBeenCalledWith("openai", undefined, undefined);
  });

  it("renders a failure result from onTest", async () => {
    const onTest = vi.fn().mockResolvedValue({
      provider: "openai",
      success: false,
      latency_ms: 50,
      models_available: null,
      error: "invalid key",
    });
    render(
      <ApiKeyManager configuredProviders={[]} onStore={vi.fn()} onDelete={vi.fn()} onTest={onTest} />
    );

    const openaiRow = screen.getByText("OpenAI").closest(".api-key-row") as HTMLElement;
    fireEvent.click(within(openaiRow).getByRole("button", { name: /test connection/i }));

    await waitFor(() => expect(within(openaiRow).getByText(/Failed: invalid key/)).toBeInTheDocument());
  });

  it("shows a Remove button only for configured providers, and calls onDelete", async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(
      <ApiKeyManager configuredProviders={["groq"]} onStore={vi.fn()} onDelete={onDelete} onTest={vi.fn()} />
    );

    const groqRow = screen.getByText("Groq").closest(".api-key-row") as HTMLElement;
    fireEvent.click(within(groqRow).getByRole("button", { name: /remove/i }));

    await waitFor(() => expect(onDelete).toHaveBeenCalledWith("groq"));

    const openaiRow = screen.getByText("OpenAI").closest(".api-key-row") as HTMLElement;
    expect(within(openaiRow).queryByRole("button", { name: /remove/i })).not.toBeInTheDocument();
  });

  it("renders a base URL field only for the custom provider", () => {
    render(
      <ApiKeyManager configuredProviders={[]} onStore={vi.fn()} onDelete={vi.fn()} onTest={vi.fn()} />
    );

    const customRow = screen.getByText(/Custom \(OpenAI-compatible\)/).closest(".api-key-row") as HTMLElement;
    expect(within(customRow).getByLabelText(/base url/i)).toBeInTheDocument();

    const openaiRow = screen.getByText("OpenAI").closest(".api-key-row") as HTMLElement;
    expect(within(openaiRow).queryByLabelText(/base url/i)).not.toBeInTheDocument();
  });
});
