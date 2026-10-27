import type { ProgressBarProps } from "../../types/ui";

export function ProgressBar({
  value,
  label,
  variant = "primary",
  showLabel = false,
  className = "",
}: ProgressBarProps) {
  const pct = Math.max(0, Math.min(100, Math.round(value)));

  const variantClass = {
    primary: "",
    success: "success",
    warning: "warning",
  }[variant];

  return (
    <div className={className}>
      {showLabel && (
        <div className="row-between" style={{ marginBottom: "4px" }}>
          <span className="small muted">{label}</span>
          <span className="small muted" style={{ fontWeight: 600 }}>{pct}%</span>
        </div>
      )}
      <div
        className="progress"
        role="progressbar"
        aria-label={label}
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={`progress-fill ${variantClass}`.trim()}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default ProgressBar;
