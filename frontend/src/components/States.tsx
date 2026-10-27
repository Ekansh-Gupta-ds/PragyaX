import type { ReactNode } from "react";
import { LoadingState } from "./ui/LoadingState";
import { Alert } from "./ui/Alert";
import { EmptyState } from "./ui/EmptyState";
import { Badge } from "./ui/Badge";
import { ProgressBar as UIProgressBar } from "./ui/ProgressBar";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <LoadingState label={label} />;
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <Alert variant="error" message={message} onRetry={onRetry} />;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <EmptyState title={title}>{children}</EmptyState>;
}

export function DemoBadge({ label = "Demo AI" }: { label?: string }) {
  return (
    <Badge
      variant="demo"
      title="Responses come from the offline deterministic mock provider, not a live AI model."
    >
      {label}
    </Badge>
  );
}

export function ProgressBar({ value, label }: { value: number; label: string }) {
  return <UIProgressBar value={value} label={label} />;
}

export function levelClass(level: string): string {
  return `badge level-${level.toLowerCase().replace(/\s+/g, "-")}`;
}

export const formatDate = (s?: string | null): string => {
  if (!s) return "";
  // SQLite CURRENT_TIMESTAMP is UTC without a zone marker.
  const d = new Date(s.includes("T") || s.endsWith("Z") ? s : `${s.replace(" ", "T")}Z`);
  return isNaN(d.getTime()) ? s : d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
};
