"""Confidence timeline data structures + aggregation, per Phase 5 spec §5.7,
§5.12, §5.13.

Everything in this module is pure computation over already-extracted
numerical signals (landmark-derived ratios/scores/classifications) — it
has zero dependency on MediaPipe, TensorFlow, or a webcam. That split is
deliberate: the browser-side code (frontend/src/services/vision/) does the
actual computer vision and can't be exercised without a camera in this
environment, but everything downstream of "here are some ConfidenceFrame
values" — summarizing a session, finding notable confidence drops,
comparing warm-up vs. interview, tracking progress across sessions — is
ordinary data aggregation and is fully real and tested here.
"""

from __future__ import annotations

from pydantic import BaseModel

EyeContactDirection = str  # "direct" | "away_left" | "away_right" | "down" | "up"
MovementPattern = str  # "stable" | "nodding" | "shaking" | "fidgeting"
BlinkAssessment = str  # "normal" | "elevated" | "low"
Expression = str  # "neutral" | "happy" | "surprised" | "confused" | "anxious" | "focused"
HandPosition = str  # "resting" | "gesturing" | "face_touching" | "fidgeting" | "crossed_arms"
GestureAssessment = str  # "natural" | "too_still" | "excessive" | "defensive"


class EyeContactSignal(BaseModel):
    direction: EyeContactDirection
    confidence: float
    contact_ratio_30s: float


class HeadStabilitySignal(BaseModel):
    pitch: float
    yaw: float
    roll: float
    stability_score: float
    movement_pattern: MovementPattern


class BlinkSignal(BaseModel):
    ear_left: float
    ear_right: float
    is_blinking: bool
    blinks_per_minute: float
    assessment: BlinkAssessment


class GestureSignal(BaseModel):
    hand_position: HandPosition
    gesture_frequency: float
    assessment: GestureAssessment


class ConfidenceFrame(BaseModel):
    timestamp_ms: int
    eye_contact: EyeContactSignal
    head_stability: HeadStabilitySignal
    blink_rate: BlinkSignal
    expression: Expression
    gesture: GestureSignal | None = None
    composite_score: float


class NotableMoment(BaseModel):
    timestamp_ms: int
    description: str
    composite_score: float


class ConfidenceSummary(BaseModel):
    avg_eye_contact_ratio: float
    avg_stability_score: float
    avg_blink_rate: float
    dominant_expression: Expression
    composite_score: float
    notable_moments: list[NotableMoment] = []
    frame_count: int = 0


class ConfidenceTimeline(BaseModel):
    session_id: str
    frames: list[ConfidenceFrame]
    summary: ConfidenceSummary


class BaselineComparison(BaseModel):
    warmup_confidence: float
    interview_confidence: float
    confidence_delta: float
    worst_drop_timestamp_ms: int | None
    recovery_pattern: str  # "quick_recovery" | "gradual_decline" | "sustained_drop" | "no_drop"


class ProgressPoint(BaseModel):
    session_id: str
    eye_contact_ratio: float
    stability_score: float
    expression_positivity: float
    composite_confidence: float


# ---- pure aggregation functions ----

# A composite-score drop of at least this many points relative to the
# frame directly before it is flagged as a notable moment — small,
# continuous drift isn't "notable", a sudden drop is.
NOTABLE_DROP_THRESHOLD = 15.0

_POSITIVE_EXPRESSIONS = {"happy", "focused"}
_NEGATIVE_EXPRESSIONS = {"anxious", "confused"}


def compute_summary(frames: list[ConfidenceFrame]) -> ConfidenceSummary:
    if not frames:
        return ConfidenceSummary(
            avg_eye_contact_ratio=0.0,
            avg_stability_score=0.0,
            avg_blink_rate=0.0,
            dominant_expression="neutral",
            composite_score=0.0,
            notable_moments=[],
            frame_count=0,
        )

    avg_eye_contact = sum(f.eye_contact.contact_ratio_30s for f in frames) / len(frames)
    avg_stability = sum(f.head_stability.stability_score for f in frames) / len(frames)
    avg_blink = sum(f.blink_rate.blinks_per_minute for f in frames) / len(frames)
    avg_composite = sum(f.composite_score for f in frames) / len(frames)

    expression_counts: dict[str, int] = {}
    for f in frames:
        expression_counts[f.expression] = expression_counts.get(f.expression, 0) + 1
    dominant_expression = max(expression_counts, key=lambda k: expression_counts[k])

    return ConfidenceSummary(
        avg_eye_contact_ratio=round(avg_eye_contact, 3),
        avg_stability_score=round(avg_stability, 3),
        avg_blink_rate=round(avg_blink, 1),
        dominant_expression=dominant_expression,
        composite_score=round(avg_composite, 1),
        notable_moments=detect_notable_moments(frames),
        frame_count=len(frames),
    )


