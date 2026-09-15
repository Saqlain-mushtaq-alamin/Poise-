/**
 * CodingRound — Phase 6.
 *
 * Mount point: frontend/src/pages/CodingRound.tsx (or
 * frontend/src/components/coding/CodingRound.tsx if your app treats
 * it as an embedded component rather than a routed page — Phase 4's
 * conductor renders this when `InterviewSection.type === "coding"`).
 *
 * Split-view layout: problem (left) + editor/output (right), matching
 * the ASCII mock in 06-coding-sandbox.md §6.6.
 *
 * Emits `coding-round-complete` (CustomEvent) with the CodeEvaluation
 * payload when the round finishes, per the Phase 4 handoff contract:
 * "The coding round emits `coding-round-complete` with the CodeEvaluation."
 */
import { useEffect, useState } from 'react';
import { CodeEditor } from '../components/coding/CodeEditor';
import { OutputPanel } from '../components/coding/OutputPanel';
import { ProblemPanel } from '../components/coding/ProblemPanel';
import { ScreenCaptureButton } from '../components/coding/ScreenCapture';
import { CodingAPI } from '../lib/codingApi';
import '../components/coding/coding.css';
import type {
  CodeEvaluation,
  ExecutionResult,
  Language,
} from '../../../contracts/types/coding';

export interface CodingRoundProps {
  sessionId: string;
  codingApi: CodingAPI;
  difficulty?: string;
  topics?: string[];
  questionPrompt?: string;
  personaId?: string;
  onComplete?: (evaluation: CodeEvaluation | null, submittedCode?: string) => void;
  onInterimReview?: (interviewerMessage: string, improvements: string[]) => void;
}

const CODING_ROUND_COMPLETE_EVENT = 'coding-round-complete';

function getStarterCode(lang: Language, prompt: string): string {
  const p = prompt.toLowerCase();
  if (lang === 'python') {
    if (p.includes('django')) {
      return `# Django REST Framework / Django View Implementation
from rest_framework import serializers, viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import models
from django.contrib.auth.models import User

# 1. Models
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

# 2. Serializers
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

# 3. Views / API Endpoints
class UserDataAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
`;
    }
    if (p.includes('fastapi')) {
      return `from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List

app = FastAPI()

# Implement your models and endpoints below:
`;
    }
    return `# Write your solution below:
def solution():
    pass
`;
  }
  if (lang === 'javascript' || lang === 'typescript') {
    if (p.includes('express') || p.includes('api')) {
      return `// Express / Node.js API Implementation
import express from 'express';
const app = express();
app.use(express.json());

// 1. Authentication Middleware
const authenticate = (req, res, next) => {
  const authHeader = req.headers.authorization;
  if (!authHeader) return res.status(401).json({ error: 'Unauthorized' });
  next();
};

// 2. Endpoints
app.get('/api/users', authenticate, async (req, res) => {
  // Query database and return users
  res.json({ message: 'User data' });
});
`;
    }
    return `function solution() {
  // Write your code here
}
`;
  }
  return `// Write your code here\n`;
}

function detectInitialLanguage(prompt?: string): Language {
  if (!prompt) return 'python';
  const p = prompt.toLowerCase();
  if (p.includes('django') || p.includes('python') || p.includes('flask') || p.includes('fastapi')) return 'python';
  if (p.includes('typescript') || p.includes('angular') || p.includes('next.js')) return 'typescript';
  if (p.includes('javascript') || p.includes('react') || p.includes('node') || p.includes('express')) return 'javascript';
  if (p.includes('sql') || p.includes('postgres') || p.includes('mysql')) return 'python'; // python runner supports sql/scripts
  if (p.includes('java') && !p.includes('javascript')) return 'java';
  if (p.includes('c++') || p.includes('cpp')) return 'cpp';
  if (p.includes('go') || p.includes('golang')) return 'go';
  return 'python';
}

