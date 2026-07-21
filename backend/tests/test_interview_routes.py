"""Interview engine HTTP integration tests — full request/response
lifecycle through FastAPI's TestClient, with the LLM provider swapped for
a fake at the dependency-injection boundary (app.dependency_overrides)."""

from __future__ import annotations

import io
import json

import pytest


class ScriptedProvider:
    """Returns queued responses in order; raises clearly if the test
    script runs out (usually means the router made an unexpected call)."""

    def __init__(self):
        self.queue: list[str] = []
        self.calls: list[list[dict]] = []

    def queue_response(self, text: str) -> None:
        self.queue.append(text)

    async def chat(self, messages, model_role=None, stream=False, **kwargs):
        self.calls.append(messages)
        if not self.queue:
            raise AssertionError(
                f"ScriptedProvider ran out of queued responses (call #{len(self.calls)})"
            )
        return self.queue.pop(0)


@pytest.fixture()
def scripted_provider(client):
    from app.services.provider import get_router

    fake = ScriptedProvider()
    client.app.dependency_overrides[get_router] = lambda: fake
    yield fake
    client.app.dependency_overrides.pop(get_router, None)


RESUME_JSON = json.dumps(
    {
        "name": "Jane Doe",
        "summary": "Backend engineer",
        "skills": [{"name": "Python"}],
        "experience": [{"company": "Acme", "title": "Engineer", "highlights": ["Built things"]}],
    }
)
JD_JSON = json.dumps(
    {
        "title": "Senior Backend Engineer",
        "company": "Acme Corp",
        "required_skills": ["Python"],
        "responsibilities": ["Design APIs"],
        "experience_level": "senior",
    }
)
PLAN_JSON = json.dumps(
    {
        "sections": [
            {
                "type": "behavioral",
                "title": "Behavioral",
                "time_budget_minutes": 10,
                "questions": [
                    {
                        "id": "q1",
                        "text": "Tell me about a challenging project.",
                        "evaluation_criteria": ["specificity"],
                        "source": "behavioral_framework",
                        "skills_tested": ["behavioral"],
                    },
                    {
                        "id": "q2",
                        "text": "How do you handle conflicting priorities?",
                        "evaluation_criteria": ["prioritization"],
                        "source": "jd_requirement",
                    },
                ],
            }
        ],
        "coverage_matrix": {},
    }
)


