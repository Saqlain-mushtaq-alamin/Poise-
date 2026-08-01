// frontend/src/lib/errors.ts
// Phase 9.6 — Error Handling & Crash Reporting
//
// Central place that turns internal error codes/exceptions into the
// user-facing messages defined in the Phase 9 spec. Import ErrorCategory
// anywhere a raw error needs to become something a user can act on.

export enum ErrorCategory {
  SIDECAR_CRASH = "SIDECAR_CRASH",
  MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED",
  GPU_OUT_OF_MEMORY = "GPU_OUT_OF_MEMORY",
  CLOUD_AUTH_FAILED = "CLOUD_AUTH_FAILED",
  CLOUD_RATE_LIMIT = "CLOUD_RATE_LIMIT",
  MIC_PERMISSION = "MIC_PERMISSION",
  CAMERA_PERMISSION = "CAMERA_PERMISSION",
  NETWORK_ERROR = "NETWORK_ERROR",
  UNKNOWN = "UNKNOWN",
}

export const ERROR_MESSAGES: Record<ErrorCategory, string> = {
  [ErrorCategory.SIDECAR_CRASH]: "The backend process stopped unexpectedly.",
  [ErrorCategory.MODEL_LOAD_FAILED]: "Failed to load the AI model.",
  [ErrorCategory.GPU_OUT_OF_MEMORY]: "Not enough GPU memory — try closing other apps.",
  [ErrorCategory.CLOUD_AUTH_FAILED]: "Your API key was rejected — check Settings.",
  [ErrorCategory.CLOUD_RATE_LIMIT]: "API rate limit reached — wait and try again.",
  [ErrorCategory.MIC_PERMISSION]: "Microphone access denied — check system settings.",
  [ErrorCategory.CAMERA_PERMISSION]: "Camera access denied — check system settings.",
  [ErrorCategory.NETWORK_ERROR]: "Network request failed — check your connection.",
  [ErrorCategory.UNKNOWN]: "Something went wrong. Please try again.",
};

/** Whether the app should offer a retry action for this category. */
export const RETRYABLE: Record<ErrorCategory, boolean> = {
  [ErrorCategory.SIDECAR_CRASH]: true,
  [ErrorCategory.MODEL_LOAD_FAILED]: true,
  [ErrorCategory.GPU_OUT_OF_MEMORY]: false,
  [ErrorCategory.CLOUD_AUTH_FAILED]: false,
  [ErrorCategory.CLOUD_RATE_LIMIT]: true,
  [ErrorCategory.MIC_PERMISSION]: false,
  [ErrorCategory.CAMERA_PERMISSION]: false,
  [ErrorCategory.NETWORK_ERROR]: true,
  [ErrorCategory.UNKNOWN]: true,
};

export class PoiseError extends Error {
  category: ErrorCategory;
  cause?: unknown;

  constructor(category: ErrorCategory, cause?: unknown) {
    super(ERROR_MESSAGES[category]);
    this.name = "PoiseError";
    this.category = category;
    this.cause = cause;
  }
}

/**
 * Best-effort classification of an arbitrary caught error into a
 * PoiseError. Backend responses should ideally already send a `category`
 * field (see backend/app/errors.py convention) — this is the fallback for
 * anything raw (fetch failures, browser permission errors, etc).
 */
export function classifyError(err: unknown): PoiseError {
  if (err instanceof PoiseError) return err;

  if (err && typeof err === "object" && "category" in err) {
    const cat = (err as { category?: string }).category;
    if (cat && cat in ErrorCategory) {
      return new PoiseError(ErrorCategory[cat as keyof typeof ErrorCategory], err);
    }
  }

  const message = err instanceof Error ? err.message.toLowerCase() : String(err).toLowerCase();

  if (message.includes("notallowederror") || message.includes("microphone")) {
    return new PoiseError(ErrorCategory.MIC_PERMISSION, err);
  }
  if (message.includes("camera")) {
    return new PoiseError(ErrorCategory.CAMERA_PERMISSION, err);
  }
  if (message.includes("out of memory") || message.includes("cuda oom") || message.includes("vram")) {
    return new PoiseError(ErrorCategory.GPU_OUT_OF_MEMORY, err);
  }
  if (message.includes("401") || message.includes("unauthorized") || message.includes("invalid api key")) {
    return new PoiseError(ErrorCategory.CLOUD_AUTH_FAILED, err);
  }
  if (message.includes("429") || message.includes("rate limit")) {
    return new PoiseError(ErrorCategory.CLOUD_RATE_LIMIT, err);
  }
  if (message.includes("failed to fetch") || message.includes("network")) {
    return new PoiseError(ErrorCategory.NETWORK_ERROR, err);
  }
  if (message.includes("sidecar")) {
    return new PoiseError(ErrorCategory.SIDECAR_CRASH, err);
  }
  if (message.includes("model") && message.includes("load")) {
    return new PoiseError(ErrorCategory.MODEL_LOAD_FAILED, err);
  }

  return new PoiseError(ErrorCategory.UNKNOWN, err);
}
