"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Panel } from "@/components/ui";
import { mocksEnabled } from "@/lib/api";
import { authClient } from "@/lib/neon-auth-client";
import { decideGoogleOutcome, isNewGoogleUser, readOAuthUrlError } from "@/lib/auth-flow";
import {
  clearDeclinedEmail,
  clearIntent,
  flagWelcomeBack,
  isDeclinedEmail,
  markDeclinedEmail,
  readIntent,
} from "@/lib/auth-flow-storage";
import { GoogleCreateConfirm } from "@/components/auth/google-create-confirm";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [confirmEmail, setConfirmEmail] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function completeOAuth() {
      const params = new URLSearchParams(window.location.search);
      const paramError = readOAuthUrlError(window.location.search);
      if (paramError) {
        clearIntent();
        if (!cancelled) setError(paramError);
        return;
      }

      if (mocksEnabled) {
        router.replace("/");
        return;
      }

      try {
        const res = await authClient.getSession();
        if (cancelled) return;
        if (res.data?.session) {
          const user = res.data.user as { email?: string; createdAt?: string | Date } | undefined;
          const email = user?.email ?? "";
          const intent = readIntent();
          const isNewUser = isNewGoogleUser({
            newUserParam: params.get("new") === "1",
            createdAt: user?.createdAt,
            previouslyDeclined: email ? isDeclinedEmail(email) : false,
          });
          const outcome = decideGoogleOutcome({ intent, isNewUser });
          if (outcome === "confirm_create") {
            // Signed in via Google but no PaisaProof account existed: ask before continuing.
            setConfirmEmail(email);
            return;
          }
          if (outcome === "welcome_back") flagWelcomeBack();
          clearIntent();
          router.replace("/");
        } else {
          setError("Your sign-in session was not established. Please try signing in again.");
        }
      } catch {
        if (!cancelled) {
          setError("Could not verify your session after sign-in. Please return to sign in.");
        }
      }
    }

    void completeOAuth();

    return () => {
      cancelled = true;
    };
  }, [router]);

  async function createAccount() {
    if (confirmEmail) clearDeclinedEmail(confirmEmail);
    clearIntent();
    router.replace("/");
  }

  async function cancelCreate() {
    setBusy(true);
    // The account row already exists in Neon Auth (no client-side delete endpoint), so remember
    // the decline: the next Google sign-in for this email asks again instead of entering.
    if (confirmEmail) markDeclinedEmail(confirmEmail);
    clearIntent();
    try {
      await authClient.signOut();
    } catch {
      // Ignore: the user is returned to sign-in either way.
    }
    router.replace("/");
  }

  return (
    <main className="welcome-screen">
      <div className="welcome-noise" aria-hidden="true" />
      <div className="mx-auto flex w-full max-w-md flex-1 items-center justify-center py-12">
        <Panel className="signin-panel w-full text-center">
          <div className="signin-icon mx-auto" aria-hidden="true">
            ✳
          </div>
          <span className="eyebrow">AUTHENTICATION</span>
          <h2>
            {confirmEmail !== null
              ? "Create your account?"
              : error
                ? "Sign-in paused"
                : "Finishing sign-in…"}
          </h2>
          {confirmEmail !== null ? (
            <GoogleCreateConfirm
              email={confirmEmail}
              busy={busy}
              onCreate={() => void createAccount()}
              onCancel={() => void cancelCreate()}
            />
          ) : !error ? (
            <p>Connecting your learning space cleanly. You will be redirected automatically.</p>
          ) : (
            <div className="mt-4 text-left">
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
              <div className="mt-4 text-center">
                <Link href="/" className="pp-link-btn inline-block">
                  Back to sign in
                </Link>
              </div>
            </div>
          )}
        </Panel>
      </div>
    </main>
  );
}
