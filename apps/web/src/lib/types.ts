import type {
  AssessmentStartResponse,
  AssessmentSubmitResponse,
  ClaimRecord,
  ChartPoint,
  DashboardResponse,
  DataOrigin,
  ExplainResponse,
  HealthResponse,
  LessonDetailResponse,
  MeResponse,
  OnboardingAnswerResponse,
  OnboardingResult as OnboardingResultContract,
  OnboardingStartResponse,
  PlanResponse,
  QuestionItem,
  ScenarioAnswerResponse,
  ScenarioNextResponse,
  SourceDetailResponse,
  SubmissionMineItem,
  VerifyResponse,
} from "@/lib/contracts";

export type {
  DataOrigin,
  ProfileExperience,
  ProfileGoal,
  ProfileRecord,
  ProfileResponse,
  ProfileUpdateInput,
  SkillArea,
} from "@/lib/contracts";
export type UserProfile = MeResponse;
export type Health = HealthResponse;
export type Question = QuestionItem;
export type OnboardingStart = OnboardingStartResponse & { data_origin: DataOrigin };
export type OnboardingAnswer = OnboardingAnswerResponse & { data_origin: DataOrigin };
export type OnboardingResult = OnboardingResultContract;
export type LearningPlan = PlanResponse & { data_origin: DataOrigin };
export type PlanLesson = PlanResponse["lessons"][number];
export type Lesson = LessonDetailResponse & { data_origin: DataOrigin };
export type PricePoint = ChartPoint;
export type Scenario = ScenarioNextResponse;
export type ScenarioResult = ScenarioAnswerResponse & { data_origin: DataOrigin };
export type Assessment = AssessmentStartResponse & { data_origin: DataOrigin };
export type AssessmentResult = AssessmentSubmitResponse & { data_origin: DataOrigin };
export type ExplainResult = ExplainResponse & { data_origin: DataOrigin };
export type DashboardData = DashboardResponse & { data_origin: DataOrigin };
export type VerifyResult = VerifyResponse & { data_origin: DataOrigin };
export type SourceDetail = SourceDetailResponse & { data_origin: DataOrigin };
export type SubmissionSummary = SubmissionMineItem & { data_origin: DataOrigin };
export type { ClaimRecord };
