// Phase 10 — Motivation Engine shared types.
// Append these to `contracts/types/index.d.ts` (or import this file from it).

export interface StreakData {
  current_streak_days: number;
  longest_streak_days: number;
  total_practice_days: number;
  total_sessions: number;
  total_practice_hours: number;
  last_practice_date: string | null; // ISO date
  streak_status: "active" | "at_risk" | "broken" | "none";
  calendar: Record<string, number>; // ISO date -> session count
}

export interface Goal {
  id: string;
  type: "ielts_band" | "interview_score" | "sessions_per_week";
  target_value: number;
  current_value: number;
  starting_value: number;
  deadline: string | null;
  created_at: string;
  status: "active" | "achieved" | "abandoned";
  progress_percent: number;
  projected_completion: string | null;
}

export interface GoalCreate {
  type: Goal["type"];
  target_value: number;
  deadline?: string | null;
}

export interface PracticeItem {
  id: string;
  category: "behavioral" | "technical" | "pronunciation" | "topic";
  content: string;
  source_sessions: string[];
  difficulty: number;
  easiness_factor: number;
  interval_days: number;
  repetitions: number;
  next_review_date: string;
  last_score: number | null;
  is_mastered: boolean;
}

export interface CoachSummary {
  week_start: string;
  sessions_count: number;
  practice_time_hours: number;
  score_trend: "improving" | "stable" | "declining" | "no_data";
  narrative: string;
  focus_areas: string[];
  celebration: string[];
  next_week_plan: string[];
  generated_at: string;
}

export interface Achievement {
  id: string;
  name: string;
  icon: string;
  desc: string;
  category: string;
  unlocked: boolean;
  unlocked_at: string | null;
}

export interface PracticeSuggestion {
  type: "review" | "new_skill" | "improvement";
  title: string;
  reason: string;
  priority: "high" | "medium" | "low";
  action?: Record<string, string> | null;
}

export interface NotificationSettings {
  streak_reminders: boolean;
  weekly_summary: boolean;
  goal_progress: boolean;
  achievements: boolean;
  quiet_hours_start: string; // "HH:MM"
  quiet_hours_end: string;
  max_per_day: number;
}

export interface NotificationEvent {
  type: "streak_at_risk" | "weekly_summary_ready" | "goal_approaching" | "achievement_unlocked";
  title: string;
  body: string;
}

export interface ReflectionPrompt {
  prompt_id: string;
  prompt: string;
  purpose: string;
}

export interface ReflectionAnswer {
  prompt_id: string;
  response?: string | null;
  self_rating?: number | null;
}

export interface ReflectionSubmission {
  session_id: string;
  answers: ReflectionAnswer[];
}

export interface ConfidenceCalibration {
  self_rating: number;
  actual_score: number;
  calibration_gap: number;
  calibration_trend: "over_confident" | "under_confident" | "well_calibrated";
  historical_gaps: number[];
  insight: string;
}

export interface AnxietyExercise {
  id: string;
  name: string;
  type: "breathing" | "body" | "mental" | "vocal" | "cognitive";
  description: string;
  duration_seconds: number;
  pattern?: { inhale: number; hold: number; exhale: number; cycles: number };
  warmup_text?: string;
  message?: string; // only present on positive_reframe
}

export interface InterviewDayConfig {
  company_format: "amazon" | "google" | "meta" | "custom";
  total_rounds: number;
  break_duration_minutes: number;
  include_lunch_break: boolean;
  fatigue_tracking: boolean;
}

export interface FatigueAnalysis {
  confidence_by_round: number[];
  quality_by_round: number[];
  energy_trend: "sustained" | "gradual_decline" | "sharp_drop" | "insufficient_data";
  recommendation: string;
}

export interface RoundComparison {
  round_number: number;
  confidence_score: number | null;
  quality_score: number | null;
  delta_from_round_1: number | null;
}

export interface InterviewDayReport {
  id: string;
  status: string;
  rounds_completed: number;
  total_rounds: number;
  fatigue_analysis: FatigueAnalysis | null;
  overall_verdict: string;
  stamina_score: number | null;
  round_comparison: RoundComparison[];
}
