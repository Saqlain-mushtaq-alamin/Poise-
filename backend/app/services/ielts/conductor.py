"""
IELTSSessionConductor — the orchestrator that ties together the state
machine, topic generator, and the three analyzers (band scorer,
pronunciation, prosody) into the request/response shape the router needs.

Mirrors the responsibility split of Phase 4's `InterviewConductor`
(`deliver_question` / `process_answer`), so a developer who's read Phase 4
will recognize the pattern immediately.
"""

from __future__ import annotations

import logging
import random
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session as DBSession

from app.models.ielts import IELTSAnswer, IELTSSession
from app.schemas.ielts import CueCardOut, CurrentPromptOut
from app.services.ielts.llm_client import IELTSLLMClient
from app.services.ielts.pronunciation import PronunciationAnalyzer
from app.services.ielts.prosody import ProsodyAnalyzer
from app.services.ielts.scorer import IELTSBandEvaluator, IELTSBandScore
from app.services.ielts.state_machine import IELTSState, IELTSStateMachine
from app.services.ielts.topics import IELTSTopicGenerator

logger = logging.getLogger("poise.ielts.conductor")


class IELTSSessionNotFound(Exception):
    pass


class IELTSSessionConductor:
    def __init__(
        self,
        db: DBSession,
        topic_generator: IELTSTopicGenerator | None = None,
        evaluator: IELTSBandEvaluator | None = None,
        pronunciation_analyzer: PronunciationAnalyzer | None = None,
        prosody_analyzer: ProsodyAnalyzer | None = None,
        llm_client: IELTSLLMClient | None = None,
    ):
        self.db = db
        # Wire the real LLM router so dynamic follow-ups and LLM scoring work.
        if llm_client is None:
            try:
                from app.services.provider import get_router  # noqa: PLC0415
                router = get_router()
                llm_client = IELTSLLMClient(router=router)
            except Exception:
                llm_client = IELTSLLMClient()  # graceful offline fallback
        self.llm_client = llm_client
        self.topic_generator = topic_generator or IELTSTopicGenerator(self.llm_client)
        self.evaluator = evaluator or IELTSBandEvaluator(self.llm_client)
        self.pronunciation_analyzer = pronunciation_analyzer or PronunciationAnalyzer()
        self.prosody_analyzer = prosody_analyzer or ProsodyAnalyzer()

    # -- lookups ---------------------------------------------------------

    def _get(self, ielts_session_id: str) -> IELTSSession:
        row = (
            self.db.query(IELTSSession)
            .filter(IELTSSession.id == ielts_session_id)
            .one_or_none()
        )
        if row is None:
            raise IELTSSessionNotFound(ielts_session_id)
        return row

    def _machine_for(self, row: IELTSSession) -> IELTSStateMachine:
        return IELTSStateMachine(state=IELTSState(row.status))

    # -- creation ---------------------------------------------------------

    async def create_session(
        self, target_band: float = 6.5, topics_preference: str | None = None
    ) -> IELTSSession:
        from app.models.session import Session as ParentSession  # Phase 1 shared table

        parent = ParentSession(id=str(uuid4()), mode="ielts", status="created")
        self.db.add(parent)

        # Collect previously used categories to avoid repetition across sessions.
        exclude_categories = self._get_used_categories(limit=5)

        topic_set = await self.topic_generator.generate_session_topics(
            target_band=target_band,
            topics_preference=topics_preference,
            exclude_categories=exclude_categories,
        )

        row = IELTSSession(
            id=str(uuid4()),
            session_id=parent.id,
            status=IELTSState.SETUP.value,
            target_band=target_band,
            topics_preference=topics_preference,
            part1_categories=topic_set.part1_categories,
            part2_cue_card=topic_set.part2_cue_card,
            part3_questions=topic_set.part3_questions,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def _get_used_categories(self, limit: int = 5) -> list[str]:
        """Return Part 1 category names used in recent sessions to avoid repetition."""
        try:
            recent = (
                self.db.query(IELTSSession)
                .filter(IELTSSession.part1_categories.isnot(None))
                .order_by(IELTSSession.created_at.desc())
                .limit(limit)
                .all()
            )
            seen: list[str] = []
            for row in recent:
                for cat in (row.part1_categories or []):
                    name = cat.get("category", "")
                    if name and name not in seen:
                        seen.append(name)
            return seen
        except Exception:
            return []

    # -- flow control ------------------------------------------------------

    async def start_session(self, ielts_session_id: str) -> CurrentPromptOut:
        row = self._get(ielts_session_id)
        machine = self._machine_for(row)
        if machine.state != IELTSState.SETUP:
            return self._current_prompt(row)

        transition = machine.advance()  # -> PART1_INTRO
        row.status = transition.to_state.value
        self.db.commit()
        return self._current_prompt(row)

    async def advance(self, ielts_session_id: str) -> CurrentPromptOut:
        """
        Move forward through non-spoken transitions: examiner intro
        finished, cue card acknowledged, prep timer elapsed.
        """
        row = self._get(ielts_session_id)
        machine = self._machine_for(row)

        if machine.state == IELTSState.PART1_INTRO:
            transition = machine.advance()  # -> PART1_QA
            row.status = transition.to_state.value
        elif machine.state == IELTSState.PART2_CUE_CARD:
            transition = machine.advance()  # -> PART2_PREP
            row.status = transition.to_state.value
        elif machine.state == IELTSState.PART2_PREP:
            transition = machine.advance()  # -> PART2_SPEAKING
            row.status = transition.to_state.value
        else:
            # Speaking states advance via submit_answer, not advance().
            pass

        self.db.commit()
        return self._current_prompt(row)

    async def submit_answer(
        self, ielts_session_id: str, audio_path: str, transcript: str
    ) -> tuple[IELTSAnswer, CurrentPromptOut]:
        row = self._get(ielts_session_id)
        machine = self._machine_for(row)

        if not machine.is_speaking_state():
            raise ValueError(f"Cannot submit an answer while in state {machine.state}")

        part, question_text = self._question_for_state(row, machine.state)

        prosody = await self.prosody_analyzer.analyze(Path(audio_path), transcript)
        pronunciation = await self.pronunciation_analyzer.analyze(Path(audio_path), transcript)
        band_score = await self.evaluator.score_response(
            transcript=transcript,
            context=f"IELTS Part {part}: {question_text}",
            pronunciation=pronunciation,
            prosody=prosody,
        )

        answer = IELTSAnswer(
            id=str(uuid4()),
            ielts_session_id=row.id,
            part=part,
            question_text=question_text,
            audio_path=audio_path,
            transcript=transcript,
            band_score=asdict(band_score),
            pronunciation=asdict(pronunciation),
            prosody=asdict(prosody),
        )
        self.db.add(answer)

        # Store Part 2 transcript for contextual follow-up generation
        if machine.state == IELTSState.PART2_SPEAKING:
            row.part2_answer_transcript = transcript

        next_prompt = await self._advance_after_answer(row, machine, transcript)
        self.db.commit()
        return answer, next_prompt

    async def _advance_after_answer(
        self, row: IELTSSession, machine: IELTSStateMachine, last_answer: str
    ) -> CurrentPromptOut:
        if machine.state == IELTSState.PART1_QA:
            categories = row.part1_categories or []
            cat = categories[row.part1_index]
            if row.part1_question_index + 1 < len(cat["questions"]):
                row.part1_question_index += 1
            elif row.part1_index + 1 < len(categories):
                row.part1_index += 1
                row.part1_question_index = 0
            else:
                transition = machine.advance()  # -> PART2_CUE_CARD
                row.status = transition.to_state.value

        elif machine.state == IELTSState.PART2_SPEAKING:
            transition = machine.advance()  # -> PART2_FOLLOW_UP
            row.status = transition.to_state.value
            # Generate contextual follow-up from Part 2 answer
            theme = (row.part2_cue_card or {}).get("theme", "")
            followup = await self._generate_followup(last_answer, part=2, theme=theme)
            if followup:
                row.dynamic_followup = followup

        elif machine.state == IELTSState.PART2_FOLLOW_UP:
            transition = machine.advance()  # -> PART3_DISCUSSION
            row.status = transition.to_state.value

        elif machine.state == IELTSState.PART3_DISCUSSION:
            questions = row.part3_questions or []
            if row.part3_index + 1 < len(questions):
                row.part3_index += 1
                # Occasionally insert a contextual follow-up (~40% chance)
                if random.random() < 0.4:
                    theme = (row.part2_cue_card or {}).get("theme", "")
                    followup = await self._generate_followup(last_answer, part=3, theme=theme)
                    if followup:
                        row.dynamic_followup = followup
            else:
                transition = machine.advance()  # -> SCORING
                row.status = transition.to_state.value
                row.dynamic_followup = None

        return self._current_prompt(row)

    async def _generate_followup(self, answer: str, part: int, theme: str) -> str | None:
        """Generate a contextual follow-up via LLM, with graceful fallback."""
        try:
            result = await self.llm_client.generate_followup(answer, part, theme)
            return result
        except Exception as exc:
            logger.debug("Follow-up generation failed (offline fallback): %s", exc)
            return None

    def _question_for_state(self, row: IELTSSession, state: IELTSState) -> tuple[int, str]:
        if state == IELTSState.PART1_QA:
            cat = (row.part1_categories or [])[row.part1_index]
            return 1, cat["questions"][row.part1_question_index]
        if state == IELTSState.PART2_SPEAKING:
            return 2, row.part2_cue_card["topic"]
        if state == IELTSState.PART2_FOLLOW_UP:
            return 2, row.dynamic_followup or "Now, let's talk about the topic a little more generally."
        if state == IELTSState.PART3_DISCUSSION:
            # Serve dynamic follow-up if one exists, otherwise serve bank question
            followup = getattr(row, "dynamic_followup", None)
            if followup:
                row.dynamic_followup = None  # consume it
                return 3, followup
            return 3, (row.part3_questions or [])[row.part3_index]
        raise ValueError(f"No question mapped for state {state}")

    def _current_prompt(self, row: IELTSSession) -> CurrentPromptOut:
        machine = self._machine_for(row)
        state = machine.state
        budget = machine.time_budget_s()

        if state == IELTSState.PART1_QA:
            cat = (row.part1_categories or [])[row.part1_index]
            return CurrentPromptOut(
                state=state.value, part=1, question=cat["questions"][row.part1_question_index],
                time_budget_s=budget,
            )
        if state == IELTSState.PART2_CUE_CARD:
            card = row.part2_cue_card
            return CurrentPromptOut(
                state=state.value, part=2,
                cue_card=CueCardOut(topic=card["topic"], bullets=card["bullets"], theme=card["theme"]),
                time_budget_s=budget,
            )
        if state == IELTSState.PART2_PREP:
            return CurrentPromptOut(state=state.value, part=2, time_budget_s=budget)
        if state == IELTSState.PART2_SPEAKING:
            return CurrentPromptOut(
                state=state.value, part=2, question=row.part2_cue_card["topic"], time_budget_s=budget
            )
        if state == IELTSState.PART2_FOLLOW_UP:
            # Use dynamic follow-up if available, else contextual generic
            followup_q = (
                getattr(row, "dynamic_followup", None)
                or "Now, let's discuss the broader aspects of this topic."
            )
            return CurrentPromptOut(
                state=state.value, part=2,
                question=followup_q,
                time_budget_s=budget,
            )
        if state == IELTSState.PART3_DISCUSSION:
            followup = getattr(row, "dynamic_followup", None)
            question = followup or (row.part3_questions or [])[row.part3_index]
            return CurrentPromptOut(
                state=state.value, part=3,
                question=question, time_budget_s=budget,
            )
        if state == IELTSState.SCORING:
            return CurrentPromptOut(state=state.value, time_budget_s=budget)
        if state == IELTSState.COMPLETE:
            return CurrentPromptOut(state=state.value, is_final=True)
        # SETUP / PART1_INTRO
        return CurrentPromptOut(state=state.value, time_budget_s=budget)

    # -- scoring -------------------------------------------------------------

    async def finalize_score(self, ielts_session_id: str) -> IELTSBandScore:
        row = self._get(ielts_session_id)
        machine = self._machine_for(row)

        answers = (
            self.db.query(IELTSAnswer)
            .filter(IELTSAnswer.ielts_session_id == row.id)
            .all()
        )
        session_score = await self.evaluator.score_session(answers)

        row.overall_band_score = asdict(session_score)
        if machine.state == IELTSState.SCORING:
            transition = machine.advance()  # -> COMPLETE
            row.status = transition.to_state.value
        row.completed_at = datetime.now(timezone.utc)
        self.db.commit()

        # Auto-cache the fused report so it shows in History immediately.
        try:
            from app.services.scoring.report_service import ReportService  # noqa: PLC0415
            await ReportService(self.db).get_report(row.session_id)
            logger.info("Cached fused report for IELTS session %s", row.session_id)
        except Exception as exc:
            logger.warning("Could not pre-cache IELTS report for %s: %s", row.session_id, exc)

        return session_score
