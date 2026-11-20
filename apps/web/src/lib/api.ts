import { apiFetch, ApiClientError, type ApiFetchOptions } from "@/lib/api-client";
import { authClient } from "@/lib/neon-auth-client";
import type {
  AssessmentStartResponse,
  AssessmentSubmitRequest,
  AssessmentSubmitResponse,
  DashboardResponse,
  ExplainResponse,
  HealthResponse,
  LessonCheckResponse,
  LessonDetailResponse,
  MeResponse,
  OnboardingAnswerRequest,
  OnboardingAnswerResponse,
  OnboardingStartResponse,
  PlanResponse,
  QuestionItem,
  ScenarioAnswerRequest,
  ScenarioAnswerResponse,
  ScenarioNextResponse,
  SourceDetailResponse,
  SubmissionMineItem,
  SubmissionsMineResponse,
  VerifyRequest,
  VerifyResponse,
} from "@/lib/contracts";
import type {
  Assessment,
  AssessmentResult,
  DashboardData,
  ExplainResult,
  LearningPlan,
  Lesson,
  OnboardingAnswer,
  OnboardingStart,
  Scenario,
  ScenarioResult,
  SourceDetail,
  SubmissionSummary,
  VerifyResult,
} from "@/lib/types";

// Fixtures exist only for local development and automated tests. They are never
// reachable in a production build, and there is no in-app way to switch them on.
const useMocks =
  process.env.NODE_ENV !== "production" && process.env.NEXT_PUBLIC_USE_MOCKS === "true";
export const mocksEnabled = useMocks;

// Loaded only when fixtures are enabled; the branch is removed from production bundles.
/* eslint-disable @typescript-eslint/no-require-imports */
const demo = (useMocks ? require("@/lib/mock-data") : null) as typeof import("@/lib/mock-data");
/* eslint-enable @typescript-eslint/no-require-imports */

async function request<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const token = await (
    authClient as typeof authClient & { getJWTToken?: () => Promise<string | null> }
  ).getJWTToken?.();
  return apiFetch<T>(path, { ...options, token: token ?? null });
}

/** Find the first data_origin label in a response (top level, then nested). */
function findOrigin(value: unknown, depth = 0): "real" | "synthetic" | undefined {
  if (!value || typeof value !== "object" || depth > 4) return undefined;
  const record = value as Record<string, unknown>;
  if (record.data_origin === "real" || record.data_origin === "synthetic")
    return record.data_origin;
  for (const child of Object.values(record)) {
    const found = findOrigin(child, depth + 1);
    if (found) return found;
  }
  return undefined;
}

/**
 * Every payload shown in the UI carries a Real/Synthetic label. The API labels most
 * responses itself; for the few that do not, use a nested label if present and otherwise
 * the conservative "synthetic" (never claim real data that was not labelled real).
 */
function attachOrigin<T extends object>(value: T): T & { data_origin: "real" | "synthetic" } {
  return { ...value, data_origin: findOrigin(value) ?? "synthetic" } as T & {
    data_origin: "real" | "synthetic";
  };
}

