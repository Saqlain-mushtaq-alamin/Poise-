"""
Coding problem generator — Phase 6.

Mount point: backend/app/services/problem_generator.py

Generates a coding problem grounded in the JD + resume produced by
Phase 4's ingestion pipeline (`app.services.ingestion.ResumeData`,
`app.services.ingestion.JobDescription`). Falls back to a small local
problem bank when no JD/resume context is available (e.g. a standalone
coding-practice session) or when generation fails validation.
"""
from __future__ import annotations

import json
import logging
import random

from app.schemas.coding import CodingProblem, Example, TestCase

logger = logging.getLogger("poise.problem_generator")

PROBLEM_GEN_SYSTEM_PROMPT = """You are writing a coding interview problem for a candidate. Ground \
the problem's theme/domain in the job description and resume context you're given (e.g. a backend \
role heavy on data pipelines might get a stream-processing themed array problem; this only affects \
flavor text, not core CS fundamentals — the underlying algorithmic skill being tested should still \
be a standard, well-defined pattern like arrays, strings, graphs, DP, etc.)

Respond with STRICT JSON ONLY, matching this schema:
{
  "title": string,
  "description": string (markdown, includes the problem statement),
  "examples": [{"input": string, "output": string, "explanation": string|null}, ...],
  "constraints": [string, ...],
  "test_cases": [{"input": string, "expected_output": string, "is_hidden": bool}, ...],
  "hints": [string, ...],
  "difficulty": "easy" | "medium" | "hard",
  "topics": [string, ...],
  "starter_code": {"python": string, "javascript": string, "java": string, "cpp": string}
}

Requirements:
- Include at least 4 test_cases: 2 visible (is_hidden=false) matching the examples, and at least 2
  hidden (is_hidden=true) covering edge cases (empty input, boundary values, duplicates, etc.)
- starter_code should define the function signature only, with a short docstring/comment — no
  solution logic.
- Keep the problem solvable within ~25-35 minutes at the requested difficulty.
- input/output in test_cases must be given exactly as they'd appear on stdin/stdout for a program
  that reads input and prints output (not as function-call syntax), so it works with the sandbox
  runner as written.
"""


