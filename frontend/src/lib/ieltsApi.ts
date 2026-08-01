import { api as sharedApi, type PoiseAPI } from "../lib/api"; // Phase 1's shared PoiseAPI singleton (frontend/src/lib/api.ts)
import type {
  AnswerResult,
  CurrentPrompt,
  IELTSBandScore,
  IELTSSessionDetail,
  ProsodyAnalysis,
  PronunciationAnalysis,
} from "../types/ielts";

// Holds a reference to the live PoiseAPI client so the IELTS state machine
// always uses the correct sidecar port, even when it is dynamically assigned.
let _api: PoiseAPI = sharedApi;

export const ieltsApi = {
  /** Called by useIELTSSession whenever a new connected api is available. */
  syncApi(api: PoiseAPI) {
    _api = api;
  },

  createSession(targetBand = 6.5, topicsPreference?: string) {
    return _api.request<IELTSSessionDetail>("POST", "/ielts/sessions", {
      target_band: targetBand,
      topics_preference: topicsPreference ?? null,
    });
  },

  getSession(id: string) {
    return _api.request<IELTSSessionDetail>("GET", `/ielts/sessions/${id}`);
  },

  startSession(id: string) {
    return _api.request<IELTSSessionDetail>("POST", `/ielts/sessions/${id}/start`);
  },

  advance(id: string) {
    return _api.request<IELTSSessionDetail>("POST", `/ielts/sessions/${id}/advance`);
  },

  submitAnswer(id: string, audioPath: string, transcript: string) {
    return _api.request<AnswerResult>("POST", `/ielts/sessions/${id}/answer`, {
      audio_path: audioPath,
      transcript,
    });
  },

  getScore(id: string) {
    return _api.request<IELTSBandScore>("GET", `/ielts/sessions/${id}/score`);
  },

  getPronunciation(id: string) {
    return _api.request<PronunciationAnalysis[]>("GET", `/ielts/sessions/${id}/pronunciation`);
  },

  getProsody(id: string) {
    return _api.request<ProsodyAnalysis[]>("GET", `/ielts/sessions/${id}/prosody`);
  },
};

export type { CurrentPrompt };
