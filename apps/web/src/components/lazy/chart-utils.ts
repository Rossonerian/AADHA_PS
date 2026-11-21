/** True when any point carries a numeric benchmark/index value, so callers can show an "Index" legend only then. */
export function chartHasIndex(data: unknown[]) {
  return data.some((p) => typeof (p as { index?: unknown }).index === "number");
}
