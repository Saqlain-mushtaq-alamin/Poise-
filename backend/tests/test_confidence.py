"""Confidence aggregation logic — pure computation over synthetic frames,
no CV/ML dependency at all."""

from __future__ import annotations

from app.services.confidence import (
    BlinkSignal,
    ConfidenceFrame,
    EyeContactSignal,
    HeadStabilitySignal,
    compute_baseline_comparison,
    compute_progress,
    compute_summary,
    detect_notable_moments,
    downsample_frames,
)


def _frame(
    timestamp_ms: int,
    composite_score: float,
    eye_contact_ratio: float = 0.7,
    stability: float = 0.8,
    blinks_per_minute: float = 16.0,
    expression: str = "neutral",
) -> ConfidenceFrame:
    return ConfidenceFrame(
        timestamp_ms=timestamp_ms,
        eye_contact=EyeContactSignal(
            direction="direct", confidence=0.9, contact_ratio_30s=eye_contact_ratio
        ),
        head_stability=HeadStabilitySignal(
            pitch=0.0, yaw=0.0, roll=0.0, stability_score=stability, movement_pattern="stable"
        ),
        blink_rate=BlinkSignal(
            ear_left=0.3,
            ear_right=0.3,
            is_blinking=False,
            blinks_per_minute=blinks_per_minute,
            assessment="normal",
        ),
        expression=expression,
        composite_score=composite_score,
    )


class TestComputeSummary:
    def test_empty_frames_returns_zeroed_summary(self):
        summary = compute_summary([])
        assert summary.composite_score == 0.0
        assert summary.frame_count == 0
        assert summary.dominant_expression == "neutral"

    def test_averages_are_computed_correctly(self):
        frames = [
            _frame(0, 80, eye_contact_ratio=0.6, stability=0.9, blinks_per_minute=14),
            _frame(500, 90, eye_contact_ratio=0.8, stability=0.7, blinks_per_minute=18),
        ]
        summary = compute_summary(frames)
        assert summary.composite_score == 85.0
        assert summary.avg_eye_contact_ratio == 0.7
        assert summary.avg_stability_score == 0.8
        assert summary.avg_blink_rate == 16.0
        assert summary.frame_count == 2

    def test_dominant_expression_is_the_most_frequent(self):
        frames = [
            _frame(0, 80, expression="happy"),
            _frame(500, 80, expression="happy"),
            _frame(1000, 80, expression="anxious"),
        ]
        summary = compute_summary(frames)
        assert summary.dominant_expression == "happy"

    def test_summary_includes_notable_moments(self):
        frames = [_frame(0, 90), _frame(500, 60)]  # 30-point drop
        summary = compute_summary(frames)
        assert len(summary.notable_moments) == 1


class TestDetectNotableMoments:
    def test_no_moments_when_scores_are_stable(self):
        frames = [_frame(0, 80), _frame(500, 82), _frame(1000, 79)]
        assert detect_notable_moments(frames) == []

    def test_sharp_drop_is_flagged(self):
        frames = [_frame(0, 85), _frame(500, 60)]
        moments = detect_notable_moments(frames)
        assert len(moments) == 1
        assert moments[0].timestamp_ms == 500
        assert moments[0].composite_score == 60

    def test_gradual_decline_below_threshold_is_not_flagged(self):
        frames = [_frame(i * 500, 85 - i * 5) for i in range(5)]  # -5/frame, under 15 threshold
        assert detect_notable_moments(frames) == []

    def test_custom_threshold_is_respected(self):
        frames = [_frame(0, 85), _frame(500, 78)]  # 7-point drop
        assert detect_notable_moments(frames, threshold=15.0) == []
        assert len(detect_notable_moments(frames, threshold=5.0)) == 1

    def test_single_frame_has_no_moments(self):
        assert detect_notable_moments([_frame(0, 85)]) == []

    def test_multiple_drops_are_all_flagged(self):
        frames = [_frame(0, 90), _frame(500, 60), _frame(1000, 88), _frame(1500, 50)]
        moments = detect_notable_moments(frames)
        assert len(moments) == 2


