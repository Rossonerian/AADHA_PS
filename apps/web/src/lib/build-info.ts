const sha = (process.env.NEXT_PUBLIC_COMMIT_SHA ?? process.env.VERCEL_GIT_COMMIT_SHA ?? "").trim();

/** e.g. "v0 · a068783"; empty (hidden) when no commit SHA was provided at build time. */
export const BUILD_LABEL = sha ? `v0 · ${sha.slice(0, 7)}` : "";
