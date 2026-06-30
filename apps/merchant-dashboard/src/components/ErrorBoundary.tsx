import { Component, type ReactNode } from "react";
import { AlertOctagon, RefreshCcw } from "lucide-react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * ErrorBoundary — wraps the entire <Routes/> tree so an unexpected runtime
 * error in any page renders a friendly recovery card instead of a blank
 * screen. Reload button calls window.location.reload() to drop any tainted
 * React state.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string | null }) {
    // Log to the console so the developer has a stack trace; the in-app
    // surface stays calm.
    // eslint-disable-next-line no-console
    console.error("[merchant-dashboard] uncaught error in render tree", error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="mer-error-boundary" role="alert">
        <div className="mer-error-boundary__icon" aria-hidden="true">
          <AlertOctagon size={28} />
        </div>
        <h2>Something went wrong rendering this page.</h2>
        <p>
          The dashboard hit an unexpected error. Your data is safe — reloading should bring you
          back to a working view. If the problem persists, sign out and back in.
        </p>
        <pre className="mer-error-boundary__detail" aria-label="Error detail">
          {this.state.error.message}
        </pre>
        <div className="mer-error-boundary__actions">
          <button
            type="button"
            className="sp-button sp-button--primary"
            onClick={() => window.location.reload()}
          >
            <RefreshCcw size={15} aria-hidden="true" />
            <span>Reload dashboard</span>
          </button>
          <button
            type="button"
            className="sp-button sp-button--ghost"
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </button>
        </div>
      </div>
    );
  }
}
