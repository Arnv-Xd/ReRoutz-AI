import { Component } from "react";

export default class AppErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6 text-slate-900">
        <section className="bg-white border border-slate-200 max-w-md w-full rounded-2xl overflow-hidden shadow-lg p-0">
          <div className="h-1.5 bg-rose-500 w-full"></div>
          <div className="p-6 space-y-4">
            <div>
              <h1 className="text-lg font-bold text-slate-900">Console Execution Interrupted</h1>
              <p className="mt-1 text-xs text-slate-500">An unexpected React runtime exception occurred.</p>
            </div>
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs font-mono text-rose-600 break-words">
              {this.state.error.message || "Unknown client error"}
            </div>
            <button
              type="button"
              className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition shadow-sm"
              onClick={() => window.location.reload()}
            >
              Reload Command Console
            </button>
          </div>
        </section>
      </main>
    );
  }
}