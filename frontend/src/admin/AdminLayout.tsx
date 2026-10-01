import { Link, NavLink, Outlet } from "react-router-dom";

export function AdminLayout() {
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
