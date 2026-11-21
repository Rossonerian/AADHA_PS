/**
 * PaisaProof API v1 TypeScript contracts.
 * Strictly aligned with docs/SOURCE_OF_TRUTH.md Sections 7 & 8.
 */

export type DataOrigin = "real" | "synthetic";

export type SourceLabel = "reliable" | "semi_reliable" | "not_reliable" | "not_enough_history";

export type RedFlagCode =
  | "guaranteed_returns"
  | "urgency"
  | "illiquid_small_cap"
  | "surveillance_list"
  | "pre_post_volume_spike"
  | "not_sebi_registered"
  | "vague_claim"
  | "deleted_post";

export type UserLevel = 1 | 2 | 3 | 4;

export type ToolName =
  "scenarios" | "red_flag_check" | "explain_stock" | "verifier" | "dashboard" | "nasdaq_verifier";

export type SkillArea = "basics" | "reading_stock" | "judging_info" | "risk";

export type ClaimStatus = "open" | "scored" | "needs_review" | "unscorable";

export type ClaimDirection = "up" | "down";

export type LessonStatus = "locked" | "not_started" | "in_progress" | "completed";

export type ProfileGoal = "learn_basics" | "avoid_scams" | "invest_smarter" | "other";

export type ProfileExperience = "new" | "some" | "experienced";

export interface ProfileRecord {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  goal: ProfileGoal | null;
  experience: ProfileExperience | null;
  weekly_minutes: number | null;
  onboarding_completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProfileUpdateInput {
  display_name?: string;
  avatar_url?: string | null;
  goal?: ProfileGoal | null;
  experience?: ProfileExperience | null;
  weekly_minutes?: number | null;
}

export interface ProfileResponse {
  profile: ProfileRecord;
  onboarding_completed: boolean;
  data_origin: DataOrigin;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  required_level?: UserLevel;
  missing_requirements?: string[];
}

export interface ApiErrorEnvelope {
  error: ApiErrorDetail;
}

/* -------------------------------------------------------------------------- */
/* Shared domain primitives                                                   */
/* -------------------------------------------------------------------------- */

export interface QuestionItem {
  id: string;
  text: string;
  skill_area?: SkillArea;
  difficulty?: number;
  options: string[];
  /** Display text per option value (used when the answer value is not human readable). */
  labels?: Record<string, string>;
}

export interface ChartPoint {
  date: string;
  open?: number;
  high?: number;
  low?: number;
  close: number;
  volume?: number;
}

export interface RedFlagItem {
  code: RedFlagCode;
  text: string;
  evidence: string;
}

export interface VerifySourceSummary {
  id: string;
  platform: string;
  handle: string | null;
  label: SourceLabel;
  score: number | null;
  facts: Record<string, unknown>;
  sebi_reg_no?: string | null;
  scored_claims?: number;
  data_origin?: DataOrigin;
}

export interface ClaimRecord {
  tip_facts?: TipFact[];
  evidence_start_s?: number | null;
  evidence_end_s?: number | null;
  id: string;
  submission_id?: string;
  symbol: string | null;
  direction: ClaimDirection | null;
  entry: number | null;
  target: number | null;
  stop: number | null;
  window_end: string | null;
  scorable: boolean;
  status: ClaimStatus;
  outcome: Record<string, unknown> | null;
}

/* -------------------------------------------------------------------------- */
/* 1. GET /api/v1/health                                                      */
/* -------------------------------------------------------------------------- */

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  db: "ok" | "error";
  market_data_as_of: string | null;
}

/* -------------------------------------------------------------------------- */
/* 2. GET /api/v1/me                                                          */
/* -------------------------------------------------------------------------- */

export interface MeResponse {
  id: string;
  name: string;
  level: UserLevel;
  unlocks: ToolName[];
  profile: ProfileRecord;
  onboarding_completed: boolean;
  data_origin?: DataOrigin;
}

/* -------------------------------------------------------------------------- */
/* 3. POST /api/v1/onboarding/start                                           */
/* -------------------------------------------------------------------------- */

export interface OnboardingStartResponse {
  session_id: string;
  question: QuestionItem;
}

/* -------------------------------------------------------------------------- */
/* 4. POST /api/v1/onboarding/answer                                          */
/* -------------------------------------------------------------------------- */

