"use client";

import { useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  ChartNoAxesCombined,
  CircleHelp,
  House,
  Landmark,
  Lock,
  LogOut,
  Moon,
  Search,
  Sparkles,
  Sun,
} from "lucide-react";
import { chartHasIndex } from "@/components/lazy/chart-utils";
import { DashboardCharts, ExplainChart, ScenarioChart } from "@/components/lazy/lazy-charts";
import {
  Alert,
  Avatar,
  AvatarFallback,
  Button,
  Checkbox,
  ChoiceOption,
  ConfidenceControl,
  DataBadge,
  Input,
  LockNotice,
  Panel,
  ProgressBar,
  RadioGroup,
  SectionHeading,
  Slider,
  Tabs,
  TabsList,
  TabsTrigger,
  Textarea,
} from "@/components/ui";
import { Chip } from "@/components/minor/chip";
import { Separator } from "@/components/minor/separator";
import { Skeleton } from "@/components/minor/skeleton";
import { Toaster, notify } from "@/components/minor/toaster";
import { Tooltip, TooltipProvider } from "@/components/minor/tooltip";
import { BUILD_LABEL } from "@/lib/build-info";
import { api, isToolLocked, mockAuthBridge, mocksEnabled } from "@/lib/api";
import { ApiClientError } from "@/lib/api-client";
import type {
  Assessment,
  AssessmentResult,
  DashboardData,
  DataOrigin,
  ExplainResult,
  LearningPlan,
  Lesson,
  OnboardingResult,
  Question,
  Scenario,
  ScenarioResult,
  SourceDetail,
  SubmissionSummary,
  UserProfile,
  VerifyResult,
} from "@/lib/types";
import { authClient } from "@/lib/neon-auth-client";
import type { LessonCheckResponse } from "@/lib/contracts";
import { AUTH_EXPIRED_EVENT, SESSION_EXPIRED_MESSAGE } from "@/lib/auth-errors";
import { AuthScreen } from "@/components/auth/auth-screen";
import { avatarInitials } from "@/components/auth/profile-options";
import { ProfileOnboarding } from "@/components/onboarding/profile-onboarding";
import { AvatarImage } from "@/components/ui/avatar";
import { NasdaqVerifier, ProfilePanel } from "@/components/lazy/lazy-views";

type View =
  | "home"
  | "onboarding"
  | "learn"
  | "lesson"
  | "assessment"
  | "scenario"
  | "explain"
  | "verifier"
  | "progress"
  | "nasdaq"
  | "profile";
type NavItem = { id: View; label: string; icon: typeof House; tool?: string; level?: number };
const navItems: NavItem[] = [
  { id: "home", label: "Overview", icon: House },
  { id: "learn", label: "Learning path", icon: BookOpen },
  { id: "scenario", label: "Practice scenarios", icon: Sparkles, tool: "scenarios", level: 1 },
  { id: "explain", label: "Explain a stock", icon: Search, tool: "explain_stock", level: 2 },
  { id: "verifier", label: "Source verifier", icon: CircleHelp, tool: "verifier", level: 3 },
  { id: "progress", label: "My progress", icon: ChartNoAxesCombined, tool: "dashboard", level: 4 },
  { id: "nasdaq", label: "Nasdaq capstone", icon: Landmark, level: 4 },
];

const verifierLevel = navItems.find((item) => item.id === "verifier")?.level ?? 3;
const sentenceCase = (value: string) => {
  const text = value.replace(/_/g, " ").trim().toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
};

function friendlyError(error: unknown): string {
  if (isToolLocked(error)) return `This tool opens at Level ${error.requiredLevel ?? 3}.`;
  if (error instanceof Error) return error.message;
  return "That did not load. Check your connection and try again.";
}

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

