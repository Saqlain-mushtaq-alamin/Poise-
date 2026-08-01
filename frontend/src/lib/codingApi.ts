/**
 * Coding sandbox API client — Phase 6.
 *
 * Mount point: frontend/src/lib/codingApi.ts
 *
 * Follows the same pattern as Phase 1's `frontend/src/lib/api.ts`
 * (PoiseAPI class wrapping the FastAPI sidecar over localhost HTTP).
 * This file adds a `CodingAPI` companion so each phase's client stays
 * small and easy to review; wire it up the same way the app already
 * wires up other phase-specific API extensions — either as methods
 * bolted onto the shared `PoiseAPI` instance, or as a sibling class
 * constructed with the same base URL. Example (adjust to match your
 * actual api.ts export shape):
 *
 *   import { PoiseAPI } from './api';
 *   import { CodingAPI } from './codingApi';
 *
 *   const api = new PoiseAPI(port);
 *   const coding = new CodingAPI(api);
 */
import type {
  CodeEvaluation,
  CodeSubmissionRequest,
  CodingProblem,
  CodingRoundCompleteResponse,
  CodingRoundStartRequest,
  CodingRoundStartResponse,
  ExecutionResult,
  ProblemGenerateRequest,
  ScreenEvaluation,
} from '../../../contracts/types/coding';

interface RequestClient {
  request<T>(method: string, path: string, body?: unknown): Promise<T>;
  baseUrl: string;
}

export class CodingAPI {
  constructor(private client: RequestClient) {}

  async generateProblem(req: ProblemGenerateRequest): Promise<CodingProblem> {
    return this.client.request<CodingProblem>('POST', '/coding/problems/generate', req);
  }

  async execute(submission: CodeSubmissionRequest): Promise<ExecutionResult> {
    return this.client.request<ExecutionResult>('POST', '/coding/execute', submission);
  }

  async evaluate(
    code: string,
    language: string,
    problemId: string,
    executionResult?: ExecutionResult
  ): Promise<CodeEvaluation> {
    return this.client.request<CodeEvaluation>('POST', '/coding/evaluate', {
      code,
      language,
      problem_id: problemId,
      execution_result: executionResult,
    });
  }

  async evaluateScreenshot(imageBlob: Blob, context: string, sessionId?: string): Promise<ScreenEvaluation> {
    const form = new FormData();
    form.append('image', imageBlob, 'screenshot.png');
    form.append('context', context);
    if (sessionId) form.append('session_id', sessionId);

    const resp = await fetch(`${this.client.baseUrl}/coding/screen/evaluate`, {
      method: 'POST',
      body: form,
    });
    if (!resp.ok) {
      throw new Error(`Screenshot evaluation failed: ${resp.status} ${await resp.text()}`);
    }
    return resp.json();
  }

  // Phase 4 handoff — called by the interview conductor when a coding
  // section starts / completes.
  async startCodingRound(
    sessionId: string,
    req: CodingRoundStartRequest
  ): Promise<CodingRoundStartResponse> {
    return this.client.request<CodingRoundStartResponse>(
      'POST',
      `/interview/sessions/${sessionId}/coding-round`,
      req
    );
  }

  async completeCodingRound(
    sessionId: string,
    roundId: string
  ): Promise<CodingRoundCompleteResponse> {
    return this.client.request<CodingRoundCompleteResponse>(
      'POST',
      `/interview/sessions/${sessionId}/coding-round/${roundId}/complete`
    );
  }
}
