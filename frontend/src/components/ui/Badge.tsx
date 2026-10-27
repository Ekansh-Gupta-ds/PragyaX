import type { BadgeProps } from "../../types/ui";

export function Badge({
  variant = "default",
  icon: Icon,
  children,
  className = "",
  title,
}: BadgeProps) {
  const variantClass = {
    default: "",
    primary: "badge-primary",
    accent: "badge-accent",
    success: "badge-success",
    warning: "badge-warn",
    error: "badge-error",
    demo: "badge-demo",
    soon: "badge-soon",
  }[variant];

  const classNames = ["badge", variantClass, className].filter(Boolean).join(" ");

  return (
    <span className={classNames} title={title}>
      {Icon && <Icon size={12} aria-hidden />}
      {children}
    </span>
  );
}

export default Badge;
