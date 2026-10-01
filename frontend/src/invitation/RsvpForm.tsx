import type { FormEvent } from "react";
import { Button } from "../components/Button";
import { Field } from "../components/Field";
import { Spinner } from "../components/Spinner";
import type { FormErrors, RsvpFormState } from "../hooks/useRsvpForm";
import type { InvitationConfig } from "../types/config";

interface RsvpFormProps {
  config: InvitationConfig;
  name: string;
  setName: (v: string) => void;
  phone: string;
  setPhone: (v: string) => void;
  email: string;
  setEmail: (v: string) => void;
  formState: RsvpFormState;
  errors: FormErrors;
  onSubmit: () => void;
  onShowDetails?: () => void;
}

export function RsvpForm({
  config,
  name,
  setName,
  phone,
  setPhone,
  email,
  setEmail,
  formState,
  errors,
  onSubmit,
  onShowDetails,
}: RsvpFormProps) {
  const isSubmitting = formState === "submitting";

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!isSubmitting) {
      onSubmit();
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        width: "100%",
        maxWidth: "400px",
        margin: "0 auto",
        padding: "1.5rem 0",
      }}
      noValidate
    >
      <h3
        style={{
          fontFamily: "var(--font-display)",
          fontSize: "2.8rem",
          fontWeight: 400,
          color: "var(--color-gold-light)",
          textAlign: "center",
          marginBottom: "2rem",
          textShadow: "0 2px 14px rgba(212, 168, 67, 0.3)",
        }}
      >
        {config.rsvp_heading || "¿Nos vemos?"}
      </h3>

      <Field
        label="Nombre Completo"
        placeholder="Tu nombre y apellido"
        value={name}
        onChange={(e) => setName(e.target.value)}
        disabled={isSubmitting}
        error={errors.name}
        required
      />

      <Field
        label="Teléfono (Móvil)"
        placeholder="300 123 4567"
        type="tel"
        value={phone}
        onChange={(e) => setPhone(e.target.value)}
        disabled={isSubmitting}
        hint="Número colombiano de 10 dígitos (ej: 300 123 4567)"
        error={errors.phone}
        required
      />

      <Field
        label="Correo Electrónico (Opcional)"
        placeholder="ejemplo@correo.com"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        disabled={isSubmitting}
        error={errors.email}
      />

      <div style={{ marginTop: "2rem", textAlign: "center" }}>
        <Button type="submit" variant="primary" fullWidth disabled={isSubmitting}>
          {isSubmitting ? (
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.6rem" }}>
              <Spinner size={16} />
              <span>ENVIANDO...</span>
            </span>
          ) : (
            config.submit_label || "TE VEO AHÍ"
          )}
        </Button>

        {onShowDetails && (
          <div style={{ marginTop: "1.4rem" }}>
            <button
              type="button"
              onClick={onShowDetails}
              style={{
                background: "none",
                border: "none",
                color: "var(--color-gold)",
                fontSize: "0.78rem",
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                cursor: "pointer",
                padding: "0.4rem 0.8rem",
                borderRadius: "4px",
                textDecoration: "underline",
                textUnderlineOffset: "4px",
                opacity: 0.85,
                transition: "opacity 0.2s ease, color 0.2s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.opacity = "1";
                e.currentTarget.style.color = "var(--color-gold-light)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.opacity = "0.85";
                e.currentTarget.style.color = "var(--color-gold)";
              }}
            >
              ¿Ya confirmaste? Ver ubicación y mapa ↓
            </button>
          </div>
        )}
      </div>
    </form>
  );
}
