import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { DataOrigin } from "@/lib/types";

export function Button({ children, variant = "primary", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "quiet"; children: ReactNode }) {
  return <button className={`button button-${variant} ${className}`} {...props}>{children}</button>;
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}>{children}</section>;
}

export function DataBadge({ origin }: { origin: DataOrigin }) {
  return <span className={`data-badge ${origin}`} aria-label={`Data origin: ${origin}`}><span aria-hidden="true" />{origin === "real" ? "REAL DATA" : "SYNTHETIC DATA"}</span>;
}

export function ProgressBar({ value, label }: { value: number; label?: string }) {
  return <div className="progress-wrap"><div className="progress-track" role="progressbar" aria-label={label ?? "Progress"} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}><span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div>{label && <span className="progress-label">{label}</span>}</div>;
}

export function SectionHeading({ eyebrow, title, action }: { eyebrow: string; title: string; action?: ReactNode }) {
  return <div className="section-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1></div>{action}</div>;
}

export function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  return <div className="toast" role="status"><span className="toast-icon" aria-hidden="true">✓</span><span>{message}</span><button onClick={onClose} aria-label="Dismiss message">×</button></div>;
}

export function LockNotice({ level }: { level: number }) {
  return <div className="lock-notice"><span className="lock-icon" aria-hidden="true">⌑</span><div><strong>Unlocks at Level {level}</strong><p>Complete the next learning check to access this tool.</p></div></div>;
}
