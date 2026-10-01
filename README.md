# bdinvite

Interactive digital birthday invitation with RSVP.

## Overview

A mobile-first invitation app with animated golden bokeh particles, an RSVP form with semantic state feedback, a live countdown timer, and an admin dashboard for managing responses and invitation content.

- **Guest**: `demos.roadtotech.me/birthday/`
- **Admin**: `demos.roadtotech.me/birthday/admin` (Authelia-protected)

## Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, TypeScript, Canvas 2D, CSS Modules |
| Backend | FastAPI, SQLAlchemy, Pydantic, SQLite (WAL) |
| Infrastructure | Docker (multi-stage), Traefik, Authelia SSO |

## Documentation

- [Frontend Specification](specs/front.md)
- [Backend Specification](specs/backend.md)
- [Infrastructure Specification](specs/infra.md)
- [Roadmap](ROADMAP.md)

## License

[Unlicense](UNLICENSE) — public domain.
