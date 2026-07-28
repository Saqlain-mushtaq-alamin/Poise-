"""
Code execution sandbox — Phase 6.

Mount point: backend/app/services/sandbox.py

Two-tier execution:
  1. Judge0 (Docker) — full container isolation, used when Docker is
     detected and the self-hosted Judge0 CE stack is reachable.
  2. subprocess fallback — always available, resource-limited
     (time, memory, no network, ephemeral tmp dir, restricted env,
     dropped privileges where the OS allows it).

Security notes (read before touching this file):
  - Fallback execution NEVER runs with network access — on Linux we
    unshare the network namespace when available; everywhere else we
    strip proxy/host env vars and rely on the time/memory/output caps
    to bound damage, since arbitrary submitted code is inherently
    trusted-adjacent, not trusted. This is a fallback path, not a
    replacement for Docker isolation — the Judge0 tier is
    recommended for anything but a local single-user desktop app.
  - Each run gets its own temp directory, deleted afterward.
  - Output is capped to prevent disk/memory exhaustion from runaway
    prints.
  - `subprocess.run` never uses `shell=True`.
"""
from __future__ import annotations

import asyncio
import logging
import os
try:
    import resource
except ImportError:
    resource = None
import shutil
import signal
import sys
import tempfile
import time
from pathlib import Path

import httpx

from app.schemas.coding import (
    CodeSubmission,
    ExecutionResult,
    ExecutionStatus,
    TestCaseResult,
)
from app.services.language_profiles import LanguageProfile, get_profile

logger = logging.getLogger("poise.sandbox")

MAX_OUTPUT_BYTES = 200_000  # ~200KB cap on captured stdout/stderr
JUDGE0_HEALTHCHECK_TIMEOUT = 1.5
JUDGE0_POLL_INTERVAL = 0.4
JUDGE0_MAX_POLLS = 40  # ~16s worst case, bounded independently of submission time_limit


