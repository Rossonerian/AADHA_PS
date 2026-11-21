"use client";

import { Button } from "@/components/ui";

/** Shown when "Sign in with Google" found no PaisaProof account for the chosen Google email. */
export function GoogleCreateConfirm({
  email,
  busy = false,
  onCreate,
  onCancel,
}: {
  email: string;
  busy?: boolean;
  onCreate: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="pp-auth-confirm" role="group" aria-labelledby="google-confirm-title">
      <strong id="google-confirm-title">No PaisaProof account found</strong>
      <p>
        We couldn&apos;t find an account for {email || "this Google email"}. Create a new PaisaProof
        account with it?
      </p>
      <Button type="button" disabled={busy} onClick={onCreate}>
        Create account
      </Button>
      <Button type="button" variant="secondary" disabled={busy} onClick={onCancel}>
        Cancel
      </Button>
    </div>
  );
}
