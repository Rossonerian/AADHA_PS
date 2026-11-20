"use client";

import { useEffect, useMemo, useState } from "react";
import { DashboardCharts, ExplainChart, ScenarioChart } from "@/components/charts";
import { Button, DataBadge, LockNotice, Panel, ProgressBar, SectionHeading, Toast } from "@/components/ui";
import { api, isToolLocked } from "@/lib/api";
import type { Assessment, AssessmentResult, DashboardData, ExplainResult, LearningPlan, Lesson, OnboardingResult, Question, Scenario, ScenarioResult, SourceDetail, SubmissionSummary, UserProfile, VerifyResult } from "@/lib/types";
import { supabase } from "@/lib/supabase";

type View = "home" | "onboarding" | "learn" | "lesson" | "assessment" | "scenario" | "explain" | "verifier" | "progress";
type NavItem = { id: View; label: string; icon: string; tool?: string; level?: number };
const navItems: NavItem[] = [
  { id: "home", label: "Overview", icon: "⌂" },
  { id: "learn", label: "Learning path", icon: "▤" },
  { id: "scenario", label: "Practice scenarios", icon: "⌁", tool: "scenarios", level: 1 },
  { id: "explain", label: "Explain a stock", icon: "◷", tool: "explain_stock", level: 2 },
  { id: "verifier", label: "Source verifier", icon: "⌕", tool: "verifier", level: 3 },
  { id: "progress", label: "My progress", icon: "↗", tool: "dashboard", level: 4 },
];

function friendlyError(error: unknown): string {
  if (isToolLocked(error)) return `This tool opens at Level ${error.error.required_level}.`;
  if (typeof error === "object" && error !== null && "error" in error) {
    const message = (error as { error?: { message?: string } }).error?.message;
    if (message) return message;
  }
  return "That did not load. Check your connection and try again.";
}

function formatLabel(value: string) { return value.split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" "); }

