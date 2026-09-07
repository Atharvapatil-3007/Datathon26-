import { NavLink } from "react-router-dom";
import { PropsWithChildren } from "react";
import clsx from "clsx";

const navClass = (active: boolean) =>
  clsx(
    "px-3 py-1.5 rounded-md text-sm transition-colors",
    active ? "bg-brand-soft text-ink" : "text-ink-muted hover:text-ink hover:bg-bg-hover",
  );

export default function Shell({ children }: PropsWithChildren) {
  return (
    <div className="min-h-full flex flex-col">
      <header className="border-b border-line bg-bg-soft/60 backdrop-blur">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-md bg-brand-soft border border-brand-muted flex items-center justify-center">
              <svg viewBox="0 0 32 32" className="h-5 w-5 text-brand">
                <path
                  d="M6 22 L12 14 L17 18 L26 8"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2.5}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <circle cx="26" cy="8" r="2.2" fill="currentColor" />
              </svg>
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-semibold tracking-tight text-ink">
                Financial Intelligence Platform
              </span>
              <span className="text-[11px] text-ink-faint">
                Upload · Understand · Analyze · Compare · Decide
              </span>
            </div>
          </div>
          <nav className="flex items-center gap-1">
            <NavLink to="/upload" className={({ isActive }) => navClass(isActive)}>
              Upload
            </NavLink>
            <NavLink to="/datasets" className={({ isActive }) => navClass(isActive)}>
              Datasets
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <div className="max-w-7xl mx-auto px-6 py-8">{children}</div>
      </main>
      <footer className="border-t border-line py-4 text-center text-[11px] text-ink-faint">
        Financial Intelligence &amp; Decision-Support Platform · Ingest · Profile · Analyze
      </footer>
    </div>
  );
}
