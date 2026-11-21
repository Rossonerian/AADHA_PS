"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, Eye, EyeOff, Moon, Sun } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, Input, Panel } from "@/components/ui";
import { Separator } from "@/components/minor/separator";
import { mockAuthBridge, mocksEnabled } from "@/lib/api";
import { ApiClientError } from "@/lib/api-client";
import { classifyAuthError, type AuthFailure } from "@/lib/auth-errors";
import { readOAuthUrlError, stripOAuthErrorParams } from "@/lib/auth-flow";
import { authClient } from "@/lib/neon-auth-client";
import { SilkBackground } from "@/components/effects/silk-background";

type PasswordMode = "signin" | "signup";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function GoogleMark() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="pp-google-icon shrink-0"
    >
      <path
        fill="#4285F4"
        d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.3 0 6.08-1.09 8.1-2.96l-3.88-3.05c-1.1.74-2.51 1.18-4.22 1.18-3.24 0-5.99-2.19-6.97-5.13H1.03v3.14C3.04 21.18 7.21 24 12 24Z"
      />
      <path
        fill="#FBBC05"
        d="M5.03 14.04c-.25-.74-.39-1.54-.39-2.36 0-.82.14-1.62.39-2.36V6.18H1.03C.37 7.5 0 8.99 0 10.68s.37 3.18 1.03 4.5l4-3.14Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.8 0 3.41.62 4.68 1.84l3.51-3.51C18.07 1.19 15.3 0 12 0 7.21 0 3.04 2.82 1.03 6.95l4 3.14C6.01 6.94 8.76 4.75 12 4.75Z"
      />
    </svg>
  );
}

function isUnknownUserFailure(err: unknown, failure: AuthFailure): boolean {
  if ((failure.kind as string) === "unknown_user") return true;
  const code =
    err && typeof err === "object" && "code" in err
      ? String((err as { code?: unknown }).code ?? "").toUpperCase()
      : "";
  return (
    code === "USER_NOT_FOUND" ||
    /no account found|user not found|user does not exist/i.test(failure.message)
  );
}

