"use client";

import { useState } from "react";
import { ArrowLeft, ArrowRight, Check, LogOut, Moon, Sparkles, Sun } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback, Button, Input, Panel, ProgressBar } from "@/components/ui";
import { AvatarImage } from "@/components/ui/avatar";
import { Chip } from "@/components/minor/chip";
import { api } from "@/lib/api";
import type { ProfileExperience, ProfileGoal, UserProfile } from "@/lib/types";
import {
  EXPERIENCE_OPTIONS,
  GOAL_OPTIONS,
  WEEKLY_MINUTES_OPTIONS,
  avatarInitials,
  labelForExperience,
  labelForGoal,
} from "@/components/auth/profile-options";

const TOTAL_STEPS = 4;
const stepStorageKey = (userId: string) => `pp.onboarding.step.${userId}`;

function resolveInitialStep(me: UserProfile): number {
  const p = me.profile;
  let serverStep = 0;
  if (p?.weekly_minutes != null) serverStep = 3;
  else if (p?.goal != null && p?.experience != null) serverStep = 2;

  if (typeof window === "undefined") return serverStep;
  try {
    const raw = window.localStorage.getItem(stepStorageKey(me.id));
    const parsed = raw !== null ? Number(raw) : NaN;
    if (Number.isInteger(parsed) && parsed >= 0 && parsed < TOTAL_STEPS) {
      return Math.max(serverStep, parsed);
    }
  } catch {
    // Ignore storage access errors.
  }
  return serverStep;
}

function saveStepHint(userId: string, nextStep: number): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(stepStorageKey(userId), String(nextStep));
  } catch {
    // Ignore storage access errors.
  }
}

function clearStepHint(userId: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(stepStorageKey(userId));
  } catch {
    // Ignore storage access errors.
  }
}

function errorMessage(reason: unknown): string {
  if (reason instanceof Error && reason.message) return reason.message;
  return "Could not save your preferences. Please try again.";
}

