import { forwardRef } from "react";
import { LoaderCircle } from "lucide-react";
import type { ButtonProps } from "../../types/ui";

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    size = "md",
    block = false,
    loading = false,
    disabled = false,
    leftIcon: LeftIcon,
    rightIcon: RightIcon,
    children,
    className = "",
    type = "button",
    ...rest
  },
  ref
) {
  const variantClass = {
    primary: "btn-primary",
    accent: "btn-accent",
    secondary: "btn-secondary",
    ghost: "btn-ghost",
    outline: "btn-outline",
    danger: "btn-danger",
  }[variant];

  const sizeClass = {
    sm: "btn-sm",
    md: "",
    lg: "btn-lg",
  }[size];

  const classNames = [
    "btn",
    variantClass,
    sizeClass,
    block ? "btn-block" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      ref={ref}
      type={type}
      className={classNames}
      disabled={disabled || loading}
      aria-busy={loading ? "true" : undefined}
      {...rest}
    >
      {loading ? (
        <LoaderCircle size={size === "sm" ? 14 : 16} className="spin" aria-hidden />
      ) : LeftIcon ? (
        <LeftIcon size={size === "sm" ? 14 : 16} aria-hidden />
      ) : null}
      {children}
      {!loading && RightIcon && <RightIcon size={size === "sm" ? 14 : 16} aria-hidden />}
    </button>
  );
});

export default Button;
