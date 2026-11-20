import type { Assessment, DashboardData, ExplainResult, LearningPlan, Lesson, OnboardingResult, PlanLesson, Question, Scenario, ScenarioResult, SourceDetail, SubmissionSummary, UserProfile, VerifyResult } from "@/lib/types";

export const me: UserProfile = { id: "demo-user", name: "Ananya", level: 2, unlocks: ["scenarios", "red_flag_check", "explain_stock"] };
export const onboardingQuestions: Question[] = [
  { id: "onb-1", level: 1, skill_area: "basics", difficulty: 1, text: "A company’s share price fell 8% today. What can you safely conclude from that alone?", options: ["The company is failing", "The price fell today; more context is needed", "It will rise tomorrow", "Nothing can ever be learned"] },
  { id: "onb-2", level: 1, skill_area: "judging_info", difficulty: 2, text: "A forwarded message promises a large return but names no source. What is the most useful first check?", options: ["Forward it to friends", "Check who made the claim and what evidence they cite", "Assume it is true if it has many likes", "Ignore the date"] },
  { id: "onb-3", level: 1, skill_area: "risk", difficulty: 2, text: "What does a 70% confidence estimate mean?", options: ["The outcome is certain", "You expect about 7 in 10 similar calls to be right", "The price will move 70%", "You should act now"] },
];
export const onboardingResult: OnboardingResult = { level: 2, skills: { basics: 72, reading_stock: 58, judging_info: 44, risk: 64 }, brier: 0.22 };
export const lessons: PlanLesson[] = [
  { id: "lesson-1", title: "How markets and shares work", status: "done", minutes: 6 },
  { id: "lesson-2", title: "Read a price chart with context", status: "in_progress", minutes: 8 },
  { id: "lesson-3", title: "Check the source behind a claim", status: "available", minutes: 7 },
  { id: "lesson-4", title: "Think in risks and time windows", status: "locked", minutes: 9 },
];
export const plan: LearningPlan = { level: 2, progress_pct: 38, lessons };
export const lesson: Lesson = {
  id: "lesson-2", title: "Read a price chart with context",
  sections: [
    "A price chart shows what happened over time. It does not explain why it happened. A single sharp move can hide a longer pattern.",
    "Compare the share with a broad index over the same dates. Then look for dated, checkable events. A headline after a price move cannot explain what came before it.",
    "Use a time window that matches the claim. Keep the company’s move, the index move, and the source of each clue separate in your notes.",
  ],
  check_questions: [ { id: "lesson-check-1", level: 2, skill_area: "reading_stock", difficulty: 2, text: "A chart rises after a headline. What should you check next?", options: ["Whether the dates line up and what the index did", "Whether the headline sounds exciting", "Whether the chart has green candles"] } ],
};
export const scenario: Scenario = {
  id: "scenario-54", as_of_date: "2024-02-16", window_days: 30, data_origin: "synthetic",
  context: { company: "Kavach Components (fictional case)", chart: [
    { date: "Jan 18", stock: 42, index: 55 }, { date: "Jan 23", stock: 49, index: 56 }, { date: "Jan 28", stock: 47, index: 57 }, { date: "Feb 2", stock: 65, index: 58 }, { date: "Feb 7", stock: 59, index: 59 }, { date: "Feb 12", stock: 38, index: 60 }, { date: "Feb 16", stock: 31, index: 61 },
  ], headlines: [ { date: "Feb 02", text: "Unusual trading activity reported ahead of a viral message", source: "Exchange notice (mock)" }, { date: "Feb 06", text: "Company says it has no knowledge of the circulated order", source: "Company filing (mock)" } ], numbers: { "Volume vs 20-day average": "5.4×", "Promoter pledge": "62%", "Time window": "30 days" } },
};
export const scenarioResult: ScenarioResult = { correct: false, outcome: { stock_pct: -18.4, index_pct: 3.1 }, key_clues: ["Trading volume rose before the message circulated", "The company denied the claimed order", "The broad index was stable during the same period"], explanation: "The clues pointed to a high-uncertainty claim. The share fell over the period while the index rose slightly. The exercise scores your forecast, not the company." };
export const assessment: Assessment = { assessment_id: "assessment-l2", items: [ { id: "q-1", text: "Which detail makes a market claim easier to check?", options: ["A clear source and a dated filing", "A large number of forwards", "A promise with no end date"], skill_area: "judging_info" }, { id: "q-2", text: "Why compare a share with an index over the same dates?", options: ["To see how much of the move was market-wide", "To predict tomorrow", "To remove all risk"], skill_area: "reading_stock" } ] };
export const assessmentResult = { passed: true, score: 82, brier: 0.16, new_level: 3, unlocked: ["verifier"] };
export const explain: ExplainResult = { data_origin: "synthetic", chart: [ { date: "Jan", stock: 33, index: 38 }, { date: "Mar", stock: 51, index: 44 }, { date: "May", stock: 42, index: 48 }, { date: "Jul", stock: 67, index: 50 }, { date: "Sep", stock: 58, index: 53 }, { date: "Nov", stock: 76, index: 55 } ], moves: [ { date: "18 Apr", pct: 22, events: [{ text: "Quarterly results released", source: "Company filing · 18 Apr" }, { text: "Broad market rose during the week", source: "NSE index data · 19 Apr" }] }, { date: "02 Aug", pct: -14, events: [{ text: "Trading moved to additional surveillance", source: "Exchange notice · 02 Aug" }] } ], summary: "This fictional example shows why one year of price movement needs context. Dated filings and exchange notices help explain some moves; they do not predict what comes next." };
export const dashboard: DashboardData = { level: 2, data_origin: "synthetic", skills_over_time: [ { date: "W1", basics: 42, reading_stock: 35, judging_info: 28, risk: 31 }, { date: "W2", basics: 51, reading_stock: 40, judging_info: 36, risk: 38 }, { date: "W3", basics: 63, reading_stock: 49, judging_info: 39, risk: 52 }, { date: "W4", basics: 72, reading_stock: 58, judging_info: 44, risk: 64 } ], brier_over_time: [ { date: "W1", brier: 0.36 }, { date: "W2", brier: 0.29 }, { date: "W3", brier: 0.24 }, { date: "W4", brier: 0.22 } ], scenario_accuracy: [ { date: "W1", accuracy: 48 }, { date: "W2", accuracy: 55 }, { date: "W3", accuracy: 61 }, { date: "W4", accuracy: 68 } ] };
export const verification: VerifyResult = {
  submission_id: "sub-demo-01", mode: "full", data_origin: "synthetic",
  source: { id: "source-demo-7", platform: "Telegram", handle: "MarketWatch_Pro (sample)", label: "not_reliable", score: 18, facts: { "SEBI registration": "Not found in this sample", "Claims checked": 12, "Scored outcomes": 9, "Last checked": "20 Nov 2026" } },
  claim: { symbol: "KAVACH (fictional)", direction: "up", status: "scored", outcome: { stock_pct: -18.4, index_pct: 3.1 } },
  red_flags: [ { code: "guaranteed_returns", text: "Promises a result as if it were certain.", evidence: "‘Double your money in 30 days’" }, { code: "urgency", text: "Pressures readers to act or share quickly.", evidence: "‘Forward this to five groups now’" }, { code: "pre_post_volume_spike", text: "Trading activity rose sharply before the post.", evidence: "Volume was 5.4× its 20-day average" }, { code: "not_sebi_registered", text: "No matching registered adviser was found for this sample source.", evidence: "Registration check returned no match" } ],
};
export const sourceDetail: SourceDetail = { data_origin: "synthetic", source: verification.source, history: [ { date: "Jun", score: 34 }, { date: "Jul", score: 29 }, { date: "Aug", score: 25 }, { date: "Sep", score: 21 }, { date: "Oct", score: 18 } ], recent_claims: [ { symbol: "KAVACH (fictional)", status: "scored", outcome: "Underperformed index" }, { symbol: "Demo Infra", status: "needs_review", outcome: "Not enough data yet" } ] };
export const submissions: SubmissionSummary[] = [ { submission_id: "sub-demo-01", claim: verification.claim, status: "scored", outcome: { stock_pct: -18.4, index_pct: 3.1 }, data_origin: "synthetic" }, { submission_id: "sub-demo-02", claim: { symbol: "Demo Infra", direction: "up", status: "needs_review" }, status: "needs_review", data_origin: "synthetic" } ];
