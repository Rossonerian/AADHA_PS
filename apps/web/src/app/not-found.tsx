import Link from "next/link";

const NOT_FOUND_STYLES = `
  .pp-not-found {
    --nf-bg: #f6f3ea;
    --nf-card: #fbfaf7;
    --nf-border: #dce2d9;
    --nf-ink: #202a24;
    --nf-muted: #536157;
    --nf-pill-bg: #eaf1eb;
    --nf-pill-ink: #1f4d3a;
    --nf-cta-bg: #1f4d3a;
    --nf-cta-hover: #173c2d;
    --nf-cta-ink: #f6f3ea;
    --nf-focus: #1f4d3a;
    --nf-shadow: 0 18px 48px rgba(31, 77, 58, 0.08);

    min-height: 100vh;
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px 16px;
    background:
      radial-gradient(circle at 18% 12%, rgba(31, 77, 58, 0.07), transparent 45%),
      var(--nf-bg);
    color: var(--nf-ink);
  }

  :root[data-theme="dark"] .pp-not-found,
  :root.dark .pp-not-found {
    --nf-bg: #09160c;
    --nf-card: #14291a;
    --nf-border: #2b4930;
    --nf-ink: #ecf8ed;
    --nf-muted: #c0d4c1;
    --nf-pill-bg: #19351d;
    --nf-pill-ink: #b4e4b4;
    --nf-cta-bg: #8fd78e;
    --nf-cta-hover: #a6e3a5;
    --nf-cta-ink: #071307;
    --nf-focus: #8fd78e;
    --nf-shadow: 0 22px 54px rgba(0, 0, 0, 0.42);
  }

  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) .pp-not-found {
      --nf-bg: #09160c;
      --nf-card: #14291a;
      --nf-border: #2b4930;
      --nf-ink: #ecf8ed;
      --nf-muted: #c0d4c1;
      --nf-pill-bg: #19351d;
      --nf-pill-ink: #b4e4b4;
      --nf-cta-bg: #8fd78e;
      --nf-cta-hover: #a6e3a5;
      --nf-cta-ink: #071307;
      --nf-focus: #8fd78e;
      --nf-shadow: 0 22px 54px rgba(0, 0, 0, 0.42);
    }
  }

  .pp-nf-card {
    width: 100%;
    max-width: 520px;
    background: var(--nf-card);
    border: 1px solid var(--nf-border);
    border-radius: 20px;
    padding: 36px 32px 30px;
    box-shadow: var(--nf-shadow);
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .pp-nf-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .pp-nf-brand {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    font-family: Georgia, "Times New Roman", serif;
    font-size: 18px;
    font-weight: 700;
    color: var(--nf-ink);
  }

  .pp-nf-badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    border-radius: 999px;
    background: var(--nf-pill-bg);
    color: var(--nf-pill-ink);
    font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.08em;
  }

  .pp-nf-title {
    margin: 0;
    font-family: Georgia, "Times New Roman", serif;
    font-size: clamp(26px, 4vw, 34px);
    line-height: 1.18;
    font-weight: 700;
    color: var(--nf-ink);
  }

  .pp-nf-copy {
    margin: 0;
    font-size: 15px;
    line-height: 1.6;
    color: var(--nf-muted);
  }

  .pp-nf-actions {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-top: 4px;
  }

  .pp-nf-cta {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    min-height: 44px;
    padding: 0 20px;
    border-radius: 12px;
    background: var(--nf-cta-bg);
    color: var(--nf-cta-ink);
    font-size: 14px;
    font-weight: 600;
    text-decoration: none;
    transition: background-color 150ms ease, transform 150ms ease;
  }

  .pp-nf-cta:hover {
    background: var(--nf-cta-hover);
  }

  .pp-nf-cta:active {
    transform: translateY(1px);
  }

  .pp-nf-cta:focus-visible {
    outline: 3px solid var(--nf-focus);
    outline-offset: 3px;
  }

  .pp-nf-note {
    margin: 4px 0 0;
    padding-top: 16px;
    border-top: 1px solid var(--nf-border);
    font-size: 12px;
    line-height: 1.5;
    color: var(--nf-muted);
  }

  @media (max-width: 480px) {
    .pp-nf-card {
      padding: 28px 22px 24px;
    }
  }
`;

export default function NotFound() {
  return (
    <main className="pp-not-found">
      <style>{NOT_FOUND_STYLES}</style>
      <section className="pp-nf-card" aria-labelledby="nf-heading">
        <div className="pp-nf-header">
          <div className="pp-nf-brand">
            <svg width="32" height="32" viewBox="0 0 64 64" fill="none" aria-hidden="true">
              <rect width="64" height="64" rx="15" fill="#1f4d3a" />
              <rect
                x="4.5"
                y="4.5"
                width="55"
                height="55"
                rx="11.5"
                stroke="#f6f3ea"
                strokeOpacity="0.16"
                strokeWidth="1.5"
              />
              <path
                d="M19 19H43M19 27.5H40M23.5 19C29.5 19 33 22.4 33 27.5C33 32.8 29 36.2 22.5 36.2H19.5L32.5 47"
                stroke="#f6f3ea"
                strokeWidth="4.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M36.5 41.5L41.5 46.5L51 35.5"
                stroke="#d6b265"
                strokeWidth="4.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span>PaisaProof</span>
          </div>
          <span className="pp-nf-badge">404 · PAGE NOT FOUND</span>
        </div>

        <h1 id="nf-heading" className="pp-nf-title">
          This page isn&apos;t in your ledger.
        </h1>

        <p className="pp-nf-copy">
          The link you followed may have moved or doesn&apos;t exist. Head back to your dashboard to
          continue building calibration and checking financial claims.
        </p>

        <div className="pp-nf-actions">
          <Link href="/" className="pp-nf-cta">
            <span>Go to dashboard</span>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M3.5 8H12.5M8.5 4L12.5 8L8.5 12"
                stroke="currentColor"
                strokeWidth="1.75"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </Link>
        </div>

        <p className="pp-nf-note">
          PaisaProof is a learning tool. It never tells you what to buy or sell.
        </p>
      </section>
    </main>
  );
}
