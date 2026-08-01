// Phase 10 — typed client for /motivation/* endpoints.
// Built on top of the shared `PoiseAPI` request helper from Phase 1
// (`frontend/src/lib/api.ts`) — swap the import path if yours differs.
import type {
  Achievement,
  AnxietyExercise,
  CoachSummary,
  ConfidenceCalibration,
  Goal,
  GoalCreate,
  InterviewDayConfig,
  InterviewDayReport,
  NotificationEvent,
  NotificationSettings,
  PracticeItem,
  PracticeSuggestion,
  ReflectionPrompt,
  ReflectionSubmission,
  StreakData,
} from "../../../contracts/types/motivation";
import { api } from "./api"; // Phase 1's PoiseAPI singleton/instance

export const motivationApi = {
  getStreak: () => api.request<StreakData>("GET", "/motivation/streak"),

  listGoals: () => api.request<Goal[]>("GET", "/motivation/goals"),
  createGoal: (body: GoalCreate) => api.request<Goal>("POST", "/motivation/goals", body),
  getGoalProgress: (id: string) => api.request<Goal>("GET", `/motivation/goals/${id}/progress`),

  getPracticeQueue: (limit = 3) =>
    api.request<PracticeSuggestion[]>("GET", `/motivation/practice-queue?limit=${limit}`),

  getDueItems: (limit = 5) =>
    api.request<PracticeItem[]>("GET", `/motivation/spaced-repetition/due?limit=${limit}`),
  reviewItem: (id: string, score: number) =>
    api.request<PracticeItem>("POST", `/motivation/spaced-repetition/${id}/review`, { score }),

  getWeeklySummary: (weekStart?: string, refresh = false) =>
    api.request<CoachSummary>(
      "GET",
      `/motivation/weekly-summary?${weekStart ? `week_start=${weekStart}&` : ""}refresh=${refresh}`
    ),

  listAchievements: () => api.request<Achievement[]>("GET", "/motivation/achievements"),

  getNotificationSettings: () => api.request<NotificationSettings>("GET", "/motivation/notifications/settings"),
  updateNotificationSettings: (body: NotificationSettings) =>
    api.request<NotificationSettings>("PUT", "/motivation/notifications/settings", body),
  getPendingNotification: () =>
    api.request<NotificationEvent | null>("GET", "/motivation/notifications/pending"),

  getReflectionPrompts: () => api.request<ReflectionPrompt[]>("GET", "/motivation/reflection/prompts"),
  submitReflection: (body: ReflectionSubmission) =>
    api.request<{ self_rating: number | null; session_id: string }>(
      "POST", "/motivation/reflection/submit", body
    ),

  getCalibration: () => api.request<ConfidenceCalibration>("GET", "/motivation/calibration"),

  getAnxietyToolkit: () => api.request<{ exercises: AnxietyExercise[] }>("GET", "/motivation/anxiety-toolkit"),

  startInterviewDay: (config: InterviewDayConfig) =>
    api.request<InterviewDayReport>("POST", "/motivation/interview-day", config),
  getInterviewDay: (id: string) => api.request<InterviewDayReport>("GET", `/motivation/interview-day/${id}`),
};

/**
 * Poll for a pending notification and forward it to the OS tray via
 * Tauri's notification plugin. Call this from a `setInterval` (e.g. every
 * 5 minutes) in the app shell — not more often, the backend already caps
 * delivery at `max_per_day`.
 */
export async function pollAndDeliverNotification(): Promise<void> {
  const pending = await motivationApi.getPendingNotification();
  if (!pending) return;

  const { isPermissionGranted, requestPermission, sendNotification } = await import(
    "@tauri-apps/plugin-notification"
  );
  let granted = await isPermissionGranted();
  if (!granted) {
    granted = (await requestPermission()) === "granted";
  }
  if (granted) {
    sendNotification({ title: pending.title, body: pending.body });
  }
}