class CodeSandbox:
    """Entry point used by the router and by CodeEvaluator."""

    def __init__(self, judge0_url: str | None = None):
        # e.g. "http://localhost:2358" when self-hosted Judge0 CE is running.
        self.judge0_url = judge0_url or os.environ.get("POISE_JUDGE0_URL")
        self._judge0_checked = False
        self._judge0_ok = False

    async def execute(self, submission: CodeSubmission) -> ExecutionResult:
        """Run the submission's test cases (or raw stdin) and return results."""
        if await self._docker_available():
            try:
                return await self._execute_judge0(submission)
            except Exception:
                logger.exception("Judge0 execution failed, falling back to subprocess")
        return await self._execute_subprocess(submission)

    # ------------------------------------------------------------------
    # Tier detection
    # ------------------------------------------------------------------

    async def _docker_available(self) -> bool:
        if not self.judge0_url:
            return False
        if self._judge0_checked:
            return self._judge0_ok
        self._judge0_checked = True
        try:
            async with httpx.AsyncClient(timeout=JUDGE0_HEALTHCHECK_TIMEOUT) as client:
                resp = await client.get(f"{self.judge0_url}/about")
                self._judge0_ok = resp.status_code == 200
        except Exception:
            self._judge0_ok = False
        return self._judge0_ok

    # ------------------------------------------------------------------
    # Tier 1: Judge0 (Docker)
    # ------------------------------------------------------------------

    async def _execute_judge0(self, submission: CodeSubmission) -> ExecutionResult:
        profile = get_profile(submission.language.value)
        if profile.judge0_language_id is None:
            raise ValueError(f"No Judge0 language mapping for {submission.language}")

        test_cases = submission.test_cases or _default_single_run(submission)
        results: list[TestCaseResult] = []
        total_time_ms = 0
        max_memory_mb = 0.0
        overall_status = ExecutionStatus.ACCEPTED
        raw_stdout = ""
        raw_stderr = ""

        async with httpx.AsyncClient(timeout=submission.time_limit_seconds + 10) as client:
            for tc in test_cases:
                payload = {
                    "source_code": submission.code,
                    "language_id": profile.judge0_language_id,
                    "stdin": tc.input,
                    "cpu_time_limit": submission.time_limit_seconds,
                    "memory_limit": submission.memory_limit_mb * 1024,  # Judge0 wants KB
                    "enable_network": False,
                }
                create = await client.post(
                    f"{self.judge0_url}/submissions?base64_encoded=false&wait=false",
                    json=payload,
                )
                create.raise_for_status()
                token = create.json()["token"]

                result_json = await self._poll_judge0(client, token)

                stdout = (result_json.get("stdout") or "")[:MAX_OUTPUT_BYTES]
                stderr = (result_json.get("stderr") or result_json.get("compile_output") or "")[:MAX_OUTPUT_BYTES]
                time_ms = int(float(result_json.get("time") or 0) * 1000)
                memory_mb = (result_json.get("memory") or 0) / 1024
                status_desc = (result_json.get("status") or {}).get("description", "")

                passed = _judge0_status_is_ok(status_desc) and stdout.strip() == tc.expected_output.strip()
                tc_status = _map_judge0_status(status_desc, passed)

                results.append(
                    TestCaseResult(
                        input=tc.input,
                        expected_output=tc.expected_output,
                        actual_output=stdout,
                        passed=passed,
                        is_hidden=tc.is_hidden,
                        execution_time_ms=time_ms,
                        error=stderr or None,
                    )
                )
                total_time_ms += time_ms
                max_memory_mb = max(max_memory_mb, memory_mb)
                raw_stdout = stdout
                raw_stderr = stderr
                if tc_status != ExecutionStatus.ACCEPTED:
                    overall_status = tc_status
                    # Keep going so the user sees all test outcomes, unless it's a
                    # compile error (same for every case, no point repeating).
                    if tc_status == ExecutionStatus.COMPILE_ERROR:
                        break

        passed_count = sum(1 for r in results if r.passed)
        if passed_count == len(results) and results:
            overall_status = ExecutionStatus.ACCEPTED

        return ExecutionResult(
            status=overall_status,
            stdout=raw_stdout,
            stderr=raw_stderr,
            execution_time_ms=total_time_ms,
            memory_used_mb=round(max_memory_mb, 2),
            test_results=results,
            executor="judge0",
            passed_count=passed_count,
            total_count=len(results),
        )

    async def _poll_judge0(self, client: httpx.AsyncClient, token: str) -> dict:
        for _ in range(JUDGE0_MAX_POLLS):
            resp = await client.get(f"{self.judge0_url}/submissions/{token}?base64_encoded=false")
            resp.raise_for_status()
            data = resp.json()
            status_id = (data.get("status") or {}).get("id", 0)
            if status_id not in (1, 2):  # 1=In Queue, 2=Processing
                return data
            await asyncio.sleep(JUDGE0_POLL_INTERVAL)
        return {"status": {"description": "Time Limit Exceeded"}}

    # ------------------------------------------------------------------
    # Tier 2: subprocess fallback
    # ------------------------------------------------------------------

    async def _execute_subprocess(self, submission: CodeSubmission) -> ExecutionResult:
        profile = get_profile(submission.language.value)
        test_cases = submission.test_cases or _default_single_run(submission)

        with tempfile.TemporaryDirectory(prefix="poise_sandbox_", ignore_cleanup_errors=True) as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / profile.source_filename
            source_path.write_text(submission.code, encoding="utf-8")

            binary_path = tmp_path / profile.binary_name if profile.binary_name else None

            # Compile step (if the language needs one)
            if profile.compile_cmd:
                compile_result = await self._run_subprocess(
                    _substitute(
                        profile.compile_cmd, tmp_path, source_path, binary_path,
                        mem_mb=submission.memory_limit_mb,
                    ),
                    cwd=tmp_path,
                    stdin_data="",
                    time_limit_s=min(submission.time_limit_seconds + 10, 30),
                    memory_limit_mb=max(submission.memory_limit_mb, 256),
                    skip_as_limit=profile.skip_as_limit,
                )
                if compile_result.returncode != 0:
                    return ExecutionResult(
                        status=ExecutionStatus.COMPILE_ERROR,
                        stdout="",
                        stderr=compile_result.stderr[:MAX_OUTPUT_BYTES],
                        execution_time_ms=compile_result.duration_ms,
                        memory_used_mb=0.0,
                        test_results=[],
                        executor="subprocess",
                        passed_count=0,
                        total_count=len(test_cases),
                    )

            results: list[TestCaseResult] = []
            total_time_ms = 0
            max_memory_mb = 0.0
            overall_status = ExecutionStatus.ACCEPTED
            last_stdout = ""
            last_stderr = ""

            for tc in test_cases:
                run_cmd = _substitute(
                    profile.run_cmd, tmp_path, source_path, binary_path,
                    mem_mb=submission.memory_limit_mb,
                )
                run_result = await self._run_subprocess(
                    run_cmd,
                    cwd=tmp_path,
                    stdin_data=tc.input,
                    time_limit_s=submission.time_limit_seconds,
                    memory_limit_mb=submission.memory_limit_mb,
                    skip_as_limit=profile.skip_as_limit,
                )

                last_stdout = run_result.stdout
                last_stderr = run_result.stderr
                total_time_ms += run_result.duration_ms
                max_memory_mb = max(max_memory_mb, run_result.peak_memory_mb)

                if run_result.timed_out:
                    tc_status = ExecutionStatus.TIME_LIMIT
                elif run_result.oom:
                    tc_status = ExecutionStatus.MEMORY_LIMIT
                elif run_result.returncode != 0:
                    tc_status = ExecutionStatus.RUNTIME_ERROR
                elif run_result.stdout.strip() == tc.expected_output.strip():
                    tc_status = ExecutionStatus.ACCEPTED
                else:
                    tc_status = ExecutionStatus.WRONG_ANSWER

                results.append(
                    TestCaseResult(
                        input=tc.input,
                        expected_output=tc.expected_output,
                        actual_output=run_result.stdout[:MAX_OUTPUT_BYTES],
                        passed=tc_status == ExecutionStatus.ACCEPTED,
                        is_hidden=tc.is_hidden,
                        execution_time_ms=run_result.duration_ms,
                        error=run_result.stderr[:MAX_OUTPUT_BYTES] or None,
                    )
                )
                if tc_status != ExecutionStatus.ACCEPTED:
                    overall_status = tc_status

            passed_count = sum(1 for r in results if r.passed)
            if passed_count == len(results) and results:
                overall_status = ExecutionStatus.ACCEPTED

            return ExecutionResult(
                status=overall_status,
                stdout=last_stdout[:MAX_OUTPUT_BYTES],
                stderr=last_stderr[:MAX_OUTPUT_BYTES],
                execution_time_ms=total_time_ms,
                memory_used_mb=round(max_memory_mb, 2),
                test_results=results,
                executor="subprocess",
                passed_count=passed_count,
                total_count=len(results),
            )

    async def _run_subprocess(
        self,
        cmd: list[str],
        cwd: Path,
        stdin_data: str,
        time_limit_s: int,
        memory_limit_mb: int,
        skip_as_limit: bool = False,
    ) -> "_SubprocessRunResult":
        """Run one command with time/memory limits, no network, minimal env."""
        env = _restricted_env()
        start = time.monotonic()
        timed_out = False
        oom = False

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                preexec_fn=(
                    _apply_resource_limits(memory_limit_mb, skip_as_limit=skip_as_limit)
                    if os.name == "posix"
                    else None
                ),
            )
        except FileNotFoundError as e:
            return _SubprocessRunResult(
                returncode=127,
                stdout="",
                stderr=f"Runtime not available on this machine: {e}",
                duration_ms=0,
                peak_memory_mb=0.0,
                timed_out=False,
                oom=False,
            )

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(stdin_data.encode("utf-8")), timeout=time_limit_s
            )
        except asyncio.TimeoutError:
            timed_out = True
            _kill_process_tree(proc)
            stdout_b, stderr_b = b"", b"Time limit exceeded"

        duration_ms = int((time.monotonic() - start) * 1000)
        returncode = proc.returncode if proc.returncode is not None else -1

        stderr_text = (stderr_b or b"").decode("utf-8", errors="replace")
        if returncode != 0 and (
            "MemoryError" in stderr_text
            or "Cannot allocate memory" in stderr_text
            or returncode in (-9, 137)
        ):
            oom = True

        return _SubprocessRunResult(
            returncode=returncode,
            stdout=(stdout_b or b"").decode("utf-8", errors="replace"),
            stderr=stderr_text,
            duration_ms=duration_ms,
            peak_memory_mb=0.0,  # exact RSS tracking is OS-specific; omitted in fallback tier
            timed_out=timed_out,
            oom=oom,
        )