function createImmediateProblem(prompt: string, difficulty: string, topics: string[]): any {
  return {
    id: `interview-${Date.now()}`,
    title: 'Live Technical Challenge',
    description: prompt,
    difficulty: difficulty || 'medium',
    topics: topics.length > 0 ? topics : ['Implementation', 'System Design', 'Backend API'],
    constraints: [
      'Write clean, modular, and maintainable code.',
      'Ensure authentication and authorization requirements are addressed.',
      'Handle potential edge cases and error conditions gracefully.',
    ],
    hints: [
      'Structure models and schema definitions clearly first.',
      'Add permissions/middleware to verify authenticated user requests.',
    ],
    examples: [],
    test_cases: [],
    starter_code: {
      python: getStarterCode('python', prompt),
      javascript: getStarterCode('javascript', prompt),
      typescript: getStarterCode('typescript', prompt),
      java: getStarterCode('java', prompt),
      cpp: getStarterCode('cpp', prompt),
      go: getStarterCode('go', prompt),
      rust: getStarterCode('rust', prompt),
    },
  };
}

export function CodingRound({
  sessionId,
  codingApi,
  difficulty = 'medium',
  topics = [],
  questionPrompt,
  personaId = 'professional',
  onComplete,
  onInterimReview,
}: CodingRoundProps) {
  const [roundId, setRoundId] = useState<string | null>(() =>
    questionPrompt ? `prompt-${Date.now()}` : null
  );
  const [problem, setProblem] = useState<any>(() =>
    questionPrompt ? createImmediateProblem(questionPrompt, difficulty, topics) : null
  );
  const [language, setLanguage] = useState<Language>(() => detectInitialLanguage(questionPrompt));
  const [executionResult, setExecutionResult] = useState<ExecutionResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [isReviewing, setIsReviewing] = useState(false);
  const [reviewNote, setReviewNote] = useState<{ message: string; improvements: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastCode, setLastCode] = useState('');

  // When questionPrompt updates from interviewer, update problem immediately without reload
  useEffect(() => {
    if (questionPrompt) {
      setProblem(createImmediateProblem(questionPrompt, difficulty, topics));
      setLanguage(detectInitialLanguage(questionPrompt));
      setRoundId(`prompt-${Date.now()}`);
      setReviewNote(null);
    }
  }, [questionPrompt, difficulty, topics]);

  // Fallback to generator ONLY if no questionPrompt is supplied
  useEffect(() => {
    if (questionPrompt) return; // already initialized instantly
    let cancelled = false;
    (async () => {
      try {
        const res = await codingApi.startCodingRound(sessionId, { difficulty, topics });
        if (cancelled) return;
        setRoundId(res.round_id);
        setProblem(res.problem);
      } catch {
        try {
          const fallbackProblem = await codingApi.generateProblem({ difficulty, topics });
          if (cancelled) return;
          setRoundId(`local-${Date.now()}`);
          setProblem(fallbackProblem);
        } catch (e2) {
          if (!cancelled) setError('Could not load a coding problem. Please retry.');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId, difficulty, topics, codingApi, questionPrompt]);

  const handleRun = async (code: string) => {
    if (!problem?.id) return;
    setIsRunning(true);
    setError(null);
    setLastCode(code);
    try {
      const result = await codingApi.execute({
        code,
        language,
        problem_id: problem.id,
      });
      setExecutionResult(result);
    } catch (e) {
      setError('Execution failed. Please try again.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleAskReview = async (code: string) => {
    if (!code.trim()) return;
    setIsReviewing(true);
    setError(null);
    setLastCode(code);
    try {
      const res = await codingApi.reviewInterimCode({
        sessionId,
        question: problem?.description || questionPrompt || 'Implement the solution',
        code,
        language,
        personaId,
      });
      setReviewNote({
        message: res.interviewer_message,
        improvements: res.suggested_improvements || [],
      });
      if (onInterimReview) {
        onInterimReview(res.interviewer_message, res.suggested_improvements || []);
      }
    } catch (e) {
      setError('Could not get mid-code review. Continuing...');
    } finally {
      setIsReviewing(false);
    }
  };

  const handleSubmit = async (code: string) => {
    if (!problem?.id) return;
    setIsSubmitting(true);
    setError(null);
    setLastCode(code);
    try {
      // If prompt-based question, we can evaluate or directly complete
      if (roundId?.startsWith('prompt-') || roundId?.startsWith('local-')) {
        onComplete?.(null, code);
        window.dispatchEvent(
          new CustomEvent(CODING_ROUND_COMPLETE_EVENT, { detail: { code } })
        );
        return;
      }
      const execution = await codingApi.execute({ code, language, problem_id: problem.id });
      setExecutionResult(execution);
      await codingApi.evaluate(code, language, problem.id, execution);
      await finalizeRound(code);
    } catch (e) {
      // Gracefully submit code to interview even if evaluation fails
      onComplete?.(null, code);
    } finally {
      setIsSubmitting(false);
    }
  };

  const finalizeRound = async (code?: string) => {
    if (!roundId) return;
    setIsFinalizing(true);
    try {
      if (roundId.startsWith('local-') || roundId.startsWith('prompt-')) {
        onComplete?.(null, code ?? lastCode);
        window.dispatchEvent(new CustomEvent(CODING_ROUND_COMPLETE_EVENT, { detail: null }));
        return;
      }
      const result = await codingApi.completeCodingRound(sessionId, roundId);
      onComplete?.(result.final_evaluation, code ?? lastCode);
      window.dispatchEvent(
        new CustomEvent(CODING_ROUND_COMPLETE_EVENT, { detail: result })
      );
    } catch {
      onComplete?.(null, code ?? lastCode);
    } finally {
      setIsFinalizing(false);
    }
  };

  const handleScreenshotCapture = async (blob: Blob) => {
    try {
      await codingApi.evaluateScreenshot(blob, `Coding round: ${problem?.title ?? ''}`, sessionId);
    } catch {
      setError('Screenshot analysis failed, continuing without it.');
    }
  };

  if (error && !problem) {
    return <div className="poise-coding-round__error">{error}</div>;
  }

  if (!problem) {
    return (
      <div className="poise-coding-round__loading">
        <span className="poise-spinner" style={{ width: 28, height: 28, borderWidth: 3 }} />
        Preparing live coding workspace…
      </div>
    );
  }

  return (
    <div className="poise-coding-round">
      <div className="poise-coding-round__left">
        <ProblemPanel problem={problem} />
        {reviewNote && (
          <div className="poise-coding-round__interim-feedback">
            <div className="poise-coding-round__interim-header">
              <span>🤖 Interviewer Observation</span>
            </div>
            <p className="poise-coding-round__interim-msg">{reviewNote.message}</p>
            {reviewNote.improvements?.length > 0 && (
              <ul className="poise-coding-round__interim-list">
                {reviewNote.improvements.map((imp, idx) => (
                  <li key={idx}>{imp}</li>
                ))}
              </ul>
            )}
          </div>
        )}
        <ScreenCaptureButton onCapture={handleScreenshotCapture} disabled={isFinalizing} />
      </div>

      <div className="poise-coding-round__right">
        <div className="poise-coding-round__editor">
          <CodeEditor
            language={language}
            onLanguageChange={setLanguage}
            starterCode={problem.starter_code}
            testCases={problem.test_cases}
            onRun={handleRun}
            onAskReview={handleAskReview}
            isReviewing={isReviewing}
            onSubmit={handleSubmit}
            isRunning={isRunning}
            isSubmitting={isSubmitting || isFinalizing}
          />
        </div>
        <div className="poise-coding-round__output">
          <OutputPanel result={executionResult} isLoading={isRunning} />
        </div>
      </div>

      {error && <div className="poise-coding-round__toast">{error}</div>}
    </div>
  );
}
