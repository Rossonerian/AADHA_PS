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

function Badge({ origin }: { origin: "real" | "synthetic" }) {
  return origin === "real" ? (
    <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
      REAL DATA
    </span>
  ) : (
    <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
      SYNTHETIC DEMO DATA
    </span>
  );
}

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
      <div className="flex justify-between text-sm text-gray-800">
        <span>
          <span aria-hidden="true">{ok ? "✓" : "○"}</span> {label}
        </span>
        <span className="text-gray-600">{value}</span>
      </div>
      <div className="mt-1 h-1.5 rounded bg-gray-100" role="presentation">
        <div
          className={`h-1.5 rounded ${ok ? "bg-emerald-600" : "bg-amber-500"}`}
          style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
        />
      </div>
    </li>
  );
}

function LockedCard({ missing, progress }: { missing: string[]; progress: Progress }) {
  const planOk = !missing.includes("plan_progress_100");
  const brierOk = !missing.includes("brier_lte_0.25");
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-5" aria-labelledby="cap-title">
      <div className="flex items-center justify-between gap-3">
        <h2 id="cap-title" className="text-base font-semibold text-gray-900">
          Final capstone: Nasdaq literacy check
        </h2>
        <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700">Locked</span>
      </div>
      <p className="mt-2 text-sm text-gray-600">
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
    </section>
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
      <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900" role="note">
        {data.disclaimer}
      </p>
      <div className="grid gap-4 md:grid-cols-[1.25fr_1fr]">
        <section
          className="rounded-lg border border-gray-200 bg-white p-4"
          aria-label="Market snapshot"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-gray-900">
              {snap.name} · {snap.symbol}
            </h2>
            <Badge origin={data.data_origin} />
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
              <div key={k} className="rounded bg-gray-50 px-2 py-1.5">
                <dt className="text-xs text-gray-500">{k}</dt>
                <dd className="font-medium text-gray-900">{v}</dd>
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
                  <CartesianGrid stroke="#e5e7eb" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={40} />
                  <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} width={44} />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="close"
                    stroke="#2a78d6"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="pt-16 text-center text-sm text-gray-500">
                Price history isn&apos;t available.
              </p>
            )}
          </div>
          <a
            href={data.nasdaq_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-block text-sm text-blue-700 underline"
          >
            ↗ Open full page on Nasdaq.com
          </a>
        </section>

        <section
          className="rounded-lg border border-gray-200 bg-white p-4"
          aria-label="Comprehension check"
        >
          {result ? (
            <div aria-live="polite">
              <h2 className="text-base font-semibold text-gray-900">
                {result.passed ? "Passed" : "Not passed yet"}
              </h2>
              <p className="mt-1 text-sm text-gray-700">
                {Math.round(result.score * 100)}% correct · Brier {result.brier.toFixed(2)}
              </p>
              <p className="mt-2 text-sm text-gray-600">{result.feedback}</p>
              <ul className="mt-3 space-y-1 text-sm">
                {result.results.map((r) => (
                  <li
                    key={r.question_id}
                    className={r.correct ? "text-emerald-700" : "text-amber-800"}
                  >
                    {r.correct ? "✓" : "✗"} {r.explanation}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <fieldset>
              <legend className="flex w-full justify-between text-sm">
                <span className="font-semibold text-gray-900">Comprehension check</span>
                <span className="text-gray-500">
                  Q {i + 1} of {data.questions.length}
                </span>
              </legend>
              <p className="mt-2 text-sm text-gray-800">{q.text}</p>
              <div className="mt-2 space-y-1.5">
                {q.options.map((o) => (
                  <label
                    key={o}
                    className={`flex cursor-pointer items-center gap-2 rounded border px-2.5 py-1.5 text-sm ${
                      answers[q.id] === o ? "border-blue-500 bg-blue-50" : "border-gray-200"
                    }`}
                  >
                    <input
                      type="radio"
                      name={q.id}
                      checked={answers[q.id] === o}
                      onChange={() => {
                        setAnswers({ ...answers, [q.id]: o });
                        setErr(null);
                      }}
                    />
                    {o}
                  </label>
                ))}
              </div>
              <label className="mt-3 block text-sm text-gray-700">
                Confidence: <span className="font-medium">{conf}%</span>
                <input
                  type="range"
                  min={50}
                  max={100}
                  step={5}
                  value={conf}
                  onChange={(e) => setConf(Number(e.target.value))}
                  className="mt-1 w-full"
                />
              </label>
              {err && (
                <p className="mt-2 text-sm text-red-700" role="alert">
                  {err}
                </p>
              )}
              <button
                type="button"
                onClick={next}
                className="mt-3 w-full rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800"
              >
                {i + 1 < data.questions.length ? "Next question" : "Submit answers"}
              </button>
            </fieldset>
          )}
        </section>
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
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-gray-900">
          Nasdaq literacy check
        </h1>
        {view.s === "ready" && (
          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              reload(symbol);
            }}
          >
            <label className="sr-only" htmlFor="sym">
              Nasdaq symbol
            </label>
            <input
              id="sym"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-24 rounded-md border border-gray-300 px-2 py-1.5 text-sm"
            />
            <button type="submit" className="rounded-md border border-gray-300 px-3 py-1.5 text-sm">
              Load
            </button>
            <button
              type="button"
              onClick={() => {
                setSymbol("NDX");
                reload("NDX");
              }}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm"
            >
              NDX benchmark
            </button>
          </form>
        )}
      </header>
      {view.s === "loading" && <p className="text-sm text-gray-600">Loading…</p>}
      {view.s === "error" && (
        <p className="text-sm text-amber-800" role="alert">
          {view.message}
        </p>
      )}
      {view.s === "locked" && <LockedCard missing={view.missing} progress={view.progress} />}
      {view.s === "ready" && <Verifier key={view.data.challenge_id} data={view.data} />}
    </div>
  );
}