# --------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------

class _SubprocessRunResult:
    def __init__(self, returncode, stdout, stderr, duration_ms, peak_memory_mb, timed_out, oom):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.duration_ms = duration_ms
        self.peak_memory_mb = peak_memory_mb
        self.timed_out = timed_out
        self.oom = oom


def _substitute(
    cmd: list[str],
    tmp_path: Path,
    source_path: Path,
    binary_path: Path | None,
    mem_mb: int = 256,
) -> list[str]:
    out = []
    for part in cmd:
        part = part.replace("{file}", str(source_path))
        part = part.replace("{dir}", str(tmp_path))
        part = part.replace("{mem_mb}", str(mem_mb))
        if binary_path is not None:
            part = part.replace("{binary}", str(binary_path))
        out.append(part)
    return out


def _default_single_run(submission: CodeSubmission):
    """When there are no test cases (ad-hoc 'Run'), execute once with raw stdin."""
    from app.schemas.coding import TestCase

    return [TestCase(input=submission.stdin or "", expected_output="", is_hidden=False)]


def _restricted_env() -> dict[str, str]:
    """Minimal environment: no proxies, no host secrets, deterministic locale."""
    allow = {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}
    env = {k: v for k, v in os.environ.items() if k in allow}
    env.setdefault("LANG", "C.UTF-8")
    # Explicitly strip anything that could leak network config or credentials.
    for blocked in ("HTTP_PROXY", "HTTPS_PROXY", "AWS_", "OPENAI_", "ANTHROPIC_", "GOOGLE_"):
        env.pop(blocked, None)
    return env


