import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "outline" | "danger" | "accent";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  block?: boolean;
  loading?: boolean;
  leftIcon?: LucideIcon;
  rightIcon?: LucideIcon;
  children?: ReactNode;
}

export type BadgeVariant = "default" | "primary" | "accent" | "success" | "warning" | "error" | "demo" | "soon";

export interface BadgeProps {
  variant?: BadgeVariant;
  icon?: LucideIcon;
  children: ReactNode;
  className?: string;
  title?: string;
}

export interface CardProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  hoverable?: boolean;
  role?: string;
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
  error?: string;
  leftIcon?: LucideIcon;
  containerClassName?: string;
}

export type AlertVariant = "info" | "success" | "warning" | "error";

export interface AlertProps {
  variant?: AlertVariant;
  title?: string;
  message?: string;
  children?: ReactNode;
  icon?: LucideIcon;
  onRetry?: () => void;
  className?: string;
}

export interface ProgressBarProps {
  value: number; // 0 - 100
  label: string;
  variant?: "primary" | "success" | "warning";
  showLabel?: boolean;
  className?: string;
}

export interface LoadingStateProps {
  label?: string;
  fullPage?: boolean;
}

export interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: LucideIcon;
  action?: ReactNode;
  children?: ReactNode;
}
