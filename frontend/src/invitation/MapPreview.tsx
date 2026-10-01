import { useState } from "react";

interface MapPreviewProps {
  previewUrl: string;
  mapUrl: string;
  venueName: string;
}

export function MapPreview({ previewUrl, mapUrl, venueName }: MapPreviewProps) {
  const [imgError, setImgError] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div style={{ textAlign: "center", margin: "1.6rem 0" }}>
      <a
        href={mapUrl}
        target="_blank"
        rel="noopener noreferrer"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        onFocus={() => setIsHovered(true)}
        onBlur={() => setIsHovered(false)}
        style={{
          display: "inline-block",
          textDecoration: "none",
          color: "inherit",
          outline: "none",
        }}
        aria-label={`Ver ubicación de ${venueName} en Google Maps`}
      >
        <div
          style={{
            width: "140px",
            height: "140px",
            margin: "0 auto",
            borderRadius: "50%",
            overflow: "hidden",
            border: `1.5px solid ${isHovered ? "var(--color-gold-border-focus)" : "var(--color-gold-border)"}`,
            boxShadow: isHovered
              ? "0 6px 24px rgba(0, 0, 0, 0.7), 0 0 20px rgba(212, 168, 67, 0.3)"
              : "0 4px 20px rgba(0, 0, 0, 0.5), 0 0 15px rgba(212, 168, 67, 0.15)",
            transform: isHovered ? "scale(1.06)" : "scale(1)",
            transition:
              "transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease",
            position: "relative",
            backgroundColor: "#1a1a1a",
          }}
        >
          {!imgError && previewUrl ? (
            <img
              src={previewUrl}
              alt={`Mapa de ${venueName}`}
              onError={() => setImgError(true)}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                display: "block",
                filter: "contrast(1.1) brightness(0.9)",
              }}
            />
          ) : (
            <div
              style={{
                width: "100%",
                height: "100%",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--color-gold)",
                backgroundColor: "#151515",
                padding: "0.5rem",
              }}
            >
              <svg
                width="28"
                height="28"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                role="img"
                aria-label="Icono de mapa"
              >
                <title>Icono de mapa</title>
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                <circle cx="12" cy="10" r="3" />
              </svg>
              <span
                style={{
                  fontSize: "0.65rem",
                  letterSpacing: "0.1em",
                  marginTop: "0.3rem",
                  color: "var(--color-text-muted)",
                }}
              >
                MAPA
              </span>
            </div>
          )}
        </div>

        <span
          style={{
            display: "inline-block",
            fontSize: "0.74rem",
            fontWeight: 600,
            letterSpacing: "0.22em",
            color: "var(--color-gold-light)",
            textTransform: "uppercase",
            marginTop: "0.9rem",
            transition: "color 0.2s ease",
          }}
        >
          VER UBICACIÓN ↗
        </span>
      </a>
    </div>
  );
}
