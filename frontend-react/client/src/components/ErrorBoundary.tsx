import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "./ui/button";

interface Props {
  children?: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] p-6 bg-neutral-950 border border-neutral-800 rounded-lg text-neutral-200">
          <AlertTriangle className="w-12 h-12 text-red-500 mb-4" />
          <h2 className="text-xl font-bold mb-2">Algo deu errado</h2>
          <p className="text-neutral-400 mb-6 text-center max-w-md">
            Ocorreu um erro ao renderizar este componente.
          </p>
          {this.state.error && (
            <pre className="bg-neutral-900 p-4 rounded text-xs font-mono text-red-300 mb-6 max-w-full overflow-auto border border-red-900/30">
              {this.state.error.toString()}
            </pre>
          )}
          <Button
            onClick={() => this.setState({ hasError: false, error: null })}
            variant="outline"
            className="border-neutral-700 hover:bg-neutral-800 hover:text-white"
          >
            Tentar Novamente
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;