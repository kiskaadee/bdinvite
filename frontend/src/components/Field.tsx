import type { InputHTMLAttributes } from "react";

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

export function Field({ label, id, error, hint, disabled, style, ...props }: FieldProps) {
  const inputId = id || `field-${label.toLowerCase().replace(/\s+/g, "-")}`;
  const errorId = `${inputId}-error`;
  const hintId = `${inputId}-hint`;

  return (
    <div style={{ marginBottom: "1.4rem", width: "100%", textAlign: "left" }}>
      <label
        htmlFor={inputId}
        style={{
          display: "block",
          fontSize: "0.72rem",
          fontWeight: 500,
          letterSpacing: "0.15em",
          textTransform: "uppercase",
          color: "var(--color-text-muted)",
          marginBottom: "0.45rem",
        }}
      >
        {label}
      </label>
      <input
        id={inputId}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        style={{
          width: "100%",
          padding: "0.85rem 1rem",
          backgroundColor: "rgba(255, 255, 255, 0.05)",
          border: error
            ? "1px solid var(--color-error)"
            : "1px solid var(--color-gold-border)",
          borderRadius: "4px",
          color: "var(--color-text)",
          fontSize: "0.95rem",
          outline: "none",
          transition: "border-color 0.2s ease, box-shadow 0.2s ease",
          ...style,
        }}
        onFocus={(e) => {
          if (!error) {
            e.currentTarget.style.borderColor = "var(--color-gold-border-focus)";
            e.currentTarget.style.boxShadow = "0 0 0 2px rgba(212, 168, 67, 0.15)";
          }
        }}
        onBlur={(e) => {
          if (!error) {
            e.currentTarget.style.borderColor = "var(--color-gold-border)";
            e.currentTarget.style.boxShadow = "none";
          }
        }}
        {...props}
      />
      {hint && !error && (
        <span
          id={hintId}
          style={{
            display: "block",
            fontSize: "0.72rem",
            color: "var(--color-text-dim)",
            marginTop: "0.3rem",
          }}
        >
          {hint}
        </span>
      )}
      {error && (
        <span
          id={errorId}
          role="alert"
          style={{
            display: "block",
            fontSize: "0.75rem",
            color: "var(--color-error)",
            marginTop: "0.35rem",
          }}
        >
          {error}
        </span>
      )}
    </div>
  );
}
