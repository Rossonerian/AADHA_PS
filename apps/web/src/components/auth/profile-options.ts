import type { ProfileExperience, ProfileGoal } from "@/lib/types";

export const GOAL_OPTIONS: {
  value: ProfileGoal;
  title: string;
  description: string;
}[] = [
  {
    value: "learn_basics",
    title: "Learn the basics",
    description: "Build core money and market judgment from the ground up.",
  },
  {
    value: "avoid_scams",
    title: "Avoid scams & hype",
    description: "Spot red flags and pressure tactics before acting on tips.",
  },
  {
    value: "invest_smarter",
    title: "Judge market claims",
    description: "Separate evidence from noise and calibrate your confidence.",
  },
  {
    value: "other",
    title: "Explore at my own pace",
    description: "Try guided lessons, scenarios, and claim checks freely.",
  },
];

export const EXPERIENCE_OPTIONS: {
  value: ProfileExperience;
  title: string;
  description: string;
}[] = [
  {
    value: "new",
    title: "Just starting out",
    description: "New to market terms and reading stock information.",
  },
  {
    value: "some",
    title: "Know the basics",
    description: "Familiar with common terms, still sharpening judgment.",
  },
  {
    value: "experienced",
    title: "Follow regularly",
    description: "Read market news often and want sharper calibration.",
  },
];

export const WEEKLY_MINUTES_OPTIONS: {
  value: number;
  label: string;
  tag: string;
  description: string;
}[] = [
  {
    value: 10,
    label: "10 min / week",
    tag: "Light habit",
    description: "One short lesson or two scenarios on a coffee break.",
  },
  {
    value: 20,
    label: "20 min / week",
    tag: "Recommended",
    description: "Balanced weekly pace across lessons and practice.",
  },
  {
    value: 45,
    label: "45 min / week",
    tag: "Deep focus",
    description: "Steady progress through all levels and claim checks.",
  },
];

export function labelForGoal(goal: ProfileGoal | null | undefined): string {
  return GOAL_OPTIONS.find((item) => item.value === goal)?.title ?? "Not set";
}

export function labelForExperience(exp: ProfileExperience | null | undefined): string {
  return EXPERIENCE_OPTIONS.find((item) => item.value === exp)?.title ?? "Not set";
}

export function avatarInitials(name: string | null | undefined): string {
  const cleaned = (name ?? "").trim();
  if (!cleaned) return "L";
  const parts = cleaned.split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0].slice(0, 1)}${parts[parts.length - 1].slice(0, 1)}`.toUpperCase();
}
