import type {
  AssessmentStartResponse,
  AssessmentSubmitResponse,
  DashboardResponse,
  ExplainResponse,
  LessonDetailResponse,
  MeResponse,
  OnboardingResult,
  PlanResponse,
  QuestionItem,
  ScenarioAnswerResponse,
  ScenarioNextResponse,
  SourceDetailResponse,
  SubmissionMineItem,
  VerifyResponse,
} from "@/lib/contracts";

export const me = {
  id: "demo-user",
  name: "Ananya",
  level: 2,
  unlocks: ["scenarios", "red_flag_check", "explain_stock"],
} satisfies MeResponse;

export const onboardingQuestions = [
  {
    id: "onb-1",
    skill_area: "basics",
    difficulty: 1,
    text: "A company’s share price fell 8% today. What can you safely conclude from that alone?",
    options: [
      "The company is failing",
      "The price fell today; more context is needed",
      "It will rise tomorrow",
      "Nothing can ever be learned",
    ],
  },
  {
    id: "onb-2",
    skill_area: "judging_info",
    difficulty: 2,
    text: "A forwarded message promises a large return but names no source. What is the most useful first check?",
    options: [
      "Forward it to friends",
      "Check who made the claim and what evidence they cite",
      "Assume it is true if it has many likes",
      "Ignore the date",
    ],
  },
  {
    id: "onb-3",
    skill_area: "risk",
    difficulty: 2,
    text: "What does a 70% confidence estimate mean?",
    options: [
      "The outcome is certain",
      "You expect about 7 in 10 similar calls to be right",
      "The price will move 70%",
      "You should act now",
    ],
  },
] satisfies QuestionItem[];

export const onboardingResult = {
  level: 2,
  skills: { basics: 72, reading_stock: 58, judging_info: 44, risk: 64 },
  brier: 0.22,
} satisfies OnboardingResult;

export const plan = {
  level: 2,
  progress_pct: 38,
  lessons: [
    { id: "lesson-1", title: "How markets and shares work", status: "completed", minutes: 6 },
    { id: "lesson-2", title: "Read a price chart with context", status: "in_progress", minutes: 8 },
    { id: "lesson-3", title: "Check the source behind a claim", status: "not_started", minutes: 7 },
    { id: "lesson-4", title: "Think in risks and time windows", status: "locked", minutes: 9 },
  ],
} satisfies PlanResponse;

export const lesson = {
  id: "lesson-2",
  title: "Read a price chart with context",
  sections: [
    {
      heading: "Start with the dates",
      body: "A price chart shows what happened over time. It does not explain why it happened. A single sharp move can hide a longer pattern.",
      example: "A headline after a price move cannot explain what came before it.",
    },
    {
      heading: "Compare what changed",
      body: "Compare the share with a broad index over the same dates. Then look for dated, checkable events.",
    },
    {
      heading: "Keep the clues separate",
      body: "Use a time window that matches the claim. Keep the company move, index move, and source of each clue separate in your notes.",
    },
  ],
  check_questions: [
    {
      id: "lesson-check-1",
      skill_area: "reading_stock",
      difficulty: 2,
      text: "A chart rises after a headline. What should you check next?",
      options: [
        "Whether the dates line up and what the index did",
        "Whether the headline sounds exciting",
        "Whether the chart has green candles",
      ],
    },
  ],
} satisfies LessonDetailResponse;

export const scenario = {
  id: "scenario-54",
  as_of_date: "2024-02-16",
  window_days: 30,
  data_origin: "synthetic",
  context: {
    company: "Kavach Components (fictional case)",
    chart: [
      { date: "Jan 18", close: 42, volume: 100 },
      { date: "Jan 23", close: 49, volume: 105 },
      { date: "Jan 28", close: 47, volume: 98 },
      { date: "Feb 02", close: 65, volume: 540 },
      { date: "Feb 07", close: 59, volume: 131 },
      { date: "Feb 12", close: 38, volume: 145 },
      { date: "Feb 16", close: 31, volume: 106 },
    ],
    headlines: [
      {
        date: "Feb 02",
        text: "Unusual trading activity reported ahead of a viral message",
        source: "Exchange notice (mock)",
      },
      {
        date: "Feb 06",
        text: "Company says it has no knowledge of the circulated order",
        source: "Company filing (mock)",
      },
    ],
    numbers: {
      "Volume vs 20-day average": "5.4×",
      "Promoter pledge": "62%",
      "Time window": "30 days",
    },
  },
} satisfies ScenarioNextResponse;

export const scenarioResult = {
  correct: false,
  outcome: { stock_pct: -18.4, index_pct: 3.1 },
  key_clues: [
    "Trading volume rose before the message circulated",
    "The company denied the claimed order",
    "The broad index was stable during the same period",
  ],
  explanation:
    "The clues pointed to a high-uncertainty claim. The share fell over the period while the index rose slightly. The exercise scores your forecast, not the company.",
} satisfies ScenarioAnswerResponse;

export const assessment = {
  assessment_id: "assessment-l2",
  items: [
    {
      id: "q-1",
      skill_area: "judging_info",
      difficulty: 2,
      text: "Which detail makes a market claim easier to check?",
      options: [
        "A clear source and a dated filing",
        "A large number of forwards",
        "A promise with no end date",
      ],
    },
    {
      id: "q-2",
      skill_area: "reading_stock",
      difficulty: 2,
      text: "Why compare a share with an index over the same dates?",
      options: [
        "To see how much of the move was market-wide",
        "To predict tomorrow",
        "To remove all risk",
      ],
    },
  ],
} satisfies AssessmentStartResponse;

