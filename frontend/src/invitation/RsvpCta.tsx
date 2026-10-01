interface RsvpCtaProps {
  label: string;
  onClick: () => void;
}

export function RsvpCta({ label, onClick }: RsvpCtaProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "inline-flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "none",
        border: "none",
        color: "var(--color-gold-light)",
        cursor: "pointer",
        padding: "0.8rem 1.4rem",
        borderRadius: "8px",
        outline: "none",
        transition: "all 0.25s ease",
      }}
      onFocus={(e) => {
        e.currentTarget.style.boxShadow = "0 0 0 2px var(--color-gold-border-focus)";
      }}
      onBlur={(e) => {
        e.currentTarget.style.boxShadow = "none";
      }}
      aria-label={`${label} — Desplazarse al formulario de confirmación`}
    >
      <span
        style={{
          fontSize: "0.75rem",
          fontWeight: 600,
          letterSpacing: "0.26em",
          textTransform: "uppercase",
          marginBottom: "0.5rem",
          transition: "letter-spacing 0.2s ease, color 0.2s ease",
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: "1.2rem",
          lineHeight: 1,
          animation: "bounceSoft 2s infinite ease-in-out",
        }}
        aria-hidden="true"
      >
        ↓
      </span>
      <style>{`
        @keyframes bounceSoft {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(5px); }
        }
        @media (prefers-reduced-motion: reduce) {
          span { animation: none !important; }
        }
      `}</style>
    </button>
  );
}
