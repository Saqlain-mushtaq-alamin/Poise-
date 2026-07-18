import { useCallback, useEffect, useState, type ReactNode } from "react";

import type { PoiseAPI } from "../lib/api";
import { ThemeContext, type Theme } from "../lib/theme-context";

const THEME_SETTING_KEY = "theme";
const DEFAULT_THEME: Theme = "dark";

interface ThemeProviderProps {
  children: ReactNode;
  /** null while the sidecar isn't connected yet — theme still applies
   * in-memory, it just won't persist until the API is available. */
  api: PoiseAPI | null;
}

export function ThemeProvider({ children, api }: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>(DEFAULT_THEME);
  const [loaded, setLoaded] = useState(false);

  // Load persisted preference once the sidecar API becomes available.
  useEffect(() => {
    if (!api || loaded) return;
    let cancelled = false;

    api
      .getSetting(THEME_SETTING_KEY)
      .then((res) => {
        if (!cancelled && (res.value === "dark" || res.value === "light")) {
          setThemeState(res.value);
        }
      })
      .catch(() => {
        // No persisted value yet, or sidecar hiccup — keep the default.
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });

    return () => {
      cancelled = true;
    };
  }, [api, loaded]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const setTheme = useCallback(
    (next: Theme) => {
      setThemeState(next);
      api?.putSetting(THEME_SETTING_KEY, next).catch(() => {
        // Best-effort persistence; the in-memory theme still applies.
      });
    },
    [api]
  );

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
