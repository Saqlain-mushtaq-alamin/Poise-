"""
Model answer generation + diffing (spec §8.9) — generates a strong answer
GROUNDED IN THE CANDIDATE'S OWN BACKGROUND (never invented experience),
then diffs it against what the candidate actually said so the report can
show "here's what changed" rather than just "here's a better answer".

Requires an LLM provider to generate genuinely useful model answers (this
is creative synthesis, not something a heuristic can fake well) — without
one, `generate()` returns a clearly-labeled placeholder that still lets
the rest of the report render.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.scoring.llm_client import ScoringLLMClient


@dataclass
class ModelAnswer:
    full_text: str
    framework_used: str
    key_elements: list[str] = field(default_factory=list)
    why_it_works: str = ""
    is_placeholder: bool = False


@dataclass
class DiffSegment:
    text: str
    kind: str   # "unchanged" | "added" | "removed"


@dataclass
class AnswerDiff:
    segments: list[DiffSegment]
    similarity_ratio: float   # 0-1, from difflib


class ModelAnswerGenerator:
    def __init__(self, llm_client: Optional[ScoringLLMClient] = None):
        self.llm_client = llm_client or ScoringLLMClient()

    async def generate(
        self, question: str, jd_summary: str = "", resume_summary: str = ""
    ) -> ModelAnswer:
        result = await self.llm_client.generate_model_answer(question, jd_summary, resume_summary)
        if result:
            return ModelAnswer(
                full_text=result.get("full_text", ""),
                framework_used=result.get("framework_used", "STAR"),
                key_elements=result.get("key_elements", []),
                why_it_works=result.get("why_it_works", ""),
            )

        return ModelAnswer(
            full_text=(
                "Model answer generation requires an LLM provider (Settings > BYOK). "
                "Once configured, this will generate a strong answer grounded in your "
                "actual resume and the target job description — never invented experience."
            ),
            framework_used="unavailable",
            is_placeholder=True,
        )

    def diff(self, user_answer: str, model_answer: str) -> AnswerDiff:
        user_words = re.findall(r"\S+|\s+", user_answer)
        model_words = re.findall(r"\S+|\s+", model_answer)

        matcher = difflib.SequenceMatcher(a=user_words, b=model_words, autojunk=False)
        segments: list[DiffSegment] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                segments.append(DiffSegment(text="".join(user_words[i1:i2]), kind="unchanged"))
            elif tag == "delete":
                segments.append(DiffSegment(text="".join(user_words[i1:i2]), kind="removed"))
            elif tag == "insert":
                segments.append(DiffSegment(text="".join(model_words[j1:j2]), kind="added"))
            elif tag == "replace":
                segments.append(DiffSegment(text="".join(user_words[i1:i2]), kind="removed"))
                segments.append(DiffSegment(text="".join(model_words[j1:j2]), kind="added"))

        return AnswerDiff(segments=segments, similarity_ratio=round(matcher.ratio(), 3))
