/**
 * Shared TypeScript types for Phase 6 — Coding Sandbox.
 *
 * Mount point: contracts/types/coding.d.ts
 * Re-export from contracts/types/index.d.ts alongside the other phases:
 *
 *   export * from './coding';
 *
 * These mirror backend/app/schemas/coding.py 1:1. Keep them in sync
 * manually, or wire up openapi-typescript against the generated
 * OpenAPI spec if the project already does that for other phases.
 */

export type Language =
  | 'python'
  | 'javascript'
  | 'typescript'
  | 'java'
  | 'cpp'
  | 'go'
  | 'rust';

export type ExecutionStatus =
  | 'accepted'
  | 'wrong_answer'
  | 'runtime_error'
  | 'time_limit'
  | 'memory_limit'
  | 'compile_error'
  | 'internal_error';

export type ApproachAssessment = 'brute_force' | 'near_optimal' | 'optimal';

export interface Example {
  input: string;
  output: string;
  explanation?: string | null;
}

export interface TestCase {
  input: string;
  expected_output: string;
  is_hidden: boolean;
}

export interface CodingProblem {
  id?: string;
  title: string;
  description: string; // markdown
  examples: Example[];
  constraints: string[];
  test_cases: TestCase[]; // hidden ones only populated after submit
  hints: string[];
  difficulty: string;
  topics: string[];
  starter_code: Record<string, string>;
}

export interface ProblemGenerateRequest {
  session_id?: string;
  jd_id?: string;
  resume_id?: string;
  difficulty?: string;
  topics?: string[];
  language_hint?: Language;
}

export interface CodeSubmissionRequest {
  code: string;
  language: Language;
  problem_id?: string;
  test_cases?: TestCase[];
  time_limit_seconds?: number;
  memory_limit_mb?: number;
  stdin?: string;
}

export interface TestCaseResult {
  input: string;
  expected_output: string;
  actual_output: string;
  passed: boolean;
  is_hidden: boolean;
  execution_time_ms?: number | null;
  error?: string | null;
}

export interface ExecutionResult {
  status: ExecutionStatus;
  stdout: string;
  stderr: string;
  execution_time_ms: number;
  memory_used_mb: number;
  test_results: TestCaseResult[];
  executor: 'judge0' | 'subprocess';
  passed_count: number;
  total_count: number;
}

export interface CodeEvaluation {
  correctness_score: number;
  style_score: number;
  efficiency_score: number;
  approach_assessment: ApproachAssessment;
  time_complexity: string;
  space_complexity: string;
  strengths: string[];
  improvements: string[];
  alternative_approaches: string[];
  overall_score: number;
}

export interface ScreenEvaluation {
  description: string;
  diagram_quality: number;
  completeness: number;
  feedback: string[];
}

export interface CodingRoundStartRequest {
  difficulty?: string;
  topics?: string[];
  language_hint?: Language;
}

export interface CodingRoundStartResponse {
  round_id: string;
  problem: CodingProblem;
}

export interface CodingRoundCompleteResponse {
  round_id: string;
  session_id: string;
  final_evaluation: CodeEvaluation;
  execution_summary: ExecutionResult;
  screen_evaluations: ScreenEvaluation[];
}
