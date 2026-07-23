import { HashRouter, Route, Routes } from "react-router-dom";

import { Shell } from "./components/Shell";
import { ThemeProvider } from "./components/ThemeProvider";
import { useSidecar } from "./hooks/useSidecar";
import { Dashboard } from "./pages/Dashboard";
import { History } from "./pages/History";
import { IELTSSetup } from "./pages/IELTSSetup";
import { InterviewSetup } from "./pages/InterviewSetup";
import { Settings } from "./pages/Settings";

// HashRouter, not BrowserRouter: Tauri serves the app from a local file/
// custom-protocol origin, where History API routing has no server to fall
// back to on refresh/deep link.
export function App() {
  const { status, api } = useSidecar();

  return (
    <ThemeProvider api={api}>
      <HashRouter>
        <Shell sidecarStatus={status} api={api}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/interview" element={<InterviewSetup api={api} />} />
            <Route path="/ielts" element={<IELTSSetup />} />
            <Route path="/history" element={<History />} />
            <Route
              path="/settings"
              element={<Settings api={api} sidecarPort={status?.port ?? null} />}
            />
          </Routes>
        </Shell>
      </HashRouter>
    </ThemeProvider>
  );
}
