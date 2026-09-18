"""
Score fusion engine — combines sub-scores from Phase 4 (content), Phase 5
(webcam confidence), Phase 6 (coding), Phase 3 (communication/prosody), and
Phase 7 (IELTS) into one `FusedReport`.

Data-source adapter pattern
----------------------------
This phase's job is aggregation, but the four upstream phases' actual
persistence schemas aren't available to this deliverable. Rather than
guess at table/column names and risk a fragile "integration" that silently
returns wrong numbers, sub-score retrieval is behind the `ScoreSourceAdapter`
Protocol below. Two implementations ship:

  - `IELTSScoreSourceAdapter` — REAL, fully wired against Phase 7's actual
    `IELTSSession` / `IELTSAnswer` models (both live in this codebase).
  - `InterviewScoreSourceAdapter` — the integration point for Phases 3/4/5/6.
    Its methods raise `DimensionUnavailable` by default. `ScoreFusionEngine`
    catches that per-dimension (not per-report) and renders the dimension
    as "not yet available" rather than failing the whole report — so this
    phase merges and runs *today*, and each dimension lights up for real
    the moment you implement its adapter method against your actual
    Phase 3/4/5/6 tables. See README "Wiring the adapters" for the exact
    method signatures to fill in and what each one is expected to return.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Optional

from app.services.scoring.llm_client import ScoringLLMClient


class DimensionUnavailable(Exception):
    """Raised by an adapter method when the upstream phase's data isn't wired yet."""


# ---------------------------------------------------------------------------
# Dataclasses (mirror the spec's dataclasses in 07-scoring-progress.md §8.1)
# ---------------------------------------------------------------------------


@dataclass
class SubScore:
    name: str
    score: float          # 0-100
    detail: str = ""


@dataclass
class ScoreDimension:
    name: str
    score: float                       # 0-100, or -1 if unavailable
    max_score: float
    weight: float
    sub_scores: list[SubScore] = field(default_factory=list)
    description: str = ""
    available: bool = True


@dataclass
class ActionItem:
    priority: str          # "high" | "medium" | "low"
    category: str          # "content" | "delivery" | "technical" | "communication"
    description: str
    suggested_practice: str


@dataclass
class SentenceAnnotation:
    text: str
    rating: str             # "strong" | "adequate" | "weak" | "filler" | "off_topic"
    reason: str
    suggestion: Optional[str] = None
    highlight_color: str = "gray"   # green / yellow / red / gray


@dataclass
class FrameworkAnalysis:
    framework: str                      # "STAR" | "SOAR" | "none_detected"
    situation_present: bool = False
    task_present: bool = False
    action_present: bool = False
    result_present: bool = False
    result_has_metric: bool = False


@dataclass
class AnnotatedAnswer:
    sentences: list[SentenceAnnotation]
    overall_structure: str              # "well_structured" | "rambling" | "too_brief" | "unfocused"
    framework_analysis: FrameworkAnalysis


@dataclass
class QuestionBreakdown:
    question: str
    user_answer: str
    score: float                        # 0-100
    skill_tags: list[str] = field(default_factory=list)
    annotated_answer: Optional[AnnotatedAnswer] = None


@dataclass
class CostEstimate:
    provider: str
    input_tokens: int
    output_tokens: int
    estimated_usd: float


@dataclass
class FusedReport:
    session_id: str
    mode: str                            # "interview" | "ielts"
    overall_score: float                 # 0-100
    dimensions: list[ScoreDimension]
    strengths: list[str]
    improvements: list[str]
    action_items: list[ActionItem]
    per_question_breakdown: list[QuestionBreakdown]
    duration_minutes: float
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cost_estimate: Optional[CostEstimate] = None
    persona_label: str = ""
    jd_title: str = ""


# ---------------------------------------------------------------------------
# Adapter protocol
# ---------------------------------------------------------------------------


class ScoreSourceAdapter(ABC):
    """One adapter per upstream phase's data. Each `get_*` method returns a
    `ScoreDimension` (0-100 `score`) or raises `DimensionUnavailable`."""

    @abstractmethod
    async def get_content_scores(self, session_id: str) -> ScoreDimension: ...

    @abstractmethod
    async def get_confidence_summary(self, session_id: str) -> ScoreDimension: ...

    @abstractmethod
    async def get_coding_scores(self, session_id: str) -> ScoreDimension: ...

    @abstractmethod
    async def get_communication_scores(self, session_id: str) -> ScoreDimension: ...

    async def get_question_breakdown(self, session_id: str) -> list[QuestionBreakdown]:
        return []

    async def get_duration_minutes(self, session_id: str) -> float:
        return 0.0

    async def get_persona_and_jd(self, session_id: str) -> tuple[str, str]:
        return "", ""


class InterviewScoreSourceAdapter(ScoreSourceAdapter):
    """
    Wired against Phase 4 real tables:
      - QuestionTurn           -> per-question scores and answers
      - InterviewSessionDetail -> duration, persona, JD reference
      - JobDescriptionRecord   -> JD title for the report header
      - CodingRound            -> coding evaluation (Phase 6)
    Phases 3/5 stubs remain until prosody/webcam analysis is wired.
    """

    def __init__(self, db=None) -> None:
        self.db = db

    async def get_content_scores(self, session_id: str) -> ScoreDimension:
        if self.db is None:
            raise DimensionUnavailable("content_quality: no DB session provided")
        try:
            from app.models.interview import QuestionTurn  # noqa: PLC0415
            turns = (
                self.db.query(QuestionTurn)
                .filter(
                    QuestionTurn.session_id == session_id,
                    QuestionTurn.evaluation_json.isnot(None),
                    QuestionTurn.answer_text.isnot(None),
                )
                .order_by(QuestionTurn.asked_at)
                .all()
            )
        except Exception as exc:
            raise DimensionUnavailable(f"content_quality: DB query failed — {exc}") from exc

        if not turns:
            raise DimensionUnavailable("content_quality: no evaluated answers in this session")

        import json as _json
        scores: list[float] = []
        sub_scores: list[SubScore] = []
        for turn in turns:
            try:
                ev = _json.loads(turn.evaluation_json) if turn.evaluation_json else {}
                raw = float(ev.get("score", 0))
                score_100 = raw * 100 if raw <= 1.0 else raw
                scores.append(score_100)
                sub_scores.append(SubScore(
                    name=turn.question_text[:60],
                    score=round(score_100, 1),
                    detail=ev.get("feedback", ""),
                ))
            except (ValueError, TypeError):
                continue

        if not scores:
            raise DimensionUnavailable("content_quality: could not parse any evaluation scores")

        return ScoreDimension(
            name="Content Quality",
            score=round(mean(scores), 1),
            max_score=100,
            weight=0.35,
            sub_scores=sub_scores,
            description=f"Average answer quality across {len(scores)} evaluated question(s).",
            available=True,
        )

    async def get_confidence_summary(self, session_id: str) -> ScoreDimension:
        raise DimensionUnavailable("delivery_confidence: webcam analysis (Phase 5) not wired yet")

    async def get_coding_scores(self, session_id: str) -> ScoreDimension:
        if self.db is None:
            raise DimensionUnavailable("technical_skill: no DB session provided")
        try:
            from app.models.coding import CodingRound  # noqa: PLC0415
            rounds = (
                self.db.query(CodingRound)
                .filter(
                    CodingRound.session_id == session_id,
                    CodingRound.status == "completed",
                )
                .all()
            )
        except Exception as exc:
            raise DimensionUnavailable(f"technical_skill: DB query failed — {exc}") from exc

        if not rounds:
            raise DimensionUnavailable("technical_skill: no completed coding rounds in this session")

        sub_scores2: list[SubScore] = []
        all_scores: list[float] = []
        for rnd in rounds:
            if rnd.final_evaluation and isinstance(rnd.final_evaluation, dict):
                overall = float(rnd.final_evaluation.get("overall_score", 0))
                all_scores.append(overall)
                sub_scores2.append(SubScore(
                    name=f"Coding Round ({rnd.id[:8]})",
                    score=round(overall, 1),
                    detail="; ".join(rnd.final_evaluation.get("strengths", [])[:2]),
                ))

        if not all_scores:
            raise DimensionUnavailable("technical_skill: no finalized coding evaluations found")

        return ScoreDimension(
            name="Technical Skill",
            score=round(mean(all_scores), 1),
            max_score=100,
            weight=0.25,
            sub_scores=sub_scores2,
            description=f"Coding evaluation across {len(all_scores)} round(s).",
            available=True,
        )

    async def get_communication_scores(self, session_id: str) -> ScoreDimension:
        raise DimensionUnavailable("communication: prosody analysis (Phase 3) not wired yet")

    async def get_question_breakdown(self, session_id: str) -> list[QuestionBreakdown]:
        if self.db is None:
            return []
        try:
            from app.models.interview import QuestionTurn  # noqa: PLC0415
            import json as _json
            turns = (
                self.db.query(QuestionTurn)
                .filter(QuestionTurn.session_id == session_id)
                .order_by(QuestionTurn.asked_at)
                .all()
            )
            result = []
            for turn in turns:
                ev: dict = {}
                if turn.evaluation_json:
                    try:
                        ev = _json.loads(turn.evaluation_json)
                    except (ValueError, TypeError):
                        ev = {}
                raw = float(ev.get("score", 0))
                score_100 = raw * 100 if raw <= 1.0 else raw
                result.append(QuestionBreakdown(
                    question=turn.question_text,
                    user_answer=turn.answer_text or "",
                    score=round(score_100, 1),
                    skill_tags=["follow_up" if turn.is_follow_up else "main"],
                ))
            return result
        except Exception:
            return []

    async def get_duration_minutes(self, session_id: str) -> float:
        if self.db is None:
            return 0.0
        try:
            from app.models.interview import InterviewSessionDetail, QuestionTurn  # noqa: PLC0415
            detail = (
                self.db.query(InterviewSessionDetail)
                .filter(InterviewSessionDetail.session_id == session_id)
                .one_or_none()
            )
            if detail is None:
                return 0.0

            start = detail.started_at or detail.created_at
            end = detail.ended_at

            # Fallback to last answered question timestamp if ended_at wasn't set
            if end is None:
                last_turn = (
                    self.db.query(QuestionTurn)
                    .filter(QuestionTurn.session_id == session_id, QuestionTurn.answered_at.isnot(None))
                    .order_by(QuestionTurn.answered_at.desc())
                    .first()
                )
                if last_turn and last_turn.answered_at:
                    end = last_turn.answered_at

            if start is None or end is None:
                return 0.0

            delta_seconds = max(0.0, (end - start).total_seconds())
            duration_mins = round(delta_seconds / 60.0, 1)

            # If questions were answered, ensure minimum duration is at least 1.0 min rather than 0
            if duration_mins == 0.0:
                has_turns = (
                    self.db.query(QuestionTurn.id)
                    .filter(QuestionTurn.session_id == session_id, QuestionTurn.answer_text.isnot(None))
                    .first()
                )
                if has_turns:
                    duration_mins = 1.0

            return duration_mins
        except Exception:
            return 0.0

    async def get_persona_and_jd(self, session_id: str) -> tuple[str, str]:
        if getattr(self, "db", None) is None:
            return "", ""
        try:
            from app.models.interview import InterviewSessionDetail, JobDescriptionRecord  # noqa: PLC0415
            import json as _json
            detail = (
                self.db.query(InterviewSessionDetail)
                .filter(InterviewSessionDetail.session_id == session_id)
                .one_or_none()
            )
            if detail is None:
                return "", ""
            persona = detail.persona_id or ""
            jd_title = ""
            if detail.jd_id:
                jd_row = self.db.get(JobDescriptionRecord, detail.jd_id)
                if jd_row:
                    try:
                        jd_data = _json.loads(jd_row.structured_json)
                        jd_title = jd_data.get("title", "")
                    except (ValueError, TypeError):
                        jd_title = ""
            return persona, jd_title
        except Exception:
            return "", ""


class IELTSScoreSourceAdapter(ScoreSourceAdapter):
    """Real adapter wired against Phase 7's actual `IELTSSession`/`IELTSAnswer` models."""

    def __init__(self, db):
        self.db = db

    def _ielts_session(self, session_id: str):
        from app.models.ielts import IELTSSession

        return (
            self.db.query(IELTSSession)
            .filter(IELTSSession.session_id == session_id)
            .one_or_none()
        )

    async def get_content_scores(self, session_id: str) -> ScoreDimension:
        raise DimensionUnavailable("IELTS mode doesn't use the interview 'content' dimension")

    async def get_confidence_summary(self, session_id: str) -> ScoreDimension:
        raise DimensionUnavailable("IELTS mode doesn't use the interview 'confidence' dimension")

    async def get_coding_scores(self, session_id: str) -> ScoreDimension:
        raise DimensionUnavailable("IELTS mode doesn't use the interview 'technical' dimension")

    async def get_communication_scores(self, session_id: str) -> ScoreDimension:
        raise DimensionUnavailable("IELTS mode doesn't use the interview 'communication' dimension")

    async def get_ielts_dimensions(self, session_id: str) -> list[ScoreDimension]:
        row = self._ielts_session(session_id)
        if row is None or not row.overall_band_score:
            raise DimensionUnavailable(f"No scored IELTS session for {session_id}")

        band = row.overall_band_score
        # IELTS bands are 0-9; fused report scale is 0-100.
        def to100(b: float) -> float:
            return round((b / 9.0) * 100, 1)

        return [
            ScoreDimension(
                name="Fluency & Coherence", score=to100(band["fluency_and_coherence"]["band"]),
                max_score=100, weight=0.25, description=band["fluency_and_coherence"]["justification"],
                sub_scores=[SubScore(name="Band", score=band["fluency_and_coherence"]["band"] * 100 / 9)],
            ),
            ScoreDimension(
                name="Lexical Resource", score=to100(band["lexical_resource"]["band"]),
                max_score=100, weight=0.25, description=band["lexical_resource"]["justification"],
            ),
            ScoreDimension(
                name="Grammatical Range & Accuracy", score=to100(band["grammatical_range_accuracy"]["band"]),
                max_score=100, weight=0.25, description=band["grammatical_range_accuracy"]["justification"],
            ),
            ScoreDimension(
                name="Pronunciation", score=to100(band["pronunciation"]["band"]),
                max_score=100, weight=0.25, description=band["pronunciation"]["justification"],
            ),
        ]

    async def get_question_breakdown(self, session_id: str) -> list[QuestionBreakdown]:
        from app.models.ielts import IELTSAnswer

        row = self._ielts_session(session_id)
        if row is None:
            return []
        answers = (
            self.db.query(IELTSAnswer)
            .filter(IELTSAnswer.ielts_session_id == row.id)
            .order_by(IELTSAnswer.created_at)
            .all()
        )
        return [
            QuestionBreakdown(
                question=a.question_text,
                user_answer=a.transcript or "",
                score=round((a.band_score["overall_band"] / 9.0) * 100, 1) if a.band_score else 0.0,
                skill_tags=[f"IELTS Part {a.part}"],
            )
            for a in answers
        ]

    async def get_duration_minutes(self, session_id: str) -> float:
        row = self._ielts_session(session_id)
        if row is None or not row.completed_at or not row.created_at:
            return 0.0
        return round((row.completed_at - row.created_at).total_seconds() / 60, 1)