def _parse_resume(client, scripted_provider):
    scripted_provider.queue_response(RESUME_JSON)
    resp = client.post(
        "/interview/parse-resume",
        files={"file": ("resume.docx", _fake_docx_bytes(), "application/octet-stream")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["resume_id"]


def _fake_docx_bytes() -> io.BytesIO:
    import docx

    buf = io.BytesIO()
    document = docx.Document()
    document.add_paragraph("Jane Doe - Backend Engineer")
    document.save(buf)
    buf.seek(0)
    return buf


def _parse_jd(client, scripted_provider):
    scripted_provider.queue_response(JD_JSON)
    resp = client.post("/interview/parse-jd", json={"text": "We need a senior backend engineer"})
    assert resp.status_code == 200, resp.text
    return resp.json()["jd_id"]


def _create_session(client, scripted_provider, resume_id, jd_id, **config_overrides):
    scripted_provider.queue_response(PLAN_JSON)
    config = {
        "duration_minutes": 20,
        "include_behavioral": True,
        "include_technical": False,
        "include_coding": False,
        **config_overrides,
    }
    resp = client.post(
        "/interview/sessions",
        json={
            "resume_id": resume_id,
            "jd_id": jd_id,
            "config": config,
            "persona_id": "professional",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_parse_resume_extracts_and_structures(client, scripted_provider):
    resume_id = _parse_resume(client, scripted_provider)
    assert resume_id is not None


def test_parse_jd_structures(client, scripted_provider):
    jd_id = _parse_jd(client, scripted_provider)
    assert jd_id is not None


def test_generate_plan_returns_a_valid_plan(client, scripted_provider):
    resume_id = _parse_resume(client, scripted_provider)
    jd_id = _parse_jd(client, scripted_provider)

    scripted_provider.queue_response(PLAN_JSON)
    resp = client.post(
        "/interview/generate-plan",
        json={
            "resume_id": resume_id,
            "jd_id": jd_id,
            "config": {
                "include_behavioral": True,
                "include_technical": False,
                "include_coding": False,
            },
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["sections"][0]["questions"][0]["id"] == "q1"


def test_generate_plan_404s_on_unknown_resume(client, scripted_provider):
    resp = client.post(
        "/interview/generate-plan",
        json={"resume_id": "nope", "jd_id": "nope", "config": {}},
    )
    assert resp.status_code == 404


def test_personas_endpoint_lists_at_least_three(client):
    resp = client.get("/interview/personas")
    assert resp.status_code == 200
    assert len(resp.json()) >= 3


def test_company_formats_endpoint_lists_amazon(client):
    resp = client.get("/interview/company-formats")
    ids = [f["id"] for f in resp.json()]
    assert "amazon" in ids


def test_create_session_runs_through_setup_to_ready(client, scripted_provider):
    resume_id = _parse_resume(client, scripted_provider)
    jd_id = _parse_jd(client, scripted_provider)
    session = _create_session(client, scripted_provider, resume_id, jd_id)

    assert session["state"] == "ready"
    assert session["plan"]["sections"][0]["questions"][0]["id"] == "q1"


def test_create_session_rejects_unknown_persona(client, scripted_provider):
    resume_id = _parse_resume(client, scripted_provider)
    jd_id = _parse_jd(client, scripted_provider)

    scripted_provider.queue_response(PLAN_JSON)
    resp = client.post(
        "/interview/sessions",
        json={
            "resume_id": resume_id,
            "jd_id": jd_id,
            "config": {
                "include_behavioral": True,
                "include_technical": False,
                "include_coding": False,
            },
            "persona_id": "not-a-real-persona",
        },
    )
    assert resp.status_code == 400


def test_full_happy_path_through_two_questions_to_completion(client, scripted_provider):
    resume_id = _parse_resume(client, scripted_provider)
    jd_id = _parse_jd(client, scripted_provider)
    session = _create_session(client, scripted_provider, resume_id, jd_id)
    session_id = session["session_id"]

    # start() -> greeting
    scripted_provider.queue_response("Hi Jane, welcome!")
    resp = client.post(f"/interview/sessions/{session_id}/start")
    assert resp.status_code == 200, resp.text
    assert resp.json()["message"] == "Hi Jane, welcome!"

    # warm-up: 4 stages (greeting -> logistics -> ice_breaker -> role_context -> complete)
    for _ in range(3):
        scripted_provider.queue_response("okay, cool")
        resp = client.post(
            f"/interview/sessions/{session_id}/warmup-respond", json={"text": "sure"}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["is_complete"] is False

    scripted_provider.queue_response("Great, let's begin!")  # role_context reply
    resp = client.post(
        f"/interview/sessions/{session_id}/warmup-respond", json={"text": "excited!"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_complete"] is True
    assert body["first_question"] is not None
    assert "Tell me about a challenging project" in body["first_question"]

    # answer question 1 with a strong score -> next_question
    scripted_provider.queue_response(json.dumps({"score": 0.9, "feedback": "Great", "gaps": []}))
    resp = client.post(
        f"/interview/sessions/{session_id}/answer", json={"text": "A detailed STAR answer."}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["next_action"] == "next_question"
    assert "conflicting priorities" in body["next_message"]

    # answer question 2 -> plan exhausted -> session_complete
    scripted_provider.queue_response(json.dumps({"score": 0.85, "feedback": "Solid", "gaps": []}))
    resp = client.post(
        f"/interview/sessions/{session_id}/answer", json={"text": "I prioritize by impact."}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["next_action"] == "session_complete"

    # evaluations available for Phase 8
    resp = client.get(f"/interview/sessions/{session_id}/evaluations")
    assert resp.status_code == 200
    evaluations = resp.json()
    assert len(evaluations) == 2
    assert evaluations[0]["score"] == 0.9
    assert evaluations[1]["score"] == 0.85


def test_follow_up_path_inserts_an_extra_turn(client, scripted_provider):
    resume_id = _parse_resume(client, scripted_provider)
    jd_id = _parse_jd(client, scripted_provider)
    session = _create_session(client, scripted_provider, resume_id, jd_id)
    session_id = session["session_id"]

    scripted_provider.queue_response("Hi!")
    client.post(f"/interview/sessions/{session_id}/start")
    for _ in range(3):
        scripted_provider.queue_response("ok")
        client.post(f"/interview/sessions/{session_id}/warmup-respond", json={"text": "sure"})
    scripted_provider.queue_response("Let's start.")
    client.post(f"/interview/sessions/{session_id}/warmup-respond", json={"text": "ready"})

    scripted_provider.queue_response(
        json.dumps({"score": 0.3, "feedback": "Too vague", "gaps": ["no concrete outcome"]})
    )
    scripted_provider.queue_response("What was the measurable result?")
    resp = client.post(
        f"/interview/sessions/{session_id}/answer", json={"text": "I did some stuff."}
    )
    body = resp.json()

    assert body["next_action"] == "follow_up"
    assert "What was the measurable result?" in body["next_message"]

    resp = client.get(f"/interview/sessions/{session_id}/evaluations")
    assert len(resp.json()) == 2  # original turn + follow-up turn


def test_answer_before_start_is_rejected(client, scripted_provider):
    resume_id = _parse_resume(client, scripted_provider)
    jd_id = _parse_jd(client, scripted_provider)
    session = _create_session(client, scripted_provider, resume_id, jd_id)

    resp = client.post(
        f"/interview/sessions/{session['session_id']}/answer", json={"text": "too early"}
    )
    assert resp.status_code == 400


def test_get_session_returns_current_state(client, scripted_provider):
    resume_id = _parse_resume(client, scripted_provider)
    jd_id = _parse_jd(client, scripted_provider)
    session = _create_session(client, scripted_provider, resume_id, jd_id)

    resp = client.get(f"/interview/sessions/{session['session_id']}")
    assert resp.status_code == 200
    assert resp.json()["state"] == "ready"


def test_get_unknown_session_404s(client):
    resp = client.get("/interview/sessions/not-a-real-id")
    assert resp.status_code == 404


def test_manual_end_session_from_ready_state_is_handled_gracefully(client, scripted_provider):
    resume_id = _parse_resume(client, scripted_provider)
    jd_id = _parse_jd(client, scripted_provider)
    session = _create_session(client, scripted_provider, resume_id, jd_id)

    # "ready" isn't in-progress or warm_up, so end_session should just
    # leave the state alone rather than crash.
    resp = client.post(f"/interview/sessions/{session['session_id']}/end")
    assert resp.status_code == 200
    assert resp.json()["state"] == "ready"


def test_manual_end_mid_interview_reaches_completed(client, scripted_provider):
    resume_id = _parse_resume(client, scripted_provider)
    jd_id = _parse_jd(client, scripted_provider)
    session = _create_session(client, scripted_provider, resume_id, jd_id)
    session_id = session["session_id"]

    scripted_provider.queue_response("Hi!")
    client.post(f"/interview/sessions/{session_id}/start")
    for _ in range(3):
        scripted_provider.queue_response("ok")
        client.post(f"/interview/sessions/{session_id}/warmup-respond", json={"text": "sure"})
    scripted_provider.queue_response("Let's start.")
    client.post(f"/interview/sessions/{session_id}/warmup-respond", json={"text": "ready"})

    resp = client.post(f"/interview/sessions/{session_id}/end")
    assert resp.status_code == 200
    assert resp.json()["state"] == "completed"
