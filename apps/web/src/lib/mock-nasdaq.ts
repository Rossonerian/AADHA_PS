import type {
  NasdaqChallengeResponse,
  NasdaqSubmitRequest,
  NasdaqSubmitResponse,
} from "./contracts";

/** SYNTHETIC demo data for when the API or FINNHUB_API_KEY is unavailable. Never shown as REAL. */
const KEY: Record<string, string> = {
  q1: "150.00 to 200.00",
  q2: "Upper half",
  q3: "$3,000.0B",
};

export function mockNasdaqChallenge(symbol: string): NasdaqChallengeResponse {
  const sym = symbol.toUpperCase();
  return {
    challenge_id: "mock_1",
    data_origin: "synthetic",
    as_of: new Date().toISOString(),
    snapshot: {
      symbol: sym,
      name: "Demo company",
      sector: "Technology",
      price: 190,
      day_low: 188,
      day_high: 192,
      week52_low: 150,
      week52_high: 200,
      market_cap_musd: 3_000_000,
      pe_ttm: 30,
      chart: Array.from({ length: 12 }, (_, i) => ({
        date: `2026-${String(i + 1).padStart(2, "0")}-01`,
        close: 160 + i * 3 + (i % 3) * 2,
      })),
      data_origin: "synthetic",
    },
    nasdaq_url: `https://www.nasdaq.com/market-activity/stocks/${sym.toLowerCase()}`,
    disclaimer:
      "Educational literacy check only — PaisaProof never recommends buying, selling, or holding any security.",
    questions: [
      {
        id: "q1",
        text: "Which range is the 52-week range shown in the snapshot?",
        options: ["120.00 to 180.00", "150.00 to 200.00", "172.50 to 240.00"],
      },
      {
        id: "q2",
        text: "Is the latest price in the upper or lower half of its 52-week range?",
        options: ["Upper half", "Lower half"],
      },
      {
        id: "q3",
        text: "What market capitalization does the snapshot show?",
        options: ["$300.0B", "$3,000.0B", "$30,000.0B"],
      },
    ],
  };
}

export function mockNasdaqSubmit(req: NasdaqSubmitRequest): NasdaqSubmitResponse {
  const results = Object.entries(KEY).map(([id, correct]) => {
    const a = req.answers.find((x) => x.question_id === id);
    return {
      question_id: id,
      correct: a?.answer === correct,
      correct_answer: correct,
      explanation: `The snapshot shows ${correct}.`,
    };
  });
  const sq = results.reduce((sum, r) => {
    const conf = (req.answers.find((x) => x.question_id === r.question_id)?.confidence ?? 50) / 100;
    return sum + (conf - (r.correct ? 1 : 0)) ** 2;
  }, 0);
  const brier = Math.round((sq / results.length) * 10000) / 10000;
  const right = results.filter((r) => r.correct).length;
  return {
    passed: brier <= 0.25,
    score: right / results.length,
    brier,
    results,
    feedback: `You read ${right} of ${results.length} figures correctly with a Brier score of ${brier.toFixed(2)}. Lower Brier means your confidence matched your accuracy.`,
  };
}
