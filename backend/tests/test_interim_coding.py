from __future__ import annotations

import json


class ScriptedProvider:
    def __init__(self):
        self.queue = []
        self.calls = []

    def queue_response(self, text: str) -> None:
        self.queue.append(text)

    async def chat(self, messages, model_role=None, stream=False, **kwargs):
        self.calls.append(messages)
        if not self.queue:
            return json.dumps({
                "interviewer_message": "How do you plan to handle authentication and authorization in this Django API?",
                "status": "on_track",
                "suggested_improvements": ["Add permission classes", "Validate request data"]
            })
        return self.queue.pop(0)


def test_review_interim_code_llm(client):
    from app.routers.coding import get_provider

    fake = ScriptedProvider()
    fake.queue_response(json.dumps({
        "interviewer_message": "I see your User model. How will you implement authentication on the endpoints?",
        "status": "good_progress",
        "suggested_improvements": ["Add IsAuthenticated permission", "Use serializers for input validation"]
    }))
    client.app.dependency_overrides[get_provider] = lambda: fake

    try:
        resp = client.post(
            "/coding/review-interim",
            json={
                "question": "Design a simple API using Django that interacts with a relational database to retrieve and display user data. The API should handle authentication and authorization.",
                "code": "from django.db import models\nclass User(models.Model):\n    name = models.CharField(max_length=100)",
                "language": "python",
                "persona_id": "professional"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "interviewer_message" in data
        assert "User model" in data["interviewer_message"] or "authentication" in data["interviewer_message"]
        assert data["status"] in ["on_track", "needs_modification", "good_progress"]
        assert isinstance(data["suggested_improvements"], list)
    finally:
        client.app.dependency_overrides.pop(get_provider, None)


def test_review_interim_code_heuristic_fallback(client):
    from app.routers.coding import get_provider

    class FailingProvider:
        async def chat(self, *args, **kwargs):
            raise RuntimeError("LLM unavailable")

    client.app.dependency_overrides[get_provider] = lambda: FailingProvider()

    try:
        resp = client.post(
            "/coding/review-interim",
            json={
                "question": "Design a simple API using Django that interacts with a relational database to retrieve and display user data. The API should handle authentication and authorization.",
                "code": "class UserData:\n    pass",
                "language": "python",
                "persona_id": "professional"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "interviewer_message" in data
        assert len(data["interviewer_message"]) > 0
        assert data["status"] == "good_progress"
    finally:
        client.app.dependency_overrides.pop(get_provider, None)
