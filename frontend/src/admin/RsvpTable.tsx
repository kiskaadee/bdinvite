import { useCallback, useEffect, useState } from "react";
import { fetchAdminRsvps, getExportCsvUrl } from "../api/client";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";
import type { RSVPAdminItem } from "../types/config";

export function RsvpTable() {
  const [rsvps, setRsvps] = useState<RSVPAdminItem[]>([]);
  const [count, setCount] = useState<number>(0);
  const [search, setSearch] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async (searchTerm = "") => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAdminRsvps(searchTerm);
      setRsvps(data.rsvps);
      setCount(data.count);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar las respuestas.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData(search);
  }, [search, loadData]);

  function formatDate(isoStr: string) {
    if (!isoStr) return "—";
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString("es-CO", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoStr;
    }
  }

  function formatPhone(phone: string) {
    if (phone.length === 10) {
      return `${phone.slice(0, 3)} ${phone.slice(3, 6)} ${phone.slice(6)}`;
    }
    return phone;
  }

  return (
    <div>
      {/* Top action bar: Count, Search, Export */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "1.2rem",
          marginBottom: "1.8rem",
        }}
      >
        <div>
          <h2 style={{ fontSize: "1.4rem", fontWeight: 600, color: "#ffffff" }}>
            Asistentes Confirmados
          </h2>
          <p
            style={{
              fontSize: "0.88rem",
              color: "rgba(255, 255, 255, 0.6)",
              marginTop: "0.2rem",
            }}
          >
            Total de registros:{" "}
            <strong style={{ color: "var(--color-gold-light)" }}>{count}</strong>
          </p>
        </div>

        <div
          style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}
        >
          <input
            type="search"
            placeholder="Buscar por nombre, tel..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              padding: "0.6rem 1rem",
              borderRadius: "4px",
              backgroundColor: "rgba(255, 255, 255, 0.08)",
              border: "1px solid rgba(255, 255, 255, 0.2)",
              color: "#ffffff",
              fontSize: "0.88rem",
              outline: "none",
              minWidth: "220px",
            }}
          />

          <a
            href={getExportCsvUrl()}
            download="rsvps.csv"
            style={{ textDecoration: "none" }}
          >
            <Button
              variant="outline"
              style={{ padding: "0.6rem 1.2rem", fontSize: "0.75rem" }}
            >
              Descargar CSV ⤓
            </Button>
          </a>
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: "1rem",
            backgroundColor: "var(--color-error-bg)",
            border: "1px solid var(--color-error)",
            borderRadius: "4px",
            color: "#ff8b80",
            marginBottom: "1.5rem",
            fontSize: "0.88rem",
          }}
        >
          {error}
        </div>
      )}

      {/* Table container */}
      <div
        style={{
          backgroundColor: "#161618",
          borderRadius: "6px",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          overflowX: "auto",
        }}
      >
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            textAlign: "left",
            fontSize: "0.88rem",
          }}
        >
          <thead>
            <tr
              style={{
                borderBottom: "1px solid rgba(255, 255, 255, 0.12)",
                backgroundColor: "rgba(255, 255, 255, 0.03)",
                color: "rgba(255, 255, 255, 0.6)",
                fontSize: "0.75rem",
                letterSpacing: "0.1em",
                textTransform: "uppercase",
              }}
            >
              <th style={{ padding: "0.9rem 1.2rem" }}>Nombre</th>
              <th style={{ padding: "0.9rem 1.2rem" }}>Teléfono</th>
              <th style={{ padding: "0.9rem 1.2rem" }}>Correo</th>
              <th style={{ padding: "0.9rem 1.2rem" }}>Fecha de Registro</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} style={{ padding: "3rem", textAlign: "center" }}>
                  <Spinner size={28} />
                </td>
              </tr>
            ) : rsvps.length === 0 ? (
              <tr>
                <td
                  colSpan={4}
                  style={{
                    padding: "3rem",
                    textAlign: "center",
                    color: "rgba(255, 255, 255, 0.5)",
                  }}
                >
                  {search
                    ? "No se encontraron coincidencias."
                    : "Aún no hay confirmaciones registradas."}
                </td>
              </tr>
            ) : (
              rsvps.map((row) => (
                <tr
                  key={row.id}
                  style={{
                    borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
                    transition: "background-color 0.15s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.04)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = "transparent";
                  }}
                >
                  <td
                    style={{
                      padding: "0.9rem 1.2rem",
                      fontWeight: 500,
                      color: "#ffffff",
                    }}
                  >
                    {row.name}
                  </td>
                  <td
                    style={{ padding: "0.9rem 1.2rem", color: "var(--color-gold-light)" }}
                  >
                    {formatPhone(row.phone)}
                  </td>
                  <td
                    style={{
                      padding: "0.9rem 1.2rem",
                      color: "rgba(255, 255, 255, 0.7)",
                    }}
                  >
                    {row.email || "—"}
                  </td>
                  <td
                    style={{
                      padding: "0.9rem 1.2rem",
                      color: "rgba(255, 255, 255, 0.5)",
                      fontSize: "0.8rem",
                    }}
                  >
                    {formatDate(row.created_at)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
