"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Alert,
  Badge,
  Button,
  ConfidenceControl,
  DataBadge,
  Input,
  Panel,
  ProgressBar,
  ChoiceOption,
  RadioGroup,
} from "@/components/ui";
import {
  ApiClientError,
  apiFetch,
  getNasdaqChallenge,
  submitNasdaqVerifier,
} from "@/lib/api-client";
import type {
  DashboardResponse,
  MeResponse,
  NasdaqChallengeResponse,
  NasdaqSubmitResponse,
  PlanResponse,
} from "@/lib/contracts";

type Progress = { level: number | null; planPct: number | null; brier: number | null };
type View =
  | { s: "loading" }
  | { s: "locked"; missing: string[]; progress: Progress }
  | { s: "error"; message: string }
  | { s: "ready"; data: NasdaqChallengeResponse };

const num = (v: number | null, d = 2) =>
  v === null || v === undefined ? "—" : v.toLocaleString("en-US", { maximumFractionDigits: d });

function Check({
  ok,
  label,
  value,
  pct,
}: {
  ok: boolean;
  label: string;
  value: string;
  pct: number;
}) {
  return (
    <li>
      <div className="flex justify-between text-sm text-[var(--ink)]">
        <span>
          <span aria-hidden="true">{ok ? "✓" : "○"}</span> {label}
        </span>
        <span className="text-[var(--ink-soft)]">{value}</span>
      </div>
      <ProgressBar value={pct} ariaLabel={`${label} progress`} />
    </li>
  );
}

function LockedCard({ missing, progress }: { missing: string[]; progress: Progress }) {
  const planOk = !missing.includes("plan_progress_100");
  const brierOk = !missing.includes("brier_lte_0.25");
  return (
    <Panel className="p-5" aria-labelledby="cap-title">
      <div className="flex items-center justify-between gap-3">
        <h2 id="cap-title" className="text-base font-semibold text-[var(--ink)]">
          Final capstone: Nasdaq literacy check
        </h2>
        <Badge variant="outline" className="text-xs">
          Locked
        </Badge>
      </div>
      <p className="mt-2 text-sm text-[var(--ink-soft)]">
        Finish every requirement to read real Nasdaq data. The server checks these, not this page.
      </p>
      <ul className="mt-4 space-y-3">
        <Check
          ok={!missing.includes("level_4")}
          label="Level 4 of 4"
          value={`${progress.level ?? "—"} / 4`}
          pct={((progress.level ?? 0) / 4) * 100}
        />
        <Check
          ok={planOk}
          label="Learning plan complete"
          value={progress.planPct === null ? "—" : `${progress.planPct}%`}
          pct={planOk ? 100 : (progress.planPct ?? 0)}
        />
        <Check
          ok={brierOk}
          label="Calibration Brier ≤ 0.25"
          value={progress.brier === null ? "—" : progress.brier.toFixed(2)}
          pct={brierOk ? 100 : 40}
        />
      </ul>
    </Panel>
  );
}

