"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, Panel } from "@/components/ui";
import { mocksEnabled } from "@/lib/api";
import { authClient } from "@/lib/neon-auth-client";
import { readOAuthUrlError } from "@/lib/auth-flow";
import { clearDeclinedEmail, clearIntent } from "@/lib/auth-flow-storage";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function completeOAuth() {
      await Promise.resolve();
      if (cancelled) return;

      const paramError = readOAuthUrlError(window.location.search);
      if (paramError) {
        clearIntent();
        setError(paramError);
        return;
      }

      if (mocksEnabled) {
        clearIntent();
        router.replace("/");
        return;
      }

      try {
        const res = await authClient.getSession();
        if (cancelled) return;
        if (res.data?.session) {
          const user = res.data.user as { email?: string } | undefined;
          const email = user?.email ?? "";
          if (email) clearDeclinedEmail(email);
          clearIntent();
          router.replace("/");
        } else {
          clearIntent();
          setError("Your sign-in session was not established. Please try signing in again.");
        }
      } catch {
        if (!cancelled) {
          clearIntent();
          setError("Could not verify your session after sign-in. Please return to sign in.");
        }
      }
    }

    void completeOAuth();

    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <main className="welcome-screen">
      <div className="welcome-noise" aria-hidden="true" />
      <div className="mx-auto flex w-full max-w-md flex-1 items-center justify-center py-12">
        <Panel className="signin-panel w-full text-center">
          <div className="signin-icon mx-auto" aria-hidden="true">
            ✳
          </div>
          <span className="eyebrow">AUTHENTICATION</span>
          <h2>{error ? "Sign-in paused" : "Signing you in…"}</h2>
          {!error ? (
            <p>Connecting your learning space cleanly. You will be redirected automatically.</p>
          ) : (
            <div className="mt-4 flex flex-col gap-3 text-left">
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
              <div className="flex flex-col items-center gap-2 pt-1">
                <Button type="button" className="w-full" onClick={() => router.replace("/")}>
                  Try again
                </Button>
                <Link href="/" className="pp-link-btn inline-block py-1">
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
