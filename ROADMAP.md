# Roadmap

## Phase 0 — Documentation Foundation

- [x] Frontend specification
- [x] Backend specification
- [x] Infrastructure specification
- [x] Project README
- [x] Roadmap
- [x] License (Unlicense)

## Phase 1 — Backend

- [x] Project scaffolding (`pyproject.toml`, app directory)
- [x] SQLite database with WAL mode
- [x] SQLAlchemy models (`RSVP`, `InvitationConfig`)
- [x] Pydantic request/response schemas
- [x] Config seeding and CRUD
- [x] `POST /birthday/api/rsvp` with phone normalization
- [x] `GET /birthday/api/config`
- [x] Admin endpoints with `Remote-User` guard
- [x] CSV export endpoint
- [x] SPA catch-all route
- [x] Backend tests (15 unit/integration tests passing)

## Phase 2 — Frontend Scaffolding

- [x] Vite + React + TypeScript setup
- [x] React Router with `basename=/birthday`
- [x] API client (`/birthday/api/*`)
- [x] Config loading state (`CONFIG_LOADING` → `INVITATION` | `CONFIG_ERROR`)
- [x] Self-hosted font files (display script + Montserrat)
- [x] CSS Modules setup and global styles
- [x] TypeScript interfaces for config and API responses

## Phase 3 — Guest Experience

- [x] Invitation hero section (fixed aspect ratio)
- [x] Canvas 2D particle background (golden bokeh)
- [x] RSVP CTA with smooth scroll transition
- [x] RSVP form with client-side validation (Colombian phone format)
- [x] Submission state machine (`SUBMITTING` → `SUCCESS` | `DUPLICATE` | `ERROR`)
- [x] Confirmation section: personalized message
- [x] Countdown timer (timezone-aware, `NOS VEMOS EN DD:HH:MM:SS`)
- [x] Map preview (circular static image, link to `mapUrl`)
- [x] Venue info (compact name + address)
- [x] `sessionStorage` post-RSVP state preservation
- [x] Accessibility (semantic HTML, keyboard nav, aria-live, focus states)
- [x] `prefers-reduced-motion` support (static particles)
- [x] Responsive behavior (mobile-first, desktop stage)

## Phase 4 — Admin Dashboard

- [x] Admin layout shell (header, navigation)
- [x] RSVP table with total count
- [x] Search/filter RSVPs
- [x] CSV export download button
- [x] Config editor form (flat fields, Pydantic-validated)
- [x] Text preview of invitation content


## Phase 5 — Infrastructure & Deployment

- [x] Dockerfile (multi-stage build)
- [x] `docker-compose.yml` with split Traefik routing
- [x] `app.yaml` manifest for `appctl`
- [x] `.gitignore` finalized
- [x] Local Docker build verification
- [ ] Deployment to `demos.roadtotech.me`
- [ ] Post-deployment verification
- [ ] Authelia admin route verification

## Future

- [ ] Font selection (visual comparison of candidates)
- [x] Application-owned map preview asset (replace URL with static file)
- [ ] Miniature rendered invitation preview in admin config editor
- [ ] Enhanced admin features (edit/delete RSVP, attendance status, guest count)
- [ ] CSV import
