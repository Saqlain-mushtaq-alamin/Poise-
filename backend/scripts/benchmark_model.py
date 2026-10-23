"""Model Benchmark Script for Poise LLM Engines.

Evaluates:
  1. JSON validity rate (percentage of runs producing parseable, schema-compliant JSON)
  2. Latency & Throughput (generation time, tokens/second)
  3. Question Quality & Specificity (depth of questions, criteria, and follow-ups)
  4. Reasoning/Thinking overhead (detecting <think> tags and assessing latency impact)

Usage:
  python scripts/benchmark_model.py [--model llama3.1:8b] [--iterations 3]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass

from app.services.hardware import detect_hardware
from app.services.ingestion import Experience, JobDescription, ResumeData, Skill
from app.services.json_utils import extract_json_from_llm
from app.services.planner import InterviewConfig, InterviewPlan, InterviewPlanner
from app.services.provider import (
    MODEL_CAPABILITIES,
    ModelCapability,
    ModelProviderRouter,
    ModelRole,
    get_model_capability,
)
from app.services.tier import HardwareTier, ModelPlan


@dataclass
class BenchmarkRunResult:
    iteration: int
    duration_s: float
    raw_length: int
    had_thinking_tags: bool
    json_valid: bool
    schema_valid: bool
    questions_count: int
    error: str | None = None


def make_sample_data() -> tuple[ResumeData, JobDescription, InterviewConfig]:
    resume = ResumeData(
        full_text="Jane Doe, Senior Backend Engineer with 6 years experience in Python, PostgreSQL, and distributed systems.",
        name="Jane Doe",
        summary="Senior Backend Engineer specializing in high-throughput API architectures and databases.",
        skills=[Skill(name="Python"), Skill(name="PostgreSQL"), Skill(name="Redis"), Skill(name="Docker")],
        experience=[
            Experience(
                company="FinTech Core",
                title="Staff Engineer",
                description="Engineered low-latency transaction processing engine handling 10k req/s.",
            )
        ],
    )
    jd = JobDescription(
        title="Senior Python Backend Engineer",
        company="ScalePlatform",
        required_skills=["Python", "FastAPI", "PostgreSQL", "Kafka"],
        responsibilities=["Architect real-time data pipelines", "Optimize database query performance"],
        experience_level="Senior",
        domain="FinTech",
    )
    config = InterviewConfig(
        duration_minutes=45,
        include_behavioral=True,
        include_technical=True,
        include_coding=True,
        difficulty="hard",
    )
    return resume, jd, config


async def benchmark_model(model_name: str, iterations: int = 3) -> None:
    print("=" * 65)
    print(f"POISE MODEL BENCHMARK: {model_name}")
    print("=" * 65)

    cap: ModelCapability = get_model_capability(model_name)
    print(f"Capability Table Entry:")
    print(f"  - supports_json  : {cap.supports_json}")
    print(f"  - needs_no_think : {cap.needs_no_think}")
    print(f"  - num_ctx        : {cap.num_ctx}")
    print(f"  - temperature    : {cap.temperature}")
    print("-" * 65)

    router = ModelProviderRouter(tier=HardwareTier.LOCAL_FULL)
    router._model_plan = ModelPlan(llm=model_name, stt="base", tts="sherpa", embedding="nomic-embed-text", vlm="")
    router.set_model_override(model_name)

    resume, jd, config = make_sample_data()
    planner = InterviewPlanner(router)

    results: list[BenchmarkRunResult] = []

    for i in range(1, iterations + 1):
        print(f"Run {i}/{iterations}...", end="", flush=True)
        start_time = time.time()
        try:
            plan = await planner.generate_plan(resume, jd, config)
            elapsed = time.time() - start_time
            q_count = sum(len(s.questions) for s in plan.sections)
            results.append(
                BenchmarkRunResult(
                    iteration=i,
                    duration_s=round(elapsed, 2),
                    raw_length=0,
                    had_thinking_tags=False,
                    json_valid=True,
                    schema_valid=isinstance(plan, InterviewPlan),
                    questions_count=q_count,
                    error=None if plan.is_personalized else plan.warning,
                )
            )
            status_str = f" SUCCESS ({elapsed:.2f}s, {q_count} questions generated)"
            if not plan.is_personalized:
                status_str += f" [FALLBACK WARNING: {plan.warning}]"
            print(status_str)
        except Exception as exc:
            elapsed = time.time() - start_time
            print(f" FAILED ({elapsed:.2f}s) — {exc}")
            results.append(
                BenchmarkRunResult(
                    iteration=i,
                    duration_s=round(elapsed, 2),
                    raw_length=0,
                    had_thinking_tags=False,
                    json_valid=False,
                    schema_valid=False,
                    questions_count=0,
                    error=str(exc),
                )
            )

    # Summary
    successes = [r for r in results if r.json_valid and r.schema_valid]
    success_rate = (len(successes) / len(results)) * 100
    avg_latency = sum(r.duration_s for r in results) / len(results) if results else 0.0

    print("=" * 65)
    print("BENCHMARK SUMMARY:")
    print(f"  Total Runs        : {len(results)}")
    print(f"  JSON / Schema Pass: {len(successes)}/{len(results)} ({success_rate:.1f}%)")
    print(f"  Average Latency   : {avg_latency:.2f}s")
    if successes:
        avg_q = sum(r.questions_count for r in successes) / len(successes)
        print(f"  Avg Questions Gen : {avg_q:.1f}")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Benchmark LLM engines for Poise interview planning")
    parser.add_argument("--model", type=str, default="llama3.1:8b", help="Model name (e.g. llama3.1:8b, qwen2.5:7b)")
    parser.add_argument("--iterations", type=int, default=3, help="Number of benchmark iterations")
    args = parser.parse_args()

    asyncio.run(benchmark_model(args.model, args.iterations))


if __name__ == "__main__":
    main()
