"""
JD coverage matrix (spec §8.6) — extracts the skills/requirements implied
by a job description, then checks which ones the actual interview
questions exercised, so a candidate can see "you were never asked about
X, which the JD lists as required" as clearly as "you nailed Y".

Skill extraction has an LLM path (more accurate, handles JD prose) and a
keyword-bank fallback (works fully offline, catches the most common
technical/soft skills verbatim in the JD text).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.scoring.fusion import QuestionBreakdown
from app.services.scoring.llm_client import ScoringLLMClient

# Deliberately broad and mixed technical/soft-skill, since JDs mix both.
COMMON_SKILL_KEYWORDS = [
    "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust", "sql",
    "react", "vue", "angular", "node.js", "django", "flask", "fastapi", "spring",
    "aws", "azure", "gcp", "docker", "kubernetes", "ci/cd", "terraform",
    "system design", "distributed systems", "microservices", "rest api", "graphql",
    "machine learning", "data pipelines", "etl", "data structures", "algorithms",
    "leadership", "mentoring", "stakeholder management", "cross-functional",
    "communication", "project management", "agile", "scrum", "problem solving",
    "testing", "unit testing", "debugging", "code review", "security",
]


@dataclass
class SkillCoverage:
    skill: str
    covered: bool
    evidence_question: str | None = None
    confidence: float = 0.0   # 0-1


@dataclass
class CoverageMatrix:
    required_skills: list[str]
    coverage: list[SkillCoverage] = field(default_factory=list)
    coverage_pct: float = 0.0
    gaps: list[str] = field(default_factory=list)


class CoverageMatrixBuilder:
    def __init__(self, llm_client: ScoringLLMClient | None = None):
        self.llm_client = llm_client or ScoringLLMClient()

    async def build(self, jd_text: str, breakdown: list[QuestionBreakdown]) -> CoverageMatrix:
        skills = await self._extract_skills(jd_text)
        if not skills:
            return CoverageMatrix(required_skills=[], coverage=[], coverage_pct=0.0, gaps=[])

        corpus = " ".join(f"{qb.question} {qb.user_answer} {' '.join(qb.skill_tags)}" for qb in breakdown).lower()

        coverage: list[SkillCoverage] = []
        for skill in skills:
            evidence_q, confidence = self._find_evidence(skill, breakdown, corpus)
            coverage.append(
                SkillCoverage(
                    skill=skill, covered=confidence > 0.0,
                    evidence_question=evidence_q, confidence=round(confidence, 2),
                )
            )

        covered_count = sum(1 for c in coverage if c.covered)
        coverage_pct = round((covered_count / len(coverage)) * 100, 1) if coverage else 0.0
        gaps = [c.skill for c in coverage if not c.covered]

        return CoverageMatrix(required_skills=skills, coverage=coverage, coverage_pct=coverage_pct, gaps=gaps)

    async def _extract_skills(self, jd_text: str) -> list[str]:
        if not jd_text.strip():
            return []

        llm_result = await self._llm_extract(jd_text)
        if llm_result:
            return llm_result

        lower = jd_text.lower()
        found = [kw for kw in COMMON_SKILL_KEYWORDS if kw in lower]
        return found

    async def _llm_extract(self, jd_text: str) -> list[str] | None:
        result = await self.llm_client._complete_json(  # noqa: SLF001 - internal reuse within the same package
            system="Extract the concrete required skills/technologies/competencies from a job "
            "description. Return 8-15 short skill names, no duplicates.",
            user=f'Job description:\n"""\n{jd_text}\n"""\n\nReturn JSON: {{"skills": ["..."]}}',
            max_tokens=300,
        )
        if result and "skills" in result:
            return [s.strip() for s in result["skills"] if s.strip()][:15]
        return None

    def _find_evidence(
        self, skill: str, breakdown: list[QuestionBreakdown], corpus: str
    ) -> tuple[str | None, float]:
        skill_lower = skill.lower()
        pattern = re.escape(skill_lower)

        # Prefer a question that directly mentions the skill.
        for qb in breakdown:
            haystack = f"{qb.question} {' '.join(qb.skill_tags)}".lower()
            if re.search(pattern, haystack):
                return qb.question, 0.9

        # Weaker signal: skill only appears in the candidate's answer text.
        for qb in breakdown:
            if re.search(pattern, qb.user_answer.lower()):
                return qb.question, 0.5

        if re.search(pattern, corpus):
            return None, 0.3

        return None, 0.0
