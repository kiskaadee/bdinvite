import { Button } from "../components/Button";
import { useCountdown } from "../hooks/useCountdown";
import type { RsvpFormState } from "../hooks/useRsvpForm";
import type { InvitationConfig } from "../types/config";
import { Countdown } from "./Countdown";
import { MapPreview } from "./MapPreview";
import { VenueInfo } from "./VenueInfo";

interface RsvpResultProps {
  formState: RsvpFormState;
  confirmedName: string;
  config: InvitationConfig;
  onRetry: () => void;
}

export function RsvpResult({
  formState,
  confirmedName,
  config,
  onRetry,
}: RsvpResultProps) {
  const countdown = useCountdown(
    config.event_date,
    config.event_time,
    config.event_timezone,
  );

  if (formState === "duplicate") {
    return (
      <div
        style={{
          width: "100%",
          maxWidth: "420px",
          margin: "0 auto",
          padding: "2.5rem 1.5rem",
          textAlign: "center",
        }}
        role="alert"
      >
        <h3
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "3.2rem",
            fontWeight: 400,
            color: "var(--color-gold-light)",
            marginBottom: "1rem",
            textShadow: "0 2px 14px rgba(212, 168, 67, 0.3)",
          }}
        >
          ¡Ups!
        </h3>
        <p
          style={{
            fontSize: "0.92rem",
            lineHeight: 1.7,
            color: "var(--color-text-muted)",
            marginBottom: "2rem",
          }}
        >
          {config.msg_duplicate ||
            "Parece que ya tenemos tus datos registrados. Si necesitas modificar tu información, ponte en contacto con nosotros."}
        </p>
        <Button variant="outline" onClick={onRetry}>
          VOLVER AL FORMULARIO
        </Button>
      </div>
    );
  }

  if (formState === "error") {
    return (
      <div
        style={{
          width: "100%",
          maxWidth: "420px",
          margin: "0 auto",
          padding: "2.5rem 1.5rem",
          textAlign: "center",
        }}
        role="alert"
      >
        <h3
          style={{
            fontSize: "1.2rem",
            fontWeight: 600,
            letterSpacing: "0.15em",
            color: "var(--color-error)",
            marginBottom: "1rem",
            textTransform: "uppercase",
          }}
        >
          Algo salió mal
        </h3>
        <p
          style={{
            fontSize: "0.92rem",
            lineHeight: 1.7,
            color: "var(--color-text-muted)",
            marginBottom: "2rem",
          }}
        >
          {config.msg_error ||
            "No pudimos registrar tu asistencia. Inténtalo nuevamente."}
        </p>
        <Button variant="primary" onClick={onRetry}>
          INTENTAR DE NUEVO
        </Button>
      </div>
    );
  }

  // Success Confirmation State
  const greeting = (config.msg_success_greeting || "Gracias, {name}.").replace(
    "{name}",
    confirmedName || "",
  );

  return (
    <div
      style={{
        width: "100%",
        maxWidth: "440px",
        margin: "0 auto",
        padding: "2.5rem 1.5rem 4rem 1.5rem",
        textAlign: "center",
      }}
      aria-live="polite"
    >
      <h3
        style={{
          fontFamily: "var(--font-display)",
          fontSize: "clamp(3.2rem, 10vw, 4rem)",
          fontWeight: 400,
          color: "var(--color-gold-light)",
          lineHeight: 1.15,
          marginBottom: "0.8rem",
          textShadow: "0 2px 20px rgba(212, 168, 67, 0.4)",
        }}
      >
        ¡Perfecto!
      </h3>

      <p
        style={{
          fontSize: "0.92rem",
          fontWeight: 400,
          letterSpacing: "0.12em",
          color: "var(--color-text)",
          lineHeight: 1.6,
          marginBottom: "0.4rem",
        }}
      >
        {config.msg_success || "Tu asistencia ha sido confirmada."}
      </p>

      {confirmedName && (
        <p
          style={{
            fontSize: "1.05rem",
            fontWeight: 600,
            letterSpacing: "0.08em",
            color: "var(--color-gold-light)",
            marginBottom: "2rem",
          }}
        >
          {greeting}
        </p>
      )}

      {/* Decorative divider dot */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: "0.4rem",
          margin: "1.5rem 0",
          color: "var(--color-gold)",
          opacity: 0.5,
          fontSize: "1.2rem",
        }}
        aria-hidden="true"
      >
        <span>·</span>
        <span>·</span>
        <span>·</span>
      </div>

      {/* Live Countdown */}
      <Countdown
        days={countdown.days}
        hours={countdown.hours}
        minutes={countdown.minutes}
        seconds={countdown.seconds}
        state={countdown.state}
        label={config.countdown_label}
        inProgressLabel={config.countdown_in_progress}
        finishedLabel={config.countdown_finished}
      />

      {/* Decorative divider dot */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: "0.4rem",
          margin: "1.5rem 0",
          color: "var(--color-gold)",
          opacity: 0.5,
          fontSize: "1.2rem",
        }}
        aria-hidden="true"
      >
        <span>·</span>
        <span>·</span>
        <span>·</span>
      </div>

      {/* Circular Map Preview and Venue Logistics */}
      <MapPreview
        previewUrl={config.map_preview_url}
        mapUrl={config.map_url}
        venueName={config.address_name}
      />

      <VenueInfo venueName={config.address_name} addressLines={config.address_lines} />
    </div>
  );
}