def detect_notable_moments(
    frames: list[ConfidenceFrame], threshold: float = NOTABLE_DROP_THRESHOLD
) -> list[NotableMoment]:
    """Flags frames where the composite score drops sharply relative to
    the immediately preceding frame — a sudden dip reads as "something
    happened here" (e.g. a hard question), which is more useful for
    session replay than flagging every below-average moment."""
    moments: list[NotableMoment] = []
    for prev, current in zip(frames, frames[1:], strict=False):
        drop = prev.composite_score - current.composite_score
        if drop >= threshold:
            moments.append(
                NotableMoment(
                    timestamp_ms=current.timestamp_ms,
                    description=(
                        f"Confidence dropped {drop:.0f} points "
                        f"(from {prev.composite_score:.0f} to {current.composite_score:.0f})"
                    ),
                    composite_score=current.composite_score,
                )
            )
    return moments


def compute_baseline_comparison(
    warmup_frames: list[ConfidenceFrame], interview_frames: list[ConfidenceFrame]
) -> BaselineComparison:
    """Per spec §5.12 — compares average confidence during warm-up
    (relaxed small talk) against the actual interview questions."""
    warmup_avg = (
        sum(f.composite_score for f in warmup_frames) / len(warmup_frames) if warmup_frames else 0.0
    )
    interview_avg = (
        sum(f.composite_score for f in interview_frames) / len(interview_frames)
        if interview_frames
        else 0.0
    )
    delta = interview_avg - warmup_avg

    worst_drop_ts: int | None = None
    if interview_frames:
        worst_frame = min(interview_frames, key=lambda f: f.composite_score)
        worst_drop_ts = worst_frame.timestamp_ms

    recovery_pattern = _classify_recovery_pattern(warmup_avg, interview_frames)

    return BaselineComparison(
        warmup_confidence=round(warmup_avg, 1),
        interview_confidence=round(interview_avg, 1),
        confidence_delta=round(delta, 1),
        worst_drop_timestamp_ms=worst_drop_ts,
        recovery_pattern=recovery_pattern,
    )


def _classify_recovery_pattern(warmup_avg: float, interview_frames: list[ConfidenceFrame]) -> str:
    if not interview_frames:
        return "no_drop"

    min_score = min(f.composite_score for f in interview_frames)
    if warmup_avg - min_score < 10:
        return "no_drop"

    # Did the score recover to within 10 points of the warm-up baseline
    # after the low point, and stay there for the rest of the session?
    min_index = min(range(len(interview_frames)), key=lambda i: interview_frames[i].composite_score)
    remaining = interview_frames[min_index + 1 :]
    if not remaining:
        return "sustained_drop"

    recovered_frames = [f for f in remaining if f.composite_score >= warmup_avg - 10]
    if not recovered_frames:
        return "sustained_drop"

    # Recovered within the first third of what's left -> quick recovery;
    # otherwise it took a while but did recover -> gradual decline
    # framing doesn't fit "recovered", so we call this gradual recovery
    # bucketed under "gradual_decline" per the spec's three named states
    # (the spec doesn't have a fourth "gradual_recovery" label).
    recovery_index = remaining.index(recovered_frames[0])
    if recovery_index <= max(len(remaining) // 3, 1):
        return "quick_recovery"
    return "gradual_decline"


def compute_progress(
    session_ids: list[str], summaries: list[ConfidenceSummary]
) -> list[ProgressPoint]:
    """Per spec §5.13 — one ProgressPoint per session, in the order given,
    for a before/after comparison chart."""
    points = []
    for session_id, summary in zip(session_ids, summaries, strict=True):
        positive = (
            1.0
            if summary.dominant_expression in _POSITIVE_EXPRESSIONS
            else (0.0 if summary.dominant_expression in _NEGATIVE_EXPRESSIONS else 0.5)
        )
        points.append(
            ProgressPoint(
                session_id=session_id,
                eye_contact_ratio=summary.avg_eye_contact_ratio,
                stability_score=summary.avg_stability_score,
                expression_positivity=positive,
                composite_confidence=summary.composite_score,
            )
        )
    return points


def downsample_frames(
    frames: list[ConfidenceFrame], target_fps: float = 2.0
) -> list[ConfidenceFrame]:
    """Reduces a 30fps capture stream to ~target_fps for timeline storage
    (per spec §5.7's "~2 per second (downsampled from 30fps)"). Picks
    evenly-spaced frames rather than averaging them, so each stored frame
    is still a real, individually valid observation — useful for replay,
    where you want to see an actual moment, not a blended one."""
    if not frames or target_fps <= 0:
        return []

    if len(frames) <= 1:
        return list(frames)

    duration_ms = frames[-1].timestamp_ms - frames[0].timestamp_ms
    if duration_ms <= 0:
        return [frames[0]]

    source_fps = len(frames) / (duration_ms / 1000)
    if source_fps <= target_fps:
        return list(frames)

    step = source_fps / target_fps
    result = []
    i = 0.0
    while int(i) < len(frames):
        result.append(frames[int(i)])
        i += step
    return result
