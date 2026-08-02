import { useMemo } from "react";
import { HashRouter, Route, Routes, useNavigate, useParams } from "react-router-dom";

import { Shell } from "./components/Shell";
import { ThemeProvider } from "./components/ThemeProvider";
import { useSidecar } from "./hooks/useSidecar";
import { api as sharedApi, PoiseAPI } from "./lib/api";
import { CodingAPI } from "./lib/codingApi";
import Analytics from "./pages/Analytics";
import { CodingRound } from "./pages/CodingRound";
import { Dashboard } from "./pages/Dashboard";
import History from "./pages/History";
import IELTSSession from "./pages/IELTSSession";
import { InterviewSetup } from "./pages/InterviewSetup";
import SessionReport from "./pages/SessionReport";
import { Settings } from "./pages/Settings";

function DashboardPage() {
  const navigate = useNavigate();
  return (
    <Dashboard
      onStartInterview={() => navigate("/interview")}
      onStartIelts={() => navigate("/ielts")}
    />
  );
}

function HistoryPage() {
  const navigate = useNavigate();
  return <History onSelectSession={(id) => navigate(`/report/${id}`)} />;
}

function SessionReportPage() {
  const { id } = useParams<{ id: string }>();
  if (!id) return <div className="page">Invalid Session ID</div>;
  return <SessionReport sessionId={id} />;
}

function CodingRoundPage({ api }: { api: PoiseAPI | null }) {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const codingApi = useMemo(() => new CodingAPI(api ?? sharedApi), [api]);
  return (
    <CodingRound
      sessionId={id || "demo-session"}
      codingApi={codingApi}
      onComplete={() => navigate(id ? `/report/${id}` : "/history")}
    />
  );
}

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
            <Route path="/" element={<DashboardPage />} />
            <Route path="/interview" element={<InterviewSetup api={api} />} />
            <Route path="/ielts" element={<IELTSSession api={api} />} />
            <Route path="/coding" element={<CodingRoundPage api={api} />} />
            <Route path="/coding/:id" element={<CodingRoundPage api={api} />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/report/:id" element={<SessionReportPage />} />
            <Route path="/analytics" element={<Analytics />} />
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
