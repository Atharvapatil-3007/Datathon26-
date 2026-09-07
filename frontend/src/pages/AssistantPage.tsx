import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Link } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/States";
import { EvidenceCard } from "@/components/ui/EvidenceCard";
import { BRAND } from "@/config/brand";
import {
  getLastAnalysisMode,
  getLastAnalysisResult,
  getLastDatasetId,
  getLastDatasetName,
} from "@/lib/assistantContext";
import {
  answerQuestion,
  suggestedQuestions,
  type AssistantAnswer,
} from "@/lib/assistantEngine";
import type { AnalysisMode } from "@/lib/types";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  answer?: AssistantAnswer;
  at: number;
}

const MODE_LABEL: Record<AnalysisMode, string> = {
  self_analysis: "Self analysis",
  merger_partnership_analysis: "Merger analysis",
  competitor_market_benchmark: "Competitor benchmark",
};

export default function AssistantPage() {
  const datasetId = getLastDatasetId();
  const datasetName = getLastDatasetName();
  const mode = getLastAnalysisMode();
  const result = useMemo(() => getLastAnalysisResult(), []);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  const suggestions = useMemo(() => suggestedQuestions(mode), [mode]);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTo({
        top: listRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, thinking]);

  function submit(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      text: trimmed,
      at: Date.now(),
    };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setThinking(true);

    // Small artificial delay so the "thinking" state is visible.
    window.setTimeout(() => {
      const answer = answerQuestion(trimmed, result, mode);
      const aiMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        text: answer.text,
        answer,
        at: Date.now(),
      };
      setMessages((m) => [...m, aiMsg]);
      setThinking(false);
    }, 350);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    submit(input);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(input);
    }
  }

  const hasContext = !!result;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Financial Intelligence Assistant"
        title="Ask about your data"
        subtitle={
          hasContext
            ? `${BRAND.name} is grounded in your latest analysis — answers come from the numbers you've already seen, never from imagination.`
            : `${BRAND.name} answers questions using your most recent analysis. Run a self, merger or benchmark analysis first to give the assistant something to reason about.`
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
        {/* Chat pane */}
        <Card
          className="flex flex-col overflow-hidden"
          bodyClassName="p-0 flex-1 flex flex-col min-h-[560px]"
        >
          {/* Chat header */}
          <div className="px-5 py-3 border-b border-line bg-bg-soft/40 flex items-center gap-3">
            <span className="brand-mark shrink-0">
              <AssistantAvatar />
            </span>
            <div className="min-w-0">
              <div className="text-sm font-semibold text-ink">
                Financial Intelligence Assistant
              </div>
              <div className="text-[11px] text-ink-faint mt-0.5">
                {hasContext
                  ? `Based on ${datasetName ?? "your dataset"} · ${mode ? MODE_LABEL[mode] : "analysis"}`
                  : "No analysis context loaded"}
              </div>
            </div>
            <div className="ml-auto">
              {hasContext && datasetId && (
                <Link
                  to={`/datasets/${datasetId}/analysis`}
                  className="text-[11px] text-ink-muted hover:text-ink"
                >
                  Open analysis →
                </Link>
              )}
            </div>
          </div>

          {/* Message list */}
          <div
            ref={listRef}
            className="flex-1 overflow-y-auto px-5 py-6 space-y-4"
            aria-live="polite"
          >
            {messages.length === 0 && (
              <EmptyStateChat
                hasContext={hasContext}
                suggestions={suggestions}
                onPick={submit}
              />
            )}
            {messages.map((m) => (
              <MessageRow key={m.id} message={m} />
            ))}
            {thinking && <ThinkingRow />}
          </div>

          {/* Composer */}
          <form
            onSubmit={onSubmit}
            className="border-t border-line bg-bg-soft/50 px-4 py-3"
          >
            <label htmlFor="assistant-input" className="sr-only">
              Ask a question
            </label>
            <div className="flex items-end gap-2">
              <textarea
                id="assistant-input"
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={
                  hasContext
                    ? "Ask about your financial data…"
                    : "Run an analysis first to enable Q&A."
                }
                className="input flex-1 resize-none min-h-[40px] max-h-32"
              />
              <Button
                type="submit"
                variant="primary"
                disabled={!input.trim() || thinking}
              >
                Ask
              </Button>
            </div>
            <div className="mt-2 text-[10px] text-ink-faint">
              Press <span className="kbd">Enter</span> to send ·{" "}
              <span className="kbd">Shift+Enter</span> for newline. Answers come
              from your cached analysis — nothing is fabricated.
            </div>
          </form>
        </Card>

        {/* Sidebar rail: context + suggestions */}
        <div className="space-y-4">
          <Card eyebrow="Context" title="What I'm reading">
            {hasContext ? (
              <div className="space-y-2 text-sm">
                <ContextRow label="Dataset" value={datasetName ?? "—"} />
                <ContextRow
                  label="Analysis"
                  value={mode ? MODE_LABEL[mode] : "—"}
                />
                <ContextRow
                  label="Metrics"
                  value={result ? String(result.metrics.length) : "—"}
                />
                <ContextRow
                  label="Ratios"
                  value={result ? String(result.ratios.length) : "—"}
                />
                <ContextRow
                  label="Insights"
                  value={result ? String(result.insights.length) : "—"}
                />
              </div>
            ) : (
              <p className="text-sm text-ink-muted leading-relaxed">
                Once you run an analysis, its full result is cached locally so I
                can answer questions grounded in the numbers.
              </p>
            )}
          </Card>

          <Card eyebrow="Try asking" title="Suggested questions">
            <ul className="space-y-2">
              {suggestions.map((s) => (
                <li key={s}>
                  <button
                    onClick={() => submit(s)}
                    className="w-full text-left rounded-lg border border-line bg-bg-soft/40 px-3 py-2 text-sm text-ink-muted hover:text-ink hover:border-brand-muted/60 hover:bg-bg-hover transition-colors"
                    disabled={!hasContext}
                  >
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </Card>

          <Card eyebrow="How this works" title="Grounded, not generative">
            <p className="text-xs text-ink-muted leading-relaxed">
              I pattern-match your question and read the underlying analysis
              result. Every answer includes an evidence card showing the exact
              values I used — with the same
              <span className="text-ink"> REPORTED</span>,
              <span className="text-ink"> CALCULATED</span>,
              <span className="text-ink"> ESTIMATED</span> or
              <span className="text-ink"> SCENARIO</span> label they carry
              elsewhere in the app.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Sub-components
 * ------------------------------------------------------------------------- */
function EmptyStateChat({
  hasContext,
  suggestions,
  onPick,
}: {
  hasContext: boolean;
  suggestions: string[];
  onPick: (q: string) => void;
}) {
  if (!hasContext) {
    return (
      <EmptyState
        title="No analysis loaded yet"
        hint="Head to Datasets, open one, and run a self, merger or benchmark analysis. I'll then be ready to answer questions using its results."
        action={
          <Link to="/datasets">
            <Button variant="primary">Open datasets</Button>
          </Link>
        }
        icon={
          <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6">
            <path
              d="M8 12h8m-8 4h5M12 3v3M4 12H3M21 12h-1M6 6l-1-1M18 6l1-1M12 3a9 9 0 0 1 9 9 9 9 0 0 1-3.4 7L12 21l-5.6-2A9 9 0 0 1 3 12a9 9 0 0 1 9-9Z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        }
      />
    );
  }
  return (
    <div className="flex flex-col items-center text-center py-4">
      <div className="brand-mark mb-4">
        <AssistantAvatar />
      </div>
      <div className="text-lg font-semibold text-ink">
        How can I help analyze your finances?
      </div>
      <p className="mt-1.5 text-sm text-ink-muted max-w-md">
        I answer using the metrics, ratios and insights from your most recent
        analysis. Pick a starter question or type your own.
      </p>
      <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => onPick(s)}
            className="text-left rounded-lg border border-line bg-bg-soft/50 px-3 py-2.5 text-sm text-ink-muted hover:text-ink hover:border-brand-muted/60 hover:bg-bg-hover transition-colors"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageRow({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end animate-fadeIn">
        <div className="max-w-[85%] rounded-2xl rounded-tr-md border border-brand-muted/40 bg-brand-soft/40 px-3.5 py-2 text-sm text-ink">
          {message.text}
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-start gap-3 animate-fadeIn">
      <span className="brand-mark shrink-0 h-8 w-8">
        <AssistantAvatar />
      </span>
      <div className="flex-1 min-w-0">
        <div className="rounded-2xl rounded-tl-md border border-line bg-bg-soft/60 px-3.5 py-2 text-sm text-ink leading-relaxed text-pretty">
          {message.text}
        </div>
        {message.answer && (
          <div className="mt-2">
            <EvidenceCard
              title="Evidence"
              source={message.answer.source}
              confidence={message.answer.confidence}
              status={
                message.answer.status &&
                message.answer.status !== "unavailable"
                  ? (message.answer.status as
                      | "reported"
                      | "calculated"
                      | "estimated"
                      | "scenario")
                  : undefined
              }
            >
              <dl className="space-y-1.5">
                {message.answer.evidence.length === 0 ? (
                  <div className="text-ink-faint">No structured evidence.</div>
                ) : (
                  message.answer.evidence.map((e, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between gap-3 text-[11px]"
                    >
                      <dt className="text-ink-faint uppercase tracking-widest">
                        {e.label}
                      </dt>
                      <dd className="font-mono tabular-nums text-ink">
                        {e.value}
                      </dd>
                    </div>
                  ))
                )}
              </dl>
            </EvidenceCard>
          </div>
        )}
      </div>
    </div>
  );
}

function ThinkingRow() {
  return (
    <div className="flex items-start gap-3 animate-fadeIn">
      <span className="brand-mark shrink-0 h-8 w-8">
        <AssistantAvatar />
      </span>
      <div className="rounded-2xl rounded-tl-md border border-line bg-bg-soft/60 px-3.5 py-2 flex items-center gap-2">
        <span className="inline-flex gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-brand animate-pulseSoft" />
          <span
            className="h-1.5 w-1.5 rounded-full bg-brand animate-pulseSoft"
            style={{ animationDelay: "150ms" }}
          />
          <span
            className="h-1.5 w-1.5 rounded-full bg-brand animate-pulseSoft"
            style={{ animationDelay: "300ms" }}
          />
        </span>
        <span className="text-xs text-ink-muted">Reasoning over your data</span>
      </div>
    </div>
  );
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-ink-faint text-[11px] uppercase tracking-widest">
        {label}
      </span>
      <span className="text-ink truncate max-w-[180px]" title={value}>
        {value}
      </span>
    </div>
  );
}

function AssistantAvatar() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden>
      <defs>
        <linearGradient
          id="assistantAvatar"
          x1="0"
          y1="0"
          x2="32"
          y2="32"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="#7aa8ff" />
          <stop offset="1" stopColor="#a78bfa" />
        </linearGradient>
      </defs>
      <path
        d="M12 3v4m0 10v4M3 12h4m10 0h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"
        stroke="url(#assistantAvatar)"
        strokeWidth="2"
        strokeLinecap="round"
        transform="translate(4 4)"
      />
    </svg>
  );
}
