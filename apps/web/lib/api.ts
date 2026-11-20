import * as demo from "@/lib/mock-data";
import { supabase } from "@/lib/supabase";
import type { Assessment, AssessmentResult, DashboardData, ExplainResult, LearningPlan, Lesson, OnboardingResult, Question, Scenario, ScenarioResult, SourceDetail, SubmissionSummary, UserProfile, VerifyResult } from "@/lib/types";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const useMocks = process.env.NEXT_PUBLIC_USE_MOCKS !== "false";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { data } = supabase ? await supabase.auth.getSession() : { data: { session: null } };
  const token = data.session?.access_token;
  const response = await fetch(`${apiBase}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init?.headers } });
  const body = await response.json();
  if (!response.ok) throw body;
  return body as T;
}

function post(body: unknown): RequestInit { return { method: "POST", body: JSON.stringify(body) }; }
const delay = () => new Promise((resolve) => setTimeout(resolve, 180));

// Each endpoint in SOURCE_OF_TRUTH_1.md has a typed live path and a local fixture.
export const api = {
  async health() { if (useMocks) { await delay(); return { status: "ok", version: "demo", db: "mock", market_data_as_of: "sample" }; } return request<{ status: string; version: string; db: string; market_data_as_of: string }>("/health"); },
  async me(): Promise<UserProfile> { if (useMocks) { await delay(); return demo.me; } return request<UserProfile>("/me"); },
  async onboardingStart() { if (useMocks) { await delay(); return { session_id: "demo-session", question: demo.onboardingQuestions[0] }; } return request<{ session_id: string; question: Question }>("/onboarding/start", post({})); },
  async onboardingAnswer(payload: { session_id: string; question_id: string; answer: string; confidence: number }, index: number) { if (useMocks) { await delay(); const next_question = demo.onboardingQuestions[index + 1] ?? null; return { next_question, result: next_question ? undefined : demo.onboardingResult }; } return request<{ next_question: Question | null; result?: OnboardingResult }>("/onboarding/answer", post(payload)); },
  async plan(): Promise<LearningPlan> { if (useMocks) { await delay(); return demo.plan; } return request<LearningPlan>("/plan"); },
  async lesson(id: string): Promise<Lesson> { if (useMocks) { await delay(); return { ...demo.lesson, id }; } return request<Lesson>(`/lessons/${encodeURIComponent(id)}`); },
  async scenarioNext(): Promise<Scenario> { if (useMocks) { await delay(); return demo.scenario; } return request<Scenario>("/scenarios/next?difficulty=2"); },
  async scenarioAnswer(id: string, payload: { direction: "up" | "down"; confidence: number; clues: string[] }): Promise<ScenarioResult> { if (useMocks) { await delay(); void id; void payload; return demo.scenarioResult; } return request<ScenarioResult>(`/scenarios/${encodeURIComponent(id)}/answer`, post(payload)); },
  async assessmentStart(level: number): Promise<Assessment> { if (useMocks) { await delay(); return { ...demo.assessment, assessment_id: `assessment-l${level}` }; } return request<Assessment>(`/assessments/${level}/start`, post({})); },
  async assessmentSubmit(id: string, answers: { item_id: string; answer: string; confidence: number }[]): Promise<AssessmentResult> { if (useMocks) { await delay(); void answers; const level = Number(id.split("l").at(-1)) || 2; const new_level = Math.min(4, level + 1); const unlockByLevel: Record<number, string[]> = { 2: ["verifier"], 3: ["dashboard"] }; return { ...demo.assessmentResult, new_level, unlocked: unlockByLevel[level] ?? [] }; } return request<AssessmentResult>(`/assessments/${encodeURIComponent(id)}/submit`, post({ answers })); },
  async explain(symbol: string, year: number): Promise<ExplainResult> { if (useMocks) { await delay(); void symbol; void year; return demo.explain; } return request<ExplainResult>(`/explain?symbol=${encodeURIComponent(symbol)}&year=${year}`); },
  async dashboard(): Promise<DashboardData> { if (useMocks) { await delay(); return demo.dashboard; } return request<DashboardData>("/me/dashboard"); },
  async verify(payload: { url?: string; text?: string; image_base64?: string; user_guess?: string; user_confidence?: number }): Promise<VerifyResult> { if (useMocks) { await delay(); void payload; return demo.verification; } return request<VerifyResult>("/verify", post(payload)); },
  async source(id: string): Promise<SourceDetail> { if (useMocks) { await delay(); void id; return demo.sourceDetail; } return request<SourceDetail>(`/sources/${encodeURIComponent(id)}`); },
  async submissions(): Promise<SubmissionSummary[]> { if (useMocks) { await delay(); return demo.submissions; } const result = await request<{ items: SubmissionSummary[] }>("/submissions/mine"); return result.items; },
};

export function isToolLocked(error: unknown): error is { error: { code: "TOOL_LOCKED"; required_level: number } } {
  return typeof error === "object" && error !== null && "error" in error && typeof (error as { error?: { code?: string } }).error === "object" && (error as { error: { code?: string } }).error.code === "TOOL_LOCKED";
}
