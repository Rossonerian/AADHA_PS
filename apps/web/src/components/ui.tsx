import type { ButtonHTMLAttributes, ComponentProps, ReactNode } from "react";
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
  variant?: "primary" | "secondary" | "quiet";
  children: ReactNode;
}) {
  const looseleafVariant =
    variant === "primary" ? "default" : variant === "secondary" ? "secondary" : "ghost";
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

export function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <LooseleafAlert className="toast" variant="success" role="status">
      <span className="toast-icon" aria-hidden="true">
        ✓
      </span>
      <span>{message}</span>
      <Button
        variant="quiet"
        className="toast-dismiss"
        onClick={onClose}
        aria-label="Dismiss message"
      >
        ×
      </Button>
    </LooseleafAlert>
  );
}

export function LockNotice({ level }: { level: number }) {
  return (
    <LooseleafAlert className="lock-notice" variant="warning">
      <span className="lock-icon" aria-hidden="true">
        ⌑
      </span>
      <div>
        <strong>Unlocks at Level {level}</strong>
        <p>Complete the next learning check to access this tool.</p>
      </div>
    </LooseleafAlert>
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
