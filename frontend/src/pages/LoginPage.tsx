import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { BRAND } from "@/config/brand";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError("Enter your email and password to continue.");
      return;
    }
    window.localStorage.setItem("finsight.authenticated", "true");
    const destination = (location.state as { from?: string } | null)?.from ?? "/datasets";
    navigate(destination, { replace: true });
  }

  return (
    <main className="login-page min-h-screen px-5 py-8 md:px-10">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-6xl items-center justify-center">
        <div className="grid w-full overflow-hidden rounded-3xl border border-white/10 bg-bg-soft/80 shadow-elev backdrop-blur md:grid-cols-[1.1fr_0.9fr]">
          <section className="login-visual relative hidden min-h-[560px] flex-col justify-between overflow-hidden p-10 md:flex">
            <div className="relative z-10 flex items-center gap-3">
              <span className="brand-mark"><BrandLogo /></span>
              <div>
                <div className="text-sm font-semibold text-ink">{BRAND.name}</div>
                <div className="text-[10px] uppercase tracking-[0.16em] text-ink-faint">{BRAND.tagline}</div>
              </div>
            </div>
            <div className="relative z-10 max-w-md">
              <div className="eyebrow mb-3">Decision intelligence</div>
              <h1 className="text-4xl font-semibold leading-tight tracking-tight text-ink">
                See the signal inside every dataset.
              </h1>
              <p className="mt-4 text-sm leading-relaxed text-ink-muted">
                Profile quality, uncover relationships, and move from raw data to a clearer next decision.
              </p>
            </div>
            <div className="relative z-10 grid grid-cols-3 gap-3 text-[11px] text-ink-muted">
              <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3">Profile<br /><span className="text-ink">Structure</span></div>
              <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3">Compare<br /><span className="text-ink">Performance</span></div>
              <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3">Decide<br /><span className="text-ink">Confidently</span></div>
            </div>
          </section>

          <section className="flex items-center p-7 sm:p-10">
            <form className="w-full max-w-sm mx-auto" onSubmit={submit}>
              <div className="mb-8 md:hidden flex items-center gap-3">
                <span className="brand-mark"><BrandLogo /></span>
                <span className="text-sm font-semibold text-ink">{BRAND.name}</span>
              </div>
              <div className="eyebrow">Welcome back</div>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight text-ink">Sign in to your workspace</h2>
              <p className="mt-2 text-sm leading-relaxed text-ink-muted">Continue to your financial intelligence dashboard.</p>

              <label className="mt-8 block text-xs font-medium text-ink-muted" htmlFor="email">Work email</label>
              <input id="email" className="input mt-2 w-full" type="email" autoComplete="email" placeholder="you@company.com" value={email} onChange={(event) => setEmail(event.target.value)} />
              <label className="mt-4 block text-xs font-medium text-ink-muted" htmlFor="password">Password</label>
              <input id="password" className="input mt-2 w-full" type="password" autoComplete="current-password" placeholder="Enter your password" value={password} onChange={(event) => setPassword(event.target.value)} />
              {error && <p className="mt-3 text-xs text-bad" role="alert">{error}</p>}
              <button className="btn-primary mt-6 w-full justify-center py-2.5" type="submit">Enter workspace <span aria-hidden>→</span></button>
              <p className="mt-6 text-center text-[11px] text-ink-faint">Your workspace is ready when you are.</p>
            </form>
          </section>
        </div>
      </div>
    </main>
  );
}

function BrandLogo() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className="h-5 w-5">
      <circle cx="16" cy="16" r="11" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.45" />
      <path d="M10.5 20.5 14.2 16l3 2.2 5-7" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="22.2" cy="11.2" r="2.1" fill="currentColor" />
    </svg>
  );
}