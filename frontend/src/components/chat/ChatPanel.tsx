import { KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { api, ApiError } from "@/lib/api";
import type {
  AnswerClassification,
  ChatCalculation,
  ChatConfidence,
  ChatEvidence,
  ChatMessage,
  ChatResponse,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
export interface ChatPanelProps {
  datasetId: string;
  datasetName?: string;
  analysisMode?:
    | "self_analysis"
    | "merger_partnership_analysis"
    | "competitor_market_benchmark";
  secondaryDatasetId?: string | null;
  secondaryDatasetName?: string | null;
  marketDatasetId?: string | null;
  marketDatasetName?: string | null;
  className?: string;
  /** Optional storage key so the session survives navigating between pages. */
  storageKey?: string;
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------
const MODE_LABEL: Record<string, string> = {
  self_analysis: "Self Financial Analysis",
  merger_partnership_analysis: "Merger / Partnership Analysis",
  competitor_market_benchmark: "Competitor & Market Benchmarking",
};

const CLASSIFICATION_LABEL: Record<AnswerClassification, string> = {
  reported: "Reported",
  calculated: "Calculated",
  estimated: "Estimated",
  scenario: "Scenario",
  unavailable: "Unavailable",
  informational: "Info",
  refused: "Out of scope",
};

const CLASSIFICATION_COLOR: Record<AnswerClassification, string> = {
  reported: "text-good border-good/40 bg-good/10",
  calculated: "text-brand border-brand-muted/60 bg-brand-soft/40",
  estimated: "text-warn border-warn/40 bg-warn/10",
  scenario: "text-info border-info/40 bg-info/10",
  unavailable: "text-ink-faint border-line bg-bg-hover",
  informational: "text-ink-muted border-line bg-bg-soft",
  refused: "text-bad border-bad/40 bg-bad/10",
};

const CONFIDENCE_COLOR: Record<ChatConfidence, string> = {
  high: "text-good",
  medium: "text-warn",
  low: "text-bad",
  none: "text-ink-faint",
};

function storageAvailable(): boolean {
  try {
    if (typeof window === "undefined") return false;
    window.localStorage.setItem("__chat_probe", "1");
    window.localStorage.removeItem("__chat_probe");
    return true;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Chat panel
// ---------------------------------------------------------------------------
export function ChatPanel({
  datasetId,
  datasetName,
  analysisMode = "self_analysis",
  secondaryDatasetId = null,
  secondaryDatasetName = null,
  marketDatasetId = null,
  marketDatasetName = null,
  className,
  storageKey,
}: ChatPanelProps) {
  const sessionStorageKey = useMemo(
    () =>
      storageKey ??
      `chat.session.${analysisMode}.${datasetId}.${secondaryDatasetId ?? "-"}.${marketDatasetId ?? "-"}`,
    [analysisMode, datasetId, secondaryDatasetId, marketDatasetId, storageKey],
  );

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Load persisted session id if any.
  useEffect(() => {
    if (!storageAvailable()) return;
    const existing = window.localStorage.getItem(sessionStorageKey);
    if (existing) setSessionId(existing);
  }, [sessionStorageKey]);

  // Fetch history if we already have a session.
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }
    const ctrl = new AbortController();
    api
      .chatSession(sessionId, ctrl.signal)
      .then((data) => setMessages(data.messages))
      .catch(() => {
        // Session may have expired or been cleared server-side.
        if (storageAvailable()) window.localStorage.removeItem(sessionStorageKey);
        setSessionId(null);
      });
    return () => ctrl.abort();
  }, [sessionId, sessionStorageKey]);

  // Fetch starter suggestions when context changes.
  useEffect(() => {
    if (!datasetId) return;
    const ctrl = new AbortController();
    const lastIntent =
      messages.length > 0 && messages[messages.length - 1].role === "assistant"
        ? messages[messages.length - 1].intent ?? undefined
        : undefined;
    api
      .chatSuggestions(
        {
          dataset_id: datasetId,
          analysis_mode: analysisMode,
          secondary_dataset_id: secondaryDatasetId ?? null,
          market_dataset_id: marketDatasetId ?? null,
          last_intent: lastIntent ?? null,
          limit: 6,
        },
        ctrl.signal,
      )
      .then((r) => setSuggestions(r.suggestions))
      .catch(() => setSuggestions([]));
    return () => ctrl.abort();
  }, [
    datasetId,
    analysisMode,
    secondaryDatasetId,
    marketDatasetId,
    messages.length,
  ]);

  // Auto-scroll to newest message.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages.length, sending]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;
    setError(null);
    setInput("");
    setSending(true);

    // Optimistically push the user message so the UI feels snappy.
    const now = new Date().toISOString();
    const userMsg: ChatMessage = {
      role: "user",
      text: trimmed,
      timestamp: now,
      intent: null,
      classification: null,
      confidence: null,
      evidence: [],
      calculations: [],
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const response: ChatResponse = await api.chatQuery({
        message: trimmed,
        session_id: sessionId,
        dataset_id: datasetId,
        analysis_mode: analysisMode,
        secondary_dataset_id: secondaryDatasetId,
        market_dataset_id: marketDatasetId,
        primary_display_name: datasetName ?? null,
        secondary_display_name: secondaryDatasetName ?? null,
        market_display_name: marketDatasetName ?? null,
      });

      // Persist session id for reuse across page navigations.
      if (response.session_id && response.session_id !== sessionId) {
        setSessionId(response.session_id);
        if (storageAvailable()) {
          window.localStorage.setItem(sessionStorageKey, response.session_id);
        }
      }

      // Append the assistant message to the local list.
      const assistantMsg: ChatMessage = {
        role: "assistant",
        text: response.answer,
        timestamp: response.generated_at,
        intent: response.intent,
        classification: response.classification,
        confidence: response.confidence,
        evidence: response.evidence,
        calculations: response.calculations,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setSuggestions(response.suggested_followups);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : (err as Error).message ?? "Unknown error";
      setError(message);
      // Roll back the optimistic user message so the user can retry.
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setSending(false);
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(input);
    }
  }

  async function clearSession() {
    setError(null);
    if (sessionId) {
      try {
        await api.chatClearSession(sessionId);
      } catch {
        /* best effort */
      }
    }
    if (storageAvailable()) window.localStorage.removeItem(sessionStorageKey);
    setSessionId(null);
    setMessages([]);
    setExpandedIndex(null);
  }

  const modeTitle = MODE_LABEL[analysisMode] ?? analysisMode;

  return (
    <section
      className={clsx(
        "card flex flex-col overflow-hidden",
        // ~640px on tall screens keeps the panel a proper conversation area
        "h-[640px] max-h-[80vh]",
        className,
      )}
      aria-label="Dataset Intelligence Assistant"
    >
      <ChatHeader
        title="Financial Intelligence Assistant"
        modeTitle={modeTitle}
        datasetName={datasetName}
        secondaryName={secondaryDatasetName}
        marketName={marketDatasetName}
        onClear={clearSession}
        clearable={messages.length > 0}
      />

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-4 space-y-4 bg-bg-soft/40"
      >
        {messages.length === 0 && !sending && (
          <EmptyIntro
            modeTitle={modeTitle}
            datasetName={datasetName}
            suggestions={suggestions}
            onPick={(q) => void send(q)}
          />
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <UserBubble key={i} text={m.text} />
          ) : (
            <AssistantBubble
              key={i}
              message={m}
              expanded={expandedIndex === i}
              onToggle={() =>
                setExpandedIndex((prev) => (prev === i ? null : i))
              }
            />
          ),
        )}
        {sending && <TypingIndicator />}
        {error && (
          <div className="rounded-md border border-bad/40 bg-bad/10 px-3 py-2 text-xs text-bad">
            {error}
          </div>
        )}
      </div>

      {messages.length > 0 && suggestions.length > 0 && !sending && (
        <div className="px-4 pt-3 pb-1 border-t border-line bg-bg-soft/60 flex flex-wrap gap-2">
          {suggestions.slice(0, 4).map((s) => (
            <button
              key={s}
              onClick={() => void send(s)}
              className="chip hover:text-ink hover:border-brand-muted transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <ChatInput
        value={input}
        disabled={sending}
        onChange={setInput}
        onSubmit={() => void send(input)}
        onKeyDown={onKeyDown}
        placeholder={placeholderFor(analysisMode)}
      />
    </section>
  );
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------
function ChatHeader({
  title,
  modeTitle,
  datasetName,
  secondaryName,
  marketName,
  onClear,
  clearable,
}: {
  title: string;
  modeTitle: string;
  datasetName?: string;
  secondaryName?: string | null;
  marketName?: string | null;
  onClear: () => void;
  clearable: boolean;
}) {
  return (
    <header className="px-4 py-3 border-b border-line bg-bg-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="brand-mark !h-6 !w-6 !rounded-md">
              <svg viewBox="0 0 32 32" className="text-brand h-4 w-4">
                <path
                  d="M6 22 L12 14 L17 18 L26 8"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2.5}
                  strokeLinecap="round"
                />
                <circle cx="26" cy="8" r="2.2" fill="currentColor" />
              </svg>
            </span>
            <h3 className="heading-3">{title}</h3>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-ink-muted">
            <span className="text-ink-faint">Mode:</span>
            <span className="chip !bg-brand-soft/50 !border-brand-muted/50 !text-brand">
              {modeTitle}
            </span>
            {datasetName && (
              <>
                <span className="text-ink-faint">·</span>
                <span className="chip max-w-[220px] truncate" title={datasetName}>
                  {datasetName}
                </span>
              </>
            )}
            {secondaryName && (
              <span
                className="chip max-w-[220px] truncate"
                title={secondaryName}
              >
                vs {secondaryName}
              </span>
            )}
            {marketName && (
              <span
                className="chip max-w-[220px] truncate"
                title={marketName}
              >
                mkt {marketName}
              </span>
            )}
          </div>
        </div>
        {clearable && (
          <button onClick={onClear} className="btn-ghost btn-xs">
            Clear
          </button>
        )}
      </div>
      <p className="mt-2 text-[11px] text-ink-faint">
        Answers are grounded in the uploaded dataset. Values are labelled
        reported, calculated, scenario or estimated so you can verify them.
      </p>
    </header>
  );
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------
function EmptyIntro({
  modeTitle,
  datasetName,
  suggestions,
  onPick,
}: {
  modeTitle: string;
  datasetName?: string;
  suggestions: string[];
  onPick: (q: string) => void;
}) {
  return (
    <div className="text-center pt-6 pb-2">
      <div className="mx-auto brand-mark mb-3">
        <svg viewBox="0 0 24 24" fill="none">
          <path
            d="M3 6h18M3 12h18M3 18h12"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      </div>
      <p className="text-sm text-ink font-medium">
        Ask a question about {datasetName ?? "this dataset"}
      </p>
      <p className="text-[11px] text-ink-muted mt-1">
        {modeTitle} context is loaded — I only answer using verified analytical evidence.
      </p>
      {suggestions.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2 justify-center">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => onPick(s)}
              className="chip hover:text-ink hover:border-brand-muted transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bubbles
// ---------------------------------------------------------------------------
function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-brand-soft/80 border border-brand-muted/40 px-3.5 py-2 text-sm text-ink whitespace-pre-wrap">
        {text}
      </div>
    </div>
  );
}

function AssistantBubble({
  message,
  expanded,
  onToggle,
}: {
  message: ChatMessage;
  expanded: boolean;
  onToggle: () => void;
}) {
  const cls = message.classification ?? "informational";
  const conf = message.confidence ?? "none";
  const hasDetails =
    (message.evidence?.length ?? 0) > 0 || (message.calculations?.length ?? 0) > 0;

  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] rounded-2xl rounded-bl-sm bg-bg-card border border-line px-3.5 py-2.5 shadow-card">
        {/* Text */}
        <div className="text-sm text-ink whitespace-pre-wrap leading-relaxed">
          {message.text}
        </div>

        {/* Meta row */}
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span
            className={clsx(
              "inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
              CLASSIFICATION_COLOR[cls],
            )}
          >
            {CLASSIFICATION_LABEL[cls]}
          </span>
          {conf !== "none" && (
            <span className={clsx("text-[10px] uppercase tracking-wider", CONFIDENCE_COLOR[conf])}>
              Confidence: {conf}
            </span>
          )}
          {hasDetails && (
            <button
              onClick={onToggle}
              className="ml-auto text-[11px] text-ink-muted hover:text-ink underline underline-offset-2"
            >
              {expanded ? "Hide evidence" : "Show evidence"}
            </button>
          )}
        </div>

        {/* Warnings inline (rare) */}
        {message.evidence?.length === 0 && message.classification === "unavailable" && (
          <p className="mt-2 text-[11px] text-ink-faint">
            Nothing more to show — the required data isn't present in your uploaded dataset.
          </p>
        )}

        {/* Evidence + calculations (collapsible) */}
        {expanded && hasDetails && (
          <EvidencePanel
            evidence={message.evidence}
            calculations={message.calculations}
          />
        )}
      </div>
    </div>
  );
}

function EvidencePanel({
  evidence,
  calculations,
}: {
  evidence: ChatEvidence[];
  calculations: ChatCalculation[];
}) {
  return (
    <div className="mt-3 rounded-lg border border-line bg-bg-soft/60 divide-y divide-line">
      {evidence.length > 0 && (
        <div className="p-3">
          <div className="label mb-2">Evidence</div>
          <ul className="space-y-1.5">
            {evidence.slice(0, 12).map((e, i) => (
              <li key={i} className="flex items-baseline justify-between gap-3 text-xs">
                <span className="text-ink-muted truncate">
                  {e.entity_name && e.entity && e.entity !== "primary" && (
                    <span className="text-ink-faint mr-1">[{e.entity_name}]</span>
                  )}
                  {e.label}
                  {e.period && (
                    <span className="text-ink-faint ml-1">· {e.period}</span>
                  )}
                </span>
                <span className="font-mono tabular-nums text-ink shrink-0">
                  {e.display_value ??
                    (e.value != null ? e.value.toLocaleString() : "—")}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {calculations.length > 0 && (
        <div className="p-3">
          <div className="label mb-2">Calculation</div>
          <ul className="space-y-1.5">
            {calculations.slice(0, 4).map((c, i) => (
              <li key={i} className="text-[11px] text-ink-muted font-mono leading-relaxed">
                {c.formula}
                {c.result != null && (
                  <span className="text-ink"> = {c.result.toLocaleString()}</span>
                )}
                {c.explanation && (
                  <div className="text-ink-faint italic mt-0.5">
                    {c.explanation}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Input + typing indicator
// ---------------------------------------------------------------------------
function ChatInput({
  value,
  disabled,
  onChange,
  onSubmit,
  onKeyDown,
  placeholder,
}: {
  value: string;
  disabled: boolean;
  onChange: (v: string) => void;
  onSubmit: () => void;
  onKeyDown: (e: KeyboardEvent<HTMLTextAreaElement>) => void;
  placeholder: string;
}) {
  return (
    <div className="border-t border-line bg-bg-card px-3 py-3 flex items-end gap-2">
      <textarea
        rows={1}
        value={value}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        className="input flex-1 resize-none max-h-32 leading-5"
      />
      <button
        className="btn-primary"
        disabled={disabled || value.trim().length === 0}
        onClick={onSubmit}
      >
        Send
      </button>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="rounded-2xl rounded-bl-sm bg-bg-card border border-line px-3.5 py-2.5 flex items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full bg-brand animate-pulseSoft" />
        <span
          className="h-1.5 w-1.5 rounded-full bg-brand animate-pulseSoft"
          style={{ animationDelay: "150ms" }}
        />
        <span
          className="h-1.5 w-1.5 rounded-full bg-brand animate-pulseSoft"
          style={{ animationDelay: "300ms" }}
        />
        <span className="text-[11px] text-ink-faint ml-1">Analyzing…</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Placeholders
// ---------------------------------------------------------------------------
function placeholderFor(mode: string): string {
  switch (mode) {
    case "merger_partnership_analysis":
      return "Ask about combined revenue, synergies, merger risks…";
    case "competitor_market_benchmark":
      return "Ask about gaps, margin comparisons, market benchmarks…";
    default:
      return "Ask about your metrics, ratios, trends, or health score…";
  }
}
