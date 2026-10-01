import type { ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline";
  fullWidth?: boolean;
}

export function Button({
  children,
  variant = "primary",
  fullWidth = false,
  disabled,
  style,
  ...props
}: ButtonProps) {
  const isPrimary = variant === "primary";
  const isOutline = variant === "outline";

  return (
    <button
      disabled={disabled}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "0.85rem 1.8rem",
        fontSize: "0.85rem",
        fontWeight: 600,
        letterSpacing: "0.18em",
        textTransform: "uppercase",
        borderRadius: "4px",
        border: isOutline
          ? "1px solid var(--color-gold)"
          : isPrimary
            ? "1px solid var(--color-gold)"
            : "1px solid rgba(255, 255, 255, 0.2)",
        backgroundColor: isPrimary
          ? "var(--color-gold)"
          : isOutline
            ? "transparent"
            : "rgba(255, 255, 255, 0.08)",
        color: isPrimary ? "#0a0a0a" : "var(--color-text)",
        opacity: disabled ? 0.6 : 1,
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "all 0.2s ease",
        width: fullWidth ? "100%" : "auto",
        ...style,
      }}
      {...props}
    >
      {children}
    </button>
  );
}
