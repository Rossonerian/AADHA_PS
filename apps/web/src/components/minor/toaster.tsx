"use client";

import { Toaster as Sonner, toast } from "sonner";

/** Minor secondary primitive: sonner toasts themed with paper/ink tokens. */
export function Toaster({ theme }: { theme: "light" | "dark" }) {
  return (
    <Sonner
      theme={theme}
      position="bottom-right"
      closeButton
      duration={5000}
      toastOptions={{ classNames: { toast: "minor-toast" } }}
    />
  );
}

export function notify(message: string) {
  toast.success(message);
}
