import { useEffect, useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { type CurrentUser, fetchCurrentUser, logoutUser } from "../api/client";
import { Spinner } from "../components/Spinner";

export function AdminLayout() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;
    fetchCurrentUser()
      .then((userData) => {
        if (isMounted) {
          setUser(userData);
          setLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          setLoading(false);
          window.location.href = "/birthday/api/auth/login";
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleLogout = async () => {
    try {
      await logoutUser();
    } catch (err) {
      console.error("Logout failed:", err);
    }
    setUser(null);
    window.location.href = "/birthday/api/auth/login";
  };

  if (loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          backgroundColor: "#0f0f10",
          color: "#f0f0f0",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Spinner size={36} />
      </div>
    );
  }

  if (!user) {
    return (
      <div
        style={{
          minHeight: "100vh",
          backgroundColor: "#0f0f10",
          color: "#f0f0f0",
          fontFamily: "var(--font-body)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "1rem",
        }}
      >
        <p>No autenticado. Redirigiendo al inicio de sesión...</p>
        <a
          href="/birthday/api/auth/login"
          style={{
            color: "var(--color-gold-light, #e0be75)",
            textDecoration: "underline",
          }}
        >
          Iniciar sesión
        </a>
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#0f0f10",
        color: "#f0f0f0",
        fontFamily: "var(--font-body)",
      }}
    >
      {/* Admin Navigation Bar */}
      <header
        style={{
          borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
          backgroundColor: "#161618",
          padding: "1rem 1.8rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.8rem" }}>
          <span style={{ fontSize: "1.4rem" }}>🎂</span>
          <h1
            style={{
              fontSize: "1.1rem",
              fontWeight: 600,
              letterSpacing: "0.08em",
              color: "#ffffff",
              textTransform: "uppercase",
            }}
          >
            Panel de Control · Invitación
          </h1>
        </div>

        <nav style={{ display: "flex", alignItems: "center", gap: "1.4rem" }}>
          <NavLink
            to="/admin"
            end
            style={({ isActive }) => ({
              color: isActive ? "var(--color-gold-light)" : "rgba(255, 255, 255, 0.7)",
              textDecoration: "none",
              fontSize: "0.88rem",
              fontWeight: 500,
              borderBottom: isActive
                ? "2px solid var(--color-gold)"
                : "2px solid transparent",
              paddingBottom: "0.25rem",
              transition: "all 0.2s ease",
            })}
          >
            Respuestas
          </NavLink>
          <NavLink
            to="/admin/config"
            style={({ isActive }) => ({
              color: isActive ? "var(--color-gold-light)" : "rgba(255, 255, 255, 0.7)",
              textDecoration: "none",
              fontSize: "0.88rem",
              fontWeight: 500,
              borderBottom: isActive
                ? "2px solid var(--color-gold)"
                : "2px solid transparent",
              paddingBottom: "0.25rem",
              transition: "all 0.2s ease",
            })}
          >
            Configuración
          </NavLink>
          <Link
            to="/"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: "rgba(255, 255, 255, 0.5)",
              textDecoration: "none",
              fontSize: "0.82rem",
              display: "inline-flex",
              alignItems: "center",
              gap: "0.3rem",
            }}
          >
            <span>Ver Pública</span>
            <span>↗</span>
          </Link>
        </nav>

        {/* User Info and Logout Button */}
        <div style={{ display: "flex", alignItems: "center", gap: "1.2rem", flexWrap: "wrap" }}>
          <div
            style={{
              fontSize: "0.85rem",
              color: "rgba(255, 255, 255, 0.8)",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            <span style={{ color: "var(--color-gold, #c5a059)" }}>👤</span>
            <span data-testid="user-info">{user.name || user.email}</span>
            {user.name && user.email && user.name !== user.email && (
              <span
                data-testid="user-email"
                style={{ fontSize: "0.8rem", color: "rgba(255, 255, 255, 0.5)" }}
              >
                ({user.email})
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={handleLogout}
            style={{
              background: "transparent",
              border: "1px solid rgba(255, 255, 255, 0.2)",
              color: "#f0f0f0",
              padding: "0.35rem 0.75rem",
              borderRadius: "4px",
              cursor: "pointer",
              fontSize: "0.82rem",
              fontWeight: 500,
              transition: "all 0.2s ease",
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.4)";
              e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.05)";
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.2)";
              e.currentTarget.style.backgroundColor = "transparent";
            }}
          >
            Logout
          </button>
        </div>
      </header>

      {/* Main Admin Content Container */}
      <div
        style={{
          maxWidth: "1000px",
          margin: "0 auto",
          padding: "2rem 1.5rem",
        }}
      >
        <Outlet />
      </div>
    </div>
  );
}

