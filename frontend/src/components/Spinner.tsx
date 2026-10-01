export function Spinner({ size = 24 }: { size?: number }) {
  return (
    <div
      style={{
        display: "inline-block",
        width: size,
        height: size,
        border: "2px solid rgba(212, 168, 67, 0.25)",
        borderTopColor: "var(--color-gold)",
        borderRadius: "50%",
        animation: "spin 0.8s linear infinite",
      }}
      aria-label="Cargando..."
      role="status"
    >
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