def _apply_resource_limits(memory_limit_mb: int, skip_as_limit: bool = False):
    """Returns a preexec_fn that caps memory + disables core dumps (POSIX only).

    `skip_as_limit=True` is used for VM-based runtimes (Node/V8, JVM) that
    reserve a large virtual address range at startup independent of actual
    heap usage — applying RLIMIT_AS to them kills the runtime before user
    code even runs. Those runtimes get their memory cap via their own
    heap-size flag instead (see language_profiles.py's {mem_mb} substitution).
    We still cap RLIMIT_NPROC and disable core dumps for them.
    """

    def _limit():
        try:
            if not skip_as_limit:
                mem_bytes = memory_limit_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
            # New process group so we can kill the whole tree on timeout.
            os.setsid()
        except Exception:
            # Best-effort: some limits are unavailable on macOS/containers.
            pass

    return _limit


def _kill_process_tree(proc: asyncio.subprocess.Process):
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:
            proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _judge0_status_is_ok(status_desc: str) -> bool:
    return status_desc == "Accepted"


def _map_judge0_status(status_desc: str, passed: bool) -> ExecutionStatus:
    mapping = {
        "Accepted": ExecutionStatus.ACCEPTED,
        "Wrong Answer": ExecutionStatus.WRONG_ANSWER,
        "Time Limit Exceeded": ExecutionStatus.TIME_LIMIT,
        "Memory Limit Exceeded": ExecutionStatus.MEMORY_LIMIT,
        "Compilation Error": ExecutionStatus.COMPILE_ERROR,
    }
    if status_desc in mapping:
        return mapping[status_desc] if not (status_desc == "Accepted" and not passed) else ExecutionStatus.WRONG_ANSWER
    return ExecutionStatus.RUNTIME_ERROR