/** Stable per-question shuffle so the correct answer is not always in the same slot. */
function hash(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function shuffleOptions(id: string, options: string[]): string[] {
  const out = [...options];
  let seed = hash(id);
  for (let i = out.length - 1; i > 0; i -= 1) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    const j = seed % (i + 1);
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function normalizeQuestion<T extends { id: string; options: string[] }>(question: T): T {
  return { ...question, options: shuffleOptions(question.id, question.options) };
}

type RawAssessmentItem = {
  item_id: string;
  item_type: string;
  prompt: Record<string, unknown>;
};

function normalizeAssessment(raw: {
  assessment_id: string;
  items: RawAssessmentItem[];
}): AssessmentStartResponse {
  return {
    assessment_id: raw.assessment_id,
    items: raw.items.map((item): QuestionItem => {
      const prompt = item.prompt as Record<string, unknown>;
      if (item.item_type === "scenario") {
        const context = (prompt.context ?? {}) as {
          company?: string;
          headlines?: string[];
          numbers?: Record<string, unknown>;
        };
        const clues = (context.headlines ?? []).map((line) => `• ${line}`).join("\n");
        return {
          id: item.item_id,
          text: `As of ${String(prompt.as_of_date ?? "the case date")}, over the next ${String(prompt.window_days ?? 20)} trading days, will ${context.company ?? "the company"} outperform or underperform the NIFTY 50?${clues ? `\n${clues}` : ""}`,
          options: ["up", "down"],
          labels: { up: "Outperform the index", down: "Underperform the index" },
          difficulty: Number(prompt.difficulty ?? 2),
        };
      }
      return normalizeQuestion({
        id: item.item_id,
        text: String(prompt.text ?? ""),
        options: (prompt.options as string[]) ?? [],
        skill_area: prompt.skill_area as QuestionItem["skill_area"],
        difficulty: prompt.difficulty as number | undefined,
      });
    }),
  };
}

function shortDate(value: string): string {
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? value
    : d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

type RawDashboard = {
  level: number;
  skills_over_time: Record<string, unknown>[];
  brier_over_time: Record<string, unknown>[];
  scenario_accuracy: Record<string, unknown>[];
};

function normalizeDashboard(raw: RawDashboard): DashboardResponse {
  return {
    level: raw.level as DashboardResponse["level"],
    skills_over_time: raw.skills_over_time.map((row) => ({
      date: shortDate(String(row.measured_at ?? row.date ?? "")),
      skills: {
        basics: Number(row.basics ?? 0),
        reading_stock: Number(row.reading_stock ?? 0),
        judging_info: Number(row.judging_info ?? 0),
        risk: Number(row.risk ?? 0),
      },
    })),
    brier_over_time: raw.brier_over_time.map((row) => ({
      date: shortDate(String(row.measured_at ?? row.date ?? "")),
      brier: Number(row.brier ?? 0),
    })),
    scenario_accuracy: raw.scenario_accuracy.map((row) => ({
      date:
        row.difficulty !== undefined ? `Difficulty ${String(row.difficulty)}` : String(row.date),
      accuracy: Number(row.accuracy_pct ?? row.accuracy ?? 0),
      attempts: row.attempts === undefined ? undefined : Number(row.attempts),
    })),
  };
}

function normalizeScenario(raw: ScenarioNextResponse): ScenarioNextResponse {
  return {
    ...raw,
    context: {
      ...raw.context,
      headlines: (raw.context.headlines as unknown as (string | { text: string })[]).map((h) =>
        typeof h === "string" ? { text: h } : h,
      ),
    },
  };
}

function formatEvidence(evidence: unknown): string {
  if (typeof evidence === "string") return evidence;
  if (!evidence || typeof evidence !== "object") return "";
  return Object.entries(evidence as Record<string, unknown>)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${String(v)}`)
    .join(" · ");
}

function normalizeVerify(raw: VerifyResponse): VerifyResponse {
  return {
    ...raw,
    red_flags: raw.red_flags.map((flag) => ({
      ...flag,
      evidence: formatEvidence(flag.evidence),
    })),
  };
}

async function getOriginated<T extends object, R extends object = T>(
  path: string,
  fixture: () => T,
  options?: ApiFetchOptions,
  transform?: (raw: R) => T,
): Promise<T & { data_origin: "real" | "synthetic" }> {
  if (useMocks) return attachOrigin(fixture());
  const raw = await request<R>(path, options);
  const origin = findOrigin(raw);
  const value = transform ? transform(raw) : (raw as unknown as T);
  return attachOrigin(origin ? { ...value, data_origin: origin } : value);
}

const post = (body?: unknown): ApiFetchOptions => ({ method: "POST", body });
const delay = () => new Promise((resolve) => setTimeout(resolve, 180));

export const api = {
  async health(): Promise<HealthResponse> {
    if (useMocks) {
      await delay();
      return { status: "ok", version: "dev", db: "ok", market_data_as_of: "fixture" };
    }
    return request<HealthResponse>("/health");
  },

  async me(): Promise<MeResponse> {
    if (useMocks) {
      await delay();
      return demo.me;
    }
    return request<MeResponse>("/me");
  },

  async onboardingStart(): Promise<OnboardingStart> {
    const fixture = (): OnboardingStartResponse => ({
      session_id: "dev-session",
      question: demo.onboardingQuestions[0],
    });
    return getOriginated<OnboardingStartResponse>(
      "/onboarding/start",
      fixture,
      post({}),
      (raw) => ({ ...raw, question: normalizeQuestion(raw.question) }),
    );
  },

  async onboardingAnswer(
    payload: OnboardingAnswerRequest,
    index: number,
  ): Promise<OnboardingAnswer> {
    const fixture = (): OnboardingAnswerResponse => ({
      next_question: demo.onboardingQuestions[index + 1] ?? null,
      result: index + 1 >= demo.onboardingQuestions.length ? demo.onboardingResult : undefined,
    });
    return getOriginated<OnboardingAnswerResponse>(
      "/onboarding/answer",
      fixture,
      post(payload),
      (raw) => ({
        ...raw,
        next_question: raw.next_question ? normalizeQuestion(raw.next_question) : null,
        result: raw.result ?? undefined,
      }),
    );
  },

  async plan(): Promise<LearningPlan> {
    return getOriginated<PlanResponse>("/plan", () => demo.plan);
  },

  async lesson(id: string): Promise<Lesson> {
    const fixture = (): LessonDetailResponse => ({ ...demo.lesson, id });
    return getOriginated<LessonDetailResponse>(
      `/lessons/${encodeURIComponent(id)}`,
      fixture,
      undefined,
      (raw) => ({
        ...raw,
        check_questions: raw.check_questions.map((q) => normalizeQuestion(q)),
      }),
    );
  },

  async lessonCheck(
    id: string,
    answers: { question_id: string; answer: string; confidence?: number }[],
  ): Promise<LessonCheckResponse> {
    if (useMocks) {
      await delay();
      return demo.lessonCheck;
    }
    return request(`/lessons/${encodeURIComponent(id)}/check`, post({ answers }));
  },

  async scenarioNext(): Promise<Scenario> {
    if (useMocks) {
      await delay();
      return demo.scenario;
    }
    return normalizeScenario(
      await request<ScenarioNextResponse>("/scenarios/next", { query: { difficulty: 2 } }),
    );
  },

  async scenarioAnswer(id: string, payload: ScenarioAnswerRequest): Promise<ScenarioResult> {
    const fixture = (): ScenarioAnswerResponse => demo.scenarioResult;
    return getOriginated(`/scenarios/${encodeURIComponent(id)}/answer`, fixture, post(payload));
  },

  async assessmentStart(level: number): Promise<Assessment> {
    const fixture = (): AssessmentStartResponse => ({
      ...demo.assessment,
      assessment_id: `assessment-l${level}`,
    });
    return getOriginated<
      AssessmentStartResponse,
      { assessment_id: string; items: RawAssessmentItem[] }
    >(`/assessments/${level}/start`, fixture, post({}), normalizeAssessment);
  },

  async assessmentSubmit(
    id: string,
    answers: AssessmentSubmitRequest["answers"],
  ): Promise<AssessmentResult> {
    const fixture = (): AssessmentSubmitResponse => ({
      ...demo.assessmentResult,
      new_level: Math.min(4, (Number(id.split("l").at(-1)) || 2) + 1) as 1 | 2 | 3 | 4,
      unlocked: Number(id.split("l").at(-1)) === 3 ? ["dashboard"] : ["verifier"],
    });
    return getOriginated(
      `/assessments/${encodeURIComponent(id)}/submit`,
      fixture,
      post({ answers }),
    );
  },

  async explain(symbol: string, year: number): Promise<ExplainResult> {
    return getOriginated<ExplainResponse>("/explain", () => demo.explain, {
      query: { symbol, year },
    });
  },

  async dashboard(): Promise<DashboardData> {
    return getOriginated<DashboardResponse, RawDashboard>(
      "/me/dashboard",
      () => demo.dashboard,
      undefined,
      normalizeDashboard,
    );
  },

  async verify(payload: VerifyRequest): Promise<VerifyResult> {
    return getOriginated<VerifyResponse>(
      "/verify",
      () => demo.verification,
      post(payload),
      normalizeVerify,
    );
  },

  async source(id: string): Promise<SourceDetail> {
    const fixture = (): SourceDetailResponse => demo.sourceDetail;
    return getOriginated(`/sources/${encodeURIComponent(id)}`, fixture);
  },

  async submissions(): Promise<SubmissionSummary[]> {
    if (useMocks) {
      await delay();
      return demo.submissions.map((item) => ({ ...item, data_origin: "synthetic" as const }));
    }
    type Item = SubmissionMineItem & { data_origin?: string };
    const result = await request<{ items: Item[] }>("/submissions/mine");
    return result.items.map((item) => ({
      ...item,
      data_origin: item.data_origin === "real" ? "real" : ("synthetic" as const),
    }));
  },
};

export function isToolLocked(error: unknown): error is ApiClientError {
  return error instanceof ApiClientError && error.code === "TOOL_LOCKED";
}