export interface OnboardingAnswerRequest {
  session_id: string;
  question_id: string;
  answer: string;
  confidence: number;
}

export interface OnboardingResult {
  level: UserLevel;
  skills: Record<SkillArea, number>;
  brier: number;
}

export interface OnboardingAnswerResponse {
  next_question: QuestionItem | null;
  result?: OnboardingResult;
}

/* -------------------------------------------------------------------------- */
/* 5. GET /api/v1/plan                                                        */
/* -------------------------------------------------------------------------- */

export interface PlanLessonItem {
  id: string;
  title: string;
  status: LessonStatus;
  minutes: number;
}

export interface PlanResponse {
  level: UserLevel;
  progress_pct: number;
  lessons: PlanLessonItem[];
}

/* -------------------------------------------------------------------------- */
/* 6. GET /api/v1/lessons/{id}                                                */
/* -------------------------------------------------------------------------- */

export interface LessonSection {
  heading: string;
  body: string;
  example?: string;
  takeaway?: string | null;
}

export interface LessonDetailResponse {
  id: string;
  title: string;
  level?: number;
  minutes?: number;
  skill_area?: SkillArea;
  sections: LessonSection[];
  check_questions: QuestionItem[];
}

/** One entry of POST /lessons/{id}/check `feedback` (backend types it as dict). */
export interface LessonCheckFeedbackItem {
  question_id?: string;
  correct?: boolean;
  explanation?: string;
}

/** Response of POST /api/v1/lessons/{id}/check. */
export interface LessonCheckResponse {
  lesson_id?: string;
  passed: boolean;
  score_pct: number;
  plan_progress_pct: number;
  correct_count?: number;
  total_count?: number;
  feedback?: LessonCheckFeedbackItem[];
}

/* -------------------------------------------------------------------------- */
/* 7. GET /api/v1/scenarios/next?difficulty=                                  */
/* -------------------------------------------------------------------------- */

export interface ScenarioHeadline {
  date?: string;
  text: string;
  source?: string;
}

export interface ScenarioContext {
  company: string;
  chart: ChartPoint[];
  headlines: ScenarioHeadline[];
  numbers: Record<string, string | number | null>;
}

export interface ScenarioNextResponse {
  id: string;
  as_of_date: string;
  window_days: number;
  context: ScenarioContext;
  data_origin: DataOrigin;
}

/* -------------------------------------------------------------------------- */
/* 8. POST /api/v1/scenarios/{id}/answer                                      */
/* -------------------------------------------------------------------------- */

export interface ScenarioAnswerRequest {
  direction: ClaimDirection;
  confidence: number;
  clues: string[];
}

export interface ScenarioOutcome {
  stock_pct: number;
  index_pct: number;
}

export interface ScenarioAnswerResponse {
  correct: boolean;
  outcome: ScenarioOutcome;
  key_clues: string[];
  explanation: string;
}

/* -------------------------------------------------------------------------- */
/* 9. POST /api/v1/assessments/{level}/start                                  */
/* -------------------------------------------------------------------------- */

export interface AssessmentStartResponse {
  assessment_id: string;
  items: QuestionItem[];
}

/* -------------------------------------------------------------------------- */
/* 10. POST /api/v1/assessments/{id}/submit                                   */
/* -------------------------------------------------------------------------- */

export interface AssessmentAnswerInput {
  item_id: string;
  answer: string;
  confidence: number;
}

export interface AssessmentSubmitRequest {
  answers: AssessmentAnswerInput[];
}

export interface AssessmentSubmitResponse {
  passed: boolean;
  score: number;
  brier: number;
  new_level?: UserLevel;
  unlocked: ToolName[];
}

/* -------------------------------------------------------------------------- */
/* 11. GET /api/v1/explain?symbol=&year=                                      */
/* -------------------------------------------------------------------------- */

export interface ExplainMoveEvent {
  text: string;
  source: string;
}

export interface ExplainMove {
  date: string;
  pct: number;
  events: ExplainMoveEvent[];
}

export interface ExplainResponse {
  chart: ChartPoint[];
  moves: ExplainMove[];
  summary: string;
  data_origin?: DataOrigin;
}

/* -------------------------------------------------------------------------- */
/* 12. GET /api/v1/me/dashboard                                               */
/* -------------------------------------------------------------------------- */

