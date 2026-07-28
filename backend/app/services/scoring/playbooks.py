"""
Improvement playbooks (spec §8.10) — a static library of targeted
exercises for common weaknesses, plus a matcher that reads a `FusedReport`
and returns the playbooks most relevant to what that specific candidate
struggled with (not just a generic "here's every playbook" dump).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.scoring.fusion import FusedReport

IMPROVEMENT_PLAYBOOKS: dict[str, dict] = {
    "vague_answers": {
        "title": "Add specifics to your answers",
        "description": (
            "Your answers are directionally right but lack the concrete numbers, names, "
            "and timeframes that make a story credible and memorable."
        ),
        "exercises": [
            {"name": "The 'so what' drill", "description": "For every sentence in a past answer, ask 'so what number backs this up?' and add it.", "duration_minutes": 15},
            {"name": "Metric inventory", "description": "List 10 projects from your resume and write one quantified outcome for each.", "duration_minutes": 20},
        ],
    },
    "missing_star_structure": {
        "title": "Structure behavioral answers with STAR",
        "description": (
            "Your behavioral answers don't consistently establish Situation, Task, Action, "
            "and Result — interviewers lose the thread without that scaffolding."
        ),
        "exercises": [
            {"name": "STAR outline practice", "description": "Take 5 stories from your resume and outline each in strict S-T-A-R bullet form before speaking them.", "duration_minutes": 25},
            {"name": "Result-first rehearsal", "description": "Practice stating the Result in one sentence first, then backfilling S-T-A — this keeps answers tight.", "duration_minutes": 15},
        ],
    },
    "filler_words": {
        "title": "Reduce filler words and hesitations",
        "description": "Frequent 'um'/'uh'/'like' is pulling down your fluency score and distracting from your content.",
        "exercises": [
            {"name": "Slow-and-pause drill", "description": "Answer 5 practice questions, deliberately pausing silently instead of using a filler word.", "duration_minutes": 15},
            {"name": "Record and count", "description": "Record a 2-minute answer, count filler words, then re-record aiming for zero.", "duration_minutes": 10},
        ],
    },
    "poor_eye_contact": {
        "title": "Improve on-camera presence",
        "description": "Low eye-contact percentage and inconsistent framing are undercutting how confident you come across.",
        "exercises": [
            {"name": "Camera-as-interviewer drill", "description": "Tape a small dot next to your webcam lens and practice looking directly at it, not your own video preview.", "duration_minutes": 10},
            {"name": "Posture check-ins", "description": "Practice 3 answers while consciously keeping shoulders back and centered in frame.", "duration_minutes": 10},
        ],
    },
    "weak_technical_depth": {
        "title": "Deepen technical explanations",
        "description": "Technical answers stay high-level where the interviewer wanted implementation depth or trade-off discussion.",
        "exercises": [
            {"name": "Trade-off drill", "description": "For 5 technical decisions you've made, write out 2 alternatives you considered and why you rejected them.", "duration_minutes": 25},
            {"name": "Whiteboard-out-loud", "description": "Re-explain a past system design answer while sketching it, narrating every design decision.", "duration_minutes": 20},
        ],
    },
    "pacing_issues": {
        "title": "Fix pacing (too fast or too slow)",
        "description": "Your speaking rate is outside the range that reads as confident and easy to follow.",
        "exercises": [
            {"name": "Metronome pacing", "description": "Practice answering at ~140 words/min using a metronome or pacing app.", "duration_minutes": 15},
            {"name": "Chunk-and-breathe", "description": "Break a 2-minute answer into 3 chunks with a deliberate breath between each.", "duration_minutes": 10},
        ],
    },
    "low_jd_coverage": {
        "title": "Prepare for uncovered JD requirements",
        "description": "Several skills listed in the target job description were never exercised by the questions you practiced — you're likely under-prepared to speak to them.",
        "exercises": [
            {"name": "Gap-story mapping", "description": "For each uncovered skill, find one real example from your background you could use if asked.", "duration_minutes": 20},
            {"name": "Anticipated-question drill", "description": "Write the single most likely interview question for each JD gap and draft a 30-second answer.", "duration_minutes": 25},
        ],
    },
}


def match_playbooks(report: "FusedReport", coverage_gaps: list[str] | None = None) -> list[dict]:
    """Returns the playbooks (with their key attached) relevant to this
    specific report — ranked, not exhaustive."""
    matched: list[tuple[str, int]] = []  # (key, priority score, lower = more relevant)

    for dim in report.dimensions:
        if not dim.available:
            continue
        if dim.score >= 70:
            continue
        name = dim.name.lower()
        if "content" in name or "lexical" in name or "grammatical" in name:
            matched.append(("vague_answers", int(dim.score)))
        if "technical" in name:
            matched.append(("weak_technical_depth", int(dim.score)))
        if "confidence" in name or "pronunciation" in name:
            matched.append(("poor_eye_contact", int(dim.score)))
        if "communication" in name or "fluency" in name:
            matched.append(("filler_words", int(dim.score)))
            matched.append(("pacing_issues", int(dim.score)))

    weak_structured = [
        qb for qb in report.per_question_breakdown
        if qb.annotated_answer and qb.annotated_answer.overall_structure in ("rambling", "unfocused")
    ]
    if len(weak_structured) >= 2:
        matched.append(("missing_star_structure", 50))

    if coverage_gaps:
        matched.append(("low_jd_coverage", 40))

    # de-dupe, keep the lowest (most urgent) score per key, then sort by urgency
    best: dict[str, int] = {}
    for key, score in matched:
        best[key] = min(score, best.get(key, 100))

    ordered_keys = sorted(best, key=lambda k: best[k])
    return [{"key": k, **IMPROVEMENT_PLAYBOOKS[k]} for k in ordered_keys if k in IMPROVEMENT_PLAYBOOKS]
