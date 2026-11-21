import { useId, type ButtonHTMLAttributes, type ComponentProps, type ReactNode } from "react";
import { Button as LooseleafButton } from "@/components/ui/button";
import { Alert as LooseleafAlert } from "@/components/ui/alert";
import {
  Avatar as LooseleafAvatar,
  AvatarFallback as LooseleafAvatarFallback,
} from "@/components/ui/avatar";
import { Badge as LooseleafBadge } from "@/components/ui/badge";
import { Card as LooseleafCard } from "@/components/ui/card";
import { Checkbox as LooseleafCheckbox } from "@/components/ui/checkbox";
import { Input as LooseleafInput, InputControl } from "@/components/ui/input";
import { Progress as LooseleafProgress } from "@/components/ui/progress";
import {
  RadioGroup as LooseleafRadioGroup,
  RadioGroupItem as LooseleafRadioGroupItem,
} from "@/components/ui/radio-group";
import { Slider as LooseleafSlider } from "@/components/ui/slider";
import {
  Tabs as LooseleafTabs,
  TabsList as LooseleafTabsList,
  TabsTrigger as LooseleafTabsTrigger,
} from "@/components/ui/tabs";
import { Textarea as LooseleafTextarea, TextareaControl } from "@/components/ui/textarea";
import type { DataOrigin } from "@/lib/types";

export function Button({
  children,
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "quiet" | "destructive";
  children: ReactNode;
}) {
  const looseleafVariant =
    variant === "primary"
      ? "default"
      : variant === "secondary"
        ? "secondary"
        : variant === "destructive"
          ? "destructive"
          : "ghost";
  return (
    <LooseleafButton
      variant={looseleafVariant}
      className={`button button-${variant} looseleaf-button ${className}`}
      {...props}
    >
      {children}
    </LooseleafButton>
  );
}

/** A Looseleaf radio with its own visible label; use inside RadioGroup. */
export function ChoiceOption({
  value,
  selected,
  className = "",
  children,
}: {
  value: string;
  selected: boolean;
  className?: string;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <div className={`choice-option ${selected ? "chosen" : ""} ${className}`}>
      <LooseleafRadioGroupItem value={value} id={id} />
      <label htmlFor={id} data-slot="label">
        {children}
      </label>
    </div>
  );
}

export function Panel({
  children,
  className = "",
  ...props
}: ComponentProps<typeof LooseleafCard> & { children: ReactNode }) {
  return (
    <LooseleafCard as="section" stock="card" className={`panel gap-0 ${className}`} {...props}>
      {children}
    </LooseleafCard>
  );
}

export function DataBadge({ origin }: { origin: DataOrigin }) {
  return (
    <LooseleafBadge
      variant={origin === "real" ? "default" : "secondary"}
      className={`data-badge ${origin}`}
      aria-label={`Data origin: ${origin}`}
    >
      <span aria-hidden="true" />
      {origin === "real" ? "REAL DATA" : "SYNTHETIC DATA"}
    </LooseleafBadge>
  );
}

export function ProgressBar({
  value,
  label,
  ariaLabel,
}: {
  value: number;
  label?: string;
  ariaLabel?: string;
}) {
  return (
    <div className="progress-wrap">
      <LooseleafProgress
        className="progress-track"
        value={Math.max(0, Math.min(100, value))}
        aria-label={ariaLabel ?? label ?? "Progress"}
      />
      {label && <span className="progress-label">{label}</span>}
    </div>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  action,
}: {
  eyebrow: string;
  title: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
      </div>
      {action}
    </div>
  );
}

export function LockNotice({
  level,
  current,
  onLearn,
}: {
  level: number;
  current?: number;
  onLearn?: () => void;
}) {
  const away = current !== undefined ? Math.max(1, level - current) : undefined;
  return (
    <LooseleafAlert className="lock-notice" variant="warning">
      <span className="lock-icon" aria-hidden="true">
        ⌑
      </span>
      <div>
        <strong>Unlocks at Level {level}</strong>
        <p>
          {away !== undefined
            ? `You are ${away} level${away > 1 ? "s" : ""} away. Pass the level check on your learning path to open this tool.`
            : "Pass the level check on your learning path to open this tool."}
        </p>
        {onLearn && (
          <LooseleafButton variant="secondary" onClick={onLearn}>
            Go to learning path <span aria-hidden="true">→</span>
          </LooseleafButton>
        )}
      </div>
    </LooseleafAlert>
  );
}

/** Shared "how sure are you?" slider used by Practice, Verifier and the Nasdaq check. */
export function ConfidenceControl({
  value,
  onChange,
  label,
}: {
  value: number;
  onChange: (value: number) => void;
  label: string;
}) {
  return (
    <div className="confidence-control">
      <div>
        <label>{label}</label>
        <strong>{value}%</strong>
      </div>
      <LooseleafSlider
        min={50}
        max={100}
        step={5}
        value={[value]}
        onValueChange={(next) => onChange(next[0] ?? value)}
        aria-label={`${label} ${value} percent`}
      />
      <div className="range-labels">
        <span>Not sure yet</span>
        <span>Very sure</span>
      </div>
    </div>
  );
}

export function Input({
  className,
  frameClassName = "",
  ...props
}: ComponentProps<"input"> & { frameClassName?: string }) {
  return (
    <LooseleafInput
      className={`looseleaf-input-frame ${frameClassName}`}
      inputClassName={`looseleaf-input-control ${className ?? ""}`}
      {...props}
    />
  );
}

export function InputControlField({ className, ...props }: ComponentProps<"input">) {
  return <InputControl className={`looseleaf-input-control ${className ?? ""}`} {...props} />;
}

export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return (
    <LooseleafTextarea
      className="looseleaf-textarea"
      inputClassName={`looseleaf-textarea-control ${className ?? ""}`}
      {...props}
    />
  );
}

export function TextareaControlField({ className, ...props }: ComponentProps<"textarea">) {
  return <TextareaControl className={`looseleaf-textarea-control ${className ?? ""}`} {...props} />;
}

export function Avatar({
  children,
  className = "",
  ...props
}: ComponentProps<typeof LooseleafAvatar> & { children: ReactNode }) {
  return (
    <LooseleafAvatar className={className} {...props}>
      {children}
    </LooseleafAvatar>
  );
}

export function AvatarFallback({
  children,
  className = "",
  ...props
}: ComponentProps<typeof LooseleafAvatarFallback> & { children: ReactNode }) {
  return (
    <LooseleafAvatarFallback className={className} {...props}>
      {children}
    </LooseleafAvatarFallback>
  );
}

export {
  LooseleafAlert as Alert,
  LooseleafBadge as Badge,
  LooseleafCheckbox as Checkbox,
  LooseleafRadioGroup as RadioGroup,
  LooseleafRadioGroupItem as RadioGroupItem,
  LooseleafSlider as Slider,
  LooseleafTabs as Tabs,
  LooseleafTabsList as TabsList,
  LooseleafTabsTrigger as TabsTrigger,
};