export default function AacharyaApp() {
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
  const [toast, setToast] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [authMessage, setAuthMessage] = useState("");
  const [verifyProgress, setVerifyProgress] = useState(0);
  const [onboarding, setOnboarding] = useState<{ sessionId: string; question: Question; index: number; confidence: number; answer: string } | null>(null);
  const [onboardingResult, setOnboardingResult] = useState<OnboardingResult | null>(null);
  const [lessonCheck, setLessonCheck] = useState("");
  const [assessmentAnswers, setAssessmentAnswers] = useState<Record<string, { answer: string; confidence: number }>>({});
  const [scenarioAnswer, setScenarioAnswer] = useState<"up" | "down" | "" >("");
  const [scenarioConfidence, setScenarioConfidence] = useState(65);
  const [selectedClues, setSelectedClues] = useState<string[]>([]);
  const [symbol, setSymbol] = useState("DEMO");
  const [year, setYear] = useState("2025");
  const [verifyText, setVerifyText] = useState("");
  const [verifyUrl, setVerifyUrl] = useState("");
  const [userGuess, setUserGuess] = useState("");
  const [userConfidence, setUserConfidence] = useState(65);
  const [searchSource, setSearchSource] = useState(false);

  useEffect(() => {
    if (!supabase) return;
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "SIGNED_IN" && session) void api.me().then(setProfile).catch((reason: unknown) => setError(friendlyError(reason)));
    });
    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!profile) return;
    let cancelled = false;
    Promise.all([api.plan(), api.submissions()]).then(([nextPlan, nextSubmissions]) => {
      if (!cancelled) { setPlan(nextPlan); setSubmissions(nextSubmissions); }
    }).catch((reason: unknown) => { if (!cancelled) setError(friendlyError(reason)); });
    return () => { cancelled = true; };
  }, [profile]);

  const activeNav = useMemo(() => navItems.find((item) => item.id === view)?.label ?? "Overview", [view]);
  const clearError = () => setError("");
  const showError = (reason: unknown) => setError(friendlyError(reason));

  async function enterDemo() {
    clearError(); setBusy(true);
    try { const [me] = await Promise.all([api.me(), api.health()]); setProfile(me); setAuthMessage(""); }
    catch (reason) { showError(reason); }
    finally { setBusy(false); }
  }

  async function sendSignInLink(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); clearError();
    if (!supabase) { setAuthMessage("Email sign-in is not configured here. Continue with the demo workspace."); return; }
    setBusy(true);
    const { error: authError } = await supabase.auth.signInWithOtp({ email, options: { emailRedirectTo: window.location.origin } });
    setBusy(false);
    if (authError) setError(authError.message); else setAuthMessage("Check your email for a sign-in link.");
  }

  async function beginOnboarding() {
    setError(""); setBusy(true);
    try { const start = await api.onboardingStart(); setOnboarding({ sessionId: start.session_id, question: start.question, index: 0, confidence: 65, answer: "" }); setOnboardingResult(null); setView("onboarding"); }
    catch (reason) { showError(reason); }
    finally { setBusy(false); }
  }

  async function submitOnboarding() {
    if (!onboarding?.answer) { setError("Choose an answer to continue."); return; }
    setBusy(true); setError("");
    try {
      const result = await api.onboardingAnswer({ session_id: onboarding.sessionId, question_id: onboarding.question.id, answer: onboarding.answer, confidence: onboarding.confidence }, onboarding.index);
      if (result.next_question) setOnboarding({ ...onboarding, question: result.next_question, index: onboarding.index + 1, answer: "" });
      else if (result.result) { setOnboardingResult(result.result); setProfile((current) => current ? { ...current, level: result.result?.level ?? current.level } : current); setOnboarding(null); }
    } catch (reason) { showError(reason); } finally { setBusy(false); }
  }

  async function openLesson(id: string) {
    setView("lesson"); setBusy(true); setError(""); setLessonCheck("");
    try { setLesson(await api.lesson(id)); } catch (reason) { showError(reason); } finally { setBusy(false); }
  }

  async function beginAssessment() {
    setBusy(true); setError(""); setAssessmentResult(null); setAssessmentAnswers({});
    try { setAssessment(await api.assessmentStart(profile?.level ?? 1)); setView("assessment"); }
    catch (reason) { showError(reason); } finally { setBusy(false); }
  }

  async function submitAssessment() {
    if (!assessment) return;
    const answers = assessment.items.map((item) => ({ item_id: item.id, answer: assessmentAnswers[item.id]?.answer ?? "", confidence: assessmentAnswers[item.id]?.confidence ?? 50 }));
    if (answers.some((answer) => !answer.answer)) { setError("Answer each question before you continue."); return; }
    setBusy(true); setError("");
    try {
      const result = await api.assessmentSubmit(assessment.assessment_id, answers);
      setAssessmentResult(result);
      if (result.new_level && profile) setProfile({ ...profile, level: Math.max(profile.level, result.new_level), unlocks: [...new Set([...profile.unlocks, ...result.unlocked])] });
    } catch (reason) { showError(reason); } finally { setBusy(false); }
  }

  async function openScenario() {
    setBusy(true); setError(""); setScenarioResult(null); setScenarioAnswer(""); setSelectedClues([]);
    try { setScenario(await api.scenarioNext()); setView("scenario"); } catch (reason) { showError(reason); } finally { setBusy(false); }
  }

  async function revealScenario() {
    if (!scenario || !scenarioAnswer || selectedClues.length === 0) { setError("Choose a direction and at least one clue."); return; }
    setBusy(true); setError("");
    try { setScenarioResult(await api.scenarioAnswer(scenario.id, { direction: scenarioAnswer, confidence: scenarioConfidence, clues: selectedClues })); } catch (reason) { showError(reason); } finally { setBusy(false); }
  }

  async function runExplain(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setExplain(null);
    try { setExplain(await api.explain(symbol.trim().toUpperCase(), Number(year))); } catch (reason) { showError(reason); } finally { setBusy(false); }
  }

  function containsActionAdvice(text: string) { return /\b(should i|tell me whether|is it time to|do i)\b/i.test(text) && /\b(buy|sell|hold|recommend)\b/i.test(text); }

  async function runVerify(payload?: { image_base64?: string }) {
    const content = verifyText.trim();
    if (!payload?.image_base64 && !verifyUrl.trim() && !content) { setError("Paste a message, add a link, or choose a screenshot."); return; }
    if (containsActionAdvice(content)) { setVerification(null); setError("I can help check a source and explain evidence. I can’t choose an action for you."); return; }
    setBusy(true); setError(""); setVerification(null); setSourceDetail(null); setVerifyProgress(1);
    try {
      const result = await api.verify({ ...(payload ?? {}), ...(verifyUrl.trim() ? { url: verifyUrl.trim() } : {}), ...(content ? { text: content } : {}), ...(userGuess ? { user_guess: userGuess, user_confidence: userConfidence } : {}) });
      setVerifyProgress(2); setVerification(result); const [detail, mine] = await Promise.all([api.source(result.source.id), api.submissions()]); setSourceDetail(detail); setSubmissions(mine); setVerifyProgress(3);
    } catch (reason) { if (isToolLocked(reason)) setError(`The verifier opens at Level ${reason.error.required_level}. Continue your learning path to unlock it.`); else showError(reason); } finally { setBusy(false); }
  }

  async function onScreenshot(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) { setError("Choose an image file."); return; }
    if (file.size > 10 * 1024 * 1024) { setError("Choose an image smaller than 10 MB."); return; }
    const reader = new FileReader();
    reader.onload = async () => { const value = String(reader.result ?? ""); await runVerify({ image_base64: value.split(",")[1] ?? value }); };
    reader.readAsDataURL(file);
  }

  async function openDashboard() {
    setBusy(true); setError("");
    try { setDashboard(await api.dashboard()); setView("progress"); } catch (reason) { if (isToolLocked(reason)) setError(`Your skill dashboard opens at Level ${reason.error.required_level}.`); else showError(reason); } finally { setBusy(false); }
  }

  function navigate(target: View) {
    const entry = navItems.find((item) => item.id === target);
    if (entry?.level && (profile?.level ?? 1) < entry.level) { setError(`${entry.label} opens at Level ${entry.level}.`); return; }
    setError(""); setView(target);
    if (target === "scenario") void openScenario();
    if (target === "progress") void openDashboard();
    if (target === "learn" && !plan) void api.plan().then(setPlan).catch(showError);
  }

  if (!profile) return <main className="welcome-screen">
    <div className="welcome-noise" aria-hidden="true" />
    <div className="welcome-brand"><span className="brand-mark">a</span><span>Aacharya</span></div>
    <div className="welcome-content"><div className="welcome-copy"><span className="eyebrow light">A CALMER WAY TO LEARN ABOUT MARKETS</span><h1>Build your money sense,<br /><em>one question at a time.</em></h1><p>Learn to read financial information, question bold claims, and understand how your confidence matches real outcomes.</p><div className="welcome-points"><span><i>01</i> Short, guided lessons</span><span><i>02</i> Practice with real-world clues</span><span><i>03</i> See your skills grow over time</span></div><div className="welcome-disclaimer">Learning tool only · No personal financial guidance</div></div>
      <Panel className="signin-panel"><div className="signin-icon">✳</div><span className="eyebrow">YOUR LEARNING SPACE</span><h2>Start with a quick check-in</h2><p>We’ll shape a learning path around what you already know.</p><form onSubmit={sendSignInLink} className="signin-form"><label htmlFor="email">Email address</label><input id="email" type="email" placeholder="you@example.com" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" /><Button type="submit" disabled={busy}>{busy ? "Sending…" : "Continue with email"}<span aria-hidden="true">→</span></Button></form>{authMessage && <p className="form-message" role="status">{authMessage}</p>}{error && <p className="form-error" role="alert">{error}</p>}<div className="signin-divider"><span>OR</span></div><Button variant="secondary" onClick={enterDemo} disabled={busy}>Explore the demo workspace <span aria-hidden="true">↗</span></Button><small>Demo data is labeled so it’s easy to tell sample information from live data.</small></Panel>
    </div><footer className="welcome-footer"><span>© 2026 Aacharya</span><span>Learn with care. Decide with context.</span></footer>
  </main>;

  const isLocked = (entry: NavItem) => Boolean(entry.level && profile.level < entry.level);
  return <div className="app-shell">
    <aside className="sidebar">
      <button className="sidebar-brand" onClick={() => navigate("home")} aria-label="Aacharya overview"><span className="brand-mark">a</span><span>Aacharya<small>LEARNING STUDIO</small></span></button>
      <div className="side-label">YOUR SPACE</div><nav aria-label="Main navigation">{navItems.map((item) => <button key={item.id} className={`nav-link ${view === item.id || (view === "lesson" && item.id === "learn") || (view === "assessment" && item.id === "learn") ? "selected" : ""} ${isLocked(item) ? "locked" : ""}`} onClick={() => navigate(item.id)} aria-current={view === item.id ? "page" : undefined}><span className="nav-icon" aria-hidden="true">{item.icon}</span><span>{item.label}</span>{isLocked(item) && <span className="nav-level">L{item.level}</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="level-card"><div className="level-card-head"><span className="level-star">✦</span><span>YOUR LEVEL</span><strong>{profile.level}<small>/ 4</small></strong></div><ProgressBar value={(profile.level / 4) * 100} /><p>{profile.level < 4 ? `Next tools open at Level ${profile.level + 1}` : "All learning tools are open"}</p></div><button className="sidebar-help" onClick={() => setToast("Your progress is saved to this demo session.")}><span aria-hidden="true">?</span> Help & feedback</button></div>
    </aside>
    <div className="main-column"><header className="topbar"><button className="mobile-brand" onClick={() => navigate("home")}><span className="brand-mark">a</span>Aacharya</button><div className="breadcrumb"><span>Workspace</span><span className="crumb-sep">/</span><strong>{activeNav}</strong></div><div className="topbar-right"><span className="streak-chip"><span aria-hidden="true">✦</span> 4 day streak</span><button className="avatar-button" aria-label={`${profile.name} profile`} onClick={() => setToast("You’re signed in to the demo workspace.")}>{profile.name.slice(0, 1).toUpperCase()}</button></div></header>
      <main className="page-content">
        {error && <div className="inline-error" role="alert"><span aria-hidden="true">!</span>{error}<button onClick={clearError} aria-label="Dismiss error">×</button></div>}
        {view === "home" && <HomeView profile={profile} plan={plan} submissions={submissions} busy={busy} onStart={beginOnboarding} onLearn={() => navigate("learn")} onScenario={openScenario} onVerifier={() => navigate("verifier")} />}
        {view === "onboarding" && <OnboardingView state={onboarding} result={onboardingResult} busy={busy} onAnswer={(answer) => setOnboarding((current) => current ? { ...current, answer } : current)} onConfidence={(confidence) => setOnboarding((current) => current ? { ...current, confidence } : current)} onNext={submitOnboarding} onStart={beginOnboarding} onContinue={() => { setOnboardingResult(null); setView("home"); setToast("Your learning path is ready."); }} />}
        {view === "learn" && <LearningView plan={plan} busy={busy} onOpen={openLesson} onAssess={beginAssessment} />}
        {view === "lesson" && <LessonView lesson={lesson} check={lessonCheck} setCheck={setLessonCheck} busy={busy} onBack={() => setView("learn")} onContinue={beginAssessment} />}
        {view === "assessment" && <AssessmentView assessment={assessment} answers={assessmentAnswers} setAnswers={setAssessmentAnswers} result={assessmentResult} busy={busy} level={profile.level} onSubmit={submitAssessment} onLearn={() => { setAssessmentResult(null); setView("learn"); }} onContinue={() => { setAssessmentResult(null); setView("home"); }} />}
        {view === "scenario" && (profile.level < 1 ? <LockNotice level={1} /> : <ScenarioView scenario={scenario} result={scenarioResult} answer={scenarioAnswer} confidence={scenarioConfidence} clues={selectedClues} busy={busy} setAnswer={setScenarioAnswer} setConfidence={setScenarioConfidence} setClues={setSelectedClues} onReveal={revealScenario} onNext={openScenario} />)}
        {view === "explain" && (profile.level < 2 ? <LockNotice level={2} /> : <ExplainView symbol={symbol} year={year} result={explain} busy={busy} setSymbol={setSymbol} setYear={setYear} onSubmit={runExplain} />)}
        {view === "verifier" && (profile.level < 3 ? <LockNotice level={3} /> : <VerifierView text={verifyText} setText={setVerifyText} url={verifyUrl} setUrl={setVerifyUrl} guess={userGuess} setGuess={setUserGuess} confidence={userConfidence} setConfidence={setUserConfidence} result={verification} source={sourceDetail} submissions={submissions} busy={busy} verifyProgress={verifyProgress} searchSource={searchSource} setSearchSource={setSearchSource} onSubmit={runVerify} onScreenshot={onScreenshot} />)}
        {view === "progress" && (profile.level < 4 ? <LockNotice level={4} /> : <ProgressView data={dashboard} />)}
      </main><footer className="app-footer"><span>Aacharya · Learn to read the signal</span><span>Progress is personal. The market is uncertain.</span></footer>
    </div>
    {toast && <Toast message={toast} onClose={() => setToast("")} />}
  </div>;
}

function HomeView({ profile, plan, submissions, busy, onStart, onLearn, onScenario, onVerifier }: { profile: UserProfile; plan: LearningPlan | null; submissions: SubmissionSummary[]; busy: boolean; onStart: () => void; onLearn: () => void; onScenario: () => void; onVerifier: () => void }) {
  const hasVerifier = profile.level >= 3;
  return <>
    <div className="home-greeting"><div><span className="eyebrow">YOUR LEARNING SPACE <span className="data-origin-inline">DEMO</span></span><h1>Good morning, {profile.name} <span className="wave">✳</span></h1><p>A little practice today can make the next big claim easier to question.</p></div><button className="avatar-large" onClick={onLearn} aria-label="Open your learning path">{profile.name.slice(0, 1).toUpperCase()}</button></div>
    <div className="hero-card"><div className="hero-illustration" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit-center">✳</div><span className="orbit-dot dot-one"/><span className="orbit-dot dot-two"/><span className="orbit-dot dot-three"/></div><div className="hero-text"><span className="hero-kicker">YOUR NEXT SMALL STEP</span><h2>Start with your<br /><em>learning check-in.</em></h2><p>Three short questions help us find the right place for you to begin.</p><Button onClick={onStart}>Begin check-in <span aria-hidden="true">→</span></Button></div><div className="hero-side-note"><span>ABOUT 3 MIN</span><i /> No score to pass</div></div>
    <div className="section-row"><div><span className="eyebrow">A GOOD PLACE TO BEGIN</span><h2>Pick up where you are</h2></div><button className="text-link" onClick={onLearn}>View learning path <span aria-hidden="true">→</span></button></div>
    <div className="home-cards"><button className="home-action-card" onClick={onLearn}><span className="card-icon green">▤</span>{plan && <DataBadge origin="synthetic" />}<span className="card-meta">YOUR LEARNING PATH</span><strong>{plan ? `${plan.progress_pct}%` : busy ? "…" : "Start here"}</strong><span className="card-foot">Continue a short lesson <b>↗</b></span><ProgressBar value={plan?.progress_pct ?? 0} /></button><button className="home-action-card" onClick={onScenario}><span className="card-icon amber">⌁</span><span className="card-meta">PRACTICE SCENARIOS</span><strong>Read the clues</strong><span className="card-foot">Try a 2-minute practice <b>↗</b></span><span className="mini-bars" aria-hidden="true"><i/><i/><i/><i/><i/><i/><i/></span></button><button className="home-action-card" onClick={onVerifier}><span className="card-icon lilac">⌕</span><span className="card-meta">SOURCE VERIFIER</span><strong>{hasVerifier ? "Check a claim" : "Unlock at Level 3"}</strong><span className="card-foot">Look into a shared message <b>↗</b></span><span className="lock-dash">{hasVerifier ? "Available now" : "2 levels to go"}</span></button></div>
    <div className="home-lower"><Panel className="welcome-note"><div className="note-icon">✦</div><div><span className="eyebrow">A NOTE TO KEEP</span><h3>Confidence is a skill.</h3><p>A strong learner knows what they know—and stays curious about the rest. Your progress is about judgement, not prediction.</p></div></Panel><Panel className="recent-panel"><div className="panel-heading"><div><span className="eyebrow">RECENT ACTIVITY</span><h3>Your checked tips</h3></div><span className="count-pill">{submissions.length}</span></div>{submissions.length ? <ul className="recent-list">{submissions.slice(0, 2).map((item) => <li key={item.submission_id}><span className="recent-status">{item.status === "scored" ? "✓" : "…"}</span><span><strong>{item.claim.symbol ?? "Submitted tip"}</strong><small>{item.status === "scored" ? "Outcome checked" : "Still being reviewed"}</small></span><DataBadge origin={item.data_origin} /></li>)}</ul> : <p className="muted">Your checked items will appear here.</p>}</Panel></div>
  </>;
}

function OnboardingView({ state, result, busy, onAnswer, onConfidence, onNext, onStart, onContinue }: { state: { sessionId: string; question: Question; index: number; confidence: number; answer: string } | null; result: OnboardingResult | null; busy: boolean; onAnswer: (value: string) => void; onConfidence: (value: number) => void; onNext: () => void; onStart: () => void; onContinue: () => void }) {
  if (result) return <div className="narrow-view"><SectionHeading eyebrow="YOUR STARTING POINT" title="A learning path that fits." /><Panel className="result-panel"><div className="result-orbit">✳</div><span className="eyebrow">CHECK-IN COMPLETE</span><h2>Level {result.level} · Reading a stock</h2><p>Your answers suggest a good next focus: checking who is behind a claim and how strong the evidence is.</p><DataBadge origin="synthetic" /><div className="skill-bars">{Object.entries(result.skills).map(([skill, score]) => <div className="skill-bar" key={skill}><div><span>{formatLabel(skill)}</span><strong>{score}%</strong></div><ProgressBar value={score ?? 0} /></div>)}</div><p className="calibration-note">Your confidence and your answers will become easier to compare as you practice. Starting Brier score: <strong>{result.brier.toFixed(2)}</strong></p><Button onClick={onContinue}>Go to my overview <span>→</span></Button></Panel></div>;
  if (!state) return <div className="narrow-view"><SectionHeading eyebrow="A QUICK CHECK-IN" title="Find your starting point." /><Panel><p>Three short questions will help shape your learning plan.</p><Button onClick={onStart} disabled={busy}>Start check-in</Button></Panel></div>;
  return <div className="narrow-view"><div className="flow-top"><button className="back-button" onClick={onStart}>← Overview</button><span className="flow-step">Question {state.index + 1} <span>/ 3</span></span></div><ProgressBar value={((state.index + 1) / 3) * 100} label="Check-in progress" /><Panel className="quiz-panel"><div className="panel-heading"><span className="eyebrow">A QUICK CHECK-IN · {formatLabel(state.question.skill_area)}</span><DataBadge origin="synthetic" /></div><h2>{state.question.text}</h2><div className="quiz-options">{state.question.options.map((option) => <button key={option} className={`quiz-option ${state.answer === option ? "chosen" : ""}`} onClick={() => onAnswer(option)}><span className="option-radio" />{option}</button>)}</div><ConfidenceControl value={state.confidence} onChange={onConfidence} label="How sure do you feel?" /><Button onClick={onNext} disabled={busy || !state.answer}>{busy ? "Saving…" : state.index === 2 ? "See my starting point" : "Continue"}<span>→</span></Button></Panel><p className="centered-note">Your answers help us choose a useful next lesson.</p></div>;
}

function ConfidenceControl({ value, onChange, label }: { value: number; onChange: (value: number) => void; label: string }) {
  return <div className="confidence-control"><div><label>{label}</label><strong>{value}%</strong></div><input type="range" min="50" max="100" step="5" value={value} onChange={(event) => onChange(Number(event.target.value))} aria-label={`${label} ${value} percent`} /><div className="range-labels"><span>Not sure yet</span><span>Very sure</span></div></div>;
}

function LearningView({ plan, busy, onOpen, onAssess }: { plan: LearningPlan | null; busy: boolean; onOpen: (id: string) => void; onAssess: () => void }) {
  return <><SectionHeading eyebrow="YOUR LEARNING PATH" title="Small lessons. Stronger judgement." action={<DataBadge origin="synthetic" />} /><div className="learning-summary"><div><strong>{plan?.progress_pct ?? 0}%</strong><span>path complete</span></div><ProgressBar value={plan?.progress_pct ?? 0} /><span className="level-pill">LEVEL {plan?.level ?? 2}</span><DataBadge origin="synthetic" /></div><div className="lesson-list">{(plan?.lessons ?? []).map((item, index) => <Panel className={`lesson-row ${item.status}`} key={item.id}><div className="lesson-index">{item.status === "done" ? "✓" : String(index + 1).padStart(2, "0")}</div><div className="lesson-info"><span className="eyebrow">{item.minutes} MIN · {item.status === "in_progress" ? "PICK UP HERE" : formatLabel(item.status)}</span><h3>{item.title}</h3><p>{item.status === "locked" ? "Complete the current learning check to open this lesson." : "A short guide with clear examples and a quick knowledge check."}</p></div><DataBadge origin="synthetic" /><button className="lesson-open" onClick={() => item.status !== "locked" && onOpen(item.id)} disabled={busy || item.status === "locked"} aria-label={`Open ${item.title}`}>{item.status === "locked" ? "⌑" : "→"}</button></Panel>)}</div><div className="assessment-callout"><div><span className="eyebrow">READY TO CHECK IN?</span><h3>See what has stayed with you.</h3><p>A short assessment can open the next set of learning tools.</p></div><Button variant="secondary" onClick={onAssess} disabled={busy}>Start assessment <span>→</span></Button></div></>;
}

function LessonView({ lesson, check, setCheck, busy, onBack, onContinue }: { lesson: Lesson | null; check: string; setCheck: (value: string) => void; busy: boolean; onBack: () => void; onContinue: () => void }) {
  const question = lesson?.check_questions[0];
  return <div className="lesson-reader"><button className="back-button" onClick={onBack}>← Learning path</button>{busy && <Panel>Loading lesson…</Panel>}{lesson && <><div className="lesson-reader-head"><span className="eyebrow">LEVEL 2 · 8 MIN READ</span><h1>{lesson.title}</h1><p>Learn to slow down, compare, and find the story behind a chart.</p></div><Panel className="reading-panel"><DataBadge origin="synthetic" />{lesson.sections.map((section, index) => <div className="reading-section" key={index}><span className="reading-number">{String(index + 1).padStart(2, "0")}</span><p>{section}</p></div>)}</Panel>{question && <Panel className="lesson-check"><div className="panel-heading"><span className="eyebrow">QUICK CHECK</span><DataBadge origin="synthetic" /></div><h3>{question.text}</h3><div className="quiz-options">{question.options.map((option) => <button key={option} onClick={() => setCheck(option)} className={`quiz-option ${check === option ? "chosen" : ""}`}><span className="option-radio" />{option}</button>)}</div>{check && <div className="inline-feedback">{check === question.options[0] ? "That’s it. Matching dates and comparing with an index gives you more context." : "Try again. Look for the choice that checks both timing and the wider market."}</div>}</Panel>}<div className="reader-actions"><Button variant="secondary" onClick={onBack}>Save and leave</Button><Button onClick={onContinue} disabled={busy || !check || check !== question?.options[0]}>Continue to assessment <span>→</span></Button></div></>}</div>;
}

function AssessmentView({ assessment, answers, setAnswers, result, busy, level, onSubmit, onLearn, onContinue }: { assessment: Assessment | null; answers: Record<string, { answer: string; confidence: number }>; setAnswers: React.Dispatch<React.SetStateAction<Record<string, { answer: string; confidence: number }>>>; result: AssessmentResult | null; busy: boolean; level: number; onSubmit: () => void; onLearn: () => void; onContinue: () => void }) {
  if (result) return <div className="narrow-view"><SectionHeading eyebrow="LEARNING CHECK" title={result.passed ? "You’re ready for the next level." : "Keep building your confidence."} /><Panel className="assessment-result"><div className="pass-ring">{result.passed ? "✓" : "↻"}</div><DataBadge origin="synthetic" /><h2>{result.passed ? `Level ${result.new_level ?? level + 1} unlocked` : "One more practice round"}</h2><p>{result.passed ? "Your answers show stronger judgement across the skills you practised." : "Review the lesson and try again when you feel ready."}</p><div className="result-metrics"><div><strong>{result.score}%</strong><span>Check score</span></div><div><strong>{result.brier.toFixed(2)}</strong><span>Confidence score</span></div></div>{result.unlocked.length > 0 && <div className="unlock-card"><span className="unlock-burst">✦</span><div><span className="eyebrow">NEW LEARNING TOOL</span><strong>{result.unlocked.map(formatLabel).join(", ")}</strong><small>Ready when you are</small></div><span className="unlock-arrow">↗</span></div>}<Button onClick={result.passed ? onContinue : onLearn}>{result.passed ? "Return to overview" : "Review learning path"}<span>→</span></Button></Panel></div>;
  if (!assessment) return <div className="narrow-view"><SectionHeading eyebrow="LEARNING CHECK" title="A few questions to reflect." /><Panel><p>Loading your questions…</p>{busy && <div className="skeleton-line" />}</Panel></div>;
  return <div className="narrow-view"><div className="flow-top"><button className="back-button" onClick={onLearn}>← Learning path</button><span className="flow-step">{assessment.items.length} questions</span></div><SectionHeading eyebrow={`LEVEL ${level} · CHECK-IN`} title="Show what you have learned." action={<DataBadge origin="synthetic" />} />{assessment.items.map((item, index) => <Panel className="assessment-question" key={item.id}><div className="panel-heading"><span className="eyebrow">QUESTION {index + 1} · {formatLabel(item.skill_area)}</span><DataBadge origin="synthetic" /></div><h3>{item.text}</h3><div className="quiz-options">{item.options.map((option) => <button key={option} className={`quiz-option ${answers[item.id]?.answer === option ? "chosen" : ""}`} onClick={() => setAnswers((current) => ({ ...current, [item.id]: { answer: option, confidence: current[item.id]?.confidence ?? 65 } }))}><span className="option-radio" />{option}</button>)}</div><ConfidenceControl label="How sure are you?" value={answers[item.id]?.confidence ?? 65} onChange={(confidence) => setAnswers((current) => ({ ...current, [item.id]: { answer: current[item.id]?.answer ?? "", confidence } }))} /></Panel>)}<Button onClick={onSubmit} disabled={busy}>{busy ? "Checking…" : "Finish learning check"}<span>→</span></Button></div>;
}

function ScenarioView({ scenario, result, answer, confidence, clues, busy, setAnswer, setConfidence, setClues, onReveal, onNext }: { scenario: Scenario | null; result: ScenarioResult | null; answer: "up" | "down" | ""; confidence: number; clues: string[]; busy: boolean; setAnswer: (value: "up" | "down") => void; setConfidence: (value: number) => void; setClues: React.Dispatch<React.SetStateAction<string[]>>; onReveal: () => void; onNext: () => void }) {
  if (!scenario) return <div className="narrow-view"><SectionHeading eyebrow="PRACTICE SCENARIO" title="Read the clues." /><Panel>Loading your practice scenario…</Panel></div>;
  const clueOptions = ["Price moved before the message", "A dated company or exchange notice", "The broad index moved the same way", "A source makes a claim without evidence"];
  return <><SectionHeading eyebrow="PRACTICE SCENARIO" title="Read the clues. Make a call." action={<DataBadge origin={scenario.data_origin} />} /><div className="scenario-layout"><div className="scenario-main"><Panel className="scenario-chart-panel"><div className="panel-heading"><div><span className="eyebrow">{scenario.context.company}</span><h3>Price movement and broad index</h3></div><DataBadge origin={scenario.data_origin} /></div><ScenarioChart scenario={scenario} /><div className="chart-key"><span><i className="line-solid" /> Company</span><span><i className="line-dashed" /> Index</span><small>Data shown up to {scenario.as_of_date}</small></div></Panel><Panel><div className="panel-heading"><div><span className="eyebrow">WHAT ELSE DO WE KNOW?</span><h3>Context from this case</h3></div><DataBadge origin={scenario.data_origin} /></div><div className="number-grid">{Object.entries(scenario.context.numbers).map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div><div className="headline-list">{scenario.context.headlines.map((headline) => <div className="headline-item" key={headline.date}><span className="timeline-date">{headline.date}</span><div><strong>{headline.text}</strong><small>{headline.source}</small></div></div>)}</div></Panel></div>
    <div className="scenario-side">{!result ? <Panel className="answer-panel"><span className="eyebrow">YOUR READ</span><h3>Over this period, the company will…</h3><div className="direction-options"><button className={answer === "up" ? "selected" : ""} onClick={() => setAnswer("up")}><span>↗</span>Outperform the index</button><button className={answer === "down" ? "selected" : ""} onClick={() => setAnswer("down")}><span>↘</span>Underperform the index</button></div><ConfidenceControl label="How confident are you?" value={confidence} onChange={setConfidence} /><span className="eyebrow clue-label">WHICH CLUES MATTER TO YOU?</span><div className="clue-picker">{clueOptions.map((clue) => <button className={clues.includes(clue) ? "checked" : ""} key={clue} onClick={() => setClues((current) => current.includes(clue) ? current.filter((item) => item !== clue) : [...current, clue])}><span>{clues.includes(clue) ? "✓" : "+"}</span>{clue}</button>)}</div><Button onClick={onReveal} disabled={busy}>{busy ? "Checking your call…" : "Reveal the outcome"}<span>→</span></Button><p className="fine-print">This exercise is about your judgement, not a company rating.</p></Panel> : <Panel className="scenario-result"><span className="eyebrow">CASE REVEALED</span><h3>{result.correct ? "Your read matched this outcome." : "Here’s what happened."}</h3><DataBadge origin={scenario.data_origin} /><div className="outcome-pair"><div><span>Company</span><strong className={result.outcome.stock_pct < 0 ? "negative" : "positive"}>{result.outcome.stock_pct > 0 ? "+" : ""}{result.outcome.stock_pct}%</strong></div><i>vs</i><div><span>Index</span><strong className={result.outcome.index_pct < 0 ? "negative" : "positive"}>{result.outcome.index_pct > 0 ? "+" : ""}{result.outcome.index_pct}%</strong></div></div><p>{result.explanation}</p><div className="clue-feedback"><strong>Clues to revisit</strong>{result.key_clues.map((clue) => <span key={clue}>• {clue}</span>)}</div><Button onClick={onNext} disabled={busy}>Try another scenario <span>→</span></Button></Panel>}</div></div></>;
}

function ExplainView({ symbol, year, result, busy, setSymbol, setYear, onSubmit }: { symbol: string; year: string; result: ExplainResult | null; busy: boolean; setSymbol: (value: string) => void; setYear: (value: string) => void; onSubmit: (event: React.FormEvent<HTMLFormElement>) => void }) {
  return <><SectionHeading eyebrow="EXPLAIN A STOCK" title="Put a price move in context." action={result && <DataBadge origin={result.data_origin} />} /><Panel className="search-panel"><form onSubmit={onSubmit} className="stock-search"><label><span>Company or symbol</span><input value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="e.g. DEMO" aria-label="Company or symbol" /></label><label><span>Year</span><input type="number" value={year} min="2000" max="2026" onChange={(event) => setYear(event.target.value)} aria-label="Year" /></label><Button type="submit" disabled={busy}>{busy ? "Looking…" : "Explain this year"}<span>→</span></Button></form><p className="search-hint">We’ll show dated events and compare the move with a broad index. This tool explains history, not what comes next.</p></Panel>{result && <div className="explain-results"><Panel className="scenario-chart-panel"><div className="panel-heading"><div><span className="eyebrow">{symbol.toUpperCase()} · {year}</span><h3>Company compared with index</h3></div><DataBadge origin={result.data_origin} /></div><ExplainChart data={result} /><div className="chart-key"><span><i className="line-solid" /> Company</span><span><i className="line-dashed" /> Index</span></div></Panel><Panel><div className="panel-heading"><span className="eyebrow">A SHORT READ</span><DataBadge origin={result.data_origin} /></div><h3 className="explain-summary">{result.summary}</h3><div className="move-list">{result.moves.map((move) => <div className="move-item" key={move.date}><div className="move-date">{move.date}</div><div className="move-body"><strong className={move.pct < 0 ? "negative" : "positive"}>{move.pct > 0 ? "+" : ""}{move.pct}% move</strong>{move.events.map((event) => <div className="source-event" key={event.source}><span>{event.text}</span><small>Source: {event.source}</small></div>)}</div></div>)}</div></Panel></div>}</>;
}

function VerifierView({ text, setText, url, setUrl, guess, setGuess, confidence, setConfidence, result, source, submissions, busy, verifyProgress, searchSource, setSearchSource, onSubmit, onScreenshot }: { text: string; setText: (value: string) => void; url: string; setUrl: (value: string) => void; guess: string; setGuess: (value: string) => void; confidence: number; setConfidence: (value: number) => void; result: VerifyResult | null; source: SourceDetail | null; submissions: SubmissionSummary[]; busy: boolean; verifyProgress: number; searchSource: boolean; setSearchSource: (value: boolean) => void; onSubmit: (payload?: { image_base64?: string }) => void; onScreenshot: (event: React.ChangeEvent<HTMLInputElement>) => void }) {
  const labelText: Record<string, string> = { reliable: "Reliable source", semi_reliable: "Mixed track record", not_reliable: "Not reliable", not_enough_history: "Limited history" };
  return <><SectionHeading eyebrow="SOURCE VERIFIER" title="Look closer at a shared claim." action={<span className="mode-pill">{(result?.mode ?? "full").toUpperCase()} MODE · LEVEL 3</span>} /><div className="verifier-layout"><div className="verifier-input-column"><Panel className="verifier-form-panel"><div className="panel-heading"><div><span className="eyebrow">CHECK A MESSAGE</span><h3>Where did this come from?</h3></div></div><div className="input-tabs"><button className={!searchSource ? "active" : ""} onClick={() => setSearchSource(false)}>Paste or link</button><button className={searchSource ? "active" : ""} onClick={() => setSearchSource(true)}>Screenshot</button></div>{!searchSource ? <><label className="field-label" htmlFor="verify-link">Link <span>Optional</span></label><input id="verify-link" className="text-input" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://…" /><label className="field-label" htmlFor="verify-text">Paste the forwarded text</label><textarea id="verify-text" className="text-area" value={text} onChange={(event) => setText(event.target.value)} placeholder="Paste a message here. We’ll look for the source and checkable clues." rows={6} /><div className="guess-toggle"><label className="field-label" htmlFor="guess">Your first read <span>Optional</span></label><input id="guess" className="text-input" value={guess} onChange={(event) => setGuess(event.target.value)} placeholder="What do you think the claim says?" /><ConfidenceControl label="How sure are you?" value={confidence} onChange={setConfidence} /></div><Button onClick={() => onSubmit()} disabled={busy}>{busy ? "Checking the details…" : "Check this message"}<span>→</span></Button></> : <label className="dropzone"><input type="file" accept="image/*" onChange={onScreenshot} disabled={busy} /><span className="drop-icon">↑</span><strong>{busy ? "Reading the sample…" : "Choose a screenshot"}</strong><small>PNG, JPG, or WEBP · Up to 10 MB</small><span className="drop-link">Browse files</span></label>}<div className="verify-steps">{["Find the source", "Check the clues", "Show what we know"].map((step, index) => <span key={step} className={verifyProgress === index + 1 ? "current" : verifyProgress > index + 1 ? "done" : ""}><i>{verifyProgress > index + 1 ? "✓" : index + 1}</i>{busy && verifyProgress === index + 1 ? `${step}…` : step}</span>)}</div><p className="fine-print">Only send content you have permission to share. Sample results are marked synthetic.</p></Panel>
      {submissions.length > 0 && <Panel className="checked-list"><div className="panel-heading"><div><span className="eyebrow">YOUR HISTORY</span><h3>My checked tips</h3></div><span className="count-pill">{submissions.length}</span></div>{submissions.map((item) => <div className="checked-item" key={item.submission_id}><DataBadge origin={item.data_origin} /><strong>{item.claim.symbol ?? "Shared message"}</strong><span className={`status-tag ${item.status}`}>{formatLabel(item.status)}</span>{item.outcome && <small>Company {item.outcome.stock_pct}% · Index {item.outcome.index_pct}%</small>}</div>)}</Panel>}</div>
    <div className="verifier-results">{result ? <><Panel className="source-summary"><div className="source-heading"><div className="source-avatar">{result.source.platform.slice(0, 1)}</div><div><span className="eyebrow">SOURCE PROFILE</span><h3>{result.source.handle}</h3><small>{result.source.platform} · Sample profile</small></div><DataBadge origin={result.data_origin} /></div><div className="source-rating"><div className="rating-score">{result.source.score}<small>/100</small></div><div><span className={`rating-label ${result.source.label}`}>{labelText[result.source.label]}</span><p>This rating describes the source’s checked history, not a company.</p></div></div><div className="fact-grid">{Object.entries(result.source.facts).map(([key, value]) => <div key={key}><span>{key}</span><strong>{String(value)}</strong></div>)}</div><button className="text-link" onClick={() => setSearchSource(true)}>See source rating history <span>→</span></button></Panel><Panel><div className="panel-heading"><div><span className="eyebrow">CLAIM REVIEW</span><h3>{result.claim.symbol ?? "Submitted claim"}</h3></div><DataBadge origin={result.data_origin} /></div><div className="claim-outcome"><span>Reported direction</span><strong>{result.claim.direction === "up" ? "Expected to rise" : "Expected to fall"}</strong><span>Scoring status</span><strong>{formatLabel(result.claim.status ?? "needs_review")}</strong></div>{result.claim.outcome && <div className="outcome-pair compact"><div><span>Company</span><strong className={result.claim.outcome.stock_pct < 0 ? "negative" : "positive"}>{result.claim.outcome.stock_pct}%</strong></div><i>vs</i><div><span>Index</span><strong className={result.claim.outcome.index_pct < 0 ? "negative" : "positive"}>{result.claim.outcome.index_pct}%</strong></div></div>}<div className="red-flag-list"><span className="eyebrow">CLUES TO CHECK</span>{result.red_flags.map((flag) => <div className="red-flag" key={flag.code}><span className="flag-mark">!</span><div><strong>{formatLabel(flag.code)}</strong><p>{flag.text}</p><small>Evidence: {flag.evidence}</small></div></div>)}</div><div className="neutral-note">A source label summarizes available records. It does not confirm that a future claim will be correct.</div></Panel>{source && <Panel className="source-history"><div className="panel-heading"><div><span className="eyebrow">SOURCE TRACK RECORD</span><h3>Rating history</h3></div><DataBadge origin={source.data_origin} /></div><div className="history-bars">{source.history.map((item) => <div key={item.date}><span>{item.date}</span><i style={{ height: `${item.score * 1.5}px` }} /><b>{item.score}</b></div>)}</div><div className="source-recent">{source.recent_claims.map((item, index) => <div key={`${item.symbol}-${index}`}><span>{item.symbol}</span><small>{formatLabel(item.status)} · {item.outcome}</small></div>)}</div></Panel>}</> : <Panel className="results-empty"><div className="empty-orbit"><span>✳</span></div><span className="eyebrow">YOUR REVIEW WILL APPEAR HERE</span><h3>Start with the source.</h3><p>We’ll show the source label and its facts, then list the clues we could check in the message.</p><div className="empty-mini-list"><span><i>01</i> Source history</span><span><i>02</i> Claim details</span><span><i>03</i> Evidence and outcome</span></div><DataBadge origin="synthetic" /></Panel>}</div></div></>;
}

function ProgressView({ data }: { data: DashboardData | null }) {
  if (!data) return <><SectionHeading eyebrow="MY PROGRESS" title="Skills that grow with practice." /><Panel>Loading your progress…</Panel></>;
  const lastScore = data.brier_over_time.at(-1)?.brier ?? 0;
  const accuracy = data.scenario_accuracy.at(-1)?.accuracy ?? 0;
  return <><SectionHeading eyebrow="MY PROGRESS" title="Skills that grow with practice." action={<DataBadge origin={data.data_origin} />} /><div className="progress-stat-row"><Panel><span className="eyebrow">CURRENT LEVEL</span><strong>Level {data.level}</strong><small>Building stronger judgement</small><DataBadge origin={data.data_origin} /></Panel><Panel><span className="eyebrow">LATEST CONFIDENCE SCORE</span><strong>{lastScore.toFixed(2)}</strong><small>Lower means closer calibration</small><DataBadge origin={data.data_origin} /></Panel><Panel><span className="eyebrow">SCENARIO ACCURACY</span><strong>{accuracy}%</strong><small>Across recent practice</small><DataBadge origin={data.data_origin} /></Panel></div><DashboardCharts data={data} /><Panel className="evidence-note"><div className="evidence-icon">i</div><div><span className="eyebrow">ABOUT THIS DEMO DATA</span><h3>Learning progress is not a market score.</h3><p>These sample charts show how the dashboard will work. A study before-and-after comparison with confidence intervals will appear when the research export is connected.</p></div><DataBadge origin={data.data_origin} /></Panel><div className="level-reflection"><div className="panel-heading"><span className="eyebrow">YOUR CURRENT LEVEL · {data.level}</span><DataBadge origin={data.data_origin} /></div><h3>Keep asking what supports a claim.</h3><p>Source, timing, and evidence all matter. Progress comes from building a repeatable habit of checking each one.</p></div></>;
}
