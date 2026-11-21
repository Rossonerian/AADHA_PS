import type { ComponentProps } from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/** Minor secondary primitive: a soft, paper-and-ink chip for tiny status/count tags. */
const chipVariants = cva("minor-chip", {
  variants: {
    tone: { neutral: "", gold: "minor-chip-gold", violet: "minor-chip-violet" },
    shape: { pill: "", round: "minor-chip-round" },
  },
  defaultVariants: { tone: "neutral", shape: "pill" },
});

export function Chip({
  className,
  tone,
  shape,
  ...props
}: ComponentProps<"span"> & VariantProps<typeof chipVariants>) {
  return <span className={cn(chipVariants({ tone, shape }), className)} {...props} />;
}
