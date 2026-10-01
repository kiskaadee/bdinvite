import { useRef } from "react";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";
import { useConfig } from "../hooks/useConfig";
import { useRsvpForm } from "../hooks/useRsvpForm";
import { InvitationHero } from "./InvitationHero";
import { ParticleBackground } from "./ParticleBackground";
import { RsvpForm } from "./RsvpForm";
import { RsvpResult } from "./RsvpResult";

export function Invitation() {
  const { config, status, error, reload } = useConfig();
  const rsvpForm = useRsvpForm();
  const rsvpSectionRef = useRef<HTMLDivElement | null>(null);

  function scrollToRsvp() {
    if (rsvpSectionRef.current) {
      rsvpSectionRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }

  // 1. Loading Configuration State
  if (status === "loading") {
    return (
      <main
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "1.2rem",
          backgroundColor: "var(--color-bg)",
        }}
      >
        <Spinner size={36} />
        <p
          style={{
            fontSize: "0.82rem",
            letterSpacing: "0.2em",
            color: "var(--color-text-muted)",
            textTransform: "uppercase",
          }}
        >
          Cargando invitación...
        </p>
      </main>
    );
  }

  // 2. Configuration Error State
  if (status === "error" || !config) {
    return (
      <main
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "2rem",
          textAlign: "center",
          backgroundColor: "var(--color-bg)",
        }}
      >
        <h2
          style={{
            fontSize: "1.3rem",
            fontWeight: 600,
            letterSpacing: "0.15em",
            color: "var(--color-gold-light)",
            textTransform: "uppercase",
            marginBottom: "1rem",
          }}
        >
          No pudimos cargar la invitación
        </h2>
        <p
          style={{
            fontSize: "0.92rem",
            color: "var(--color-text-muted)",
            marginBottom: "2rem",
            maxWidth: "360px",
            lineHeight: 1.6,
          }}
        >
          {error || "Por favor, verifica tu conexión e inténtalo nuevamente."}
        </p>
        <Button variant="primary" onClick={reload}>
          REINTENTAR
        </Button>
      </main>
    );
  }

  // 3. Loaded Invitation Page Flow
  return (
    <div style={{ position: "relative", minHeight: "100vh" }}>
      {/* Background ambient particle canvas */}
      <ParticleBackground />

      <main
        style={{
          position: "relative",
          zIndex: 1,
          width: "100%",
          maxWidth: "480px",
          margin: "0 auto",
          boxShadow: "0 0 50px rgba(0, 0, 0, 0.8)",
          backgroundColor: "rgba(10, 10, 10, 0.85)",
          backdropFilter: "blur(2px)",
        }}
      >
        {/* Section 1: Invitation Hero */}
        <InvitationHero config={config} onCtaClick={scrollToRsvp} />

        {/* Section 2: RSVP / Confirmation Flow */}
        <div
          id="rsvp-section"
          ref={rsvpSectionRef}
          style={{
            minHeight: "80vh",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "2.5rem 1.8rem 4rem 1.8rem",
            borderTop: "1px solid var(--color-gold-border)",
            position: "relative",
          }}
        >
          {rsvpForm.formState === "idle" || rsvpForm.formState === "submitting" ? (
            <RsvpForm
              config={config}
              name={rsvpForm.name}
              setName={rsvpForm.setName}
              phone={rsvpForm.phone}
              setPhone={rsvpForm.setPhone}
              email={rsvpForm.email}
              setEmail={rsvpForm.setEmail}
              formState={rsvpForm.formState}
              errors={rsvpForm.errors}
              onSubmit={rsvpForm.submit}
            />
          ) : (
            <RsvpResult
              formState={rsvpForm.formState}
              confirmedName={rsvpForm.confirmedName}
              config={config}
              onRetry={rsvpForm.retry}
            />
          )}
        </div>
      </main>
    </div>
  );
}
