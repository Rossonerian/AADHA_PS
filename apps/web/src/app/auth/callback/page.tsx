"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Panel } from "@/components/ui";
import { mocksEnabled } from "@/lib/api";
import { authClient } from "@/lib/neon-auth-client";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function completeOAuth() {
      const params = new URLSearchParams(window.location.search);
      const paramError = params.get("error_description") ?? params.get("error");
      if (paramError) {
        if (!cancelled) setError(`Sign-in could not finish: ${paramError}`);
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

  return (
    <main className="welcome-screen">
      <div className="welcome-noise" aria-hidden="true" />
      <div className="mx-auto flex w-full max-w-md flex-1 items-center justify-center py-12">
        <Panel className="signin-panel w-full text-center">
          <div className="signin-icon mx-auto" aria-hidden="true">
            ✳
          </div>
          <span className="eyebrow">AUTHENTICATION</span>
          <h2>{error ? "Sign-in paused" : "Finishing sign-in…"}</h2>
          {!error ? (
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