export function ProfileOnboarding({
  me,
  theme,
  onToggleTheme,
  onProfileUpdated,
  onComplete,
  onSignOut,
}: {
  me: UserProfile;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onProfileUpdated: (next: UserProfile) => void;
  onComplete: (options: { startAssessment: boolean }) => Promise<void>;
  onSignOut: () => Promise<void>;
}) {
  const [step, setStep] = useState<number>(() => resolveInitialStep(me));
  const [displayName, setDisplayName] = useState(me.profile?.display_name ?? me.name ?? "");
  const [goal, setGoal] = useState<ProfileGoal | null>(me.profile?.goal ?? null);
  const [experience, setExperience] = useState<ProfileExperience | null>(
    me.profile?.experience ?? null,
  );
  const [weeklyMinutes, setWeeklyMinutes] = useState<number | null>(
    me.profile?.weekly_minutes ?? 20,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function goToStep(nextStep: number) {
    const clamped = Math.max(0, Math.min(TOTAL_STEPS - 1, nextStep));
    setStep(clamped);
    saveStepHint(me.id, clamped);
    setError("");
  }

  async function saveProfileStep(patch: Parameters<typeof api.updateProfile>[0], nextStep: number) {
    setBusy(true);
    setError("");
    try {
      const updated = await api.updateProfile(patch);
      onProfileUpdated({
        ...me,
        name: updated.profile.display_name || me.name,
        profile: updated.profile,
        onboarding_completed: updated.onboarding_completed,
      });
      goToStep(nextStep);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleStep1Submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleaned = displayName.trim();
    if (!cleaned) {
      setError("Enter the name you want us to call you.");
      return;
    }
    if (cleaned.length > 80) {
      setError("Keep your display name under 80 characters.");
      return;
    }
    await saveProfileStep({ display_name: cleaned }, 1);
  }

  async function handleStep2Continue() {
    if (!goal || !experience) {
      setError("Pick a goal and your current experience level, or skip for now.");
      return;
    }
    await saveProfileStep({ goal, experience }, 2);
  }

  async function handleStep3Continue() {
    if (!weeklyMinutes || weeklyMinutes < 1) {
      setError("Choose a weekly study pace, or skip for now.");
      return;
    }
    await saveProfileStep({ weekly_minutes: weeklyMinutes }, 3);
  }

  async function handleFinish(startAssessment: boolean) {
    setBusy(true);
    setError("");
    try {
      const completed = await api.completeOnboarding();
      clearStepHint(me.id);
      onProfileUpdated({
        ...me,
        name: completed.profile.display_name || me.name,
        profile: completed.profile,
        onboarding_completed: true,
      });
      await onComplete({ startAssessment });
    } catch (reason) {
      setError(errorMessage(reason));
      setBusy(false);
    }
  }

  const avatarName = displayName.trim() || me.name || "Learner";
  const progressPct = ((step + 1) / TOTAL_STEPS) * 100;

  return (
    <div className="pp-onboarding-shell app-shell" data-theme={theme}>
      <header className="pp-onboarding-bar">
        <div className="pp-onboarding-brand">
          <span className="brand-mark">P</span>
          <span>PaisaProof</span>
        </div>
        <div className="pp-onboarding-actions">
          <Chip tone="neutral">
            Step {step + 1} of {TOTAL_STEPS}
          </Chip>
          <Button
            variant="quiet"
            type="button"
            className="theme-toggle"
            onClick={onToggleTheme}
            aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
            aria-pressed={theme === "dark"}
          >
            {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
          </Button>
          <Button
            variant="quiet"
            type="button"
            onClick={() => void onSignOut()}
            disabled={busy}
            aria-label="Sign out"
          >
            <LogOut size={15} aria-hidden="true" />
            <span className="pp-onboarding-signout-label">Sign out</span>
          </Button>
        </div>
      </header>

      <main className="pp-onboarding-main">
        <div className="pp-onboarding-progress">
          <ProgressBar
            value={progressPct}
            ariaLabel={`Onboarding step ${step + 1} of ${TOTAL_STEPS}`}
          />
        </div>

        <Panel className="pp-onboarding-card">
          {step === 0 && (
            <form onSubmit={(e) => void handleStep1Submit(e)} noValidate>
              <span className="eyebrow">WELCOME TO YOUR STUDIO</span>
              <h1>First, how should we address you?</h1>
              <p className="pp-onboarding-lead">
                We prefilled your details where available. You can adjust this anytime in your
                profile.
              </p>

              <div className="pp-onboarding-avatar-row">
                <Avatar size="xl">
                  {me.profile?.avatar_url && (
                    <AvatarImage src={me.profile.avatar_url} alt={avatarName} />
                  )}
                  <AvatarFallback>{avatarInitials(avatarName)}</AvatarFallback>
                </Avatar>
                <div className="pp-onboarding-avatar-meta">
                  <strong>{avatarName}</strong>
                  <span>
                    {me.profile?.avatar_url
                      ? "Photo imported from your sign-in account"
                      : "Generated workspace initials"}
                  </span>
                </div>
              </div>

              <div className="field-group mt-4">
                <label htmlFor="onboarding-display-name" className="field-label">
                  Display name
                </label>
                <Input
                  id="onboarding-display-name"
                  name="display_name"
                  type="text"
                  autoFocus
                  autoComplete="name"
                  maxLength={80}
                  placeholder="Maya Rao"
                  value={displayName}
                  onChange={(event) => {
                    setDisplayName(event.target.value);
                    if (error) setError("");
                  }}
                />
              </div>

              <div className="pp-onboarding-footer">
                <span />
                <Button type="submit" disabled={busy}>
                  <span>{busy ? "Saving…" : "Continue"}</span>
                  <ArrowRight size={15} aria-hidden="true" />
                </Button>
              </div>
            </form>
          )}

          {step === 1 && (
            <div>
              <span className="eyebrow">YOUR FOCUS</span>
              <h1>What brings you to PaisaProof?</h1>
              <p className="pp-onboarding-lead">
                Choose your primary focus and comfort level so lessons and examples start at the
                right pace.
              </p>

              <div className="pp-onboarding-section">
                <label className="field-label">Primary goal</label>
                <div className="pp-choice-grid cols-2" role="radiogroup" aria-label="Primary goal">
                  {GOAL_OPTIONS.map((item) => {
                    const selected = goal === item.value;
                    return (
                      <button
                        key={item.value}
                        type="button"
                        role="radio"
                        aria-checked={selected}
                        className={`pp-choice-card ${selected ? "selected" : ""}`}
                        onClick={() => {
                          setGoal(item.value);
                          setError("");
                        }}
                      >
                        <div className="pp-choice-card-top">
                          <strong>{item.title}</strong>
                          {selected && <Check size={15} aria-hidden="true" />}
                        </div>
                        <span>{item.description}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="pp-onboarding-section">
                <label className="field-label">Current experience</label>
                <div
                  className="pp-choice-grid cols-3"
                  role="radiogroup"
                  aria-label="Current experience"
                >
                  {EXPERIENCE_OPTIONS.map((item) => {
                    const selected = experience === item.value;
                    return (
                      <button
                        key={item.value}
                        type="button"
                        role="radio"
                        aria-checked={selected}
                        className={`pp-choice-card ${selected ? "selected" : ""}`}
                        onClick={() => {
                          setExperience(item.value);
                          setError("");
                        }}
                      >
                        <div className="pp-choice-card-top">
                          <strong>{item.title}</strong>
                          {selected && <Check size={15} aria-hidden="true" />}
                        </div>
                        <span>{item.description}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="pp-onboarding-footer">
                <Button type="button" variant="quiet" onClick={() => goToStep(0)} disabled={busy}>
                  <ArrowLeft size={15} aria-hidden="true" />
                  <span>Back</span>
                </Button>
                <div className="pp-onboarding-footer-right">
                  <Button type="button" variant="quiet" onClick={() => goToStep(2)} disabled={busy}>
                    Skip
                  </Button>
                  <Button type="button" onClick={() => void handleStep2Continue()} disabled={busy}>
                    <span>{busy ? "Saving…" : "Continue"}</span>
                    <ArrowRight size={15} aria-hidden="true" />
                  </Button>
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <span className="eyebrow">WEEKLY PACE</span>
              <h1>How much time do you have each week?</h1>
              <p className="pp-onboarding-lead">
                Short, steady sessions build sharper calibration than occasional cramming.
              </p>

              <div
                className="pp-time-grid"
                role="radiogroup"
                aria-label="Weekly learning commitment"
              >
                {WEEKLY_MINUTES_OPTIONS.map((opt) => {
                  const selected = weeklyMinutes === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      className={`pp-choice-card pp-time-card ${selected ? "selected" : ""}`}
                      onClick={() => {
                        setWeeklyMinutes(opt.value);
                        setError("");
                      }}
                    >
                      <div className="pp-choice-card-top">
                        <strong>{opt.label}</strong>
                        <Chip tone={selected ? "gold" : "neutral"}>{opt.tag}</Chip>
                      </div>
                      <span>{opt.description}</span>
                    </button>
                  );
                })}
              </div>

              <div className="pp-onboarding-footer">
                <Button type="button" variant="quiet" onClick={() => goToStep(1)} disabled={busy}>
                  <ArrowLeft size={15} aria-hidden="true" />
                  <span>Back</span>
                </Button>
                <div className="pp-onboarding-footer-right">
                  <Button type="button" variant="quiet" onClick={() => goToStep(3)} disabled={busy}>
                    Skip
                  </Button>
                  <Button type="button" onClick={() => void handleStep3Continue()} disabled={busy}>
                    <span>{busy ? "Saving…" : "Continue"}</span>
                    <ArrowRight size={15} aria-hidden="true" />
                  </Button>
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div>
              <span className="eyebrow">CALIBRATION CHECK</span>
              <h1>Ready to find your starting level?</h1>
              <p className="pp-onboarding-lead">
                Our ~12-question adaptive check maps your confidence against real financial concepts
                so you never waste time repeating what you already know.
              </p>

              <div className="pp-onboarding-recap">
                <div>
                  <small>Name</small>
                  <strong>{displayName.trim() || me.name || "Learner"}</strong>
                </div>
                <div>
                  <small>Goal</small>
                  <strong>{labelForGoal(goal)}</strong>
                </div>
                <div>
                  <small>Experience</small>
                  <strong>{labelForExperience(experience)}</strong>
                </div>
                <div>
                  <small>Weekly pace</small>
                  <strong>{weeklyMinutes ? `${weeklyMinutes} min / week` : "Flexible"}</strong>
                </div>
              </div>

              <div className="pp-onboarding-footer">
                <Button type="button" variant="quiet" onClick={() => goToStep(2)} disabled={busy}>
                  <ArrowLeft size={15} aria-hidden="true" />
                  <span>Back</span>
                </Button>
                <div className="pp-onboarding-footer-right">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => void handleFinish(false)}
                    disabled={busy}
                  >
                    Skip for now
                  </Button>
                  <Button type="button" onClick={() => void handleFinish(true)} disabled={busy}>
                    <Sparkles size={15} aria-hidden="true" />
                    <span>{busy ? "Starting…" : "Find my level"}</span>
                  </Button>
                </div>
              </div>
            </div>
          )}

          <div aria-live="polite" className="mt-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </div>
        </Panel>
      </main>
    </div>
  );
}