export const assessmentResult = {
  passed: true,
  score: 82,
  brier: 0.16,
  new_level: 3,
  unlocked: ["verifier"],
} satisfies AssessmentSubmitResponse;

export const explain = {
  data_origin: "synthetic",
  chart: [
    { date: "Jan", close: 33 },
    { date: "Mar", close: 51 },
    { date: "May", close: 42 },
    { date: "Jul", close: 67 },
    { date: "Sep", close: 58 },
    { date: "Nov", close: 76 },
  ],
  moves: [
    {
      date: "18 Apr",
      pct: 22,
      events: [
        { text: "Quarterly results released", source: "Company filing · 18 Apr" },
        { text: "Broad market rose during the week", source: "NSE index data · 19 Apr" },
      ],
    },
    {
      date: "02 Aug",
      pct: -14,
      events: [
        { text: "Trading moved to additional surveillance", source: "Exchange notice · 02 Aug" },
      ],
    },
  ],
  summary:
    "This fictional example shows why one year of price movement needs context. Dated filings and exchange notices help explain some moves; they do not predict what comes next.",
} satisfies ExplainResponse;

export const dashboard = {
  level: 2,
  skills_over_time: [
    { date: "W1", skills: { basics: 42, reading_stock: 35, judging_info: 28, risk: 31 } },
    { date: "W2", skills: { basics: 51, reading_stock: 40, judging_info: 36, risk: 38 } },
    { date: "W3", skills: { basics: 63, reading_stock: 49, judging_info: 39, risk: 52 } },
    { date: "W4", skills: { basics: 72, reading_stock: 58, judging_info: 44, risk: 64 } },
  ],
  brier_over_time: [
    { date: "W1", brier: 0.36 },
    { date: "W2", brier: 0.29 },
    { date: "W3", brier: 0.24 },
    { date: "W4", brier: 0.22 },
  ],
  scenario_accuracy: [
    { date: "W1", accuracy: 48, attempts: 3 },
    { date: "W2", accuracy: 55, attempts: 5 },
    { date: "W3", accuracy: 61, attempts: 8 },
    { date: "W4", accuracy: 68, attempts: 11 },
  ],
} satisfies DashboardResponse;

export const verification = {
  submission_id: "sub-demo-01",
  mode: "full",
  data_origin: "synthetic",
  source: {
    id: "source-demo-7",
    platform: "Telegram",
    handle: "MarketWatch_Pro (sample)",
    label: "not_reliable",
    score: 18,
    facts: {
      "SEBI registration": "Not found in this sample",
      "Claims checked": 12,
      "Scored outcomes": 9,
      "Last checked": "20 Nov 2026",
    },
  },
  claim: {
    id: "claim-demo-01",
    submission_id: "sub-demo-01",
    symbol: "KAVACH (fictional)",
    direction: "up",
    entry: 100,
    target: 200,
    stop: null,
    window_end: "2024-02-16",
    scorable: true,
    status: "scored",
    outcome: { stock_pct: -18.4, index_pct: 3.1 },
  },
  red_flags: [
    {
      code: "guaranteed_returns",
      text: "Promises a result as if it were certain.",
      evidence: "‘Double your money in 30 days’",
    },
    {
      code: "urgency",
      text: "Pressures readers to act or share quickly.",
      evidence: "‘Forward this to five groups now’",
    },
    {
      code: "pre_post_volume_spike",
      text: "Trading activity rose sharply before the post.",
      evidence: "Volume was 5.4× its 20-day average",
    },
    {
      code: "not_sebi_registered",
      text: "No matching registered adviser was found for this sample source.",
      evidence: "Registration check returned no match",
    },
  ],
} satisfies VerifyResponse;

export const sourceDetail = {
  source: verification.source!,
  history: [
    { score: 34, label: "not_reliable", reason: "Initial sample score", changed_at: "2026-06-01" },
    {
      score: 29,
      label: "not_reliable",
      reason: "One more claim was scored",
      changed_at: "2026-07-01",
    },
    {
      score: 25,
      label: "not_reliable",
      reason: "More scored claims added",
      changed_at: "2026-08-01",
    },
    { score: 21, label: "not_reliable", reason: "Latest scored claim", changed_at: "2026-09-01" },
    { score: 18, label: "not_reliable", reason: "Current sample rating", changed_at: "2026-10-01" },
  ],
  recent_claims: [
    verification.claim!,
    {
      id: "claim-demo-02",
      symbol: "DEMO INFRA",
      direction: "up",
      entry: null,
      target: null,
      stop: null,
      window_end: null,
      scorable: false,
      status: "needs_review",
      outcome: null,
    },
  ],
} satisfies SourceDetailResponse;

export const submissions = [
  {
    submission_id: "sub-demo-01",
    claim: verification.claim!,
    status: "scored",
    outcome: { stock_pct: -18.4, index_pct: 3.1 },
  },
  {
    submission_id: "sub-demo-02",
    claim: sourceDetail.recent_claims[1],
    status: "needs_review",
    outcome: null,
  },
] satisfies SubmissionMineItem[];
