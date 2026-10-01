import { type FormEvent, useEffect, useState } from "react";
import { fetchAdminConfig, updateAdminConfig } from "../api/client";
import { Button } from "../components/Button";
import { Field } from "../components/Field";
import { Spinner } from "../components/Spinner";
import type { InvitationConfig } from "../types/config";

export function ConfigEditor() {
  const [formData, setFormData] = useState<InvitationConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchAdminConfig();
        setFormData(data);
      } catch (err) {
        setFeedback({
          type: "error",
          msg: err instanceof Error ? err.message : "Error al cargar la configuración.",
        });
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  function handleChange(field: keyof InvitationConfig, value: string) {
    if (!formData) return;
    setFormData({ ...formData, [field]: value });
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!formData || saving) return;

    setSaving(true);
    setFeedback(null);

    try {
      const { id, updated_at, ...cleanPayload } = formData;
      const updated = await updateAdminConfig(cleanPayload);
      setFormData(updated);
      setFeedback({ type: "success", msg: "¡Configuración guardada exitosamente!" });
    } catch (err) {
      setFeedback({
        type: "error",
        msg: err instanceof Error ? err.message : "Error al guardar.",
      });
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div style={{ padding: "4rem", textAlign: "center" }}>
        <Spinner size={32} />
      </div>
    );
  }

  if (!formData) {
    return (
      <div style={{ color: "var(--color-error)", padding: "2rem" }}>
        {feedback?.msg || "No se pudo cargar la configuración."}
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "2.5rem" }}>
      <div>
        <h2
          style={{
            fontSize: "1.4rem",
            fontWeight: 600,
            color: "#ffffff",
            marginBottom: "0.4rem",
          }}
        >
          Editar Contenido de la Invitación
        </h2>
        <p
          style={{
            fontSize: "0.88rem",
            color: "rgba(255, 255, 255, 0.6)",
            marginBottom: "1.8rem",
          }}
        >
          Los cambios guardados se reflejan inmediatamente en la invitación pública.
        </p>

        {feedback && (
          <div
            style={{
              padding: "0.9rem 1.2rem",
              borderRadius: "4px",
              marginBottom: "1.8rem",
              backgroundColor:
                feedback.type === "success"
                  ? "rgba(46, 204, 113, 0.15)"
                  : "var(--color-error-bg)",
              border: `1px solid ${feedback.type === "success" ? "#2ecc71" : "var(--color-error)"}`,
              color: feedback.type === "success" ? "#2ecc71" : "#ff8b80",
              fontSize: "0.88rem",
            }}
          >
            {feedback.msg}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: "1rem",
            }}
          >
            <Field
              label="Título Principal"
              value={formData.title}
              onChange={(e) => handleChange("title", e.target.value)}
              required
            />
            <Field
              label="Nombre del Homenajeado(a)"
              value={formData.honoree_name}
              onChange={(e) => handleChange("honoree_name", e.target.value)}
              required
            />
          </div>

          <Field
            label="Texto de Invitación"
            value={formData.invitation_text}
            onChange={(e) => handleChange("invitation_text", e.target.value)}
            required
          />

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "1rem",
            }}
          >
            <Field
              label="Fecha del Evento (YYYY-MM-DD)"
              value={formData.event_date}
              onChange={(e) => handleChange("event_date", e.target.value)}
              required
            />
            <Field
              label="Hora del Evento (HH:MM)"
              value={formData.event_time}
              onChange={(e) => handleChange("event_time", e.target.value)}
              required
            />
            <Field
              label="Zona Horaria IANA"
              value={formData.event_timezone}
              onChange={(e) => handleChange("event_timezone", e.target.value)}
              required
            />
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: "1rem",
            }}
          >
            <Field
              label="Nombre del Lugar"
              value={formData.address_name}
              onChange={(e) => handleChange("address_name", e.target.value)}
              required
            />
            <Field
              label="Enlace a Google Maps (map_url)"
              value={formData.map_url}
              onChange={(e) => handleChange("map_url", e.target.value)}
              required
            />
          </div>

          <div style={{ marginBottom: "1.4rem" }}>
            <label
              htmlFor="address_lines"
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
              Dirección (una línea por renglón)
            </label>
            <textarea
              id="address_lines"
              rows={3}
              value={formData.address_lines}
              onChange={(e) => handleChange("address_lines", e.target.value)}
              style={{
                width: "100%",
                padding: "0.85rem 1rem",
                backgroundColor: "rgba(255, 255, 255, 0.05)",
                border: "1px solid var(--color-gold-border)",
                borderRadius: "4px",
                color: "var(--color-text)",
                fontSize: "0.95rem",
                outline: "none",
              }}
            />
          </div>

          <Field
            label="URL de Imagen Previa del Mapa (map_preview_url)"
            value={formData.map_preview_url}
            onChange={(e) => handleChange("map_preview_url", e.target.value)}
            required
          />

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "1rem",
            }}
          >
            <Field
              label="Encabezado del Formulario"
              value={formData.rsvp_heading}
              onChange={(e) => handleChange("rsvp_heading", e.target.value)}
              required
            />
            <Field
              label="Texto del Botón CTA Inicial"
              value={formData.rsvp_cta}
              onChange={(e) => handleChange("rsvp_cta", e.target.value)}
              required
            />
            <Field
              label="Texto del Botón de Envío"
              value={formData.submit_label}
              onChange={(e) => handleChange("submit_label", e.target.value)}
              required
            />
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
              gap: "1rem",
            }}
          >
            <Field
              label="Mensaje de Confirmación Éxito"
              value={formData.msg_success}
              onChange={(e) => handleChange("msg_success", e.target.value)}
              required
            />
            <Field
              label="Saludo de Éxito ({name})"
              value={formData.msg_success_greeting}
              onChange={(e) => handleChange("msg_success_greeting", e.target.value)}
              required
            />
          </div>

          <Field
            label="Mensaje para Teléfono Duplicado"
            value={formData.msg_duplicate}
            onChange={(e) => handleChange("msg_duplicate", e.target.value)}
            required
          />

          <div style={{ marginTop: "2rem" }}>
            <Button type="submit" variant="primary" disabled={saving}>
              {saving ? "Guardando..." : "Guardar Cambios"}
            </Button>
          </div>
        </form>
      </div>

      {/* Live Plain-Text Preview Section */}
      <div
        style={{
          borderTop: "1px solid rgba(255, 255, 255, 0.1)",
          paddingTop: "2rem",
        }}
      >
        <h3
          style={{
            fontSize: "1.1rem",
            fontWeight: 600,
            color: "var(--color-gold-light)",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            marginBottom: "1rem",
          }}
        >
          Vista Previa de Composición (Texto)
        </h3>
        <div
          style={{
            backgroundColor: "#161618",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "6px",
            padding: "1.8rem",
            lineHeight: 1.8,
            fontSize: "0.92rem",
            maxWidth: "500px",
          }}
        >
          <p style={{ fontSize: "1.5rem", fontWeight: 700, color: "#ffffff" }}>
            {formData.title}
          </p>
          <p
            style={{
              letterSpacing: "0.15em",
              textTransform: "uppercase",
              color: "rgba(255, 255, 255, 0.6)",
            }}
          >
            {formData.invitation_text}
          </p>
          <p
            style={{
              fontSize: "1.3rem",
              color: "var(--color-gold-light)",
              margin: "0.6rem 0",
            }}
          >
            {formData.honoree_name}
          </p>
          <p style={{ color: "#ffffff" }}>
            📅 {formData.event_date} · ⏰ {formData.event_time} ({formData.event_timezone}
            )
          </p>
          <p style={{ color: "#ffffff", marginTop: "0.4rem" }}>
            📍 {formData.address_name} — {formData.address_lines.replace(/\n/g, ", ")}
          </p>
          <div
            style={{
              marginTop: "1rem",
              paddingTop: "0.8rem",
              borderTop: "1px dashed rgba(255, 255, 255, 0.15)",
            }}
          >
            <p style={{ color: "var(--color-gold)" }}>CTA: {formData.rsvp_cta}</p>
            <p style={{ color: "var(--color-text-dim)", fontSize: "0.82rem" }}>
              Éxito: "{formData.msg_success}"{" "}
              {formData.msg_success_greeting.replace("{name}", "[Nombre]")}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
