import { LoaderCircle } from "lucide-react";
import type { LoadingStateProps } from "../../types/ui";

export function LoadingState({ label = "Loading…", fullPage = false }: LoadingStateProps) {
  return (
    <div
      className="state"
      style={fullPage ? { minHeight: "60vh" } : undefined}
      role="status"
      aria-live="polite"
    >
      <LoaderCircle className="spin" size={24} aria-hidden />
      <span>{label}</span>
    </div>
  );
}

export default LoadingState;