class TestBaselineComparison:
    def test_confidence_delta_reflects_drop_under_pressure(self):
        warmup = [_frame(0, 85), _frame(500, 82)]
        interview = [_frame(1000, 60), _frame(1500, 65)]
        comparison = compute_baseline_comparison(warmup, interview)

        assert comparison.warmup_confidence == 83.5
        assert comparison.interview_confidence == 62.5
        assert comparison.confidence_delta == -21.0

    def test_worst_drop_timestamp_identifies_the_lowest_scoring_frame(self):
        warmup = [_frame(0, 85)]
        interview = [_frame(1000, 70), _frame(1500, 40), _frame(2000, 75)]
        comparison = compute_baseline_comparison(warmup, interview)
        assert comparison.worst_drop_timestamp_ms == 1500

    def test_no_drop_when_confidence_holds_steady(self):
        warmup = [_frame(0, 80)]
        interview = [_frame(1000, 82), _frame(1500, 79)]
        comparison = compute_baseline_comparison(warmup, interview)
        assert comparison.recovery_pattern == "no_drop"

    def test_quick_recovery_pattern(self):
        warmup = [_frame(0, 85)]
        interview = [
            _frame(1000, 85),
            _frame(1500, 40),  # big drop
            _frame(2000, 84),  # recovers almost immediately
            _frame(2500, 83),
            _frame(3000, 85),
        ]
        comparison = compute_baseline_comparison(warmup, interview)
        assert comparison.recovery_pattern == "quick_recovery"

    def test_sustained_drop_pattern(self):
        warmup = [_frame(0, 85)]
        interview = [_frame(1000, 84), _frame(1500, 40), _frame(2000, 42), _frame(2500, 38)]
        comparison = compute_baseline_comparison(warmup, interview)
        assert comparison.recovery_pattern == "sustained_drop"

    def test_empty_warmup_or_interview_does_not_crash(self):
        comparison = compute_baseline_comparison([], [])
        assert comparison.warmup_confidence == 0.0
        assert comparison.interview_confidence == 0.0
        assert comparison.recovery_pattern == "no_drop"


class TestComputeProgress:
    def test_one_progress_point_per_session(self):
        summaries = [compute_summary([_frame(0, 60)]), compute_summary([_frame(0, 85)])]
        points = compute_progress(["session-1", "session-2"], summaries)

        assert len(points) == 2
        assert points[0].session_id == "session-1"
        assert points[0].composite_confidence == 60
        assert points[1].composite_confidence == 85

    def test_expression_positivity_reflects_dominant_expression(self):
        happy_summary = compute_summary([_frame(0, 80, expression="happy")])
        anxious_summary = compute_summary([_frame(0, 80, expression="anxious")])
        neutral_summary = compute_summary([_frame(0, 80, expression="neutral")])

        points = compute_progress(
            ["s1", "s2", "s3"], [happy_summary, anxious_summary, neutral_summary]
        )
        assert points[0].expression_positivity == 1.0
        assert points[1].expression_positivity == 0.0
        assert points[2].expression_positivity == 0.5


class TestDownsampleFrames:
    def test_empty_input_returns_empty(self):
        assert downsample_frames([]) == []

    def test_low_fps_source_is_returned_unchanged(self):
        frames = [_frame(0, 80), _frame(1000, 80)]  # 2 frames over 1s = 2fps already
        assert downsample_frames(frames, target_fps=2.0) == frames

    def test_high_fps_source_is_reduced(self):
        # 30 frames over 1 second = 30fps -> downsample to ~2fps should give ~2 frames
        frames = [_frame(i * 33, 80) for i in range(30)]
        result = downsample_frames(frames, target_fps=2.0)
        assert len(result) < len(frames)
        assert len(result) <= 4  # roughly 2 for ~1s of footage, generous margin

    def test_downsampled_frames_are_real_frames_not_synthesized(self):
        frames = [_frame(i * 33, 70 + i) for i in range(30)]
        result = downsample_frames(frames, target_fps=2.0)
        original_scores = {f.composite_score for f in frames}
        assert all(f.composite_score in original_scores for f in result)

    def test_single_frame_is_returned_as_is(self):
        frames = [_frame(0, 80)]
        assert downsample_frames(frames) == frames
