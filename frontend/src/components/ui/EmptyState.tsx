import type { EmptyStateProps } from "../../types/ui";

export function EmptyState({
  title,
  description,
  icon: Icon,
  action,
  children,
}: EmptyStateProps) {
  return (
    <div className="empty" role="region" aria-label={title}>
      {Icon && (
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: "var(--radius-full)",
            background: "var(--bg-secondary)",
            border: "1px solid var(--border)",
            display: "grid",
            placeItems: "center",
            color: "var(--text-secondary)",
            marginBottom: 4,
          }}
        >
          <Icon size={22} aria-hidden />
        </div>
      )}
      <p className="empty-title">{title}</p>
      {description && <p>{description}</p>}
      {children}
      {action && <div style={{ marginTop: 8 }}>{action}</div>}
    </div>
  );
}

export default EmptyState;
