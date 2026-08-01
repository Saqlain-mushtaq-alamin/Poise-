export interface SubScore {
  name: string;
  score: number;
  detail: string;
}

export interface ScoreDimension {
  name: string;
  score: number;
  max_score: number;
  weight: number;
  sub_scores: SubScore[];
  description: string;
  available: boolean;
}

export interface ActionItem {
  priority: "high" | "medium" | "low";
  category: "content" | "delivery" | "technical" | "communication";
  description: string;
  suggested_practice: string;
}

export interface SentenceAnnotation {
  text: string;
  rating: "strong" | "adequate" | "weak" | "filler" | "off_topic";
  reason: string;
  suggestion?: string | null;
  highlight_color: string;
}

export interface FrameworkAnalysis {
  framework: string;
  situation_present: boolean;
  task_present: boolean;
  action_present: boolean;
  result_present: boolean;
  result_has_metric: boolean;
}

export interface AnnotatedAnswer {
  sentences: SentenceAnnotation[];
  overall_structure: "well_structured" | "rambling" | "too_brief" | "unfocused";
  framework_analysis: FrameworkAnalysis;
}

export interface QuestionBreakdown {
  question: string;
  user_answer: string;
  score: number;
  skill_tags: string[];
  annotated_answer?: AnnotatedAnswer | null;
}

export interface FusedReport {
  session_id: string;
  mode: "interview" | "ielts";
  overall_score: number;
  dimensions: ScoreDimension[];
  strengths: string[];
  improvements: string[];
  action_items: ActionItem[];
  per_question_breakdown: QuestionBreakdown[];
  duration_minutes: number;
  generated_at: string;
  persona_label: string;
  jd_title: string;
}

export interface SessionSummary {
  session_id: string;
  mode: string;
  overall_score: number;
  duration_minutes: number;
  persona_label?: string | null;
  jd_title?: string | null;
  generated_at: string;
}

export interface TrendPoint {
  session_id: string;
  generated_at: string;
  overall_score: number;
  dimension_scores: Record<string, number>;
}

export interface TrendData {
  points: TrendPoint[];
  dimension_averages: Record<string, number>;
  overall_trend: "improving" | "stable" | "declining";
}

export interface SkillCoverage {
  skill: string;
  covered: boolean;
  evidence_question?: string | null;
  confidence: number;
}

export interface CoverageMatrix {
  required_skills: string[];
  coverage: SkillCoverage[];
  coverage_pct: number;
  gaps: string[];
}

export interface ReadinessVerdict {
  verdict: "ready" | "almost_ready" | "not_ready" | "insufficient_data";
  confidence: number;
  latest_score: number;
  average_score: number;
  trend: "improving" | "stable" | "declining";
  is_consistent: boolean;
  evidence: string[];
  recommendation: string;
}

export interface DebriefMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ModelAnswer {
  full_text: string;
  framework_used: string;
  key_elements: string[];
  why_it_works: string;
  is_placeholder: boolean;
}

export interface DiffSegment {
  text: string;
  kind: "unchanged" | "added" | "removed";
}

export interface AnswerDiff {
  segments: DiffSegment[];
  similarity_ratio: number;
}

export interface ModelAnswerResponse {
  model_answer: ModelAnswer;
  diff: AnswerDiff;
}

export interface ReplayEvent {
  timestamp_s: number;
  kind: "question" | "answer" | "note";
  label: string;
  detail: string;
}

export interface ReplayData {
  session_id: string;
  duration_minutes: number;
  events: ReplayEvent[];
}

export interface Playbook {
  title: string;
  description: string;
  exercises: { name: string; description: string; duration_minutes: number }[];
}
