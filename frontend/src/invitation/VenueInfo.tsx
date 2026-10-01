interface VenueInfoProps {
  venueName: string;
  addressLines: string;
}

export function VenueInfo({ venueName, addressLines }: VenueInfoProps) {
  const lines = addressLines
    ? addressLines.split("\n").filter((line) => line.trim().length > 0)
    : [];

  return (
    <div style={{ textAlign: "center", margin: "1rem 0" }}>
      <h3
        style={{
          fontSize: "0.95rem",
          fontWeight: 600,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: "var(--color-text)",
          marginBottom: "0.4rem",
        }}
      >
        {venueName}
      </h3>
      {lines.map((line) => (
        <p
          key={line}
          style={{
            fontSize: "0.82rem",
            color: "var(--color-text-muted)",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            lineHeight: 1.5,
          }}
        >
          {line}
        </p>
      ))}
    </div>
  );
}
