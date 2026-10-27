import { forwardRef, useId } from "react";
import type { InputProps } from "../../types/ui";

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  {
    label,
    helperText,
    error,
    leftIcon: LeftIcon,
    className = "",
    containerClassName = "",
    id,
    ...rest
  },
  ref
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const errorId = `${inputId}-error`;
  const helperId = `${inputId}-helper`;

  return (
    <div className={`field ${containerClassName}`.trim()}>
      {label && <label htmlFor={inputId}>{label}</label>}
      <div style={{ position: "relative", width: "100%" }}>
        {LeftIcon && (
          <span
            style={{
              position: "absolute",
              left: 12,
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--text-secondary)",
              display: "flex",
              pointerEvents: "none",
            }}
          >
            <LeftIcon size={16} aria-hidden />
          </span>
        )}
        <input
          ref={ref}
          id={inputId}
          className={className}
          style={LeftIcon ? { paddingLeft: "38px" } : undefined}
          aria-invalid={error ? "true" : undefined}
          aria-describedby={error ? errorId : helperText ? helperId : undefined}
          {...rest}
        />
      </div>
      {error && (
        <span id={errorId} style={{ color: "var(--error)", fontSize: "0.82rem" }} role="alert">
          {error}
        </span>
      )}
      {!error && helperText && (
        <span id={helperId} style={{ color: "var(--text-secondary)", fontSize: "0.82rem" }}>
          {helperText}
        </span>
      )}
    </div>
  );
});

export default Input;
