import { useCallback, useEffect, useState } from "react";
import {
  deleteAdminRsvp,
  fetchAdminRsvps,
  getExportCsvUrl,
  updateAdminRsvp,
} from "../api/client";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";
import type { RSVPAdminItem } from "../types/config";

export function RsvpTable() {
  const [rsvps, setRsvps] = useState<RSVPAdminItem[]>([]);
  const [count, setCount] = useState<number>(0);
  const [search, setSearch] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<{ name: string; phone: string; email: string }>({
    name: "",
    phone: "",
    email: "",
  });
  const [savingId, setSavingId] = useState<number | null>(null);
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

  async function handleDelete(id: number, name: string) {
    const confirmed = window.confirm(
      `¿Estás seguro de que deseas eliminar la confirmación de "${name}"? Esta acción no se puede deshacer.`,
    );
    if (!confirmed) return;

    setDeletingId(id);
    setError(null);
    try {
      await deleteAdminRsvp(id);
      setRsvps((prev) => prev.filter((r) => r.id !== id));
      setCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error al eliminar el asistente.",
      );
    } finally {
      setDeletingId(null);
    }
  }

  function startEditing(row: RSVPAdminItem) {
    setEditingId(row.id);
    setEditForm({
      name: row.name,
      phone: row.phone,
      email: row.email || "",
    });
    setError(null);
  }

  function cancelEditing() {
    setEditingId(null);
    setError(null);
  }

  async function handleSaveEdit(id: number) {
    if (!editForm.name.trim()) {
      setError("El nombre no puede estar vacío.");
      return;
    }
    if (!editForm.phone.trim()) {
      setError("El teléfono no puede estar vacío.");
      return;
    }

    setSavingId(id);
    setError(null);
    try {
      const updated = await updateAdminRsvp(id, {
        name: editForm.name.trim(),
        phone: editForm.phone.trim(),
        email: editForm.email.trim() || null,
      });
      setRsvps((prev) => prev.map((r) => (r.id === id ? updated : r)));
      setEditingId(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error al actualizar el asistente.",
      );
    } finally {
      setSavingId(null);
    }
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
              <th style={{ padding: "0.9rem 1.2rem", textAlign: "right" }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} style={{ padding: "3rem", textAlign: "center" }}>
                  <Spinner size={28} />
                </td>
              </tr>
            ) : rsvps.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
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
                    backgroundColor:
                      editingId === row.id
                        ? "rgba(212, 168, 67, 0.08)"
                        : "transparent",
                    transition: "background-color 0.15s ease",
                  }}
                  onMouseEnter={(e) => {
                    if (editingId !== row.id) {
                      e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.04)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (editingId !== row.id) {
                      e.currentTarget.style.backgroundColor = "transparent";
                    }
                  }}
                >
                  <td
                    style={{
                      padding: editingId === row.id ? "0.5rem 0.8rem" : "0.9rem 1.2rem",
                      fontWeight: 500,
                      color: "#ffffff",
                    }}
                  >
                    {editingId === row.id ? (
                      <input
                        type="text"
                        value={editForm.name}
                        onChange={(e) =>
                          setEditForm((prev) => ({ ...prev, name: e.target.value }))
                        }
                        disabled={savingId === row.id}
                        placeholder="Nombre completo"
                        style={{
                          width: "100%",
                          minWidth: "120px",
                          backgroundColor: "rgba(0, 0, 0, 0.5)",
                          border: "1px solid var(--color-gold)",
                          borderRadius: "4px",
                          color: "#ffffff",
                          padding: "0.4rem 0.6rem",
                          fontSize: "0.85rem",
                          boxSizing: "border-box",
                        }}
                      />
                    ) : (
                      row.name
                    )}
                  </td>
                  <td
                    style={{
                      padding: editingId === row.id ? "0.5rem 0.8rem" : "0.9rem 1.2rem",
                      color: "var(--color-gold-light)",
                    }}
                  >
                    {editingId === row.id ? (
                      <input
                        type="tel"
                        value={editForm.phone}
                        onChange={(e) =>
                          setEditForm((prev) => ({ ...prev, phone: e.target.value }))
                        }
                        disabled={savingId === row.id}
                        placeholder="300 123 4567"
                        style={{
                          width: "100%",
                          minWidth: "110px",
                          backgroundColor: "rgba(0, 0, 0, 0.5)",
                          border: "1px solid var(--color-gold)",
                          borderRadius: "4px",
                          color: "var(--color-gold-light)",
                          padding: "0.4rem 0.6rem",
                          fontSize: "0.85rem",
                          boxSizing: "border-box",
                        }}
                      />
                    ) : (
                      formatPhone(row.phone)
                    )}
                  </td>
                  <td
                    style={{
                      padding: editingId === row.id ? "0.5rem 0.8rem" : "0.9rem 1.2rem",
                      color: "rgba(255, 255, 255, 0.7)",
                    }}
                  >
                    {editingId === row.id ? (
                      <input
                        type="email"
                        value={editForm.email}
                        onChange={(e) =>
                          setEditForm((prev) => ({ ...prev, email: e.target.value }))
                        }
                        disabled={savingId === row.id}
                        placeholder="Opcional"
                        style={{
                          width: "100%",
                          minWidth: "120px",
                          backgroundColor: "rgba(0, 0, 0, 0.5)",
                          border: "1px solid var(--color-gold)",
                          borderRadius: "4px",
                          color: "rgba(255, 255, 255, 0.9)",
                          padding: "0.4rem 0.6rem",
                          fontSize: "0.85rem",
                          boxSizing: "border-box",
                        }}
                      />
                    ) : (
                      row.email || "—"
                    )}
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
                  <td style={{ padding: "0.9rem 1.2rem", textAlign: "right", whiteSpace: "nowrap" }}>
                    {editingId === row.id ? (
                      <div style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
                        <button
                          type="button"
                          disabled={savingId === row.id}
                          onClick={() => handleSaveEdit(row.id)}
                          style={{
                            background: "rgba(76, 175, 80, 0.15)",
                            border: "1px solid rgba(76, 175, 80, 0.4)",
                            borderRadius: "4px",
                            color: "#81c784",
                            padding: "0.45rem 0.65rem",
                            cursor: savingId === row.id ? "not-allowed" : "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            transition: "all 0.15s ease",
                            outline: "none",
                          }}
                          onMouseEnter={(e) => {
                            if (savingId !== row.id) {
                              e.currentTarget.style.backgroundColor = "rgba(76, 175, 80, 0.3)";
                              e.currentTarget.style.borderColor = "#81c784";
                            }
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = "rgba(76, 175, 80, 0.15)";
                            e.currentTarget.style.borderColor = "rgba(76, 175, 80, 0.4)";
                          }}
                          title="Guardar cambios"
                          aria-label="Guardar cambios"
                        >
                          {savingId === row.id ? (
                            <Spinner size={14} />
                          ) : (
                            <svg
                              width="15"
                              height="15"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2.5"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              role="img"
                              aria-label="Guardar"
                            >
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                          )}
                        </button>
                        <button
                          type="button"
                          disabled={savingId === row.id}
                          onClick={cancelEditing}
                          style={{
                            background: "rgba(255, 255, 255, 0.08)",
                            border: "1px solid rgba(255, 255, 255, 0.2)",
                            borderRadius: "4px",
                            color: "rgba(255, 255, 255, 0.7)",
                            padding: "0.45rem 0.65rem",
                            cursor: savingId === row.id ? "not-allowed" : "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            transition: "all 0.15s ease",
                            outline: "none",
                          }}
                          onMouseEnter={(e) => {
                            if (savingId !== row.id) {
                              e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.18)";
                              e.currentTarget.style.color = "#ffffff";
                            }
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.08)";
                            e.currentTarget.style.color = "rgba(255, 255, 255, 0.7)";
                          }}
                          title="Cancelar edición"
                          aria-label="Cancelar edición"
                        >
                          <svg
                            width="15"
                            height="15"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            role="img"
                            aria-label="Cancelar"
                          >
                            <line x1="18" y1="6" x2="6" y2="18" />
                            <line x1="6" y1="6" x2="18" y2="18" />
                          </svg>
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
                        <button
                          type="button"
                          disabled={deletingId === row.id || editingId !== null}
                          onClick={() => startEditing(row)}
                          style={{
                            background: "rgba(212, 168, 67, 0.1)",
                            border: "1px solid rgba(212, 168, 67, 0.35)",
                            borderRadius: "4px",
                            color: "var(--color-gold)",
                            padding: "0.45rem 0.65rem",
                            cursor:
                              deletingId === row.id || editingId !== null ? "not-allowed" : "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            transition: "all 0.15s ease",
                            outline: "none",
                            opacity: editingId !== null && editingId !== row.id ? 0.35 : 1,
                          }}
                          onMouseEnter={(e) => {
                            if (deletingId !== row.id && editingId === null) {
                              e.currentTarget.style.backgroundColor = "rgba(212, 168, 67, 0.25)";
                              e.currentTarget.style.borderColor = "var(--color-gold-light)";
                            }
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = "rgba(212, 168, 67, 0.1)";
                            e.currentTarget.style.borderColor = "rgba(212, 168, 67, 0.35)";
                          }}
                          title={`Editar confirmación de ${row.name}`}
                          aria-label={`Editar confirmación de ${row.name}`}
                        >
                          <svg
                            width="15"
                            height="15"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            role="img"
                            aria-label="Editar"
                          >
                            <path d="M12 20h9" />
                            <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                          </svg>
                        </button>
                        <button
                          type="button"
                          disabled={deletingId === row.id || editingId !== null}
                          onClick={() => handleDelete(row.id, row.name)}
                          style={{
                            background: "rgba(255, 82, 82, 0.1)",
                            border: "1px solid rgba(255, 82, 82, 0.35)",
                            borderRadius: "4px",
                            color: "#ff5252",
                            padding: "0.45rem 0.65rem",
                            cursor:
                              deletingId === row.id || editingId !== null ? "not-allowed" : "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            transition: "all 0.15s ease",
                            outline: "none",
                            opacity: editingId !== null && editingId !== row.id ? 0.35 : 1,
                          }}
                          onMouseEnter={(e) => {
                            if (deletingId !== row.id && editingId === null) {
                              e.currentTarget.style.backgroundColor = "rgba(255, 82, 82, 0.25)";
                              e.currentTarget.style.borderColor = "#ff5252";
                            }
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = "rgba(255, 82, 82, 0.1)";
                            e.currentTarget.style.borderColor = "rgba(255, 82, 82, 0.35)";
                          }}
                          title={`Eliminar confirmación de ${row.name}`}
                          aria-label={`Eliminar confirmación de ${row.name}`}
                        >
                          {deletingId === row.id ? (
                            <Spinner size={14} />
                          ) : (
                            <svg
                              width="15"
                              height="15"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              role="img"
                              aria-label="Eliminar"
                            >
                              <polyline points="3 6 5 6 21 6" />
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                              <line x1="10" y1="11" x2="10" y2="17" />
                              <line x1="14" y1="11" x2="14" y2="17" />
                            </svg>
                          )}
                        </button>
                      </div>
                    )}
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
