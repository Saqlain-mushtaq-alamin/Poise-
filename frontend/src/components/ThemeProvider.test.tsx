import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useTheme } from "../hooks/useTheme";
import { ThemeProvider } from "./ThemeProvider";

function Probe() {
  const { theme, toggleTheme } = useTheme();
  return (
    <button onClick={toggleTheme} data-testid="probe">
      {theme}
    </button>
  );
}

describe("ThemeProvider / useTheme", () => {
  it("defaults to dark and toggles to light", async () => {
    render(
      <ThemeProvider api={null}>
        <Probe />
      </ThemeProvider>
    );

    const button = screen.getByTestId("probe");
    expect(button).toHaveTextContent("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    await act(async () => {
      button.click();
    });

    expect(button).toHaveTextContent("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("persists the theme change via the sidecar API when available", async () => {
    const putSetting = vi.fn().mockResolvedValue({ value: "light" });
    const getSetting = vi.fn().mockResolvedValue({ value: null });
    const fakeApi = { putSetting, getSetting } as unknown as import("../lib/api").PoiseAPI;

    render(
      <ThemeProvider api={fakeApi}>
        <Probe />
      </ThemeProvider>
    );

    await act(async () => {
      screen.getByTestId("probe").click();
    });

    expect(putSetting).toHaveBeenCalledWith("theme", "light");
  });

  it("loads a previously persisted theme from the sidecar", async () => {
    const fakeApi = {
      getSetting: vi.fn().mockResolvedValue({ value: "light" }),
      putSetting: vi.fn(),
    } as unknown as import("../lib/api").PoiseAPI;

    render(
      <ThemeProvider api={fakeApi}>
        <Probe />
      </ThemeProvider>
    );

    await screen.findByText("light");
  });
});