export function AuthScreen({
  theme,
  onToggleTheme,
  onAuthenticated,
  notice = "",
}: {
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onAuthenticated: () => Promise<void>;
  notice?: string;
}) {
  const [mode, setMode] = useState<PasswordMode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busyProvider, setBusyProvider] = useState<"google" | "email" | "reset" | null>(null);
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [suggestCreateAccount, setSuggestCreateAccount] = useState(false);

  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  const supportsReset =
    Boolean(mockAuthBridge) ||
    typeof (authClient as unknown as { requestPasswordReset?: unknown }).requestPasswordReset ===
      "function";

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(() => {
      if (cancelled) return;
      const oauthError = readOAuthUrlError(window.location.search);
      if (oauthError) {
        setError(oauthError);
        const rest = stripOAuthErrorParams(window.location.search);
        window.history.replaceState(
          window.history.state,
          "",
          `${window.location.pathname}${rest}${window.location.hash}`,
        );
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    emailRef.current?.focus();
  }, []);

  const busy = busyProvider !== null;

  async function handleGoogleContinue() {
    setError("");
    setStatusMessage("");
    setSuggestCreateAccount(false);
    setBusyProvider("google");
    try {
      if (mocksEnabled && mockAuthBridge) {
        await mockAuthBridge.signInGoogle();
        await onAuthenticated();
        return;
      }
      const origin = window.location.origin;
      const res = await authClient.signIn.social({
        provider: "google",
        callbackURL: `${origin}/auth/callback`,
        errorCallbackURL: `${origin}/auth/callback`,
      });
      if (res?.error) {
        throw res.error;
      }
      if (!res?.data?.url) {
        // Success without a redirect target means the provider is not wired up.
        throw { status: 404, message: "Provider not found" };
      }
      // The SDK navigates the browser to Google; keep the busy state until it unloads.
    } catch (err) {
      setError(classifyAuthError(err, "google").message);
      setBusyProvider(null);
    }
  }

  function suggestName(sourceEmail: string) {
    if (!fullName.trim()) {
      const local = sourceEmail.trim().split("@", 1)[0] ?? "";
      const suggested = local.replace(/[._-]+/g, " ").trim();
      if (suggested) {
        setFullName(suggested.replace(/\b\w/g, (ch) => ch.toUpperCase()).slice(0, 80));
      }
    }
  }

  function switchToSignUp() {
    setError("");
    setStatusMessage("");
    setSuggestCreateAccount(false);
    suggestName(email);
    setMode("signup");
    if (!EMAIL_PATTERN.test(email.trim())) {
      emailRef.current?.focus();
    } else if (!password) {
      passwordRef.current?.focus();
    }
  }

  function switchToSignIn() {
    setError("");
    setStatusMessage("");
    setSuggestCreateAccount(false);
    setMode("signin");
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setStatusMessage("");
    setSuggestCreateAccount(false);

    const normalizedEmail = email.trim();
    if (!EMAIL_PATTERN.test(normalizedEmail)) {
      setError("Enter a valid email address.");
      emailRef.current?.focus();
      return;
    }
    setEmail(normalizedEmail);

    if (!password) {
      setError("Enter your password to continue.");
      passwordRef.current?.focus();
      return;
    }

    if (mode === "signup" && password.length < 8) {
      setError("Use a password with at least 8 characters.");
      passwordRef.current?.focus();
      return;
    }

    setBusyProvider("email");
    try {
      if (mocksEnabled && mockAuthBridge) {
        if (mode === "signup") {
          await mockAuthBridge.signUpEmail(normalizedEmail, password, fullName.trim() || undefined);
        } else {
          await mockAuthBridge.signInEmail(normalizedEmail, password);
        }
        await onAuthenticated();
        return;
      }

      if (mode === "signup") {
        const derivedName = fullName.trim() || normalizedEmail.split("@", 1)[0] || "Learner";
        const result = await authClient.signUp.email({
          email: normalizedEmail,
          password,
          name: derivedName,
        });
        if (result.error) {
          throw result.error;
        }
      } else {
        const result = await authClient.signIn.email({
          email: normalizedEmail,
          password,
        });
        if (result.error) {
          throw result.error;
        }
      }
      await onAuthenticated();
    } catch (err) {
      if (mode === "signup" && err instanceof ApiClientError && err.status === 401) {
        // Account created but no session yet: email verification is required.
        setStatusMessage("Account created. Check your inbox to verify your email, then sign in.");
        setMode("signin");
        setPassword("");
        return;
      }
      const failure = classifyAuthError(err);
      if (failure.kind === "already_exists" && mode === "signup") {
        setMode("signin");
        setStatusMessage("You already have an account. Click Sign in to continue.");
        return;
      }
      if (
        mode === "signin" &&
        (isUnknownUserFailure(err, failure) || failure.kind === "invalid_credentials")
      ) {
        setSuggestCreateAccount(true);
      }
      setError(failure.message);
    } finally {
      setBusyProvider(null);
    }
  }

  async function handleForgotPassword() {
    setError("");
    setStatusMessage("");
    setSuggestCreateAccount(false);
    const normalizedEmail = email.trim();
    if (!EMAIL_PATTERN.test(normalizedEmail)) {
      setError("Enter your email address first so we know where to send the reset link.");
      emailRef.current?.focus();
      return;
    }
    setBusyProvider("reset");
    try {
      if (mocksEnabled && mockAuthBridge) {
        await mockAuthBridge.requestPasswordReset(normalizedEmail);
      } else {
        const result = await authClient.requestPasswordReset({
          email: normalizedEmail,
          redirectTo: window.location.origin,
        });
        if (result?.error) {
          throw result.error;
        }
      }
      setStatusMessage(
        `If an account exists for ${normalizedEmail}, password reset instructions have been sent.`,
      );
    } catch (err) {
      setError(classifyAuthError(err).message);
    } finally {
      setBusyProvider(null);
    }
  }

  return (
    <main className="welcome-screen" data-theme={theme}>
      <SilkBackground theme={theme} />
      <div className="welcome-noise" aria-hidden="true" />
      <div className="welcome-brand">
        <div className="welcome-brand-name">
          <span className="brand-mark">P</span>
          <span>PaisaProof</span>
        </div>
        <Button
          variant="quiet"
          className="theme-toggle welcome-theme-toggle"
          onClick={onToggleTheme}
          aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
          aria-pressed={theme === "dark"}
        >
          {theme === "light" ? <Moon size={17} /> : <Sun size={17} />}
        </Button>
      </div>

      <div className="welcome-content">
        <div className="welcome-copy">
          <span className="eyebrow light">A CALMER WAY TO LEARN ABOUT MARKETS</span>
          <h1>
            Build your money sense,
            <br />
            <em>one question at a time.</em>
          </h1>
          <p>
            Learn to read financial information, question bold claims, and understand how your
            confidence matches real outcomes.
          </p>
          <div className="welcome-points">
            <span>
              <i>01</i> Short, guided lessons
            </span>
            <span>
              <i>02</i> Practice with real-world clues
            </span>
            <span>
              <i>03</i> See your skills grow over time
            </span>
          </div>
          <div className="welcome-disclaimer">
            Learning tool only · No personal financial guidance
          </div>
        </div>

        <Panel className="signin-panel pp-auth-card">
          <div className="signin-icon" aria-hidden="true">
            ✳
          </div>
          <span className="eyebrow">YOUR LEARNING SPACE</span>
          <h2>{mode === "signup" ? "Create your account" : "Welcome back"}</h2>
          <p>
            {mode === "signup"
              ? "Set up a free PaisaProof account to save your progress and learning path."
              : "Sign in to pick up where you left off."}
          </p>

          <Button
            type="button"
            variant="secondary"
            className="pp-google-btn"
            disabled={busy}
            onClick={() => void handleGoogleContinue()}
          >
            <GoogleMark />
            <span>
              {busyProvider === "google" ? "Connecting with Google…" : "Sign in with Google"}
            </span>
          </Button>

          <div className="pp-auth-or" aria-hidden="true">
            <Separator />
            <span>or continue with email</span>
            <Separator />
          </div>

          <form onSubmit={(e) => void handleSubmit(e)} className="signin-form" noValidate>
            {mode === "signup" && (
              <div className="field-group">
                <label htmlFor="auth-name">Your name (optional)</label>
                <Input
                  id="auth-name"
                  name="name"
                  type="text"
                  autoComplete="name"
                  placeholder="Maya Rao"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                />
              </div>
            )}

            <div className="field-group">
              <label htmlFor="auth-email">Email address</label>
              <Input
                ref={emailRef}
                id="auth-email"
                name="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  if (error) setError("");
                  if (suggestCreateAccount) setSuggestCreateAccount(false);
                }}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? "auth-feedback" : undefined}
              />
            </div>

            <div className="field-group">
              <div className="pp-label-row">
                <label htmlFor="auth-password">Password</label>
                {mode === "signin" && supportsReset && (
                  <button
                    type="button"
                    className="pp-link-btn"
                    onClick={() => void handleForgotPassword()}
                    disabled={busy}
                  >
                    {busyProvider === "reset" ? "Sending…" : "Forgot password?"}
                  </button>
                )}
              </div>
              <div className="pp-password-wrap">
                <Input
                  ref={passwordRef}
                  id="auth-password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete={mode === "signup" ? "new-password" : "current-password"}
                  placeholder={mode === "signup" ? "At least 8 characters" : "Enter your password"}
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value);
                    if (error) setError("");
                    if (suggestCreateAccount) setSuggestCreateAccount(false);
                  }}
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? "auth-feedback" : undefined}
                />
                <button
                  type="button"
                  className="pp-password-toggle"
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <Button type="submit" disabled={busy}>
              <span>
                {busyProvider === "email"
                  ? mode === "signup"
                    ? "Creating account…"
                    : "Signing in…"
                  : mode === "signup"
                    ? "Create account"
                    : "Sign in"}
              </span>
              <ArrowRight size={15} aria-hidden="true" />
            </Button>

            <div className="pp-auth-switch">
              {mode === "signin" ? (
                <>
                  <span>New here?</span>
                  <button
                    type="button"
                    className="pp-link-btn"
                    onClick={switchToSignUp}
                    disabled={busy}
                  >
                    Create an account
                  </button>
                </>
              ) : (
                <>
                  <span>Already have an account?</span>
                  <button
                    type="button"
                    className="pp-link-btn"
                    onClick={switchToSignIn}
                    disabled={busy}
                  >
                    Sign in
                  </button>
                </>
              )}
            </div>
          </form>

          <div id="auth-feedback" aria-live="polite" className="pp-auth-feedback">
            {notice && !error && !statusMessage && (
              <Alert variant="info" className="mt-3">
                <AlertDescription>{notice}</AlertDescription>
              </Alert>
            )}
            {statusMessage && (
              <Alert variant="info" className="mt-3">
                <AlertDescription>{statusMessage}</AlertDescription>
              </Alert>
            )}
            {error && (
              <Alert variant="destructive" className="mt-3">
                <AlertDescription>
                  <span>{error}</span>
                  {suggestCreateAccount && mode === "signin" && (
                    <Button
                      type="button"
                      variant="secondary"
                      className="mt-2 w-full"
                      onClick={switchToSignUp}
                    >
                      {email.trim() ? `Create account for ${email.trim()}` : "Create an account"}
                    </Button>
                  )}
                </AlertDescription>
              </Alert>
            )}
          </div>

          <small>PaisaProof is a learning tool. It never tells you what to buy or sell.</small>
        </Panel>
      </div>

      <footer className="welcome-footer">
        <span>© 2026 PaisaProof</span>
        <span>Learn with care. Decide with context.</span>
      </footer>
    </main>
  );
}
