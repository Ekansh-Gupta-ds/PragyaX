import { CircleAlert, CircleCheck, Info, RotateCcw, TriangleAlert } from "lucide-react";
import type { AlertProps } from "../../types/ui";

export function Alert({
  variant = "info",
  title,
  message,
  children,
  icon: CustomIcon,
  onRetry,
  className = "",
}: AlertProps) {
  const Icon = CustomIcon ?? {
    info: Info,
    success: CircleCheck,
    warning: TriangleAlert,
    error: CircleAlert,
  }[variant];

  const variantClass = {
    info: "alert-info",
    success: "alert-success",
    warning: "alert-warning",
    error: "alert-error",
  }[variant];

  return (
    <div
      className={`alert ${variantClass} ${className}`.trim()}
      role={variant === "error" ? "alert" : "status"}
    >
      <Icon size={18} aria-hidden />
      <div style={{ flex: 1, minWidth: 0 }}>
        {title && <strong style={{ display: "block", marginBottom: message || children ? "2px" : 0 }}>{title}</strong>}
        {message && <span>{message}</span>}
        {children}
      </div>
      {onRetry && (
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={onRetry}
          style={{ alignSelf: "center", marginLeft: "auto" }}
        >
          <RotateCcw size={14} aria-hidden /> Retry
        </button>
      )}
    </div>
  );
}

export default Alert;