function formatLabel(value: string | null | undefined) {
  return (value ?? "not available")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function outcomePercentages(value: Record<string, unknown> | null | undefined) {
  if (!value) return null;
  const company = Number(value.stock_pct);
  const index = Number(value.index_pct);
  return Number.isFinite(company) && Number.isFinite(index) ? { company, index } : null;
}

function formatFact(value: unknown): string {
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return value == null ? "Not available" : JSON.stringify(value);
}

export default function PaisaProofApp() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [view, setView] = useState<View>("home");
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [plan, setPlan] = useState<LearningPlan | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [scenarioResult, setScenarioResult] = useState<ScenarioResult | null>(null);
  const [explain, setExplain] = useState<ExplainResult | null>(null);
  const [verification, setVerification] = useState<VerifyResult | null>(null);
  const [sourceDetail, setSourceDetail] = useState<SourceDetail | null>(null);
  const [submissions, setSubmissions] = useState<SubmissionSummary[]>([]);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [assessmentResult, setAssessmentResult] = useState<AssessmentResult | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
  }, [theme]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [verifyProgress, setVerifyProgress] = useState(0);
  const [verifyUnavailable, setVerifyUnavailable] = useState(false);
  const [onboarding, setOnboarding] = useState<{
    sessionId: string;
    question: Question;
    index: number;
    confidence: number;
    answer: string;
    data_origin: DataOrigin;
  } | null>(null);
  const [onboardingResult, setOnboardingResult] = useState<OnboardingResult | null>(null);
  const [lessonCheck, setLessonCheck] = useState<Record<string, string>>({});
  const [lessonSaved, setLessonSaved] = useState("");
  const [lessonResult, setLessonResult] = useState<LessonCheckResponse | null>(null);
  const [assessmentAnswers, setAssessmentAnswers] = useState<
    Record<string, { answer: string; confidence: number }>
  >({});
  const [scenarioAnswer, setScenarioAnswer] = useState<"up" | "down" | "">("");
  const [scenarioConfidence, setScenarioConfidence] = useState(65);
  const [selectedClues, setSelectedClues] = useState<string[]>([]);
  const [symbol, setSymbol] = useState("");
  const [year, setYear] = useState("2025");
  const [verifyText, setVerifyText] = useState("");
  const [verifyUrl, setVerifyUrl] = useState("");
  const [userGuess, setUserGuess] = useState("");
  const [userConfidence, setUserConfidence] = useState(65);
  const [searchSource, setSearchSource] = useState(false);
  const [authNotice, setAuthNotice] = useState("");

  useEffect(() => {
    let cancelled = false;
    if (mocksEnabled) {
      if (mockAuthBridge?.getActiveEmail()) {
        void api
          .me()
          .then((nextMe) => {
            if (!cancelled) setProfile(nextMe);
          })
          .catch((reason: unknown) => {
            if (!cancelled) setError(friendlyError(reason));
          });
      }
      return () => {
        cancelled = true;
      };
    }
    void authClient
      .getSession()
      .then((session) => {
        if (!cancelled && session.data?.session) {
          void api
            .me()
            .then((nextMe) => {
              if (!cancelled) setProfile(nextMe);
            })
            .catch((reason: unknown) => {
              if (!cancelled) setAuthNotice(friendlyError(reason));
            });
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) setAuthNotice(friendlyError(reason));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // A 401 that survives a token refresh means the session is dead: return to sign-in
  // with an explanation instead of leaving a half-working screen.
  useEffect(() => {
    if (mocksEnabled) return;
    const onExpired = () => {
      void Promise.resolve(authClient.signOut()).catch(() => undefined);
      setProfile(null);
      setPlan(null);
      setDashboard(null);
      setSubmissions([]);
      setVerification(null);
      setOnboarding(null);
      setOnboardingResult(null);
      setView("home");
      setError("");
      setAuthNotice(SESSION_EXPIRED_MESSAGE);
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, []);

  useEffect(() => {
    if (mocksEnabled || !profile) return;
    let lastCheckedAt = Date.now();
    const refreshSession = () => {
      if (document.visibilityState === "hidden") return;
      const now = Date.now();
      if (now - lastCheckedAt < 60_000) return;
      lastCheckedAt = now;
      void authClient.getSession().catch(() => undefined);
    };
    window.addEventListener("focus", refreshSession);
    document.addEventListener("visibilitychange", refreshSession);
    return () => {
      window.removeEventListener("focus", refreshSession);
      document.removeEventListener("visibilitychange", refreshSession);
    };
  }, [profile]);

  const profileId = profile?.id;
  const profileLevel = profile?.level;
  const profileOnboardingCompleted = profile?.onboarding_completed;

  useEffect(() => {
    if (!profileId || !profileOnboardingCompleted) return;
    let cancelled = false;
    Promise.all([api.plan(), api.submissions()])
      .then(([nextPlan, nextSubmissions]) => {
        if (!cancelled) {
          setPlan(nextPlan);
          setSubmissions(nextSubmissions);
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(friendlyError(reason));
      });
    return () => {
      cancelled = true;
    };
  }, [profileId, profileLevel, profileOnboardingCompleted]);

  const activeNav = useMemo(() => {
    if (view === "profile") return "Profile";
    return navItems.find((item) => item.id === view)?.label ?? "Overview";
  }, [view]);
  const clearError = () => setError("");
  const showError = (reason: unknown) => setError(friendlyError(reason));

  async function loadAuthenticatedUser() {
    const me = await api.me();
    setAuthNotice("");
    setProfile(me);
  }

  async function signOut() {
    try {
      if (mocksEnabled) mockAuthBridge?.signOut();
      else await authClient.signOut();
    } catch {
      // Local state is cleared below even if the server could not be reached.
    } finally {
      setAuthNotice("");
      setProfile(null);
      setPlan(null);
      setDashboard(null);
      setSubmissions([]);
      setVerification(null);
      setOnboarding(null);
      setOnboardingResult(null);
      setView("home");
      setError("");
    }
  }

  async function beginOnboarding() {
    setError("");
    setBusy(true);
    try {
      const start = await api.onboardingStart();
      setOnboarding({
        sessionId: start.session_id,
        question: start.question,
        index: 0,
        confidence: 65,
        answer: "",
        data_origin: start.data_origin,
      });
      setOnboardingResult(null);
      setView("onboarding");
    } catch (reason) {
      showError(reason);
    } finally {
      setBusy(false);
    }
  }

  async function submitOnboarding() {
    if (!onboarding?.answer) {
      setError("Choose an answer to continue.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await api.onboardingAnswer(
        {
          session_id: onboarding.sessionId,
          question_id: onboarding.question.id,
          answer: onboarding.answer,
          confidence: onboarding.confidence,
        },
        onboarding.index,
      );
      if (result.next_question)
        setOnboarding({
          ...onboarding,
          question: result.next_question,
          index: onboarding.index + 1,
          answer: "",
          data_origin: result.data_origin,
        });
      else if (result.result) {
        setOnboardingResult(result.result);
        setProfile((current) =>
          current ? { ...current, level: result.result?.level ?? current.level } : current,
        );
        setOnboarding(null);
      }
    } catch (reason) {
      showError(reason);
    } finally {
      setBusy(false);
    }
  }

  async function openLesson(id: string) {
    setView("lesson");
    setBusy(true);
    setError("");
    setLessonCheck({});
    setLessonSaved("");
    setLessonResult(null);
    try {
      setLesson(await api.lesson(id));
    } catch (reason) {
      showError(reason);
    } finally {
      setBusy(false);
    }
  }

  async function finishLesson() {
    if (!lesson) return;
    const answers = lesson.check_questions
      .filter((question) => lessonCheck[question.id])
      .map((question) => ({ question_id: question.id, answer: lessonCheck[question.id] }));
    if (answers.length === 0) {
      setError("Answer at least one quick-check question to continue.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await api.lessonCheck(lesson.id, answers);
      setLessonResult(result);
      setLessonSaved(
        `${Math.round(result.score_pct)}% on the quick check. Your learning path is now ${Math.round(result.plan_progress_pct)}% complete.`,
      );
      setPlan(await api.plan());
    } catch (reason) {
      showError(reason);
    } finally {
      setBusy(false);
    }
  }

  async function beginAssessment() {
    if ((profile?.level ?? 1) >= 4) {
      notify("You have completed every level. Try the Nasdaq capstone next.");
      return;
    }
    setBusy(true);
    setError("");
    setAssessmentResult(null);
    setAssessmentAnswers({});
    try {
      setAssessment(await api.assessmentStart(profile?.level ?? 1));
      setView("assessment");
    } catch (reason) {
      showError(reason);
    } finally {
      setBusy(false);
    }
  }

  async function submitAssessment() {
    if (!assessment) return;
    const answers = assessment.items.map((item) => ({
      item_id: item.id,
      answer: assessmentAnswers[item.id]?.answer ?? "",
      confidence: assessmentAnswers[item.id]?.confidence ?? 50,
    }));
    if (answers.some((answer) => !answer.answer)) {
      setError("Answer each question before you continue.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await api.assessmentSubmit(assessment.assessment_id, answers);
      setAssessmentResult(result);
      if (result.new_level && profile)
        setProfile({
          ...profile,
          level: result.new_level > profile.level ? result.new_level : profile.level,
          unlocks: [...new Set([...profile.unlocks, ...result.unlocked])],
        });
    } catch (reason) {
      showError(reason);
    } finally {
      setBusy(false);
    }
  }

  async function openScenario() {
    setBusy(true);
    setError("");
    setScenarioResult(null);
    setScenarioAnswer("");
    setSelectedClues([]);
    try {
      setScenario(await api.scenarioNext());
      setView("scenario");
    } catch (reason) {
      showError(reason);
    } finally {
      setBusy(false);
    }
  }

  async function revealScenario() {
    if (!scenario || !scenarioAnswer || selectedClues.length === 0) {
      setError("Choose a direction and at least one clue.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      setScenarioResult(
        await api.scenarioAnswer(scenario.id, {
          direction: scenarioAnswer,
          confidence: scenarioConfidence,
          clues: selectedClues,
        }),
      );
    } catch (reason) {
      showError(reason);
    } finally {
      setBusy(false);
    }
  }

  async function runExplain(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setExplain(null);
    try {
      setExplain(await api.explain(symbol.trim().toUpperCase(), Number(year)));
    } catch (reason) {
      if (reason instanceof ApiClientError && reason.code === "EXPLAIN_NOT_FOUND")
        setError(
          "We don’t have a prepared walkthrough for that company and year yet. Try another symbol or year.",
        );
      else showError(reason);
    } finally {
      setBusy(false);
    }
  }

  function containsActionAdvice(text: string) {
    return (
      /\b(should i|tell me whether|is it time to|do i)\b/i.test(text) &&
      /\b(buy|sell|hold|recommend)\b/i.test(text)
    );
  }

  async function runVerify(payload?: { image_base64?: string }) {
    const content = verifyText.trim();
    if (!payload?.image_base64 && !verifyUrl.trim() && !content) {
      setError("Paste a message, add a link, or choose a screenshot.");
      return;
    }
    if (containsActionAdvice(content)) {
      setVerification(null);
      setError("I can help check a source and explain evidence. I can’t choose an action for you.");
      return;
    }
    setBusy(true);
    setError("");
    setVerifyUnavailable(false);
    setVerification(null);
    setSourceDetail(null);
    setVerifyProgress(1);
    try {
      const result = await api.verify({
        ...(payload ?? {}),
        ...(verifyUrl.trim() ? { url: verifyUrl.trim() } : {}),
        ...(content ? { text: content } : {}),
        ...(userGuess ? { user_guess: userGuess, user_confidence: userConfidence } : {}),
      });
      setVerifyProgress(2);
      setVerification(result);
      const [detail, mine] = await Promise.all([
        result.source ? api.source(result.source.id) : Promise.resolve(null),
        api.submissions(),
      ]);
      setSourceDetail(detail);
      setSubmissions(mine);
      setVerifyProgress(3);
    } catch (reason) {
      if (isToolLocked(reason))
        setError(
          `The verifier opens at Level ${reason.requiredLevel ?? 3}. Continue your learning path to unlock it.`,
        );
      else if (
        reason instanceof ApiClientError &&
        (reason.code === "CONFIGURATION_ERROR" || reason.status >= 500)
      ) {
        setVerifyProgress(0);
        setVerifyUnavailable(true);
      } else showError(reason);
    } finally {
      setBusy(false);
    }
  }

  async function onScreenshot(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("Choose an image file.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("Choose an image smaller than 10 MB.");
      return;
    }
    const reader = new FileReader();
    reader.onload = async () => {
      const value = String(reader.result ?? "");
      await runVerify({ image_base64: value.split(",")[1] ?? value });
    };
    reader.readAsDataURL(file);
  }

  async function openDashboard() {
    setBusy(true);
    setError("");
    try {
      setDashboard(await api.dashboard());
      setView("progress");
    } catch (reason) {
      if (isToolLocked(reason))
        setError(`Your skill dashboard opens at Level ${reason.requiredLevel ?? 4}.`);
      else showError(reason);
    } finally {
      setBusy(false);
    }
  }

  function navigate(target: View) {
    const entry = navItems.find((item) => item.id === target);
    const locked = Boolean(entry?.level && (profile?.level ?? 0) < entry.level);
    setError("");
    setView(target);
    if (locked) return;
    if (target === "scenario") void openScenario();
    if (target === "progress") void openDashboard();
    if (target === "learn" && !plan) void api.plan().then(setPlan).catch(showError);
  }

  if (!profile) {
    return (
      <AuthScreen
        theme={theme}
        onToggleTheme={() => setTheme(theme === "light" ? "dark" : "light")}
        onAuthenticated={loadAuthenticatedUser}
        notice={authNotice}
      />
    );
  }

  if (!profile.onboarding_completed) {
    return (
      <ProfileOnboarding
        key={profile.id}
        me={profile}
        theme={theme}
        onToggleTheme={() => setTheme(theme === "light" ? "dark" : "light")}
        onProfileUpdated={setProfile}
        onComplete={async ({ startAssessment }) => {
          setProfile((current) => (current ? { ...current, onboarding_completed: true } : current));
          if (startAssessment) {
            await beginOnboarding();
          } else {
            setView("home");
            notify("Your workspace is ready.");
          }
        }}
        onSignOut={signOut}
      />
    );
  }

  const isLocked = (entry: NavItem) => Boolean(entry.level && profile.level < entry.level);
  return (
    <TooltipProvider>
      <div className="app-shell" data-theme={theme}>
        <div className="ambient-backdrop" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <aside className="sidebar">
          <Button
            variant="quiet"
            className="sidebar-brand"
            onClick={() => navigate("home")}
            aria-label="PaisaProof overview"
          >
            <span className="brand-mark">P</span>
            <span>
              PaisaProof<small>LEARNING STUDIO</small>
            </span>
          </Button>
          <div className="side-label">YOUR SPACE</div>
          <nav aria-label="Main navigation">
            {navItems.map((item) => (
              <Button
                variant="quiet"
                key={item.id}
                className={`nav-link ${view === item.id || (view === "lesson" && item.id === "learn") || (view === "assessment" && item.id === "learn") ? "selected" : ""} ${isLocked(item) ? "locked" : ""}`}
                onClick={() => navigate(item.id)}
                aria-current={view === item.id ? "page" : undefined}
              >
                <span className="nav-icon" aria-hidden="true">
                  <item.icon size={19} strokeWidth={1.8} />
                </span>
                <span>{item.label}</span>
                {isLocked(item) && <span className="nav-level">Level {item.level}</span>}
              </Button>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="level-card">
              <div className="level-card-head">
                <span className="level-star">✦</span>
                <span>YOUR LEVEL</span>
                <strong>
                  {profile.level}
                  <small>/ 4</small>
                </strong>
              </div>
              <ProgressBar value={(profile.level / 4) * 100} />
              <p>
                {profile.level < 4
                  ? `Next tools open at Level ${profile.level + 1}`
                  : "All learning tools are open"}
              </p>
            </div>
            <Button
              variant="quiet"
              className="sidebar-help"
              onClick={() =>
                notify(
                  "Questions or feedback? Tell your team lead; it goes straight to the builders.",
                )
              }
            >
              <CircleHelp size={17} aria-hidden="true" /> Help & feedback
            </Button>
          </div>
        </aside>
        <div className="main-column">
          <header className="topbar">
            <Button variant="quiet" className="mobile-brand" onClick={() => navigate("home")}>
              <span className="brand-mark">P</span>PaisaProof
            </Button>
            <div className="breadcrumb">
              <span>Workspace</span>
              <Separator orientation="vertical" className="crumb-sep" />
              <strong>{activeNav}</strong>
            </div>
            <div className="topbar-right">
              <Button
                variant="quiet"
                className="theme-toggle"
                onClick={() => setTheme(theme === "light" ? "dark" : "light")}
                aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
                aria-pressed={theme === "dark"}
              >
                {theme === "light" ? <Moon size={17} /> : <Sun size={17} />}
              </Button>
              <Chip className="streak-chip">
                <span aria-hidden="true">✦</span> Level {profile.level} of 4
              </Chip>
              <Tooltip label={profile.name}>
                <Button
                  variant="quiet"
                  className="avatar-button"
                  onClick={() => navigate("profile")}
                  aria-label={`${profile.name} profile`}
                >
                  <Avatar>
                    {profile.profile?.avatar_url && (
                      <AvatarImage src={profile.profile.avatar_url} alt={profile.name} />
                    )}
                    <AvatarFallback>{avatarInitials(profile.name)}</AvatarFallback>
                  </Avatar>
                </Button>
              </Tooltip>
              <Tooltip label="Sign out">
                <Button
                  variant="quiet"
                  className="theme-toggle"
                  onClick={() => void signOut()}
                  aria-label="Sign out"
                >
                  <LogOut size={17} />
                </Button>
              </Tooltip>
            </div>
          </header>
          <main className="page-content">
            {error && (
              <div className="inline-error" role="alert">
                <span aria-hidden="true">!</span>
                {error}
                <Button
                  variant="quiet"
                  className="error-dismiss"
                  onClick={clearError}
                  aria-label="Dismiss error"
                >
                  ×
                </Button>
              </div>
            )}
            {view === "home" && (
              <HomeView
                profile={profile}
                plan={plan}
                submissions={submissions}
                busy={busy}
                onStart={beginOnboarding}
                onLearn={() => navigate("learn")}
                onScenario={openScenario}
                onVerifier={() => navigate("verifier")}
              />
            )}
            {view === "onboarding" && (
              <OnboardingView
                state={onboarding}
                result={onboardingResult}
                busy={busy}
                onAnswer={(answer) =>
                  setOnboarding((current) => (current ? { ...current, answer } : current))
                }
                onConfidence={(confidence) =>
                  setOnboarding((current) => (current ? { ...current, confidence } : current))
                }
                onNext={submitOnboarding}
                onStart={beginOnboarding}
                onContinue={() => {
                  setOnboardingResult(null);
                  setView("home");
                  notify("Your learning path is ready.");
                }}
              />
            )}
            {view === "learn" && (
              <LearningView
                plan={plan}
                busy={busy}
                onOpen={openLesson}
                onAssess={beginAssessment}
              />
            )}
            {view === "lesson" && (
              <LessonView
                lesson={lesson}
                check={lessonCheck}
                setCheck={setLessonCheck}
                saved={lessonSaved}
                result={lessonResult}
                busy={busy}
                onBack={() => setView("learn")}
                onContinue={finishLesson}
                onAssess={beginAssessment}
              />
            )}
            {view === "assessment" && (
              <AssessmentView
                assessment={assessment}
                answers={assessmentAnswers}
                setAnswers={setAssessmentAnswers}
                result={assessmentResult}
                busy={busy}
                level={profile.level}
                onSubmit={submitAssessment}
                onLearn={() => {
                  setAssessmentResult(null);
                  setView("learn");
                }}
                onContinue={() => {
                  setAssessmentResult(null);
                  setView("home");
                }}
              />
            )}
            {view === "scenario" &&
              (profile.level < 1 ? (
                <LockNotice level={1} current={profile.level} onLearn={() => navigate("learn")} />
              ) : (
                <ScenarioView
                  scenario={scenario}
                  result={scenarioResult}
                  answer={scenarioAnswer}
                  confidence={scenarioConfidence}
                  clues={selectedClues}
                  busy={busy}
                  setAnswer={setScenarioAnswer}
                  setConfidence={setScenarioConfidence}
                  setClues={setSelectedClues}
                  onReveal={revealScenario}
                  onNext={openScenario}
                />
              ))}
            {view === "explain" &&
              (profile.level < 2 ? (
                <LockNotice level={2} current={profile.level} onLearn={() => navigate("learn")} />
              ) : (
                <ExplainView
                  symbol={symbol}
                  year={year}
                  result={explain}
                  busy={busy}
                  setSymbol={setSymbol}
                  setYear={setYear}
                  onSubmit={runExplain}
                />
              ))}
            {view === "verifier" &&
              (profile.level < 3 ? (
                <LockNotice level={3} current={profile.level} onLearn={() => navigate("learn")} />
              ) : (
                <VerifierView
                  text={verifyText}
                  setText={setVerifyText}
                  url={verifyUrl}
                  setUrl={setVerifyUrl}
                  guess={userGuess}
                  setGuess={setUserGuess}
                  confidence={userConfidence}
                  setConfidence={setUserConfidence}
                  result={verification}
                  source={sourceDetail}
                  submissions={submissions}
                  busy={busy}
                  verifyProgress={verifyProgress}
                  unavailable={verifyUnavailable}
                  level={profile.level}
                  searchSource={searchSource}
                  setSearchSource={setSearchSource}
                  onSubmit={runVerify}
                  onScreenshot={onScreenshot}
                />
              ))}
            {view === "nasdaq" &&
              (profile.level < 4 ? (
                <LockNotice level={4} current={profile.level} onLearn={() => navigate("learn")} />
              ) : (
                <NasdaqVerifier />
              ))}
            {view === "progress" &&
              (profile.level < 4 ? (
                <LockNotice level={4} current={profile.level} onLearn={() => navigate("learn")} />
              ) : (
                <ProgressView data={dashboard} />
              ))}
            {view === "profile" && (
              <ProfilePanel
                profile={profile}
                onProfileUpdated={setProfile}
                onRetakeLevelCheck={() => void beginOnboarding()}
                onSignOut={signOut}
              />
            )}
          </main>
          <footer className="app-footer">
            <span>PaisaProof · Learn to read the signal</span>
            <span>Progress is personal. The market is uncertain.</span>
            {BUILD_LABEL && <small className="build-label">{BUILD_LABEL}</small>}
          </footer>
        </div>
        <nav className="mobile-nav" aria-label="Mobile navigation">
          {navItems.map((item) => {
            const current =
              view === item.id ||
              ((view === "lesson" || view === "assessment") && item.id === "learn");
            return (
              <Button
                variant="quiet"
                key={item.id}
                className={`mobile-nav-item ${current ? "selected" : ""} ${isLocked(item) ? "locked" : ""}`}
                onClick={() => navigate(item.id)}
                aria-current={view === item.id ? "page" : undefined}
                aria-label={
                  isLocked(item) ? `${item.label} (unlocks at Level ${item.level})` : item.label
                }
              >
                <item.icon size={18} strokeWidth={1.8} aria-hidden="true" />
                <span>{item.label.split(" ")[0]}</span>
                {isLocked(item) && (
                  <em role="img" aria-label={`Unlocks at Level ${item.level}`}>
                    L{item.level}
                  </em>
                )}
              </Button>
            );
          })}
          <Button
            variant="quiet"
            className="mobile-nav-item"
            onClick={() => void signOut()}
            aria-label="Sign out"
          >
            <LogOut size={18} strokeWidth={1.8} aria-hidden="true" />
            <span>Sign out</span>
          </Button>
        </nav>
        <Toaster theme={theme} />
      </div>
    </TooltipProvider>
  );
}

function HomeView({
  profile,
  plan,
  submissions,
  busy,
  onStart,
  onLearn,
  onScenario,
  onVerifier,
}: {
  profile: UserProfile;
  plan: LearningPlan | null;
  submissions: SubmissionSummary[];
  busy: boolean;
  onStart: () => void;
  onLearn: () => void;
  onScenario: () => void;
  onVerifier: () => void;
}) {
  const hasVerifier = profile.level >= 3;
  return (
    <>
      <div className="home-greeting">
        <div>
          <span className="eyebrow">YOUR LEARNING SPACE</span>
          <h1>
            {greeting()}, {profile.name} <span className="wave">✳</span>
          </h1>
          <p>A little practice today can make the next big claim easier to question.</p>
        </div>
      </div>
      <div className="hero-card">
        <div className="hero-illustration" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="orbit-center">✳</div>
          <span className="orbit-dot dot-one" />
          <span className="orbit-dot dot-two" />
          <span className="orbit-dot dot-three" />
        </div>
        <div className="hero-text">
          <span className="hero-kicker">YOUR NEXT SMALL STEP</span>
          <h2>
            Start with your
            <br />
            <em>learning check-in.</em>
          </h2>
          <p>A short set of questions helps us find the right place for you to begin.</p>
          <Button onClick={onStart}>
            Begin check-in <span aria-hidden="true">→</span>
          </Button>
        </div>
        <div className="hero-side-note">
          <span>ABOUT 5 MIN</span>
          <i /> No score to pass
        </div>
      </div>
      <div className="section-row">
        <div>
          <span className="eyebrow">A GOOD PLACE TO BEGIN</span>
          <h2>Pick up where you are</h2>
        </div>
        <Button variant="quiet" className="text-link" onClick={onLearn}>
          View learning path <span aria-hidden="true">→</span>
        </Button>
      </div>
      <div className="home-cards">
        <Button variant="quiet" className="home-action-card" onClick={onLearn}>
          <span className="card-icon green">▤</span>
          {plan && <DataBadge origin="synthetic" />}
          <span className="card-meta">YOUR LEARNING PATH</span>
          <strong>{plan ? `${plan.progress_pct}%` : busy ? "…" : "Start here"}</strong>
          <span className="card-foot">
            Continue a short lesson <b>↗</b>
          </span>
          <ProgressBar value={plan?.progress_pct ?? 0} />
        </Button>
        <Button variant="quiet" className="home-action-card" onClick={onScenario}>
          <span className="card-icon amber">⌁</span>
          <span className="card-meta">PRACTICE SCENARIOS</span>
          <strong>Read the clues</strong>
          <span className="card-foot">
            Try a 2-minute practice <b>↗</b>
          </span>
          <span className="mini-bars" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
            <i />
            <i />
            <i />
          </span>
        </Button>
        <Button variant="quiet" className="home-action-card" onClick={onVerifier}>
          <span className="card-icon lilac">⌕</span>
          <span className="card-meta">SOURCE VERIFIER</span>
          <strong>{hasVerifier ? "Check a claim" : `Unlocks at Level ${verifierLevel}`}</strong>
          <span className="card-foot">
            Look into a shared message <b>↗</b>
          </span>
          <span className="lock-dash">
            {hasVerifier
              ? "Available now"
              : `${Math.max(1, verifierLevel - profile.level)} level${verifierLevel - profile.level > 1 ? "s" : ""} to go`}
          </span>
        </Button>
      </div>
      <div className="home-lower">
        <Panel className="welcome-note">
          <div className="note-icon">✦</div>
          <div>
            <span className="eyebrow">A NOTE TO KEEP</span>
            <h3>Confidence is a skill.</h3>
            <p>
              A strong learner knows what they know—and stays curious about the rest. Your progress
              is about judgement, not prediction.
            </p>
          </div>
        </Panel>
        <Panel className="recent-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">RECENT ACTIVITY</span>
              <h3>Your checked tips</h3>
            </div>
            <Chip shape="round" className="count-pill">
              {submissions.length}
            </Chip>
          </div>
          {submissions.length ? (
            <ul className="recent-list">
              {submissions.slice(0, 2).map((item) => (
                <li key={item.submission_id}>
                  <span className="recent-status">{item.status === "scored" ? "✓" : "…"}</span>
                  <span>
                    <strong>{item.claim?.symbol ?? "Submitted tip"}</strong>
                    <small>
                      {item.status === "scored" ? "Outcome checked" : "Still being reviewed"}
                    </small>
                  </span>
                  <DataBadge origin={item.data_origin} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Your checked items will appear here.</p>
          )}
        </Panel>
      </div>
    </>
  );
}

function OnboardingView({
  state,
  result,
  busy,
  onAnswer,
  onConfidence,
  onNext,
  onStart,
  onContinue,
}: {
  state: {
    sessionId: string;
    question: Question;
    index: number;
    confidence: number;
    answer: string;
  } | null;
  result: OnboardingResult | null;
  busy: boolean;
  onAnswer: (value: string) => void;
  onConfidence: (value: number) => void;
  onNext: () => void;
  onStart: () => void;
  onContinue: () => void;
}) {
  if (result)
    return (
      <div className="narrow-view">
        <SectionHeading eyebrow="YOUR STARTING POINT" title="A learning path that fits." />
        <Panel className="result-panel">
          <div className="result-orbit">✳</div>
          <span className="eyebrow">QUICK CHECK COMPLETE</span>
          <h2>Level {result.level} · Reading a stock</h2>
          <p>
            Your answers suggest a good next focus: checking who is behind a claim and how strong
            the evidence is.
          </p>
          <DataBadge origin="synthetic" />
          <div className="skill-bars">
            {Object.entries(result.skills).map(([skill, score]) => (
              <div className="skill-bar" key={skill}>
                <div>
                  <span>{formatLabel(skill)}</span>
                  <strong>{score}%</strong>
                </div>
                <ProgressBar value={score ?? 0} />
              </div>
            ))}
          </div>
          <p className="calibration-note">
            Your confidence and your answers will become easier to compare as you practice. Starting
            Brier score: <strong>{result.brier.toFixed(2)}</strong>
          </p>
          <Button onClick={onContinue}>
            Go to my overview <span>→</span>
          </Button>
        </Panel>
      </div>
    );
  if (!state)
    return (
      <div className="narrow-view">
        <SectionHeading eyebrow="QUICK CHECK" title="Find your starting point." />
        <Panel>
          <p>A short set of questions will help shape your learning plan.</p>
          <Button onClick={onStart} disabled={busy}>
            Start check-in
          </Button>
        </Panel>
      </div>
    );
  return (
    <div className="narrow-view">
      <div className="flow-top">
        <Button variant="quiet" className="back-button" onClick={onStart}>
          ← Overview
        </Button>
        <span className="flow-step">
          Question {state.index + 1} <span>of about 12</span>
        </span>
      </div>
      <ProgressBar
        value={Math.min(100, ((state.index + 1) / 12) * 100)}
        label="Check-in progress"
      />
      <Panel className="quiz-panel">
        <div className="panel-heading">
          <span className="eyebrow">QUICK CHECK · {formatLabel(state.question.skill_area)}</span>
          <DataBadge origin="synthetic" />
        </div>
        <h2 id="onboarding-question">{state.question.text}</h2>
        <RadioGroup
          value={state.answer}
          onValueChange={onAnswer}
          aria-labelledby="onboarding-question"
          className="quiz-options"
        >
          {state.question.options.map((option) => (
            <ChoiceOption key={option} value={option} selected={state.answer === option}>
              {option}
            </ChoiceOption>
          ))}
        </RadioGroup>
        <ConfidenceControl
          value={state.confidence}
          onChange={onConfidence}
          label="How sure do you feel?"
        />
        <Button onClick={onNext} disabled={busy || !state.answer}>
          {busy ? "Saving…" : state.index === 2 ? "See my starting point" : "Continue"}
          <span>→</span>
        </Button>
      </Panel>
      <p className="centered-note">Your answers help us choose a useful next lesson.</p>
    </div>
  );
}

function LearningView({
  plan,
  busy,
  onOpen,
  onAssess,
}: {
  plan: LearningPlan | null;
  busy: boolean;
  onOpen: (id: string) => void;
  onAssess: () => void;
}) {
  return (
    <>
      <SectionHeading
        eyebrow="YOUR LEARNING PATH"
        title="Small lessons. Stronger judgement."
        action={<DataBadge origin="synthetic" />}
      />
      <div className="learning-summary">
        <div>
          <strong>{plan?.progress_pct ?? 0}%</strong>
          <span>path complete</span>
        </div>
        <ProgressBar value={plan?.progress_pct ?? 0} />
        <Chip className="level-pill">LEVEL {plan?.level ?? 2}</Chip>
      </div>
      <div className="lesson-list">
        {(plan?.lessons ?? []).map((item, index) => (
          <Panel className={`lesson-row ${item.status}`} key={item.id}>
            <div className="lesson-index">
              {item.status === "completed" ? "✓" : String(index + 1).padStart(2, "0")}
            </div>
            <div className="lesson-info">
              <span className="eyebrow">
                {item.minutes} min ·{" "}
                {item.status === "in_progress" ? "Pick up here" : sentenceCase(item.status)}
              </span>
              <h3>{item.title}</h3>
              <p>
                {item.status === "locked"
                  ? "Complete the current quick check to open this lesson."
                  : "A short guide with clear examples and a quick knowledge check."}
              </p>
            </div>
            <Button
              variant="quiet"
              className="lesson-open"
              onClick={() => item.status !== "locked" && onOpen(item.id)}
              disabled={busy || item.status === "locked"}
              aria-label={`Open ${item.title}`}
            >
              {item.status === "locked" ? <Lock size={16} aria-hidden="true" /> : "→"}
            </Button>
          </Panel>
        ))}
      </div>
      <div className="assessment-callout">
        <div>
          <span className="eyebrow">READY TO CHECK IN?</span>
          <h3>See what has stayed with you.</h3>
          <p>A short assessment can open the next set of learning tools.</p>
        </div>
        <Button variant="secondary" onClick={onAssess} disabled={busy}>
          Start assessment <span>→</span>
        </Button>
      </div>
    </>
  );
}

function LessonView({
  lesson,
  check,
  setCheck,
  saved,
  result,
  busy,
  onBack,
  onContinue,
  onAssess,
}: {
  lesson: Lesson | null;
  check: Record<string, string>;
  setCheck: (value: Record<string, string>) => void;
  saved: string;
  result: LessonCheckResponse | null;
  busy: boolean;
  onBack: () => void;
  onContinue: () => void;
  onAssess: () => void;
}) {
  const questions = lesson?.check_questions ?? [];
  const allAnswered = questions.length > 0 && questions.every((q) => Boolean(check[q.id]));
  const feedbackFor = (id: string) => result?.feedback?.find((item) => item.question_id === id);
  const total = result?.total_count ?? questions.length;
  const hasCounts = result?.correct_count !== undefined && total > 0;
  return (
    <div className="lesson-reader">
      <Button variant="quiet" className="back-button" onClick={onBack}>
        ← Learning path
      </Button>
      {busy && <Panel>Loading lesson…</Panel>}
      {lesson && (
        <>
          <div className="lesson-reader-head">
            <span className="eyebrow">
              {lesson.level ? `LEVEL ${lesson.level}` : "LESSON"}
              {lesson.minutes ? ` · ${lesson.minutes} MIN READ` : ""}
            </span>
            <h1>{lesson.title}</h1>
          </div>
          <Panel className="reading-panel">
            <DataBadge origin="synthetic" />
            {lesson.sections.map((section, index) => (
              <div className="reading-section" key={index}>
                <span className="reading-number">{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <h3>{section.heading}</h3>
                  <p>{section.body}</p>
                  {(section.takeaway ?? section.example) && (
                    <p className="muted">Takeaway: {section.takeaway ?? section.example}</p>
                  )}
                </div>
              </div>
            ))}
          </Panel>
          {questions.map((question, qIndex) => (
            <Panel className="lesson-check" key={question.id}>
              <div className="panel-heading">
                <span className="eyebrow">
                  QUICK CHECK · {qIndex + 1} OF {questions.length}
                </span>
                <DataBadge origin={lesson.data_origin} />
              </div>
              <h3 id={`lesson-question-${qIndex}`}>{question.text}</h3>
              <RadioGroup
                value={check[question.id] ?? ""}
                onValueChange={(value) => setCheck({ ...check, [question.id]: value })}
                aria-labelledby={`lesson-question-${qIndex}`}
                className="quiz-options"
              >
                {question.options.map((option) => (
                  <ChoiceOption
                    key={option}
                    value={option}
                    selected={check[question.id] === option}
                  >
                    {option}
                  </ChoiceOption>
                ))}
              </RadioGroup>
              {(() => {
                const item = feedbackFor(question.id);
                if (!item || item.correct === undefined) return null;
                return (
                  <div
                    className={`fb-answer-feedback ${item.correct ? "correct" : "incorrect"}`}
                    role="status"
                  >
                    <strong>{item.correct ? "Correct" : "Not quite"}</strong>
                    {item.explanation && <p>{item.explanation}</p>}
                  </div>
                );
              })()}
            </Panel>
          ))}
          {saved && (
            <div className="inline-feedback" role="status">
              {hasCounts && (
                <strong className="fb-lesson-score">
                  {result!.correct_count} of {total} correct.{" "}
                </strong>
              )}
              {saved}
            </div>
          )}
          <div className="reader-actions">
            <Button variant="secondary" onClick={onBack}>
              Save and leave
            </Button>
            <Button onClick={onContinue} disabled={busy || !allAnswered || Boolean(saved)}>
              {saved ? "Saved" : "Check my answers"} <span>→</span>
            </Button>
            {saved && (
              <Button onClick={onAssess}>
                Continue to assessment <span>→</span>
              </Button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function AssessmentView({
  assessment,
  answers,
  setAnswers,
  result,
  busy,
  level,
  onSubmit,
  onLearn,
  onContinue,
}: {
  assessment: Assessment | null;
  answers: Record<string, { answer: string; confidence: number }>;
  setAnswers: React.Dispatch<
    React.SetStateAction<Record<string, { answer: string; confidence: number }>>
  >;
  result: AssessmentResult | null;
  busy: boolean;
  level: number;
  onSubmit: () => void;
  onLearn: () => void;
  onContinue: () => void;
}) {
  if (result)
    return (
      <div className="narrow-view">
        <SectionHeading
          eyebrow="QUICK CHECK"
          title={
            result.passed ? "You’re ready for the next level." : "Keep building your confidence."
          }
        />
        <Panel className="assessment-result">
          <div className="pass-ring">{result.passed ? "✓" : "↻"}</div>
          <DataBadge origin="synthetic" />
          <h2>
            {result.passed
              ? `Level ${result.new_level ?? level + 1} unlocked`
              : "One more practice round"}
          </h2>
          <p>
            {result.passed
              ? "Your answers show stronger judgement across the skills you practised."
              : "Review the lesson and try again when you feel ready."}
          </p>
          <div className="result-metrics">
            <div>
              <strong>{result.score}%</strong>
              <span>Check score</span>
            </div>
            <div>
              <strong>{result.brier.toFixed(2)}</strong>
              <span>Confidence score</span>
            </div>
          </div>
          {result.unlocked.length > 0 && (
            <div className="unlock-card">
              <span className="unlock-burst">✦</span>
              <div>
                <span className="eyebrow">NEW LEARNING TOOL</span>
                <strong>{result.unlocked.map(formatLabel).join(", ")}</strong>
                <small>Ready when you are</small>
              </div>
              <span className="unlock-arrow">↗</span>
            </div>
          )}
          <Button onClick={result.passed ? onContinue : onLearn}>
            {result.passed ? "Return to overview" : "Review learning path"}
            <span>→</span>
          </Button>
        </Panel>
      </div>
    );
  if (!assessment)
    return (
      <div className="narrow-view">
        <SectionHeading eyebrow="QUICK CHECK" title="A few questions to reflect." />
        <Panel>
          <p>Loading your questions…</p>
          {busy && <Skeleton className="skeleton-line" />}
        </Panel>
      </div>
    );
  return (
    <div className="narrow-view">
      <div className="flow-top">
        <Button variant="quiet" className="back-button" onClick={onLearn}>
          ← Learning path
        </Button>
        <span className="flow-step">{assessment.items.length} questions</span>
      </div>
      <SectionHeading
        eyebrow={`LEVEL ${level} · QUICK CHECK`}
        title="Show what you have learned."
        action={<DataBadge origin="synthetic" />}
      />
      {assessment.items.map((item, index) => (
        <Panel className="assessment-question" key={item.id}>
          <div className="panel-heading">
            <span className="eyebrow">
              QUESTION {index + 1} · {formatLabel(item.skill_area)}
            </span>
            <DataBadge origin="synthetic" />
          </div>
          <h3 id={`assessment-question-${item.id}`}>{item.text}</h3>
          <RadioGroup
            value={answers[item.id]?.answer ?? ""}
            onValueChange={(answer) =>
              setAnswers((current) => ({
                ...current,
                [item.id]: { answer, confidence: current[item.id]?.confidence ?? 65 },
              }))
            }
            aria-labelledby={`assessment-question-${item.id}`}
            className="quiz-options"
          >
            {item.options.map((option) => (
              <ChoiceOption
                key={option}
                value={option}
                selected={answers[item.id]?.answer === option}
              >
                {option}
              </ChoiceOption>
            ))}
          </RadioGroup>
          <ConfidenceControl
            label="How sure are you?"
            value={answers[item.id]?.confidence ?? 65}
            onChange={(confidence) =>
              setAnswers((current) => ({
                ...current,
                [item.id]: { answer: current[item.id]?.answer ?? "", confidence },
              }))
            }
          />
        </Panel>
      ))}
      <Button onClick={onSubmit} disabled={busy}>
        {busy ? "Checking…" : "Finish learning check"}
        <span>→</span>
      </Button>
    </div>
  );
}

function ScenarioView({
  scenario,
  result,
  answer,
  confidence,
  clues,
  busy,
  setAnswer,
  setConfidence,
  setClues,
  onReveal,
  onNext,
}: {
  scenario: Scenario | null;
  result: ScenarioResult | null;
  answer: "up" | "down" | "";
  confidence: number;
  clues: string[];
  busy: boolean;
  setAnswer: (value: "up" | "down") => void;
  setConfidence: (value: number) => void;
  setClues: React.Dispatch<React.SetStateAction<string[]>>;
  onReveal: () => void;
  onNext: () => void;
}) {
  if (!scenario)
    return (
      <div className="narrow-view">
        <SectionHeading eyebrow="PRACTICE SCENARIO" title="Read the clues." />
        <Panel>Loading your practice scenario…</Panel>
      </div>
    );
  const clueOptions = [
    "Price moved before the message",
    "A dated company or exchange notice",
    "The broad index moved the same way",
    "A source makes a claim without evidence",
  ];
  return (
    <>
      <SectionHeading
        eyebrow="PRACTICE SCENARIO"
        title="Read the clues. Make a call."
        action={<DataBadge origin={scenario.data_origin} />}
      />
      <div className="scenario-layout fb-chart-first">
        <div className="scenario-main">
          <Panel className="scenario-chart-panel fb-chart-first-chart">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">{scenario.context.company}</span>
                <h3>Company price movement</h3>
              </div>
              <DataBadge origin={scenario.data_origin} />
            </div>
            <ScenarioChart scenario={scenario} />
            <div className="chart-key">
              <span>
                <i className="line-solid" /> Company
              </span>
              {chartHasIndex(scenario.context.chart) && (
                <span>
                  <i className="line-dashed" /> Index
                </span>
              )}
              <small>Data shown up to {scenario.as_of_date}</small>
            </div>
          </Panel>
          <Panel>
            <div className="panel-heading">
              <div>
                <span className="eyebrow">WHAT ELSE DO WE KNOW?</span>
                <h3>Context from this case</h3>
              </div>
              <DataBadge origin={scenario.data_origin} />
            </div>
            <div className="number-grid">
              {Object.entries(scenario.context.numbers).map(([label, value]) => (
                <div key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            <div className="headline-list">
              {scenario.context.headlines.map((headline) => (
                <div className="headline-item" key={headline.date}>
                  <span className="timeline-date">{headline.date}</span>
                  <div>
                    <strong>{headline.text}</strong>
                    <small>{headline.source}</small>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
        <div className="scenario-side">
          {!result ? (
            <Panel className="answer-panel">
              <span className="eyebrow">YOUR READ</span>
              <h3 id="scenario-direction-question">Over this period, the company will…</h3>
              <RadioGroup
                value={answer}
                onValueChange={(value) => {
                  if (value === "up" || value === "down") setAnswer(value);
                }}
                aria-labelledby="scenario-direction-question"
                className="direction-options"
              >
                <ChoiceOption value="up" selected={answer === "up"}>
                  <span aria-hidden="true">↗</span> Outperform the index
                </ChoiceOption>
                <ChoiceOption value="down" selected={answer === "down"}>
                  <span aria-hidden="true">↘</span> Underperform the index
                </ChoiceOption>
              </RadioGroup>
              <ConfidenceControl
                label="How confident are you?"
                value={confidence}
                onChange={setConfidence}
              />
              <span className="eyebrow clue-label">WHICH CLUES MATTER TO YOU?</span>
              <div className="clue-picker">
                {clueOptions.map((clue, index) => {
                  const labelId = `clue-label-${index}`;
                  const checked = clues.includes(clue);
                  return (
                    <div className="clue-picker-option" key={clue}>
                      <Checkbox
                        checked={checked}
                        aria-labelledby={labelId}
                        onCheckedChange={(next) =>
                          setClues((current) =>
                            next === true
                              ? [...current, clue]
                              : current.filter((item) => item !== clue),
                          )
                        }
                      />
                      <span id={labelId}>{clue}</span>
                    </div>
                  );
                })}
              </div>
              <Button onClick={onReveal} disabled={busy}>
                {busy ? "Checking your call…" : "Reveal the outcome"}
                <span>→</span>
              </Button>
              <p className="fine-print">
                This exercise is about your judgement, not a company rating.
              </p>
            </Panel>
          ) : (
            <Panel className="scenario-result">
              <span className="eyebrow">CASE REVEALED</span>
              <h3>
                {result.correct ? "Your read matched this outcome." : "Here’s what happened."}
              </h3>
              <DataBadge origin={scenario.data_origin} />
              <div className="outcome-pair">
                <div>
                  <span>Company</span>
                  <strong className={result.outcome.stock_pct < 0 ? "negative" : "positive"}>
                    {result.outcome.stock_pct > 0 ? "+" : ""}
                    {result.outcome.stock_pct}%
                  </strong>
                </div>
                <i>vs</i>
                <div>
                  <span>Index</span>
                  <strong className={result.outcome.index_pct < 0 ? "negative" : "positive"}>
                    {result.outcome.index_pct > 0 ? "+" : ""}
                    {result.outcome.index_pct}%
                  </strong>
                </div>
              </div>
              <p>{result.explanation}</p>
              <div className="clue-feedback">
                <strong>Clues to revisit</strong>
                {result.key_clues.map((clue) => (
                  <span key={clue}>• {clue}</span>
                ))}
              </div>
              <Button onClick={onNext} disabled={busy}>
                Try another scenario <span>→</span>
              </Button>
            </Panel>
          )}
        </div>
      </div>
    </>
  );
}

function ExplainView({
  symbol,
  year,
  result,
  busy,
  setSymbol,
  setYear,
  onSubmit,
}: {
  symbol: string;
  year: string;
  result: ExplainResult | null;
  busy: boolean;
  setSymbol: (value: string) => void;
  setYear: (value: string) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <>
      <SectionHeading
        eyebrow="EXPLAIN A STOCK"
        title="Put a price move in context."
        action={result && <DataBadge origin={result.data_origin} />}
      />
      <Panel className="search-panel">
        <form onSubmit={onSubmit} className="stock-search">
          <label>
            <span>Company or symbol</span>
            <Input
              value={symbol}
              onChange={(event) => setSymbol(event.target.value)}
              placeholder="e.g. INFY"
              aria-label="Company or symbol"
            />
          </label>
          <label>
            <span>Year</span>
            <Input
              type="number"
              value={year}
              min="2000"
              max="2026"
              onChange={(event) => setYear(event.target.value)}
              aria-label="Year"
            />
          </label>
          <Button type="submit" disabled={busy}>
            {busy ? "Looking…" : "Explain this year"}
            <span>→</span>
          </Button>
        </form>
        <div className="fb-example-chips" role="group" aria-label="Example symbols">
          <span>Try:</span>
          {["INFY", "TCS", "RELIANCE"].map((example) => (
            <Button
              key={example}
              type="button"
              variant="secondary"
              className="fb-example-chip"
              aria-pressed={symbol.toUpperCase() === example}
              onClick={() => setSymbol(example)}
            >
              {example}
            </Button>
          ))}
        </div>
        <p className="search-hint">
          We’ll show dated events alongside the company price chart. This tool explains history, not
          what comes next.
        </p>
      </Panel>
      {result && (
        <div className="explain-results">
          <Panel className="scenario-chart-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">
                  {symbol.toUpperCase()} · {year}
                </span>
                <h3>Company price history</h3>
              </div>
              <DataBadge origin={result.data_origin} />
            </div>
            <ExplainChart data={result} />
            <div className="chart-key">
              <span>
                <i className="line-solid" /> Company
              </span>
              {chartHasIndex(result.chart) && (
                <span>
                  <i className="line-dashed" /> Index
                </span>
              )}
            </div>
          </Panel>
          <Panel>
            <div className="panel-heading">
              <span className="eyebrow">A SHORT READ</span>
              <DataBadge origin={result.data_origin} />
            </div>
            <h3 className="explain-summary">{result.summary}</h3>
            <div className="move-list">
              {result.moves.map((move) => (
                <div className="move-item" key={move.date}>
                  <div className="move-date">{move.date}</div>
                  <div className="move-body">
                    <strong className={move.pct < 0 ? "negative" : "positive"}>
                      {move.pct > 0 ? "+" : ""}
                      {move.pct}% move
                    </strong>
                    {move.events.map((event) => (
                      <div className="source-event" key={event.source}>
                        <span>{event.text}</span>
                        <small>Source: {event.source}</small>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}
    </>
  );
}

function VerifierView({
  text,
  setText,
  url,
  setUrl,
  guess,
  setGuess,
  confidence,
  setConfidence,
  result,
  source,
  submissions,
  busy,
  verifyProgress,
  unavailable,
  level,
  searchSource,
  setSearchSource,
  onSubmit,
  onScreenshot,
}: {
  text: string;
  setText: (value: string) => void;
  url: string;
  setUrl: (value: string) => void;
  guess: string;
  setGuess: (value: string) => void;
  confidence: number;
  setConfidence: (value: number) => void;
  result: VerifyResult | null;
  source: SourceDetail | null;
  submissions: SubmissionSummary[];
  busy: boolean;
  verifyProgress: number;
  unavailable: boolean;
  level: number;
  searchSource: boolean;
  setSearchSource: (value: boolean) => void;
  onSubmit: (payload?: { image_base64?: string }) => void;
  onScreenshot: (event: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  const labelText: Record<string, string> = {
    reliable: "Reliable source",
    semi_reliable: "Mixed track record",
    not_reliable: "Not reliable",
    not_enough_history: "Limited history",
  };
  return (
    <>
      <SectionHeading
        eyebrow="SOURCE VERIFIER"
        title="Look closer at a shared claim."
        action={
          <Chip tone="violet" className="mode-pill">
            {(result?.mode ?? "full").toUpperCase()} MODE · LEVEL {level}
          </Chip>
        }
      />
      <div className="verifier-layout">
        <div className="verifier-input-column">
          <Panel className="verifier-form-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">CHECK A MESSAGE</span>
                <h3>Where did this come from?</h3>
              </div>
            </div>
            <Tabs
              value={searchSource ? "screenshot" : "paste"}
              onValueChange={(value) => setSearchSource(value === "screenshot")}
            >
              <TabsList className="input-tabs">
                <TabsTrigger value="paste">Paste or link</TabsTrigger>
                <TabsTrigger value="screenshot">Screenshot</TabsTrigger>
              </TabsList>
            </Tabs>
            {!searchSource ? (
              <>
                <label className="field-label" htmlFor="verify-link">
                  Link <span>Optional</span>
                </label>
                <Input
                  id="verify-link"
                  className="text-input"
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="https://…"
                />
                <label className="field-label" htmlFor="verify-text">
                  Paste the forwarded text
                </label>
                <Textarea
                  id="verify-text"
                  className="text-area"
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  placeholder="Paste a message here. We’ll look for the source and checkable clues."
                  rows={6}
                />
                <div className="guess-toggle">
                  <label className="field-label" htmlFor="guess">
                    Your first read <span>Optional</span>
                  </label>
                  <Input
                    id="guess"
                    className="text-input"
                    value={guess}
                    onChange={(event) => setGuess(event.target.value)}
                    placeholder="What do you think the claim says?"
                  />
                  <ConfidenceControl
                    label="How sure are you?"
                    value={confidence}
                    onChange={setConfidence}
                  />
                </div>
                <Button onClick={() => onSubmit()} disabled={busy}>
                  {busy ? "Checking the details…" : "Check this message"}
                  <span>→</span>
                </Button>
              </>
            ) : (
              <label className="dropzone">
                <Input type="file" accept="image/*" onChange={onScreenshot} disabled={busy} />
                <span className="drop-icon">↑</span>
                <strong>{busy ? "Reading the sample…" : "Choose a screenshot"}</strong>
                <small>PNG, JPG, or WEBP · Up to 10 MB</small>
                <span className="drop-link">Browse files</span>
              </label>
            )}
            {unavailable && (
              <Alert variant="warning" role="alert" className="fb-verifier-unavailable">
                The source verifier is temporarily unavailable. Try again later.
              </Alert>
            )}
            <div className="verify-steps">
              {["Find the source", "Check the clues", "Show what we know"].map((step, index) => (
                <span
                  key={step}
                  className={
                    verifyProgress === index + 1
                      ? "current"
                      : verifyProgress > index + 1
                        ? "done"
                        : ""
                  }
                >
                  <i>{verifyProgress > index + 1 ? "✓" : index + 1}</i>
                  {busy && verifyProgress === index + 1 ? `${step}…` : step}
                </span>
              ))}
            </div>
            <p className="fine-print">
              Only send content you have permission to share. Sample results are marked synthetic.
            </p>
          </Panel>
          {submissions.length > 0 && (
            <Panel className="checked-list">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">YOUR HISTORY</span>
                  <h3>My checked tips</h3>
                </div>
                <Chip shape="round" className="count-pill">
                  {submissions.length}
                </Chip>
              </div>
              {submissions.map((item) => (
                <div className="checked-item" key={item.submission_id}>
                  <DataBadge origin={item.data_origin} />
                  <strong>{item.claim?.symbol ?? "Shared message"}</strong>
                  <span className={`status-tag ${item.status}`}>{sentenceCase(item.status)}</span>
                  {outcomePercentages(item.outcome) && (
                    <small>
                      Company {outcomePercentages(item.outcome)!.company}% · Index{" "}
                      {outcomePercentages(item.outcome)!.index}%
                    </small>
                  )}
                </div>
              ))}
            </Panel>
          )}
        </div>
        <div className={`verifier-results ${result ? "" : "fb-verifier-empty"}`}>
          {result ? (
            <>
              <Panel className="source-summary">
                <div className="source-heading">
                  <div className="source-avatar">
                    {(result.source?.platform ?? "?").slice(0, 1)}
                  </div>
                  <div>
                    <span className="eyebrow">SOURCE PROFILE</span>
                    <h3>{result.source?.handle ?? "Source not identified"}</h3>
                    <small>
                      {result.source?.platform ?? "No profile returned"} · Source profile
                    </small>
                  </div>
                  <DataBadge origin={result.data_origin} />
                </div>
                <div className="source-rating">
                  <div className="rating-score">
                    {result.source?.score ?? "—"}
                    <small>/100</small>
                  </div>
                  <div>
                    <span
                      className={`rating-label ${result.source?.label ?? "not_enough_history"}`}
                    >
                      {labelText[result.source?.label ?? "not_enough_history"]}
                    </span>
                    <p>This rating describes the source’s checked history, not a company.</p>
                  </div>
                </div>
                <div className="fact-grid">
                  {Object.entries(result.source?.facts ?? {}).map(([key, value]) => (
                    <div key={key}>
                      <span>{key}</span>
                      <strong>{formatFact(value)}</strong>
                    </div>
                  ))}
                </div>
                <Button variant="quiet" className="text-link" onClick={() => setSearchSource(true)}>
                  See source rating history <span>→</span>
                </Button>
              </Panel>
              <Panel>
                <div className="panel-heading">
                  <div>
                    <span className="eyebrow">CLAIM REVIEW</span>
                    <h3>{result.claim?.symbol ?? "Submitted claim"}</h3>
                  </div>
                  <DataBadge origin={result.data_origin} />
                </div>
                <div className="claim-outcome">
                  <span>Reported direction</span>
                  <strong>
                    {result.claim?.direction === "up" ? "Expected to rise" : "Expected to fall"}
                  </strong>
                  <span>Scoring status</span>
                  <strong>{sentenceCase(result.claim?.status ?? "needs_review")}</strong>
                </div>
                {outcomePercentages(result.claim?.outcome) && (
                  <div className="outcome-pair compact">
                    <div>
                      <span>Company</span>
                      <strong
                        className={
                          outcomePercentages(result.claim?.outcome)!.company < 0
                            ? "negative"
                            : "positive"
                        }
                      >
                        {outcomePercentages(result.claim?.outcome)!.company}%
                      </strong>
                    </div>
                    <i>vs</i>
                    <div>
                      <span>Index</span>
                      <strong
                        className={
                          outcomePercentages(result.claim?.outcome)!.index < 0
                            ? "negative"
                            : "positive"
                        }
                      >
                        {outcomePercentages(result.claim?.outcome)!.index}%
                      </strong>
                    </div>
                  </div>
                )}
                <div className="red-flag-list">
                  <span className="eyebrow">CLUES TO CHECK</span>
                  {result.red_flags.map((flag) => (
                    <div className="red-flag" key={flag.code}>
                      <span className="flag-mark">!</span>
                      <div>
                        <strong>{formatLabel(flag.code)}</strong>
                        <p>{flag.text}</p>
                        <small>Evidence: {flag.evidence}</small>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="neutral-note">
                  A source label summarizes available records. It does not confirm that a future
                  claim will be correct.
                </div>
              </Panel>
              {source && (
                <Panel className="source-history">
                  <div className="panel-heading">
                    <div>
                      <span className="eyebrow">SOURCE TRACK RECORD</span>
                      <h3>Rating history</h3>
                    </div>
                    <DataBadge origin={source.data_origin} />
                  </div>
                  <div className="history-bars">
                    {source.history.map((item) => (
                      <div key={item.changed_at}>
                        <span>{item.changed_at}</span>
                        <i style={{ height: `${(item.score ?? 0) * 1.5}px` }} />
                        <b>{item.score ?? "—"}</b>
                      </div>
                    ))}
                  </div>
                  <div className="source-recent">
                    {source.recent_claims.map((item, index) => (
                      <div key={`${item.symbol}-${index}`}>
                        <span>{item.symbol}</span>
                        <small>
                          {sentenceCase(item.status)} · {formatFact(item.outcome)}
                        </small>
                      </div>
                    ))}
                  </div>
                </Panel>
              )}
            </>
          ) : (
            <Panel className="results-empty">
              <div className="empty-orbit">
                <span>✳</span>
              </div>
              <span className="eyebrow">YOUR REVIEW WILL APPEAR HERE</span>
              <h3>Start with the source.</h3>
              <p>
                We’ll show the source label and its facts, then list the clues we could check in the
                message.
              </p>
              <div className="empty-mini-list">
                <span>
                  <i>01</i> Source history
                </span>
                <span>
                  <i>02</i> Claim details
                </span>
                <span>
                  <i>03</i> Evidence and outcome
                </span>
              </div>
              <DataBadge origin="synthetic" />
            </Panel>
          )}
        </div>
      </div>
    </>
  );
}

function ProgressView({ data }: { data: DashboardData | null }) {
  if (!data)
    return (
      <>
        <SectionHeading eyebrow="MY PROGRESS" title="Skills that grow with practice." />
        <Panel>Loading your progress…</Panel>
      </>
    );
  const lastScore = data.brier_over_time.at(-1)?.brier ?? 0;
  const accuracy = data.scenario_accuracy.at(-1)?.accuracy ?? 0;
  return (
    <>
      <SectionHeading
        eyebrow="MY PROGRESS"
        title="Skills that grow with practice."
        action={<DataBadge origin={data.data_origin} />}
      />
      <div className="progress-stat-row">
        <Panel>
          <span className="eyebrow">CURRENT LEVEL</span>
          <strong>Level {data.level}</strong>
          <small>Building stronger judgement</small>
          <DataBadge origin={data.data_origin} />
        </Panel>
        <Panel>
          <span className="eyebrow">LATEST CONFIDENCE SCORE</span>
          <strong>{lastScore.toFixed(2)}</strong>
          <small>Lower means closer calibration</small>
          <DataBadge origin={data.data_origin} />
        </Panel>
        <Panel>
          <span className="eyebrow">SCENARIO ACCURACY</span>
          <strong>{accuracy}%</strong>
          <small>Across recent practice</small>
          <DataBadge origin={data.data_origin} />
        </Panel>
      </div>
      <DashboardCharts data={data} />
      <Panel className="evidence-note">
        <div className="evidence-icon">i</div>
        <div>
          <span className="eyebrow">ABOUT THE DATA LABELS</span>
          <h3>Learning progress is not a market score.</h3>
          <p>
            Every chart and card here carries a Real or Synthetic label, so you can always tell
            measured data from practice material. Your level reflects what you have shown so far,
            not how any stock will perform.
          </p>
        </div>
        <DataBadge origin={data.data_origin} />
      </Panel>
      <div className="level-reflection">
        <div className="panel-heading">
          <span className="eyebrow">YOUR CURRENT LEVEL · {data.level}</span>
          <DataBadge origin={data.data_origin} />
        </div>
        <h3>Keep asking what supports a claim.</h3>
        <p>
          Source, timing, and evidence all matter. Progress comes from building a repeatable habit
          of checking each one.
        </p>
      </div>
    </>
  );
}
