"""
Pydantic schemas for Phase 6 — Coding Sandbox.

Mount point: backend/app/schemas/coding.py

These are the request/response models used by the coding router and
services. They mirror the dataclasses sketched in the planning doc
06-coding-sandbox.md, but as Pydantic v2 models so FastAPI can
validate + auto-document them (and so LLM structured-output calls can
use `model_validate_json` directly).
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------

class Language(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CPP = "cpp"
    GO = "go"
    RUST = "rust"


class ExecutionStatus(str, Enum):
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    RUNTIME_ERROR = "runtime_error"
    TIME_LIMIT = "time_limit"
    MEMORY_LIMIT = "memory_limit"
    COMPILE_ERROR = "compile_error"
    INTERNAL_ERROR = "internal_error"


class ApproachAssessment(str, Enum):
    BRUTE_FORCE = "brute_force"
    NEAR_OPTIMAL = "near_optimal"
    OPTIMAL = "optimal"


# --------------------------------------------------------------------------
# Problem
# --------------------------------------------------------------------------

class Example(BaseModel):
    input: str
    output: str
    explanation: Optional[str] = None


class TestCase(BaseModel):
    input: str
    expected_output: str
    is_hidden: bool = False


class CodingProblem(BaseModel):
    id: Optional[str] = None
    title: str
    description: str  # Markdown formatted
    examples: list[Example] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    test_cases: list[TestCase] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)
    difficulty: str = "medium"
    topics: list[str] = Field(default_factory=list)
    starter_code: dict[str, str] = Field(default_factory=dict)  # language -> template


class ProblemGenerateRequest(BaseModel):
    session_id: Optional[str] = None
    jd_id: Optional[str] = None
    resume_id: Optional[str] = None
    difficulty: str = "medium"
    topics: list[str] = Field(default_factory=list)  # optional steer, e.g. ["arrays", "graphs"]
    language_hint: Optional[Language] = None


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------

class CodeSubmission(BaseModel):
    code: str
    language: Language
    problem_id: Optional[str] = None
    test_cases: list[TestCase] = Field(default_factory=list)
    time_limit_seconds: int = 10
    memory_limit_mb: int = 256
    stdin: Optional[str] = None  # for ad-hoc "Run" without test cases


class TestCaseResult(BaseModel):
    input: str
    expected_output: str
    actual_output: str
    passed: bool
    is_hidden: bool = False
    execution_time_ms: Optional[int] = None
    error: Optional[str] = None


class ExecutionResult(BaseModel):
    status: ExecutionStatus
    stdout: str = ""
    stderr: str = ""
    execution_time_ms: int = 0
    memory_used_mb: float = 0.0
    test_results: list[TestCaseResult] = Field(default_factory=list)
    executor: str = "subprocess"  # "judge0" | "subprocess"
    passed_count: int = 0
    total_count: int = 0


# --------------------------------------------------------------------------
# LLM Evaluation
# --------------------------------------------------------------------------

class CodeEvaluation(BaseModel):
    correctness_score: float = Field(ge=0, le=100)
    style_score: float = Field(ge=0, le=100)
    efficiency_score: float = Field(ge=0, le=100)
    approach_assessment: ApproachAssessment
    time_complexity: str
    space_complexity: str
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    alternative_approaches: list[str] = Field(default_factory=list)
    overall_score: float = Field(ge=0, le=100)


class CodeEvaluateRequest(BaseModel):
    code: str
    language: Language
    problem_id: str
    execution_result: Optional[ExecutionResult] = None


# --------------------------------------------------------------------------
# Screen / Whiteboard VLM
# --------------------------------------------------------------------------

class ScreenEvaluation(BaseModel):
    description: str
    diagram_quality: float = Field(ge=0, le=100)
    completeness: float = Field(ge=0, le=100)
    feedback: list[str] = Field(default_factory=list)


class ScreenEvaluateRequest(BaseModel):
    context: str = ""
    session_id: Optional[str] = None


# --------------------------------------------------------------------------
# Coding Round (Phase 4 handoff unit)
# --------------------------------------------------------------------------

class CodingRoundStartRequest(BaseModel):
    difficulty: str = "medium"
    topics: list[str] = Field(default_factory=list)
    language_hint: Optional[Language] = None


class CodingRoundStartResponse(BaseModel):
    round_id: str
    problem: CodingProblem


class CodingRoundCompleteResponse(BaseModel):
    round_id: str
    session_id: str
    final_evaluation: CodeEvaluation
    execution_summary: ExecutionResult
    screen_evaluations: list[ScreenEvaluation] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Interim Mid-Coding Review
# --------------------------------------------------------------------------

class InterimCodeReviewRequest(BaseModel):
    session_id: Optional[str] = None
    question: str
    code: str
    language: str = "python"
    persona_id: str = "professional"


class InterimCodeReviewResponse(BaseModel):
    interviewer_message: str
    status: str = "good_progress"  # "on_track" | "needs_modification" | "good_progress"
    suggested_improvements: list[str] = Field(default_factory=list)

