"""HTTP-level tests for /webcam/* — real DB round-trips, no CV/ML involved."""

from __future__ import annotations


def _frame(timestamp_ms: int, composite_score: float, expression: str = "neutral") -> dict:
    return {
        "timestamp_ms": timestamp_ms,
        "eye_contact": {"direction": "direct", "confidence": 0.9, "contact_ratio_30s": 0.75},
        "head_stability": {
            "pitch": 0.0,
            "yaw": 0.0,
            "roll": 0.0,
            "stability_score": 0.8,
            "movement_pattern": "stable",
        },
        "blink_rate": {
            "ear_left": 0.3,
            "ear_right": 0.3,
            "is_blinking": False,
            "blinks_per_minute": 16.0,
            "assessment": "normal",
        },
        "expression": expression,
        "composite_score": composite_score,
    }


def test_submit_frames_stores_them(client):
    resp = client.post("/webcam/session/s1/frames", json=[_frame(0, 80), _frame(500, 82)])
    assert resp.status_code == 200
    assert resp.json() == {"session_id": "s1", "frames_stored": 2}


def test_get_timeline_returns_frames_and_summary(client):
    client.post("/webcam/session/s1/frames", json=[_frame(0, 80), _frame(500, 90)])

    resp = client.get("/webcam/session/s1/timeline")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["frames"]) == 2
    assert body["summary"]["composite_score"] == 85.0


def test_get_timeline_404s_for_unknown_session(client):
    resp = client.get("/webcam/session/does-not-exist/timeline")
    assert resp.status_code == 404


def test_get_summary_returns_computed_summary(client):
    client.post("/webcam/session/s1/frames", json=[_frame(0, 70), _frame(500, 90)])

    resp = client.get("/webcam/session/s1/summary")
    assert resp.status_code == 200
    assert resp.json()["composite_score"] == 80.0


def test_sessions_are_isolated(client):
    client.post("/webcam/session/session-a/frames", json=[_frame(0, 60)])
    client.post("/webcam/session/session-b/frames", json=[_frame(0, 90)])

    resp_a = client.get("/webcam/session/session-a/summary")
    resp_b = client.get("/webcam/session/session-b/summary")
    assert resp_a.json()["composite_score"] == 60
    assert resp_b.json()["composite_score"] == 90


def test_baseline_comparison_splits_frames_by_warmup_end(client):
    client.post(
        "/webcam/session/s1/frames",
        json=[_frame(0, 85), _frame(500, 83), _frame(1000, 60), _frame(1500, 65)],
    )

    resp = client.get("/webcam/session/s1/baseline-comparison", params={"warmup_end_ms": 1000})
    assert resp.status_code == 200
    body = resp.json()
    assert body["warmup_confidence"] == 84.0
    assert body["interview_confidence"] == 62.5
    assert body["confidence_delta"] < 0


def test_progress_returns_one_point_per_session(client):
    client.post("/webcam/session/s1/frames", json=[_frame(0, 60)])
    client.post("/webcam/session/s2/frames", json=[_frame(0, 85)])

    resp = client.get("/webcam/progress", params={"session_ids": ["s1", "s2"]})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["composite_confidence"] == 60
    assert body[1]["composite_confidence"] == 85


def test_frames_persist_across_requests(client):
    client.post("/webcam/session/s1/frames", json=[_frame(0, 80)])
    client.post("/webcam/session/s1/frames", json=[_frame(500, 85)])

    resp = client.get("/webcam/session/s1/timeline")
    assert len(resp.json()["frames"]) == 2


def test_frames_are_returned_in_timestamp_order_regardless_of_insert_order(client):
    client.post("/webcam/session/s1/frames", json=[_frame(1000, 70), _frame(0, 80)])

    resp = client.get("/webcam/session/s1/timeline")
    timestamps = [f["timestamp_ms"] for f in resp.json()["frames"]]
    assert timestamps == [0, 1000]
