from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# -- requests ----------------------------------------------------------------


class CreateIELTSSessionRequest(BaseModel):
    target_band: float = Field(default=6.5, ge=0, le=9)
    topics_preference: str | None = None


class SubmitAnswerRequest(BaseModel):
    audio_path: str
    transcript: str


# -- shared / nested -----------------------------------------------------------


class BandDetailOut(BaseModel):
    band: float
    justification: str
    strengths: list[str] = []
    areas_to_improve: list[str] = []
    example_from_response: str = ""


class IELTSBandScoreOut(BaseModel):
    fluency_and_coherence: BandDetailOut
    lexical_resource: BandDetailOut
    grammatical_range_accuracy: BandDetailOut
    pronunciation: BandDetailOut
    overall_band: float


class WordPronunciationScoreOut(BaseModel):
    word: str
    score: float
    expected_phonemes: str
    detected_phonemes: str
    problem_phonemes: list[str] = []
    timestamp_ms: int = 0


class PronunciationAnalysisOut(BaseModel):
    word_scores: list[WordPronunciationScoreOut]
    overall_score: float
    problem_sounds: list[str]
    confidence_caveat: str
    engine: str


class PauseEventOut(BaseModel):
    start_s: float
    duration_s: float


class PauseAnalysisOut(BaseModel):
    total_pause_time_s: float
    avg_pause_duration_s: float
    long_pauses: list[PauseEventOut] = []
    natural_pauses: int = 0
    unnatural_pauses: int = 0


class FillerWordOut(BaseModel):
    text: str
    timestamp_s: float


class ProsodyAnalysisOut(BaseModel):
    speaking_rate_wpm: float
    pace_assessment: str
    pause_analysis: PauseAnalysisOut
    filler_words: list[FillerWordOut] = []
    filler_ratio: float
    intonation_variety: float


class CueCardOut(BaseModel):
    topic: str
    bullets: list[str]
    theme: str


class CurrentPromptOut(BaseModel):
    """What the UI should render / speak right now."""

    state: str
    part: int | None = None
    question: str | None = None
    cue_card: CueCardOut | None = None
    time_budget_s: int | None = None
    is_final: bool = False


# -- responses -----------------------------------------------------------------


class IELTSSessionOut(BaseModel):
    id: str
    session_id: str
    status: str
    target_band: float
    topics_preference: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class IELTSSessionDetailOut(IELTSSessionOut):
    current_prompt: CurrentPromptOut | None = None
    part1_categories: list[dict] | None = None
    part2_cue_card: CueCardOut | None = None
    part3_questions: list[str] | None = None


class AnswerResultOut(BaseModel):
    """Returned immediately after submitting an answer — lightweight; the
    full band score/pronunciation/prosody are fetched via their own
    endpoints once scoring completes, per the contract."""

    answer_id: str
    next_prompt: CurrentPromptOut