function Verifier({ data }: { data: NasdaqChallengeResponse }) {
  const snap = data.snapshot;
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [conf, setConf] = useState(70);
  const [i, setI] = useState(0);
  const [given, setGiven] = useState<{ question_id: string; answer: string; confidence: number }[]>(
    [],
  );
  const [result, setResult] = useState<NasdaqSubmitResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const q = data.questions[i];

  async function next() {
    const answer = answers[q.id];
    if (!answer) {
      setErr("Pick an answer first.");
      return;
    }
    setErr(null);
    const all = [...given, { question_id: q.id, answer, confidence: conf }];
    setGiven(all);
    if (i + 1 < data.questions.length) {
      setI(i + 1);
      return;
    }
    try {
      setResult(await submitNasdaqVerifier({ challenge_id: data.challenge_id, answers: all }));
    } catch (e) {
      setErr(e instanceof ApiClientError ? e.message : "Couldn't submit. Try again.");
    }
  }

  return (
    <div className="space-y-4">
      <Panel role="note" className="p-4 text-sm text-[var(--ink)]">
        <span>
          <strong>Educational literacy check, not investment advice.</strong>{" "}
          {data.disclaimer.replace(/^Educational literacy check( only)?\s*[—:-]\s*/i, "")}
        </span>
      </Panel>
      <div className="grid gap-4 md:grid-cols-[1.25fr_1fr]">
        <Panel className="p-5" aria-label="Market snapshot">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-[var(--ink)]">
              {snap.name} · {snap.symbol}
            </h2>
            <DataBadge origin={data.data_origin} />
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
            {[
              ["Price", `$${num(snap.price)}`],
              ["Day range", `${num(snap.day_low)} – ${num(snap.day_high)}`],
              ["52-week range", `${num(snap.week52_low)} – ${num(snap.week52_high)}`],
              [
                "Market cap",
                snap.market_cap_musd ? `$${num(snap.market_cap_musd / 1000, 1)}B` : "—",
              ],
              ["P/E (TTM)", num(snap.pe_ttm, 1)],
              ["Sector", snap.sector ?? "—"],
            ].map(([k, v]) => (
              <div key={k} className="rounded bg-[var(--paper)] px-2 py-1.5">
                <dt className="text-xs text-[var(--ink-soft)]">{k}</dt>
                <dd className="font-medium text-[var(--ink)]">{v}</dd>
              </div>
            ))}
          </dl>
          <div
            className="mt-3 h-44"
            role="img"
            aria-label={`One-year closing price chart for ${snap.symbol}`}
          >
            {snap.chart.length > 1 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={snap.chart}>
                  <CartesianGrid stroke="var(--line)" strokeDasharray="3 5" vertical={false} />
                  <XAxis
                    dataKey="date"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 11, fill: "var(--ink-soft)" }}
                    minTickGap={40}
                  />
                  <YAxis
                    domain={["auto", "auto"]}
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 11, fill: "var(--ink-soft)" }}
                    width={44}
                  />
                  <Tooltip
                    contentStyle={{
                      borderRadius: 12,
                      border: "1px solid var(--line)",
                      background: "var(--paper)",
                      color: "var(--ink)",
                      fontSize: 12,
                    }}
                    labelStyle={{ color: "var(--ink)", fontWeight: 600 }}
                    itemStyle={{ color: "var(--ink)" }}
                  />
                  <Line
                    isAnimationActive={false}
                    type="monotone"
                    dataKey="close"
                    stroke="var(--green)"
                    strokeWidth={2.5}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="pt-16 text-center text-sm text-[var(--ink-soft)]">
                Price history isn&apos;t available.
              </p>
            )}
          </div>
          <a
            href={data.nasdaq_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-block text-sm text-[var(--green)] underline"
          >
            ↗ Open full page on Nasdaq.com
          </a>
        </Panel>

        <Panel className="p-5" aria-label="Quick check">
          {result ? (
            <div aria-live="polite">
              <h2 className="text-base font-semibold text-[var(--ink)]">
                {result.passed ? "Passed" : "Not passed yet"}
              </h2>
              <p className="mt-1 text-sm text-[var(--ink-soft)]">
                {Math.round(result.score * 100)}% correct · Brier {result.brier.toFixed(2)}
              </p>
              <p className="mt-2 text-sm text-[var(--ink-soft)]">{result.feedback}</p>
              <ul className="mt-3 space-y-1 text-sm">
                {result.results.map((r) => (
                  <li key={r.question_id} className="text-[var(--ink)]">
                    <strong className={r.correct ? "text-[var(--green)]" : ""}>
                      {r.correct ? "✓ Correct." : "✗ Not quite."}
                    </strong>{" "}
                    {r.explanation}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <fieldset className="min-w-0">
              <legend className="flex w-full justify-between text-sm">
                <span className="font-semibold text-[var(--ink)]">Quick check</span>
                <span className="text-[var(--ink-soft)]">
                  Q {i + 1} of {data.questions.length}
                </span>
              </legend>
              <p id={`nasdaq-question-${q.id}`} className="mt-2 text-sm text-[var(--ink)]">
                {q.text}
              </p>
              <RadioGroup
                value={answers[q.id] ?? ""}
                onValueChange={(answer) => {
                  setAnswers({ ...answers, [q.id]: answer });
                  setErr(null);
                }}
                aria-labelledby={`nasdaq-question-${q.id}`}
                className="mt-2 grid gap-1.5"
              >
                {q.options.map((o) => (
                  <ChoiceOption key={o} value={o} selected={answers[q.id] === o}>
                    {o}
                  </ChoiceOption>
                ))}
              </RadioGroup>
              <ConfidenceControl label="How sure are you?" value={conf} onChange={setConf} />
              {err && (
                <Alert variant="destructive" role="alert" className="mt-3 text-sm">
                  {err}
                </Alert>
              )}
              <Button
                variant="primary"
                type="button"
                onClick={next}
                disabled={!answers[q.id]}
                className="mt-3 w-full"
              >
                {i + 1 < data.questions.length ? "Next question" : "Submit answers"}
              </Button>
            </fieldset>
          )}
        </Panel>
      </div>
    </div>
  );
}

async function fetchView(sym: string): Promise<View> {
  try {
    return { s: "ready", data: await getNasdaqChallenge(sym) };
  } catch (e) {
    if (e instanceof ApiClientError && e.code === "TOOL_LOCKED") {
      const missing = (e.details as { error?: { missing_requirements?: string[] } })?.error
        ?.missing_requirements ?? ["level_4", "plan_progress_100", "brier_lte_0.25"];
      const [me, plan, dash] = await Promise.allSettled([
        apiFetch<MeResponse>("/me"),
        apiFetch<PlanResponse>("/plan"),
        apiFetch<DashboardResponse>("/me/dashboard"),
      ]);
      const brierSeries = dash.status === "fulfilled" ? dash.value.brier_over_time : [];
      return {
        s: "locked",
        missing,
        progress: {
          level: me.status === "fulfilled" ? me.value.level : null,
          planPct: plan.status === "fulfilled" ? plan.value.progress_pct : null,
          brier: brierSeries.length ? brierSeries[brierSeries.length - 1].brier : null,
        },
      };
    }
    return { s: "error", message: e instanceof ApiClientError ? e.message : "Couldn't load data." };
  }
}

export function NasdaqVerifier() {
  const [view, setView] = useState<View>({ s: "loading" });
  const [symbol, setSymbol] = useState("NDX");

  useEffect(() => {
    let live = true;
    void fetchView("NDX").then((v) => live && setView(v));
    return () => {
      live = false;
    };
  }, []);

  const reload = (sym: string) => {
    setView({ s: "loading" });
    void fetchView(sym).then(setView);
  };

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <span className="eyebrow">NASDAQ CAPSTONE</span>
          <h1 className="text-2xl font-semibold tracking-tight text-[var(--ink)]">
            Nasdaq literacy check
          </h1>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">
            Read real market data, then answer a few questions about it.
          </p>
        </div>
        {view.s === "ready" && (
          <form
            className="nasdaq-load-form flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              reload(symbol);
            }}
          >
            <label className="sr-only" htmlFor="sym">
              Nasdaq symbol
            </label>
            <Input
              id="sym"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              frameClassName="w-24"
              className="w-24 rounded-md border border-[var(--line)] px-2 py-1.5 text-sm"
            />
            <Button
              variant="secondary"
              type="submit"
              className="h-auto min-h-9 px-3 py-1.5 text-sm"
            >
              Load
            </Button>
            <Button
              variant="quiet"
              type="button"
              onClick={() => {
                setSymbol("NDX");
                reload("NDX");
              }}
              className="h-auto min-h-9 px-3 py-1.5 text-sm"
            >
              NDX benchmark
            </Button>
          </form>
        )}
      </header>
      {view.s === "loading" && (
        <Panel className="p-5" role="status" aria-live="polite">
          <p className="text-sm text-[var(--ink-soft)]">Loading Nasdaq data…</p>
        </Panel>
      )}
      {view.s === "error" && (
        <Alert variant="warning" role="alert" className="text-sm">
          {view.message}
        </Alert>
      )}
      {view.s === "locked" && (
        <>
          <Panel role="note" className="p-4 text-sm text-[var(--ink)]">
            <span>
              <strong>Educational literacy check, not investment advice.</strong> Nothing here
              recommends buying or selling anything.
            </span>
          </Panel>
          <LockedCard missing={view.missing} progress={view.progress} />
        </>
      )}
      {view.s === "ready" && <Verifier key={view.data.challenge_id} data={view.data} />}
    </div>
  );
}
