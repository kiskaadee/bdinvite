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

- [ ] Vite + React + TypeScript setup
- [ ] React Router with `basename=/birthday`
- [ ] API client (`/birthday/api/*`)
- [ ] Config loading state (`CONFIG_LOADING` → `INVITATION` | `CONFIG_ERROR`)
- [ ] Self-hosted font files (display script + Montserrat)
- [ ] CSS Modules setup and global styles
- [ ] TypeScript interfaces for config and API responses

## Phase 3 — Guest Experience

- [ ] Invitation hero section (fixed aspect ratio)
- [ ] Canvas 2D particle background (golden bokeh)
- [ ] RSVP CTA with smooth scroll transition
- [ ] RSVP form with client-side validation (Colombian phone format)
- [ ] Submission state machine (`SUBMITTING` → `SUCCESS` | `DUPLICATE` | `ERROR`)
- [ ] Confirmation section: personalized message
- [ ] Countdown timer (timezone-aware, `NOS VEMOS EN DD:HH:MM:SS`)
- [ ] Map preview (circular static image, link to `mapUrl`)
- [ ] Venue info (compact name + address)
- [ ] `sessionStorage` post-RSVP state preservation
- [ ] Accessibility (semantic HTML, keyboard nav, aria-live, focus states)
- [ ] `prefers-reduced-motion` support (static particles)
- [ ] Responsive behavior (mobile-first, desktop stage)

## Phase 4 — Admin Dashboard

- [ ] Admin layout shell (header, navigation)
- [ ] RSVP table with total count
- [ ] Search/filter RSVPs
- [ ] CSV export download button
- [ ] Config editor form (flat fields, Pydantic-validated)
- [ ] Text preview of invitation content

## Phase 5 — Infrastructure & Deployment

- [ ] Dockerfile (multi-stage build)
- [ ] `docker-compose.yml` with split Traefik routing
- [ ] `app.yaml` manifest for `appctl`
- [ ] `.gitignore` finalized
- [ ] Local Docker build verification
- [ ] Deployment to `demos.roadtotech.me`
- [ ] Post-deployment verification
- [ ] Authelia admin route verification

## Future

- [ ] Font selection (visual comparison of candidates)
- [ ] Application-owned map preview asset (replace URL with static file)
- [ ] Miniature rendered invitation preview in admin config editor
- [ ] Enhanced admin features (edit/delete RSVP, attendance status, guest count)
- [ ] CSV import