# ---------------------------------------------------------------------------
# Fusion engine
# ---------------------------------------------------------------------------


class ScoreFusionEngine:
    INTERVIEW_WEIGHTS = {
        "content_quality": 0.35,
        "delivery_confidence": 0.25,
        "technical_skill": 0.25,
        "communication": 0.15,
    }
    IELTS_WEIGHTS = {
        "fluency_coherence": 0.25,
        "lexical_resource": 0.25,
        "grammatical_range": 0.25,
        "pronunciation": 0.25,
    }

    def __init__(
        self,
        interview_adapter: Optional[InterviewScoreSourceAdapter] = None,
        ielts_adapter: Optional[IELTSScoreSourceAdapter] = None,
        llm_client: Optional[ScoringLLMClient] = None,
    ):
        self.interview_adapter = interview_adapter or InterviewScoreSourceAdapter()
        self.ielts_adapter = ielts_adapter
        self.llm_client = llm_client or ScoringLLMClient()

    async def fuse_interview_scores(self, session_id: str) -> FusedReport:
        dims: list[ScoreDimension] = []
        for key, getter, weight in [
            ("content_quality", self.interview_adapter.get_content_scores, self.INTERVIEW_WEIGHTS["content_quality"]),
            ("delivery_confidence", self.interview_adapter.get_confidence_summary, self.INTERVIEW_WEIGHTS["delivery_confidence"]),
            ("technical_skill", self.interview_adapter.get_coding_scores, self.INTERVIEW_WEIGHTS["technical_skill"]),
            ("communication", self.interview_adapter.get_communication_scores, self.INTERVIEW_WEIGHTS["communication"]),
        ]:
            try:
                dim = await getter(session_id)
                dim.weight = weight
                dims.append(dim)
            except DimensionUnavailable as exc:
                dims.append(
                    ScoreDimension(
                        name=key.replace("_", " ").title(), score=-1, max_score=100,
                        weight=weight, available=False, description=str(exc),
                    )
                )

        breakdown = await self.interview_adapter.get_question_breakdown(session_id)
        breakdown = [self._ensure_annotated(qb) for qb in breakdown]
        duration = await self.interview_adapter.get_duration_minutes(session_id)
        persona, jd = await self.interview_adapter.get_persona_and_jd(session_id)

        overall = self._weighted_average(dims)
        strengths, improvements = self._identify_strengths_and_improvements(dims, breakdown)
        action_items = self._generate_action_items(dims, improvements)

        return FusedReport(
            session_id=session_id,
            mode="interview",
            overall_score=overall,
            dimensions=dims,
            strengths=strengths,
            improvements=improvements,
            action_items=action_items,
            per_question_breakdown=breakdown,
            duration_minutes=duration,
            persona_label=persona,
            jd_title=jd,
        )

    async def fuse_ielts_scores(self, session_id: str) -> FusedReport:
        if self.ielts_adapter is None:
            raise ValueError("fuse_ielts_scores requires an IELTSScoreSourceAdapter (needs a DB session)")

        dims = await self.ielts_adapter.get_ielts_dimensions(session_id)
        breakdown = await self.ielts_adapter.get_question_breakdown(session_id)
        breakdown = [self._ensure_annotated(qb) for qb in breakdown]
        duration = await self.ielts_adapter.get_duration_minutes(session_id)

        overall = round(mean(d.score for d in dims), 1) if dims else 0.0
        strengths, improvements = self._identify_strengths_and_improvements(dims, breakdown)
        action_items = self._generate_action_items(dims, improvements)

        return FusedReport(
            session_id=session_id,
            mode="ielts",
            overall_score=overall,
            dimensions=dims,
            strengths=strengths,
            improvements=improvements,
            action_items=action_items,
            per_question_breakdown=breakdown,
            duration_minutes=duration,
        )

    # -- internals -----------------------------------------------------------

    def _weighted_average(self, dims: list[ScoreDimension]) -> float:
        available = [d for d in dims if d.available]
        if not available:
            return 0.0
        total_weight = sum(d.weight for d in available)
        if total_weight == 0:
            return 0.0
        # Renormalize weights across only the dimensions we actually have data
        # for, so a missing dimension doesn't silently drag the score down.
        weighted = sum(d.score * (d.weight / total_weight) for d in available)
        return round(weighted, 1)

    def _ensure_annotated(self, qb: QuestionBreakdown) -> QuestionBreakdown:
        if qb.annotated_answer is None and qb.user_answer:
            from app.services.scoring.answer_annotator import AnswerAnnotator

            qb.annotated_answer = AnswerAnnotator().annotate_heuristic(qb.user_answer, qb.question)
        return qb

    def _identify_strengths_and_improvements(
        self, dims: list[ScoreDimension], breakdown: list[QuestionBreakdown]
    ) -> tuple[list[str], list[str]]:
        strengths, improvements = [], []
        for d in dims:
            if not d.available:
                continue
            if d.score >= 75:
                strengths.append(f"Strong {d.name.lower()} — scored {d.score:.0f}/100")
            elif d.score < 55:
                improvements.append(f"{d.name} needs focused practice — scored {d.score:.0f}/100")

        weak_questions = [qb for qb in breakdown if qb.score < 55]
        if len(weak_questions) >= 2:
            improvements.append(
                f"{len(weak_questions)} question(s) scored below 55/100 — see per-question breakdown"
            )
        strong_questions = [qb for qb in breakdown if qb.score >= 85]
        if strong_questions:
            strengths.append(f"{len(strong_questions)} question(s) scored 85+ — this is your strongest material")

        return strengths[:6], improvements[:6]

    def _generate_action_items(
        self, dims: list[ScoreDimension], improvements: list[str]
    ) -> list[ActionItem]:
        priority_order = sorted(
            (d for d in dims if d.available), key=lambda d: d.score
        )
        items: list[ActionItem] = []
        category_map = {
            "content quality": "content", "delivery confidence": "delivery",
            "technical skill": "technical", "communication": "communication",
            "fluency & coherence": "communication", "lexical resource": "content",
            "grammatical range & accuracy": "content", "pronunciation": "delivery",
        }
        for i, d in enumerate(priority_order[:3]):
            priority = "high" if d.score < 55 else "medium" if d.score < 75 else "low"
            category = category_map.get(d.name.lower(), "content")
            items.append(
                ActionItem(
                    priority=priority,
                    category=category,
                    description=f"Improve {d.name.lower()} (currently {d.score:.0f}/100)",
                    suggested_practice=self._suggested_practice_for(category),
                )
            )
        return items

    def _suggested_practice_for(self, category: str) -> str:
        from app.services.scoring.playbooks import IMPROVEMENT_PLAYBOOKS

        by_category = {
            "content": "vague_answers", "delivery": "poor_eye_contact",
            "technical": "missing_star_structure", "communication": "filler_words",
        }
        key = by_category.get(category)
        playbook = IMPROVEMENT_PLAYBOOKS.get(key, {})
        exercises = playbook.get("exercises", [])
        return exercises[0]["name"] if exercises else "Run a focused practice session on this dimension"
