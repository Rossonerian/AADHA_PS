export type DataOrigin = "real" | "synthetic";
export type SourceLabel = "reliable" | "semi_reliable" | "not_reliable" | "not_enough_history";
export type SkillArea = "basics" | "reading_stock" | "judging_info" | "risk";
export type Direction = "up" | "down";

export interface UserProfile { id: string; name: string; level: number; unlocks: string[] }
export interface Question { id: string; level: number; skill_area: SkillArea; difficulty: number; text: string; options: string[] }
export interface OnboardingResult { level: number; skills: Partial<Record<SkillArea, number>>; brier: number }
export interface PlanLesson { id: string; title: string; status: "done" | "in_progress" | "locked" | "available"; minutes: number }
export interface LearningPlan { level: number; progress_pct: number; lessons: PlanLesson[] }
export interface Lesson { id: string; title: string; sections: string[]; check_questions: Question[] }
export interface PricePoint { date: string; stock: number; index: number }
export interface Headline { date: string; text: string; source: string }
export interface Scenario {
  id: string; as_of_date: string; window_days: number; data_origin: DataOrigin;
  context: { company: string; chart: PricePoint[]; headlines: Headline[]; numbers: Record<string, number | string> };
}
export interface ScenarioResult { correct: boolean; outcome: { stock_pct: number; index_pct: number }; key_clues: string[]; explanation: string }
export interface AssessmentItem { id: string; text: string; options: string[]; skill_area: SkillArea }
export interface Assessment { assessment_id: string; items: AssessmentItem[] }
export interface AssessmentResult { passed: boolean; score: number; brier: number; new_level?: number; unlocked: string[] }
export interface ExplainResult { chart: PricePoint[]; moves: { date: string; pct: number; events: { text: string; source: string }[] }[]; summary: string; data_origin: DataOrigin }
export interface DashboardData { level: number; skills_over_time: { date: string; basics: number; reading_stock: number; judging_info: number; risk: number }[]; brier_over_time: { date: string; brier: number }[]; scenario_accuracy: { date: string; accuracy: number }[]; data_origin: DataOrigin }
export interface RedFlag { code: string; text: string; evidence: string }
export interface VerifyResult {
  submission_id: string; mode: "basic" | "full"; data_origin: DataOrigin;
  source: { id: string; platform: string; handle: string; label: SourceLabel; score: number; facts: Record<string, string | number | boolean> };
  claim: { symbol?: string; direction?: Direction; status?: string; outcome?: { stock_pct: number; index_pct: number } };
  red_flags: RedFlag[];
}
export interface SourceDetail { source: VerifyResult["source"]; history: { date: string; score: number }[]; recent_claims: { symbol: string; status: string; outcome: string }[]; data_origin: DataOrigin }
export interface SubmissionSummary { submission_id: string; claim: VerifyResult["claim"]; status: string; outcome?: { stock_pct: number; index_pct: number }; data_origin: DataOrigin }
export interface ApiError { error: { code: string; message: string; required_level?: number } }
