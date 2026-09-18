from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

# -- fused report ------------------------------------------------------------


class SubScoreOut(BaseModel):
    name: str
    score: float
    detail: str = ""


class ScoreDimensionOut(BaseModel):
    name: str
    score: float
    max_score: float
    weight: float
    sub_scores: list[SubScoreOut] = []
    description: str = ""
    available: bool = True


class ActionItemOut(BaseModel):
    priority: str
    category: str
    description: str
    suggested_practice: str


class SentenceAnnotationOut(BaseModel):
    text: str
    rating: str
    reason: str
    suggestion: str | None = None
    highlight_color: str = "gray"


class FrameworkAnalysisOut(BaseModel):
    framework: str
    situation_present: bool = False
    task_present: bool = False
    action_present: bool = False
    result_present: bool = False
    result_has_metric: bool = False


class AnnotatedAnswerOut(BaseModel):
    sentences: list[SentenceAnnotationOut]
    overall_structure: str
    framework_analysis: FrameworkAnalysisOut


class QuestionBreakdownOut(BaseModel):
    question: str
    user_answer: str
    score: float
    skill_tags: list[str] = []
    annotated_answer: AnnotatedAnswerOut | None = None


class CostEstimateOut(BaseModel):
    provider: str
    input_tokens: int
    output_tokens: int
    estimated_usd: float


class FusedReportOut(BaseModel):
    session_id: str
    mode: str
    overall_score: float
    dimensions: list[ScoreDimensionOut]
    strengths: list[str]
    improvements: list[str]
    action_items: list[ActionItemOut]
    per_question_breakdown: list[QuestionBreakdownOut]
    duration_minutes: float
    generated_at: datetime
    cost_estimate: CostEstimateOut | None = None
    persona_label: str = ""
    jd_title: str = ""


# -- history / trends ---------------------------------------------------------


class SessionSummaryOut(BaseModel):
    session_id: str
    mode: str
    overall_score: float
    duration_minutes: float
    persona_label: str | None = None
    jd_title: str | None = None
    generated_at: datetime


class TrendPointOut(BaseModel):
    session_id: str
    generated_at: datetime
    overall_score: float
    dimension_scores: dict[str, float]


class TrendDataOut(BaseModel):
    points: list[TrendPointOut]
    dimension_averages: dict[str, float]
    overall_trend: str  # "improving" | "stable" | "declining"


# -- coverage ------------------------------------------------------------------


class SkillCoverageOut(BaseModel):
    skill: str
    covered: bool
    evidence_question: str | None = None
    confidence: float = 0.0


class CoverageMatrixOut(BaseModel):
    required_skills: list[str]
    coverage: list[SkillCoverageOut]
    coverage_pct: float
    gaps: list[str]


class CoverageRequest(BaseModel):
    jd_text: str


# -- readiness -----------------------------------------------------------------


class ReadinessVerdictOut(BaseModel):
    verdict: str
    confidence: float
    latest_score: float
    average_score: float
    trend: str
    is_consistent: bool
    evidence: list[str]
    recommendation: str


# -- debrief ---------------------------------------------------------------------


class DebriefMessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DebriefRequest(BaseModel):
    message: str


# -- model answer ----------------------------------------------------------------


class ModelAnswerOut(BaseModel):
    full_text: str
    framework_used: str
    key_elements: list[str] = []
    why_it_works: str = ""
    is_placeholder: bool = False


class DiffSegmentOut(BaseModel):
    text: str
    kind: str


class AnswerDiffOut(BaseModel):
    segments: list[DiffSegmentOut]
    similarity_ratio: float


class ModelAnswerResponse(BaseModel):
    model_answer: ModelAnswerOut
    diff: AnswerDiffOut


class ModelAnswerRequest(BaseModel):
    jd_summary: str = ""
    resume_summary: str = ""


# -- replay ----------------------------------------------------------------------


class ReplayEventOut(BaseModel):
    timestamp_s: float
    kind: str          # "question" | "answer" | "note"
    label: str
    detail: str = ""


class ReplayDataOut(BaseModel):
    session_id: str
    duration_minutes: float
    events: list[ReplayEventOut]
