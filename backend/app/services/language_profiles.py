"""
Per-language execution profiles for the subprocess sandbox fallback.

Mount point: backend/app/services/language_profiles.py

Each profile knows how to write a submission to disk, what command
compiles it (if any), and what command runs it. Kept separate from
sandbox.py so adding a language is a one-place change.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field


@dataclass
class LanguageProfile:
    name: str
    source_filename: str
    run_cmd: list[str]                       # run_cmd[i] with {file} / {binary} substitution
    compile_cmd: list[str] | None = None      # None => interpreted, no compile step
    binary_name: str | None = None
    # Docker/Judge0 language id (for the Docker tier). None => not available on Judge0.
    judge0_language_id: int | None = None
    # Extra env vars to strip/limit for this runtime specifically.
    env_overrides: dict[str, str] = field(default_factory=dict)
    # If True, the subprocess tier skips RLIMIT_AS and instead relies on the
    # runtime's own heap-size flag (substituted via {mem_mb} in run_cmd).
    # Needed for VM-based runtimes (Node/V8, JVM) that reserve large virtual
    # address ranges at startup regardless of actual memory usage.
    skip_as_limit: bool = False


LANGUAGE_PROFILES: dict[str, LanguageProfile] = {
    "python": LanguageProfile(
        name="python",
        source_filename="main.py",
        run_cmd=[sys.executable, "-I", "-S", "{file}"],  # -I isolated, -S no site packages
        judge0_language_id=71,
    ),
    "javascript": LanguageProfile(
        name="javascript",
        source_filename="main.js",
        # --max-old-space-size caps V8's heap in MB; RLIMIT_AS is NOT applied
        # for this language (see sandbox.py: skip_as_limit) because V8
        # reserves a large virtual address range at startup independent of
        # actual usage, which RLIMIT_AS would kill immediately.
        run_cmd=["node", "--no-addons", "--max-old-space-size={mem_mb}", "{file}"],
        judge0_language_id=63,
        skip_as_limit=True,
    ),
    "typescript": LanguageProfile(
        name="typescript",
        source_filename="main.ts",
        # ts-node keeps this to a single step; if unavailable, compile-then-run is used.
        run_cmd=["npx", "--yes", "ts-node", "--transpile-only", "{file}"],
        judge0_language_id=74,
        skip_as_limit=True,
    ),
    "java": LanguageProfile(
        name="java",
        source_filename="Main.java",
        compile_cmd=["javac", "{file}"],
        run_cmd=["java", "-cp", "{dir}", "-Xmx{mem_mb}m", "Main"],
        judge0_language_id=62,
        skip_as_limit=True,
    ),
    "cpp": LanguageProfile(
        name="cpp",
        source_filename="main.cpp",
        compile_cmd=["g++", "-O2", "-std=c++17", "-o", "{binary}", "{file}"],
        run_cmd=["{binary}"],
        binary_name="main.out",
        judge0_language_id=54,
    ),
    "go": LanguageProfile(
        name="go",
        source_filename="main.go",
        run_cmd=["go", "run", "{file}"],
        judge0_language_id=60,
    ),
    "rust": LanguageProfile(
        name="rust",
        source_filename="main.rs",
        compile_cmd=["rustc", "-O", "-o", "{binary}", "{file}"],
        run_cmd=["{binary}"],
        binary_name="main.out",
        judge0_language_id=73,
    ),
}


def get_profile(language: str) -> LanguageProfile:
    try:
        return LANGUAGE_PROFILES[language]
    except KeyError as e:
        raise ValueError(f"Unsupported language: {language}") from e
