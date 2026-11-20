import { apiFetch, ApiClientError, type ApiFetchOptions } from "@/lib/api-client";
import { authClient } from "@/lib/neon-auth-client";
import * as demo from "@/lib/mock-data";
import type {
  AssessmentStartResponse,
  AssessmentSubmitRequest,
  AssessmentSubmitResponse,
  DashboardResponse,
  ExplainResponse,
  HealthResponse,
  LessonDetailResponse,
  MeResponse,
  OnboardingAnswerRequest,
  OnboardingAnswerResponse,
  OnboardingStartResponse,
  PlanResponse,
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

const useMocks = process.env.NEXT_PUBLIC_USE_MOCKS !== "false";

async function request<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const token = await authClient.getJWTToken?.();
  return apiFetch<T>(path, { ...options, token: token ?? null });
}

function attachOrigin<T extends object>(value: T): T & { data_origin: "real" | "synthetic" } {
  const origin = "data_origin" in value ? value.data_origin : undefined;
  if (origin === "real" || origin === "synthetic") {
    return value as T & { data_origin: "real" | "synthetic" };
  }
  if (useMocks) {
    return { ...value, data_origin: "synthetic" } as T & { data_origin: "synthetic" };
  }
  throw new Error("The API response is missing its data_origin label.");
}

async function getOriginated<T extends object>(
  path: string,
  fixture: T,
  options?: ApiFetchOptions,
): Promise<T & { data_origin: "real" | "synthetic" }> {
  const value = useMocks ? fixture : await request<T>(path, options);
  return attachOrigin(value);
}

const post = (body?: unknown): ApiFetchOptions => ({ method: "POST", body });
const delay = () => new Promise((resolve) => setTimeout(resolve, 180));

export const api = {
  async health(): Promise<HealthResponse> {
    if (useMocks) {
      await delay();
      return { status: "ok", version: "demo", db: "ok", market_data_as_of: "sample" };
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
    const fixture: OnboardingStartResponse = {
      session_id: "demo-session",
      question: demo.onboardingQuestions[0],
    };
    return getOriginated("/onboarding/start", fixture, post({}));
  },

  async onboardingAnswer(
    payload: OnboardingAnswerRequest,
    index: number,
  ): Promise<OnboardingAnswer> {
    const fixture: OnboardingAnswerResponse = {
      next_question: demo.onboardingQuestions[index + 1] ?? null,
      result: index + 1 >= demo.onboardingQuestions.length ? demo.onboardingResult : undefined,
    };
    return getOriginated("/onboarding/answer", fixture, post(payload));
  },

  async plan(): Promise<LearningPlan> {
    return getOriginated<PlanResponse>("/plan", demo.plan);
  },

  async lesson(id: string): Promise<Lesson> {
    const fixture: LessonDetailResponse = { ...demo.lesson, id };
    return getOriginated(`/lessons/${encodeURIComponent(id)}`, fixture);
  },

  async scenarioNext(): Promise<Scenario> {
    if (useMocks) {
      await delay();
      return demo.scenario;
    }
    return request<ScenarioNextResponse>("/scenarios/next", { query: { difficulty: 2 } });
  },

  async scenarioAnswer(id: string, payload: ScenarioAnswerRequest): Promise<ScenarioResult> {
    const fixture: ScenarioAnswerResponse = demo.scenarioResult;
    return getOriginated(`/scenarios/${encodeURIComponent(id)}/answer`, fixture, post(payload));
  },

  async assessmentStart(level: number): Promise<Assessment> {
    const fixture: AssessmentStartResponse = {
      ...demo.assessment,
      assessment_id: `assessment-l${level}`,
    };
    return getOriginated(`/assessments/${level}/start`, fixture, post({}));
  },

  async assessmentSubmit(
    id: string,
    answers: AssessmentSubmitRequest["answers"],
  ): Promise<AssessmentResult> {
    const fixture: AssessmentSubmitResponse = {
      ...demo.assessmentResult,
      new_level: Math.min(4, (Number(id.split("l").at(-1)) || 2) + 1) as 1 | 2 | 3 | 4,
      unlocked: Number(id.split("l").at(-1)) === 3 ? ["dashboard"] : ["verifier"],
    };
    return getOriginated(
      `/assessments/${encodeURIComponent(id)}/submit`,
      fixture,
      post({ answers }),
    );
  },

  async explain(symbol: string, year: number): Promise<ExplainResult> {
    return getOriginated<ExplainResponse>("/explain", demo.explain, {
      query: { symbol, year },
    });
  },

  async dashboard(): Promise<DashboardData> {
    return getOriginated<DashboardResponse>("/me/dashboard", demo.dashboard);
  },

  async verify(payload: VerifyRequest): Promise<VerifyResult> {
    return getOriginated<VerifyResponse>("/verify", demo.verification, post(payload));
  },

  async source(id: string): Promise<SourceDetail> {
    const fixture: SourceDetailResponse = demo.sourceDetail;
    return getOriginated(`/sources/${encodeURIComponent(id)}`, fixture);
  },

  async submissions(): Promise<SubmissionSummary[]> {
    if (useMocks) {
      await delay();
      return demo.submissions.map((item) => ({ ...item, data_origin: "synthetic" as const }));
    }
    const result = await request<SubmissionsMineResponse>("/submissions/mine");
    const origin = attachOrigin(result).data_origin;
    return result.items.map((item: SubmissionMineItem) => ({ ...item, data_origin: origin }));
  },
};

export function isToolLocked(error: unknown): error is ApiClientError {
  return error instanceof ApiClientError && error.code === "TOOL_LOCKED";
}
