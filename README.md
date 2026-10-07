# bdinvite

Interactive digital birthday invitation with real-time RSVP management, dynamic OpenStreetMap location previews, and an administrative dashboard.

## Overview

**bdinvite** is a production self-hosted web application delivering two coordinated experiences:

1. **Guest Experience (`/birthday/`)**:
   - Mobile-first vertical composition mimicking a physical luxury invitation card.
   - Ambient golden bokeh particle canvas (Canvas 2D) with accessibility support (`prefers-reduced-motion`).
   - Phone-normalized RSVP submission flow with explicit semantic state feedback (`SUCCESS`, `DUPLICATE`, `ERROR`).
   - Timezone-aware countdown timer (`NOS VEMOS EN DD:HH:MM:SS`).
   - Dynamic OpenStreetMap venue preview tile crop with direct Google Maps navigation links.

2. **Admin Experience (`/birthday/admin`)**:
   - Reverse-proxy authentication boundary via Authelia ForwardAuth (`Remote-User`).
   - Live RSVP roster with search filtering, inline editing, and permanent deletion.
   - Event-timezone formatted registration timestamps.
   - One-click CSV export (`rsvps.csv`).
   - Live configuration editor with hierarchical text preview and on-demand map generation.

- **Guest URL**: `https://demos.roadtotech.me/birthday/`
- **Admin URL**: `https://demos.roadtotech.me/birthday/admin` (Authelia SSO protected)

---

## Architecture & System Design

The application runs as a **single unified container**:
- **Frontend**: React 18 SPA built with Vite, TypeScript, and CSS Modules.
- **Backend**: FastAPI (Python 3.11+) powered by Uvicorn, SQLAlchemy 2.0, and Pydantic v2.
- **Persistence**: SQLite with Write-Ahead Logging (`WAL`) mode mounted on `./data/bdinvite.db`.
- **Static Assets & Routing**: FastAPI serves API routes under `/birthday/api/`, static assets under `/birthday/assets/`, and fallback SPA catch-all routing for React Router.
- **Security Boundary**: Traefik intercepts `/birthday/admin` and `/birthday/api/admin` with Authelia ForwardAuth middleware, injecting `Remote-User`. Every backend admin endpoint independently asserts this header.

```text
                  HTTPS Requests (*.roadtotech.me)
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │     Traefik v3.6      │
                     └───────────┬───────────┘
                                 │
         ┌───────────────────────┴───────────────────────┐
         │                                               │
   Public Routes                                   Admin Routes
 (/birthday, /birthday/api/*)            (/birthday/admin, /birthday/api/admin/*)
         │                                               │
         │                                   ┌───────────▼───────────┐
         │                                   │   Authelia ForwardAuth│
         │                                   └───────────┬───────────┘
         │                                               │ (Injects Remote-User)
         └───────────────────────┬───────────────────────┘
                                 │
                                 ▼
                   ┌───────────────────────────┐
                   │     bdinvite Container    │
                   │                           │
                   │  ┌─────────────────────┐  │
                   │  │ FastAPI + Uvicorn   │  │
                   │  │ (Port 8000)         │  │
                   │  └──────────┬──────────┘  │
                   │             │             │
                   │      ┌──────┴──────┐      │
                   │      ▼             ▼      │
                   │  React SPA     SQLite DB  │
                   │  (static)      (WAL Mode) │
                   └───────────────────────────┘
```

---

## API Summary

All endpoints are prefixed with `/birthday/api/`.

### Public Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/birthday/api/config` | Retrieves the active invitation configuration |
| `POST` | `/birthday/api/rsvp` | Submits an RSVP (validates 10-digit Colombian phone format) |
| `GET` | `/birthday/api/map-preview.png` | Serves stitched OpenStreetMap tile preview image |

### Admin Endpoints (Requires `Remote-User`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/birthday/api/admin/rsvps` | Lists confirmed guests (supports `?search=<term>`) |
| `PATCH` | `/birthday/api/admin/rsvps/{id}` | Updates name, phone, or email for an RSVP record |
| `DELETE` | `/birthday/api/admin/rsvps/{id}` | Permanently deletes an RSVP record (`204 No Content`) |
| `GET` | `/birthday/api/admin/export` | Downloads the guest roster as a formatted CSV |
| `GET` | `/birthday/api/admin/config` | Fetches complete editable configuration |
| `PUT` | `/birthday/api/admin/config` | Updates singleton configuration and triggers map preview update |
| `POST` | `/birthday/api/admin/map-preview/generate` | Generates or regenerates OSM preview tiles from Google Maps URL |

---

## Development & Toolchain

### Prerequisites

- [Nix](https://nixos.org/) with `direnv` (recommended), or:
  - Node.js 20+
  - Python 3.11+
  - [uv](https://docs.astral.sh/uv/)
  - [Biome](https://biomejs.dev/)

If using `direnv`, simply allow the environment in the project root:
```bash
direnv allow
```
Or enter the Nix development shell:
```bash
nix-shell
```

### Backend Setup

```bash
cd backend

# Install dependencies and create virtual environment
uv sync

# Run development server with live reload
uv run uvicorn app.main:app --reload --port 8000

# Run unit and integration tests
uv run pytest

# Run strict type checker
uv run pyright

# Run linter
uv run ruff check
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server (runs on http://localhost:5173/birthday/)
npm run dev

# Run TypeScript type check and production build
npm run build

# Run Biome linter and formatter checks
npm run lint
```

### Running with Docker Locally

Build and run the multi-stage production container locally:
```bash
docker compose build
docker compose up -d
```

---

## Documentation & References

- [Frontend Specification](specs/front.md) — Visual principles, particle system, and component behaviors
- [Backend Specification](specs/backend.md) — Data schemas, phone normalization rules, and API contracts
- [Infrastructure Specification](specs/infra.md) — NixOS homelab host, Traefik labels, and deployment architecture
- [Project Roadmap](ROADMAP.md) — Phased progress, completed milestones, and future enhancements
- [SSO Graphify Benchmark](experiments/bdinvite-sso-graphify-benchmark/README.md) — Retrospective and archived evidence from an 8-checkpoint agent benchmark

---

## Staged Features

- **Phase 6 OIDC Authentication**: An application-level OpenID Connect authorization code flow (with signed session cookies and headless browser Playwright testing) has been implemented and verified in branch `feat/sso-auth` ([PR #2](https://gitea.roadtotech.me/kiskaadee/bdinvite/pulls/2)). Deployment is staged pending the homelab Authelia identity provider rework.

---

## License

[Unlicense](UNLICENSE) — Public Domain.
