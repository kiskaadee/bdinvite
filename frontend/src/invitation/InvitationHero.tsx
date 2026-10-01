import type { InvitationConfig } from "../types/config";
import { RsvpCta } from "./RsvpCta";

interface InvitationHeroProps {
  config: InvitationConfig;
  onCtaClick: () => void;
}

export function InvitationHero({ config, onCtaClick }: InvitationHeroProps) {
  // Parse date into Month, Day, and Day of Week
  const [year, monthNum, dayNum] = config.event_date.split("-").map(Number);
  const dateObj = new Date(year, (monthNum || 1) - 1, dayNum || 1);

  const monthsEs = [
    "ENE",
    "FEB",
    "MAR",
    "ABR",
    "MAY",
    "JUN",
    "JUL",
    "AGO",
    "SEP",
    "OCT",
    "NOV",
    "DIC",
  ];
  const daysEs = [
    "DOMINGO",
    "LUNES",
    "MARTES",
    "MIÉRCOLES",
    "JUEVES",
    "VIERNES",
    "SÁBADO",
  ];

  const monthStr = monthsEs[(monthNum || 1) - 1] || "OCT";
  const dayNameStr = daysEs[dateObj.getDay()] || "VIERNES";
  const dayStr = String(dayNum || 28);

  // Format 24h time to 12h AM/PM if applicable
  const [hStr, mStr] = config.event_time.split(":");
  let formattedTime = config.event_time;
  if (hStr) {
    const h = parseInt(hStr, 10);
    const m = mStr || "00";
    const ampm = h >= 12 ? "PM" : "AM";
    const h12 = h % 12 || 12;
    formattedTime = `${h12}:${m} ${ampm}`;
  }

  return (
    <section
      style={{
        width: "100%",
        maxWidth: "480px",
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "3.5rem 1.8rem 2.5rem 1.8rem",
        textAlign: "center",
        margin: "0 auto",
        position: "relative",
        zIndex: 1,
      }}
    >
      {/* 1. Header: Script Birthday Party */}
      <div style={{ marginTop: "1rem" }}>
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(3.2rem, 12vw, 4.4rem)",
            fontWeight: 400,
            lineHeight: 1.15,
            color: "var(--color-text)",
            textShadow: "0 2px 20px rgba(212, 168, 67, 0.35)",
          }}
        >
          {config.title || "Birthday Party"}
        </h1>
      </div>

      {/* 2. Invitation wording & Honoree name */}
      <div style={{ margin: "2rem 0" }}>
        <p
          style={{
            fontSize: "0.78rem",
            fontWeight: 400,
            letterSpacing: "0.24em",
            textTransform: "uppercase",
            color: "var(--color-text-muted)",
            lineHeight: 1.8,
            maxWidth: "320px",
            margin: "0 auto",
          }}
        >
          {config.invitation_text}
        </p>

        <h2
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(2.6rem, 10vw, 3.6rem)",
            fontWeight: 400,
            color: "var(--color-gold-light)",
            marginTop: "1.4rem",
            textShadow: "0 2px 18px rgba(212, 168, 67, 0.4)",
          }}
        >
          {config.honoree_name}
        </h2>
      </div>

      {/* 3. Event metadata date block */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "1.2rem",
          margin: "1.5rem 0",
          fontSize: "0.88rem",
          letterSpacing: "0.18em",
          color: "var(--color-text)",
          textTransform: "uppercase",
        }}
      >
        <span style={{ fontWeight: 500, minWidth: "75px" }}>{dayNameStr}</span>

        {/* Divider & Day Box */}
        <div
          style={{
            borderLeft: "1px solid rgba(255, 255, 255, 0.25)",
            borderRight: "1px solid rgba(255, 255, 255, 0.25)",
            padding: "0 1.2rem",
            textAlign: "center",
          }}
        >
          <span
            style={{
              display: "block",
              fontSize: "0.68rem",
              letterSpacing: "0.2em",
              color: "var(--color-text-muted)",
              marginBottom: "0.15rem",
            }}
          >
            {monthStr}
          </span>
          <span
            style={{
              display: "block",
              fontSize: "1.7rem",
              fontWeight: 700,
              lineHeight: 1,
              letterSpacing: "0.05em",
            }}
          >
            {dayStr}
          </span>
        </div>

        <span style={{ fontWeight: 500, minWidth: "75px" }}>{formattedTime}</span>
      </div>

      {/* 4. RSVP Call to action */}
      <div style={{ marginBottom: "1rem" }}>
        <RsvpCta label={config.rsvp_cta} onClick={onCtaClick} />
      </div>
    </section>
  );
}
