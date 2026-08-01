// frontend/src/lib/ErrorBoundary.tsx
// Phase 9.6 — wraps the app (or any route) so a crash renders a friendly,
// actionable message instead of a blank screen, and reports to Sentry
// (only if the user opted in — see lib/sentry.ts).
import { Component, type ErrorInfo, type ReactNode } from "react";
import { classifyError, ERROR_MESSAGES, RETRYABLE } from "./errors";
import { captureException } from "./sentry";

interface Props {
  children: ReactNode;
  onReset?: () => void;
}

interface State {
  error: ReturnType<typeof classifyError> | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(err: unknown): State {
    return { error: classifyError(err) };
  }

  componentDidCatch(err: unknown, info: ErrorInfo) {
    const classified = classifyError(err);
    captureException(classified, { componentStack: info.componentStack ?? undefined });
  }

  handleRetry = () => {
    this.setState({ error: null });
    this.props.onReset?.();
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="error-boundary" role="alert">
        <h2>{ERROR_MESSAGES[error.category]}</h2>
        <p className="error-boundary__detail">
          If this keeps happening, check <code>docs/faq.md</code> or restart the app.
        </p>
        {RETRYABLE[error.category] && (
          <button type="button" className="wizard-btn wizard-btn--primary" onClick={this.handleRetry}>
            Try again
          </button>
        )}
      </div>
    );
  }
}