export interface DashboardSkillPoint {
  date: string;
  skills: Record<SkillArea, number>;
}

export interface DashboardBrierPoint {
  date: string;
  brier: number;
}

export interface DashboardScenarioAccuracyPoint {
  date: string;
  accuracy: number;
  attempts?: number;
}

export interface DashboardResponse {
  level: UserLevel;
  skills_over_time: DashboardSkillPoint[];
  brier_over_time: DashboardBrierPoint[];
  scenario_accuracy: DashboardScenarioAccuracyPoint[];
}

/* -------------------------------------------------------------------------- */
/* 13. POST /api/v1/verify                                                    */
/* -------------------------------------------------------------------------- */

export interface VerifyRequest {
  url?: string;
  text?: string;
  image_base64?: string;
  user_guess?: string;
  user_confidence?: number;
}

export type TipFactCode =
  | "required_move_pct"
  | "move_base_rate"
  | "pre_post_run_up_pct"
  | "pre_post_volume_ratio"
  | "illiquid_small_cap"
  | "surveillance_list"
  | "stop_distance_pct"
  | "reward_risk";
export interface TipFact {
  code: TipFactCode;
  text: string;
  value: number | boolean | string | null;
  as_of: string;
  data_origin: DataOrigin;
}
export interface SourceMention {
  url: string;
  title: string;
  published_at: string | null;
  platform: string;
  fetched_at: string;
  data_origin: DataOrigin;
}

export interface VerifyResponse {
  submission_id: string;
  source: VerifySourceSummary | null;
  claim: ClaimRecord | null;
  tip_facts?: TipFact[];
  claims?: ClaimRecord[];
  red_flags: RedFlagItem[];
  mode: "basic" | "full";
  data_origin?: DataOrigin;
}

/* -------------------------------------------------------------------------- */
/* 14. GET /api/v1/sources/{id}                                               */
/* -------------------------------------------------------------------------- */

export interface SourceRatingHistoryItem {
  formula_version?: string | null;
  score: number | null;
  label: SourceLabel;
  reason: string;
  changed_at: string;
}

export interface SourceDetailResponse {
  enforcement?: { flag: boolean | null; refs: Record<string, unknown>[]; data_origin: DataOrigin };
  mentions?: SourceMention[];
  source: VerifySourceSummary;
  history: SourceRatingHistoryItem[];
  recent_claims: ClaimRecord[];
}

/* -------------------------------------------------------------------------- */
/* 15. GET /api/v1/submissions/mine                                           */
/* -------------------------------------------------------------------------- */

export interface SubmissionMineItem {
  submission_id: string;
  claim: ClaimRecord | null;
  status: ClaimStatus;
  outcome: Record<string, unknown> | null;
}

export interface SubmissionsMineResponse {
  items: SubmissionMineItem[];
}

/* -------------------------------------------------------------------------- */
/* 16–17. Nasdaq literacy verifier (capstone, gated server-side)              */
/* -------------------------------------------------------------------------- */

export interface NasdaqSnapshot {
  symbol: string;
  name: string;
  sector: string | null;
  price: number | null;
  day_low: number | null;
  day_high: number | null;
  week52_low: number | null;
  week52_high: number | null;
  market_cap_musd: number | null;
  pe_ttm: number | null;
  chart: { date: string; close: number }[];
  data_origin: DataOrigin;
}

export interface NasdaqQuestion {
  id: string;
  text: string;
  options: string[];
}

/** GET /api/v1/nasdaq-verifier/challenge?symbol= */
export interface NasdaqChallengeResponse {
  challenge_id: string;
  data_origin: DataOrigin;
  as_of: string;
  snapshot: NasdaqSnapshot;
  nasdaq_url: string;
  disclaimer: string;
  questions: NasdaqQuestion[];
}

export interface NasdaqAnswerInput {
  question_id: string;
  answer: string;
  confidence: number;
}

/** POST /api/v1/nasdaq-verifier/submit */
export interface NasdaqSubmitRequest {
  challenge_id: string;
  answers: NasdaqAnswerInput[];
}

export interface NasdaqSubmitResponse {
  passed: boolean;
  score: number;
  brier: number;
  results: { question_id: string; correct: boolean; correct_answer: string; explanation: string }[];
  feedback: string;
}
