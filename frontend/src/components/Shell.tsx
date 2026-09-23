import { PropsWithChildren, useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import clsx from "clsx";
import { BRAND } from "@/config/brand";
import { api } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";
import { getLastDatasetId } from "@/lib/assistantContext";

/**
 * Application shell — persistent sidebar, top header, main content area,
 * footer. The layout adapts down to tablet/mobile by collapsing the sidebar
 * behind a toggle.
 */
export default function Shell({ children }: PropsWithChildren) {
  const [open, setOpen] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const location = useLocation();

  useEffect(() => {
    const ctrl = new AbortController();
    api.health(ctrl.signal).then(setHealth).catch(() => setHealth(null));
    return () => ctrl.abort();
  }, []);

  // Close mobile sidebar on navigation.
  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <div className="min-h-full flex bg-bg">
      {/* Sidebar */}
      <aside
        className={clsx(
          "fixed lg:sticky top-0 z-40 h-screen w-64 shrink-0 flex flex-col border-r border-line bg-bg-soft/70 backdrop-blur transition-transform lg:transition-none",
          open ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
        aria-label="Primary navigation"
      >
        <BrandBlock />
        <SidebarNav />
        <div className="mt-auto p-3 border-t border-line">
          <BackendStatus health={health} />
        </div>
      </aside>

      {/* Overlay when sidebar is open on mobile */}
      {open && (
        <button
          className="fixed inset-0 z-30 bg-bg/70 backdrop-blur-sm lg:hidden"
          onClick={() => setOpen(false)}
          aria-label="Close navigation"
        />
      )}

      {/* Main column */}
      <div className="flex-1 min-w-0 flex flex-col min-h-screen">
        <TopBar onMenu={() => setOpen((v) => !v)} health={health} />
        <main className="flex-1">
          <div className="main-surface max-w-[1400px] mx-auto px-5 md:px-8 py-8">{children}</div>
        </main>
        <footer className="border-t border-line py-4 text-center text-[11px] text-ink-faint">
          {BRAND.footer}
        </footer>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Brand block (logo + name)
 * ------------------------------------------------------------------------- */
function BrandBlock() {
  return (
    <div className="px-4 py-4 border-b border-line">
      <div className="flex items-center gap-3">
        <span className="brand-mark">
          <BrandLogo />
        </span>
        <div className="min-w-0">
          <div className="text-sm font-semibold tracking-tight text-ink truncate">
            {BRAND.name}
          </div>
          <div className="text-[10px] uppercase tracking-[0.14em] text-ink-faint">
            {BRAND.tagline}
          </div>
        </div>
      </div>
    </div>
  );
}

function BrandLogo() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden>
      <defs>
        <linearGradient id="brandGrad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#7aa8ff" />
          <stop offset="1" stopColor="#a78bfa" />
        </linearGradient>
      </defs>
      <circle cx="16" cy="16" r="11" fill="none" stroke="url(#brandGrad)" strokeWidth={1.5} opacity="0.45" />
      <path
        d="M16 7v18M7 16h18"
        stroke="url(#brandGrad)"
        strokeWidth={1.25}
        strokeLinecap="round"
        opacity="0.7"
      />
      <path
        d="M10.5 20.5 14.2 16l3 2.2 5-7"
        fill="none"
        stroke="url(#brandGrad)"
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="22.2" cy="11.2" r="2.1" fill="#eef2ff" stroke="url(#brandGrad)" strokeWidth={1.4} />
    </svg>
  );
}

/* -------------------------------------------------------------------------
 * Sidebar navigation
 * ------------------------------------------------------------------------- */
interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  section?: "main" | "context";
  contextual?: boolean;
}

function SidebarNav() {
  const lastId = getLastDatasetId();

  const main: NavItem[] = [
    { to: "/datasets", label: "Datasets", icon: <IconFolder /> },
    { to: "/upload", label: "Upload", icon: <IconUpload /> },
    { to: "/assistant", label: "AI Assistant", icon: <IconSparkle /> },
  ];

  const contextual: NavItem[] = lastId
    ? [
        { to: `/datasets/${lastId}`, label: "Dashboard", icon: <IconChart /> },
        {
          to: `/datasets/${lastId}/analysis`,
          label: "Analysis modes",
          icon: <IconLayers />,
        },
      ]
    : [];

  return (
    <nav className="sidebar-command flex-1 overflow-y-auto py-3" aria-label="Command center">
      <div className="sidebar-command-title px-4 pb-2">
        <span className="sidebar-command-pulse" aria-hidden />
        <span>Command center</span>
        <span className="ml-auto font-mono text-[9px] text-ink-faint">LIVE</span>
      </div>
      <NavGroup label="Workspace" items={main} />
      {contextual.length > 0 && (
        <NavGroup label="Active dataset" items={contextual} className="mt-4" />
      )}
    </nav>
  );
}

function NavGroup({
  label,
  items,
  className,
}: {
  label: string;
  items: NavItem[];
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="px-4 mb-1.5 text-[10px] uppercase tracking-[0.14em] text-ink-faint">
        {label}
      </div>
      <ul className="space-y-0.5 px-2">
        {items.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-brand-soft/70 text-ink border border-brand-muted/60 shadow-insetTop"
                    : "text-ink-muted hover:text-ink hover:bg-bg-hover border border-transparent",
                )
              }
              end={item.to === "/datasets" ? false : undefined}
            >
              <span className="text-ink-muted">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Top bar
 * ------------------------------------------------------------------------- */
function TopBar({
  onMenu,
  health,
}: {
  onMenu: () => void;
  health: HealthResponse | null;
}) {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-bg/85 backdrop-blur">
      <div className="max-w-[1400px] mx-auto flex items-center gap-3 px-5 md:px-8 py-3">
        <button
          className="lg:hidden btn-ghost -ml-2"
          onClick={onMenu}
          aria-label="Open navigation"
        >
          <IconMenu />
        </button>
        <div className="flex items-center gap-2 lg:hidden">
          <span className="brand-mark scale-90">
            <BrandLogo />
          </span>
          <span className="text-sm font-semibold text-ink">{BRAND.name}</span>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <BackendPill health={health} />
          <UserChip />
        </div>
      </div>
    </header>
  );
}

function BackendPill({ health }: { health: HealthResponse | null }) {
  if (!health) {
    return (
      <span className="chip">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-bad animate-pulseSoft" />
        Backend offline
      </span>
    );
  }
  if (health.supabase_configured) {
    return (
      <span className="chip text-good">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-good" />
        Supabase connected
      </span>
    );
  }
  return (
    <span className="chip text-warn">
      <span className="inline-block h-1.5 w-1.5 rounded-full bg-warn" />
      Local storage
    </span>
  );
}

function BackendStatus({ health }: { health: HealthResponse | null }) {
  return (
    <div className="rounded-lg border border-line bg-bg-soft/60 px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.14em] text-ink-faint">
        Backend
      </div>
      <div className="mt-1 flex items-center gap-2 text-xs text-ink-muted">
        <span
          className={clsx(
            "inline-block h-1.5 w-1.5 rounded-full",
            !health ? "bg-bad animate-pulseSoft" : health.supabase_configured ? "bg-good" : "bg-warn",
          )}
        />
        <span>
          {!health
            ? "Offline"
            : health.supabase_configured
              ? "Supabase"
              : "Local storage fallback"}
        </span>
      </div>
    </div>
  );
}

function UserChip() {
  return (
    <div className="flex items-center gap-2 rounded-full border border-line bg-bg-soft/70 px-2 py-1">
      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-brand-soft border border-brand-muted text-brand text-[11px] font-semibold">
        A
      </span>
      <span className="hidden sm:inline text-xs text-ink-muted pr-1">Analyst</span>
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Icons (inline SVG so we avoid an external dependency)
 * ------------------------------------------------------------------------- */
function IconFolder() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
      <path
        d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconUpload() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
      <path
        d="M12 15V3m0 0-4 4m4-4 4 4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconChart() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
      <path
        d="M4 20V4M4 20h16M8 16V9M12 16V6M16 16v-3M20 16v-5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconLayers() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
      <path
        d="M12 4 3 9l9 5 9-5-9-5Zm-9 10 9 5 9-5M3 19l9 5 9-5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconSparkle() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
      <path
        d="M12 3v4m0 10v4M3 12h4m10 0h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconMenu() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <path
        d="M4 6h16M4 12h16M4 18h16"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
