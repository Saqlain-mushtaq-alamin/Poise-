"""
IELTSSessionConductor — the orchestrator that ties together the state
machine, topic generator, and the three analyzers (band scorer,
pronunciation, prosody) into the request/response shape the router needs.

Mirrors the responsibility split of Phase 4's `InterviewConductor`
(`deliver_question` / `process_answer`), so a developer who's read Phase 4
will recognize the pattern immediately.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
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
        self.llm_client = llm_client or IELTSLLMClient()
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

        topic_set = await self.topic_generator.generate_session_topics(
            target_band=target_band, topics_preference=topics_preference
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

        elif machine.state == IELTSState.PART2_FOLLOW_UP:
            transition = machine.advance()  # -> PART3_DISCUSSION
            row.status = transition.to_state.value

        elif machine.state == IELTSState.PART3_DISCUSSION:
            questions = row.part3_questions or []
            if row.part3_index + 1 < len(questions):
                row.part3_index += 1
            else:
                transition = machine.advance()  # -> SCORING
                row.status = transition.to_state.value

        return self._current_prompt(row)

    def _question_for_state(self, row: IELTSSession, state: IELTSState) -> tuple[int, str]:
        if state == IELTSState.PART1_QA:
            cat = (row.part1_categories or [])[row.part1_index]
            return 1, cat["questions"][row.part1_question_index]
        if state == IELTSState.PART2_SPEAKING:
            return 2, row.part2_cue_card["topic"]
        if state == IELTSState.PART2_FOLLOW_UP:
            return 2, "(follow-up)"
        if state == IELTSState.PART3_DISCUSSION:
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
            return CurrentPromptOut(
                state=state.value, part=2,
                question="Now, let's talk about the topic a little more generally.",
                time_budget_s=budget,
            )
        if state == IELTSState.PART3_DISCUSSION:
            return CurrentPromptOut(
                state=state.value, part=3,
                question=(row.part3_questions or [])[row.part3_index], time_budget_s=budget,
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
        row.completed_at = datetime.utcnow()
        self.db.commit()
        return session_score
