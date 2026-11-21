"use client";

import { useState } from "react";
import { Check, LogOut, Sparkles } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback, Button, Input, Panel, SectionHeading } from "@/components/ui";
import { AvatarImage } from "@/components/ui/avatar";
import { Chip } from "@/components/minor/chip";
import { notify } from "@/components/minor/toaster";
import { api } from "@/lib/api";
import type { ProfileExperience, ProfileGoal, UserProfile } from "@/lib/types";
import {
  EXPERIENCE_OPTIONS,
  GOAL_OPTIONS,
  WEEKLY_MINUTES_OPTIONS,
  avatarInitials,
} from "@/components/auth/profile-options";

export function ProfilePanel({
  profile,
  onProfileUpdated,
  onRetakeLevelCheck,
  onSignOut,
}: {
  profile: UserProfile;
  onProfileUpdated: (next: UserProfile) => void;
  onRetakeLevelCheck: () => void;
  onSignOut: () => Promise<void>;
}) {
  const [displayName, setDisplayName] = useState(
    profile.profile?.display_name ?? profile.name ?? "",
  );
  const [goal, setGoal] = useState<ProfileGoal | null>(profile.profile?.goal ?? null);
  const [experience, setExperience] = useState<ProfileExperience | null>(
    profile.profile?.experience ?? null,
  );
  const [weeklyMinutes, setWeeklyMinutes] = useState<number | null>(
    profile.profile?.weekly_minutes ?? null,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [savedNotice, setSavedNotice] = useState("");

  async function handleSave(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleaned = displayName.trim();
    if (!cleaned) {
      setError("Display name cannot be empty.");
      setSavedNotice("");
      return;
    }
    if (cleaned.length > 80) {
      setError("Display name must be 80 characters or fewer.");
      setSavedNotice("");
      return;
    }

    setBusy(true);
    setError("");
    setSavedNotice("");
    try {
      const updated = await api.updateProfile({
        display_name: cleaned,
        goal,
        experience,
        weekly_minutes: weeklyMinutes,
      });
      onProfileUpdated({
        ...profile,
        name: updated.profile.display_name || profile.name,
        profile: updated.profile,
        onboarding_completed: updated.onboarding_completed,
      });
      setSavedNotice("Profile changes saved.");
      notify("Profile saved.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update profile.");
    } finally {
      setBusy(false);
    }
  }

  const resolvedName = displayName.trim() || profile.name || "Learner";

  return (
    <div className="narrow-view pp-profile-panel">
      <SectionHeading
        eyebrow="ACCOUNT & PREFERENCES"
        title="Your profile"
        action={
          <Button
            type="button"
            variant="secondary"
            onClick={() => void onSignOut()}
            disabled={busy}
          >
            <LogOut size={15} aria-hidden="true" />
            <span>Sign out</span>
          </Button>
        }
      />

      <Panel className="pp-onboarding-card">
        <div className="pp-profile-header">
          <div className="pp-onboarding-avatar-row">
            <Avatar size="xl">
              {profile.profile?.avatar_url && (
                <AvatarImage src={profile.profile.avatar_url} alt={resolvedName} />
              )}
              <AvatarFallback>{avatarInitials(resolvedName)}</AvatarFallback>
            </Avatar>
            <div className="pp-onboarding-avatar-meta">
              <strong>{resolvedName}</strong>
              <Chip tone="gold">Level {profile.level} of 4</Chip>
            </div>
          </div>
          <Button type="button" variant="secondary" onClick={onRetakeLevelCheck} disabled={busy}>
            <Sparkles size={15} aria-hidden="true" />
            <span>Retake level check</span>
          </Button>
        </div>

        <form onSubmit={(e) => void handleSave(e)} noValidate className="mt-6">
          <div className="field-group">
            <label htmlFor="profile-display-name" className="field-label">
              Display name
            </label>
            <Input
              id="profile-display-name"
              name="display_name"
              type="text"
              maxLength={80}
              value={displayName}
              onChange={(event) => {
                setDisplayName(event.target.value);
                setError("");
                setSavedNotice("");
              }}
            />
          </div>

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
                      setSavedNotice("");
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
            <label className="field-label">Experience level</label>
            <div className="pp-choice-grid cols-3" role="radiogroup" aria-label="Experience level">
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
                      setSavedNotice("");
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
            <label className="field-label">Weekly study time</label>
            <div className="pp-time-grid" role="radiogroup" aria-label="Weekly study time">
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
                      setSavedNotice("");
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
          </div>

          <div className="pp-onboarding-footer">
            <span />
            <Button type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </form>

        <div aria-live="polite" className="mt-4">
          {savedNotice && (
            <Alert variant="success">
              <AlertDescription>{savedNotice}</AlertDescription>
            </Alert>
          )}
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>
      </Panel>
    </div>
  );
}
