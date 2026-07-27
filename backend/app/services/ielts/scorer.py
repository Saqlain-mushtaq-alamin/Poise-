"""
Band score evaluator — scores a candidate's spoken responses against the
four official IELTS Speaking criteria:

    Fluency & Coherence (FC)              - heuristic, transcript-driven
    Lexical Resource (LR)                 - LLM-evaluated
    Grammatical Range & Accuracy (GRA)    - LLM-evaluated
    Pronunciation (P)                     - derived from wav2vec2 + prosody

Overall band = weighted average of the four, rounded to the nearest 0.5,
which matches how IELTS reports the speaking band.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import mean

from app.services.ielts.llm_client import IELTSLLMClient
from app.services.ielts.prosody import ProsodyAnalysis
from app.services.ielts.pronunciation import PronunciationAnalysis

FILLER_WORDS = {"um", "uh", "erm", "like", "you know", "sort of", "kind of", "basically", "actually"}
DISCOURSE_MARKERS = {
    "however", "moreover", "in addition", "on the other hand", "for example",
    "for instance", "in my opinion", "although", "because", "therefore",
    "as a result", "in conclusion", "firstly", "secondly", "finally", "meanwhile",
}


@dataclass
class BandDetail:
    band: float                  # 0.0 - 9.0, increments of 0.5
    justification: str
    strengths: list[str] = field(default_factory=list)
    areas_to_improve: list[str] = field(default_factory=list)
    example_from_response: str = ""


@dataclass
class IELTSBandScore:
    fluency_and_coherence: BandDetail
    lexical_resource: BandDetail
    grammatical_range_accuracy: BandDetail
    pronunciation: BandDetail
    overall_band: float

    @classmethod
    def from_dict(cls, data: dict) -> "IELTSBandScore":
        """Reconstruct from a dict produced by `dataclasses.asdict` (i.e. as
        stored in `IELTSAnswer.band_score` / `IELTSSession.overall_band_score`
        JSON columns) — plain `IELTSBandScore(**data)` would leave the nested
        criteria as dicts instead of `BandDetail` instances."""
        return cls(
            fluency_and_coherence=BandDetail(**data["fluency_and_coherence"]),
            lexical_resource=BandDetail(**data["lexical_resource"]),
            grammatical_range_accuracy=BandDetail(**data["grammatical_range_accuracy"]),
            pronunciation=BandDetail(**data["pronunciation"]),
            overall_band=data["overall_band"],
        )


def _round_to_half(x: float) -> float:
    return round(x * 2) / 2


def _clamp_band(x: float) -> float:
    return max(0.0, min(9.0, x))


class FluencyCoherenceAnalyzer:
    """
    Heuristic FC scorer driven purely by transcript + prosody signal — this
    is the one criterion the spec calls out as "transcription analysis"
    rather than LLM judgement, so it stays deterministic and explainable.
    """

    def score(self, transcript: str, prosody: ProsodyAnalysis | None) -> BandDetail:
        words = re.findall(r"[A-Za-z']+", transcript.lower())
        word_count = len(words)

        filler_count = sum(1 for w in words if w in FILLER_WORDS)
        # multi-word fillers like "you know" / "sort of"
        for phrase in ("you know", "sort of", "kind of"):
            filler_count += transcript.lower().count(phrase)

        hesitation_ratio = filler_count / word_count if word_count else 1.0
        marker_hits = sum(1 for m in DISCOURSE_MARKERS if m in transcript.lower())

        # Base band from response substance + coherence markers.
        band = 5.0
        if word_count >= 40:
            band += 0.5
        if word_count >= 80:
            band += 0.5
        if marker_hits >= 1:
            band += 0.5
        if marker_hits >= 3:
            band += 0.5
        band -= min(2.0, hesitation_ratio * 10)  # heavy filler use pulls band down hard

        if prosody:
            if prosody.pace_assessment == "good":
                band += 0.5
            if prosody.pause_analysis.unnatural_pauses > 3:
                band -= 0.5
            if prosody.filler_ratio > 0.08:
                band -= 0.5

        band = _round_to_half(_clamp_band(band))

        strengths, improve = [], []
        if marker_hits >= 2:
            strengths.append("Uses a range of discourse markers to link ideas")
        else:
            improve.append("Use more linking words (however, for example, as a result) to connect ideas")
        if hesitation_ratio < 0.03:
            strengths.append("Speaks with very few fillers or false starts")
        else:
            improve.append("Reduce filler words (um, uh, like) to sound more fluent")
        if word_count < 30:
            improve.append("Develop answers further — short responses limit the band available")

        example = transcript.strip()[:120]
        return BandDetail(
            band=band,
            justification=(
                f"Response contains {word_count} words with a hesitation ratio of "
                f"{hesitation_ratio:.0%} and {marker_hits} discourse marker(s) used."
            ),
            strengths=strengths or ["Communicates a clear basic message"],
            areas_to_improve=improve or ["Continue building topic development in longer turns"],
            example_from_response=example,
        )


class IELTSBandEvaluator:
    def __init__(self, llm_client: IELTSLLMClient | None = None):
        self.llm_client = llm_client or IELTSLLMClient()
        self.fc_analyzer = FluencyCoherenceAnalyzer()

    async def _score_lexical_resource(self, transcript: str, context: str) -> BandDetail:
        result = await self.llm_client.score_criterion("Lexical Resource", transcript, context)
        if result:
            return BandDetail(**result)
        return self._heuristic_fallback(transcript, "vocabulary range and word choice")

    async def _score_grammar(self, transcript: str, context: str) -> BandDetail:
        result = await self.llm_client.score_criterion(
            "Grammatical Range & Accuracy", transcript, context
        )
        if result:
            return BandDetail(**result)
        return self._heuristic_fallback(transcript, "sentence structure and grammatical accuracy")

    def _heuristic_fallback(self, transcript: str, aspect: str) -> BandDetail:
        """
        Used only when no LLM provider is configured. Coarser than the LLM
        path but keeps scoring available offline, and still discriminates
        response length/complexity so short/weak answers don't outscore
        developed ones.
        """
        sentences = [s for s in re.split(r"[.!?]", transcript) if s.strip()]
        lengths = [len(s.split()) for s in sentences]
        avg_sentence_len = mean(lengths) if lengths else 0
        complex_markers = sum(
            transcript.lower().count(w) for w in ("because", "which", "although", "if", "when")
        )
        band = 5.0
        if avg_sentence_len > 8:
            band += 0.5
        if avg_sentence_len > 12:
            band += 0.5
        if complex_markers >= 2:
            band += 0.5
        band = _round_to_half(_clamp_band(band))
        return BandDetail(
            band=band,
            justification=(
                f"Offline heuristic estimate based on {aspect}: average sentence length "
                f"{avg_sentence_len:.1f} words, {complex_markers} complex-clause marker(s). "
                f"Connect an LLM provider (Settings > BYOK) for a full qualitative assessment."
            ),
            strengths=["Communicates ideas in complete sentences"] if sentences else [],
            areas_to_improve=["Enable Cloud Assist for detailed lexical/grammar feedback"],
            example_from_response=transcript.strip()[:120],
        )

    def _score_pronunciation(
        self, pronunciation: PronunciationAnalysis | None, prosody: ProsodyAnalysis | None
    ) -> BandDetail:
        if pronunciation is None:
            return BandDetail(
                band=5.0,
                justification="No audio pronunciation analysis available for this response.",
                strengths=[],
                areas_to_improve=["Ensure microphone audio is captured for pronunciation scoring"],
                example_from_response="",
            )

        # overall_score is 0-1 from the phoneme analyzer -> map onto 0-9 band scale,
        # nudged by prosody (intonation variety, pace).
        band = 3.0 + pronunciation.overall_score * 5.5
        if prosody:
            band += (prosody.intonation_variety - 0.5) * 1.0
            if prosody.pace_assessment != "good":
                band -= 0.25
        band = _round_to_half(_clamp_band(band))

        problem_words = sorted(
            (ws for ws in pronunciation.word_scores if ws.score < 0.6),
            key=lambda ws: ws.score,
        )[:5]

        strengths, improve = [], []
        if pronunciation.overall_score >= 0.75:
            strengths.append("Individual sounds are clear and mostly accurate")
        if prosody and prosody.intonation_variety >= 0.5:
            strengths.append("Uses varied intonation rather than a flat delivery")
        if problem_words:
            improve.append(
                "Focus practice on: " + ", ".join(w.word for w in problem_words)
            )
        if pronunciation.problem_sounds:
            improve.append(
                "Recurring problem sounds: " + ", ".join(pronunciation.problem_sounds[:5])
            )

        return BandDetail(
            band=band,
            justification=(
                f"Phoneme-level analysis scored overall pronunciation accuracy at "
                f"{pronunciation.overall_score:.0%}. {pronunciation.confidence_caveat}"
            ),
            strengths=strengths or ["Generally intelligible to a listener"],
            areas_to_improve=improve or ["Continue practising natural stress and rhythm"],
            example_from_response=(problem_words[0].word if problem_words else ""),
        )

    async def score_response(
        self,
        transcript: str,
        context: str,
        pronunciation: PronunciationAnalysis | None = None,
        prosody: ProsodyAnalysis | None = None,
    ) -> IELTSBandScore:
        fc = self.fc_analyzer.score(transcript, prosody)
        lr = await self._score_lexical_resource(transcript, context)
        gra = await self._score_grammar(transcript, context)
        p = self._score_pronunciation(pronunciation, prosody)

        overall = _round_to_half(mean([fc.band, lr.band, gra.band, p.band]))

        return IELTSBandScore(
            fluency_and_coherence=fc,
            lexical_resource=lr,
            grammatical_range_accuracy=gra,
            pronunciation=p,
            overall_band=overall,
        )

    async def score_session(
        self, per_answer_scores: list[IELTSBandScore]
    ) -> IELTSBandScore:
        """Aggregate several per-answer scores into one session-level score."""
        if not per_answer_scores:
            raise ValueError("Cannot score a session with no answers")

        def agg(field_name: str) -> BandDetail:
            details = [getattr(s, field_name) for s in per_answer_scores]
            avg_band = _round_to_half(mean(d.band for d in details))
            strengths = sorted({s for d in details for s in d.strengths})[:5]
            improve = sorted({a for d in details for a in d.areas_to_improve})[:5]
            example = next((d.example_from_response for d in details if d.example_from_response), "")
            return BandDetail(
                band=avg_band,
                justification=f"Averaged across {len(details)} response(s) in this session.",
                strengths=strengths,
                areas_to_improve=improve,
                example_from_response=example,
            )

        fc = agg("fluency_and_coherence")
        lr = agg("lexical_resource")
        gra = agg("grammatical_range_accuracy")
        p = agg("pronunciation")
        overall = _round_to_half(mean([fc.band, lr.band, gra.band, p.band]))

        return IELTSBandScore(
            fluency_and_coherence=fc,
            lexical_resource=lr,
            grammatical_range_accuracy=gra,
            pronunciation=p,
            overall_band=overall,
        )
