import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/** Minor secondary primitive: a calm placeholder block for loading states. */
export function Skeleton({ className, ...props }: ComponentProps<"div">) {
  return <div aria-hidden="true" className={cn("minor-skeleton", className)} {...props} />;
}
