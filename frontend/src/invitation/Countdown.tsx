import type { CountdownState } from "../hooks/useCountdown";

interface CountdownProps {
  days: string;
  hours: string;
  minutes: string;
  seconds: string;
  state: CountdownState;
  label?: string;
  inProgressLabel?: string;
  finishedLabel?: string;
}

export function Countdown({
  days,
  hours,
  minutes,
  seconds,
  state,
  label = "NOS VEMOS EN",
  inProgressLabel = "EVENTO EN CURSO",
  finishedLabel = "EVENTO FINALIZADO",
}: CountdownProps) {
  if (state === "in_progress") {
    return (
      <div style={{ textAlign: "center", margin: "1.8rem 0" }}>
        <p
          style={{
            fontSize: "1.1rem",
            fontWeight: 600,
            letterSpacing: "0.2em",
            color: "var(--color-gold-light)",
            textTransform: "uppercase",
          }}
        >
          {inProgressLabel}
        </p>
      </div>
    );
  }

  if (state === "finished") {
    return (
      <div style={{ textAlign: "center", margin: "1.8rem 0" }}>
        <p
          style={{
            fontSize: "0.95rem",
            fontWeight: 500,
            letterSpacing: "0.18em",
            color: "var(--color-text-dim)",
            textTransform: "uppercase",
          }}
        >
          {finishedLabel}
        </p>
      </div>
    );
  }

  return (
    <div style={{ textAlign: "center", margin: "1.8rem 0" }}>
      <p
        style={{
          fontSize: "0.78rem",
          fontWeight: 600,
          letterSpacing: "0.25em",
          color: "var(--color-gold-light)",
          textTransform: "uppercase",
          marginBottom: "0.75rem",
        }}
      >
        {label}
      </p>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "0.6rem",
          fontSize: "1.8rem",
          fontWeight: 300,
          letterSpacing: "0.08em",
          fontVariantNumeric: "tabular-nums",
          color: "var(--color-text)",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <span>{days}</span>
          <span
            style={{
              display: "block",
              fontSize: "0.58rem",
              letterSpacing: "0.15em",
              color: "var(--color-text-dim)",
              marginTop: "0.2rem",
            }}
          >
            DÍAS
          </span>
        </div>
        <span style={{ color: "var(--color-gold)", opacity: 0.7, marginTop: "-0.8rem" }}>
          :
        </span>
        <div style={{ textAlign: "center" }}>
          <span>{hours}</span>
          <span
            style={{
              display: "block",
              fontSize: "0.58rem",
              letterSpacing: "0.15em",
              color: "var(--color-text-dim)",
              marginTop: "0.2rem",
            }}
          >
            HORAS
          </span>
        </div>
        <span style={{ color: "var(--color-gold)", opacity: 0.7, marginTop: "-0.8rem" }}>
          :
        </span>
        <div style={{ textAlign: "center" }}>
          <span>{minutes}</span>
          <span
            style={{
              display: "block",
              fontSize: "0.58rem",
              letterSpacing: "0.15em",
              color: "var(--color-text-dim)",
              marginTop: "0.2rem",
            }}
          >
            MIN
          </span>
        </div>
        <span style={{ color: "var(--color-gold)", opacity: 0.7, marginTop: "-0.8rem" }}>
          :
        </span>
        <div style={{ textAlign: "center" }}>
          <span>{seconds}</span>
          <span
            style={{
              display: "block",
              fontSize: "0.58rem",
              letterSpacing: "0.15em",
              color: "var(--color-text-dim)",
              marginTop: "0.2rem",
            }}
          >
            SEG
          </span>
        </div>
      </div>
    </div>
  );
}
