import { api } from "../lib/api"; // Phase 1's shared PoiseAPI singleton
import type {
  CoverageMatrix,
  DebriefMessage,
  FusedReport,
  ModelAnswerResponse,
  Playbook,
  ReadinessVerdict,
  ReplayData,
  SessionSummary,
  TrendData,
} from "../types/scoring";

export const scoringApi = {
  getReport(sessionId: string, refresh = false) {
    return api.request<FusedReport>("GET", `/scoring/sessions/${sessionId}/report${refresh ? "?refresh=true" : ""}`);
  },

  getReportPdfUrl(sessionId: string) {
    // Consumed directly as a download link / new-tab href, not via api.request.
    return `${api.baseUrl}/scoring/sessions/${sessionId}/report/pdf`;
  },

  getHistory(params: { mode?: string; limit?: number; offset?: number } = {}) {
    const qs = new URLSearchParams();
    if (params.mode) qs.set("mode", params.mode);
    if (params.limit) qs.set("limit", String(params.limit));
    if (params.offset) qs.set("offset", String(params.offset));
    return api.request<SessionSummary[]>("GET", `/scoring/history?${qs.toString()}`);
  },

  getTrends(params: { mode?: string; last_n?: number } = {}) {
    const qs = new URLSearchParams();
    if (params.mode) qs.set("mode", params.mode);
    if (params.last_n) qs.set("last_n", String(params.last_n));
    return api.request<TrendData>("GET", `/scoring/trends?${qs.toString()}`);
  },

  getReadiness(params: { mode?: string; target_score?: number } = {}) {
    const qs = new URLSearchParams();
    if (params.mode) qs.set("mode", params.mode);
    if (params.target_score) qs.set("target_score", String(params.target_score));
    return api.request<ReadinessVerdict>("GET", `/scoring/readiness?${qs.toString()}`);
  },

  getReplay(sessionId: string) {
    return api.request<ReplayData>("GET", `/scoring/sessions/${sessionId}/replay`);
  },

  getCoverage(sessionId: string, jdText: string) {
    return api.request<CoverageMatrix>("POST", `/scoring/sessions/${sessionId}/coverage`, { jd_text: jdText });
  },

  postDebrief(sessionId: string, message: string) {
    return api.request<DebriefMessage>("POST", `/scoring/sessions/${sessionId}/debrief`, { message });
  },

  getDebriefHistory(sessionId: string) {
    return api.request<DebriefMessage[]>("GET", `/scoring/sessions/${sessionId}/debrief`);
  },

  getAllPlaybooks() {
    return api.request<Record<string, Playbook>>("GET", "/scoring/playbooks");
  },

  getSessionPlaybooks(sessionId: string) {
    return api.request<(Playbook & { key: string })[]>("GET", `/scoring/sessions/${sessionId}/playbooks`);
  },

  getModelAnswer(sessionId: string, questionIndex: number, jdSummary = "", resumeSummary = "") {
    return api.request<ModelAnswerResponse>(
      "POST",
      `/scoring/sessions/${sessionId}/questions/${questionIndex}/model-answer`,
      { jd_summary: jdSummary, resume_summary: resumeSummary }
    );
  },
};
