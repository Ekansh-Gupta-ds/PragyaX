import type { ReactNode } from "react";
import type { CardProps } from "../../types/ui";

export function Card({ children, className = "", onClick, role }: CardProps) {
  return (
    <div
      className={`card ${className}`.trim()}
      onClick={onClick}
      role={role}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  description,
  action,
  children,
  className = "",
}: {
  title?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`card-header ${className}`.trim()}>
      <div className="row-between">
        <div>
          {title && (typeof title === "string" ? <h2 className="card-title">{title}</h2> : title)}
          {description && (
            typeof description === "string" ? (
              <p className="card-description">{description}</p>
            ) : (
              description
            )
          )}
        </div>
        {action && <div>{action}</div>}
      </div>
      {children}
    </div>
  );
}

export function CardContent({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={className}>{children}</div>;
}

export default Card;