class ProblemGenerator:
    def __init__(self, provider):
        self.provider = provider

    async def generate(
        self,
        jd=None,
        resume=None,
        difficulty: str = "medium",
        topics: list[str] | None = None,
    ) -> CodingProblem:
        try:
            return await self._generate_via_llm(jd, resume, difficulty, topics or [])
        except Exception:
            logger.exception("LLM problem generation failed, using local bank fallback")
            return _pick_from_bank(difficulty, topics or [])

    async def _generate_via_llm(self, jd, resume, difficulty, topics) -> CodingProblem:
        from app.services.provider import ModelRole  # noqa: PLC0415

        context_lines = [f"Requested difficulty: {difficulty}"]
        if topics:
            context_lines.append(f"Preferred topics: {', '.join(topics)}")
        if jd is not None:
            title = getattr(jd, "title", None) or (jd.get("title") if isinstance(jd, dict) else None)
            domain = getattr(jd, "domain", None) or (jd.get("domain") if isinstance(jd, dict) else None)
            skills = getattr(jd, "required_skills", None) or (
                jd.get("required_skills") if isinstance(jd, dict) else None
            )
            if title:
                context_lines.append(f"Role: {title}")
            if domain:
                context_lines.append(f"Domain: {domain}")
            if skills:
                context_lines.append(f"Required skills: {', '.join(skills)}")
        if resume is not None:
            skills = getattr(resume, "skills", None) or (
                resume.get("skills") if isinstance(resume, dict) else None
            )
            if skills:
                skill_names = [s.name if hasattr(s, "name") else str(s) for s in skills][:10]
                context_lines.append(f"Candidate skills: {', '.join(skill_names)}")

        user_prompt = "\n".join(context_lines) + "\n\nGenerate the problem now. JSON only."

        response = await self.provider.chat(
            messages=[
                {"role": "system", "content": PROBLEM_GEN_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model_role=ModelRole.REASONING,
            stream=False,
        )

        text = _extract_text(response)
        data = json.loads(_strip_code_fence(text))
        problem = CodingProblem.model_validate(data)
        _validate_problem(problem)
        return problem


def _validate_problem(problem: CodingProblem) -> None:
    visible = [tc for tc in problem.test_cases if not tc.is_hidden]
    hidden = [tc for tc in problem.test_cases if tc.is_hidden]
    if len(visible) < 1 or len(hidden) < 1:
        raise ValueError("Generated problem lacks sufficient visible/hidden test cases")
    if not problem.starter_code:
        raise ValueError("Generated problem lacks starter code")


def _extract_text(response) -> str:
    if isinstance(response, str):
        return response
    try:
        return response.choices[0].message.content
    except AttributeError:
        pass
    if isinstance(response, dict):
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            pass
    return str(response)


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)
        t = t[1] if len(t) > 1 else t[0]
        if t.startswith("json"):
            t = t[4:]
    return t.strip()


# --------------------------------------------------------------------
# Local fallback bank — used if LLM generation is unavailable/invalid
# --------------------------------------------------------------------

_BANK: list[CodingProblem] = [
    CodingProblem(
        title="Two Sum",
        description=(
            "Given a list of integers and a target value, print the two 0-indexed "
            "indices whose values add up to the target, space-separated. "
            "Assume exactly one solution exists.\n\n"
            "**Input format:** first line is the array (space-separated ints), "
            "second line is the target.\n"
            "**Output format:** two space-separated indices."
        ),
        examples=[Example(input="2 7 11 15\n9", output="0 1")],
        constraints=["2 <= nums.length <= 10^4", "-10^9 <= nums[i] <= 10^9"],
        test_cases=[
            TestCase(input="2 7 11 15\n9", expected_output="0 1", is_hidden=False),
            TestCase(input="3 2 4\n6", expected_output="1 2", is_hidden=False),
            TestCase(input="3 3\n6", expected_output="0 1", is_hidden=True),
            TestCase(input="-1 -2 -3 -4 -5\n-8", expected_output="2 4", is_hidden=True),
        ],
        hints=["A hash map from value to index gets this to O(n)."],
        difficulty="easy",
        topics=["arrays", "hash_map"],
        starter_code={
            "python": (
                "import sys\n\n"
                "def two_sum(nums, target):\n"
                "    # Your code here\n"
                "    pass\n\n"
                "if __name__ == '__main__':\n"
                "    data = sys.stdin.read().split('\\n')\n"
                "    nums = list(map(int, data[0].split()))\n"
                "    target = int(data[1])\n"
                "    result = two_sum(nums, target)\n"
                "    print(*result)\n"
            ),
        },
    ),
    CodingProblem(
        title="Valid Parentheses",
        description=(
            "Given a string containing just the characters `(`, `)`, `{`, `}`, `[`, `]`, "
            "print `true` if it is valid (properly matched and nested), else `false`."
        ),
        examples=[Example(input="()[]{}", output="true"), Example(input="(]", output="false")],
        constraints=["1 <= s.length <= 10^4"],
        test_cases=[
            TestCase(input="()", expected_output="true", is_hidden=False),
            TestCase(input="(]", expected_output="false", is_hidden=False),
            TestCase(input="", expected_output="true", is_hidden=True),
            TestCase(input="([{}])", expected_output="true", is_hidden=True),
        ],
        hints=["Use a stack; push opening brackets, pop and compare on closing brackets."],
        difficulty="easy",
        topics=["stacks", "strings"],
        starter_code={
            "python": (
                "import sys\n\n"
                "def is_valid(s):\n"
                "    # Your code here\n"
                "    pass\n\n"
                "if __name__ == '__main__':\n"
                "    s = sys.stdin.readline().rstrip('\\n')\n"
                "    print('true' if is_valid(s) else 'false')\n"
            ),
        },
    ),
]


def _pick_from_bank(difficulty: str, topics: list[str]) -> CodingProblem:
    matches = [p for p in _BANK if p.difficulty == difficulty]
    if topics:
        topic_matches = [p for p in matches if set(p.topics) & set(topics)]
        if topic_matches:
            matches = topic_matches
    pool = matches or _BANK
    return random.choice(pool)
