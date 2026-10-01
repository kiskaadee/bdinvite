# Digital Invitation — Infrastructure Specification

> **Status**: Frozen · **Workload**: `bdinvite` · **Host**: `roadtotech.me` (NixOS homelab)

---

## 1. Platform Context

The application runs on the `roadtotech.me` homelab appliance — a NixOS server providing:

| Component | Role |
|---|---|
| **Traefik v3.6** | Reverse proxy with wildcard DNS/TLS for `*.roadtotech.me` (ACME DNS-01 via Dynu) |
| **Authelia** | SSO with LLDAP backend; session cookies valid across `*.roadtotech.me` |
| **`appctl`** | Orchestration tool for Sites workloads (reads `app.yaml` manifests, injects env, controls Docker Compose) |
| **Docker Compose** | Container lifecycle management |
| **`proxy-net`** | External Docker network shared between Traefik and workload containers |

The application lives at `~/Sites/bdinvite` on the server.

---

## 2. Container Architecture

A **single container** produced by a multi-stage Docker build:

- **Stage 1** (`node:20-alpine`): Builds the React frontend (`npm ci` → `npm run build`)
- **Stage 2** (`ghcr.io/astral-sh/uv:python3.11-bookworm-slim`): Runs FastAPI with uvicorn; frontend build output (`dist/`) is copied in as `./static`

| Property | Value |
|---|---|
| Container name | `bdinvite` |
| Internal port | `8000` |
| Volume mount | `./data:/app/data` (SQLite persistence) |
| Restart policy | `unless-stopped` |

---

## 3. Dockerfile

```dockerfile
# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1
COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --frozen --no-install-project --no-dev
COPY backend/ .
COPY --from=frontend-build /build/dist ./static
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 4. Traefik Routing

This application uses **path-based routing** on `demos.roadtotech.me`. Three Traefik routers are defined on the same container, all targeting a single service (`bdinvite-svc`) on container port 8000.

`demos.roadtotech.me` is covered by the existing wildcard DNS (`*.roadtotech.me`) and wildcard TLS certificate. No Core/NixOS changes are required.

### 4.1 Public Router — `bdinvite-public` (priority 10)

| Property | Value |
|---|---|
| Rule | ``Host(`demos.roadtotech.me`) && PathPrefix(`/birthday`)`` |
| Entrypoint | `websecure` (port 443) |
| TLS | Enabled (wildcard cert from ACME DNS-01) |
| Middleware | *None* — **public access** |
| Priority | 10 |

Catches all `/birthday/*` traffic that does not match a higher-priority router.

### 4.2 Admin Router — `bdinvite-admin` (priority 20)

| Property | Value |
|---|---|
| Rule | ``Host(`demos.roadtotech.me`) && PathPrefix(`/birthday/admin`)`` |
| Entrypoint | `websecure` (port 443) |
| TLS | Enabled |
| Middleware | `authelia-auth@docker` (ForwardAuth) |
| Priority | 20 |

Higher priority ensures `/birthday/admin/*` requests are intercepted before the generic public router.

### 4.3 HTTP Redirect Router — `bdinvite-red`

| Property | Value |
|---|---|
| Rule | ``Host(`demos.roadtotech.me`) && PathPrefix(`/birthday`)`` |
| Entrypoint | `web` (port 80) |
| Middleware | `https-redirect@docker` |

Redirects all HTTP traffic to HTTPS.

---

## 5. Authelia Integration

Authelia runs as a core infrastructure service (container: `authelia`, internal port 9091) on `proxy-net`. The ForwardAuth middleware is defined on the Traefik container:

```yaml
- "traefik.http.middlewares.authelia-auth.forwardauth.address=http://authelia:9091/api/verify?rd=https://auth.${DOMAIN}/"
- "traefik.http.middlewares.authelia-auth.forwardauth.trustForwardHeader=true"
- "traefik.http.middlewares.authelia-auth.forwardauth.authResponseHeaders=Remote-User,Remote-Groups,Remote-Email,Remote-Name"
```

### 5.1 Admin Authentication Flow

```
1. User visits https://demos.roadtotech.me/birthday/admin
2. Traefik matches bdinvite-admin router (priority 20)
3. Traefik forwards request to Authelia at http://authelia:9091/api/verify
4. IF unauthenticated:
   → Authelia returns 401
   → Traefik redirects browser to https://auth.roadtotech.me/?rd=https://demos.roadtotech.me/birthday/admin
5. User authenticates at Authelia portal
6. Authelia sets authelia_session cookie (valid across *.roadtotech.me)
7. Subsequent requests:
   → Authelia returns 200
   → Traefik forwards identity headers to the backend:
     Remote-User, Remote-Email, Remote-Groups, Remote-Name
8. Backend reads Remote-User header to identify the admin
```

The backend performs **no authentication of its own** — no login page, no JWT, no session management.

---

## 6. docker-compose.yml

```yaml
services:
  bdinvite:
    build: .
    container_name: bdinvite
    restart: unless-stopped
    volumes:
      - ./data:/app/data
    environment:
      - BASE_PATH=/birthday
    networks:
      - proxy-net
    labels:
      - "diun.enable=false"
      - "traefik.enable=true"

      # Public router (invitation + public API)
      - "traefik.http.routers.bdinvite-public.rule=Host(`${SERVICE_DOMAIN:-demos.roadtotech.me}`) && PathPrefix(`/birthday`)"
      - "traefik.http.routers.bdinvite-public.entrypoints=websecure"
      - "traefik.http.routers.bdinvite-public.tls=true"
      - "traefik.http.routers.bdinvite-public.priority=10"
      - "traefik.http.routers.bdinvite-public.service=bdinvite-svc"

      # Admin router (Authelia-protected)
      - "traefik.http.routers.bdinvite-admin.rule=Host(`${SERVICE_DOMAIN:-demos.roadtotech.me}`) && PathPrefix(`/birthday/admin`)"
      - "traefik.http.routers.bdinvite-admin.entrypoints=websecure"
      - "traefik.http.routers.bdinvite-admin.tls=true"
      - "traefik.http.routers.bdinvite-admin.priority=20"
      - "traefik.http.routers.bdinvite-admin.middlewares=authelia-auth@docker"
      - "traefik.http.routers.bdinvite-admin.service=bdinvite-svc"

      # HTTP to HTTPS redirect
      - "traefik.http.routers.bdinvite-red.rule=Host(`${SERVICE_DOMAIN:-demos.roadtotech.me}`) && PathPrefix(`/birthday`)"
      - "traefik.http.routers.bdinvite-red.entrypoints=web"
      - "traefik.http.routers.bdinvite-red.middlewares=https-redirect@docker"

      # Service target
      - "traefik.http.services.bdinvite-svc.loadbalancer.server.port=8000"

networks:
  proxy-net:
    external: true
```

---

## 7. appctl Manifest (app.yaml)

```yaml
name: "bdinvite"
aliases:
  - "birthday"
  - "invite"
domain: "demos.roadtotech.me"
description: "Interactive Digital Birthday Invitation with RSVP"
visible: true
auth: false
networks:
  - proxy-net
env:
  BASE_PATH: "/birthday"
homepage:
  title: "Birthday Invite"
  group: "Applications"
  icon: "party.png"
  container: "bdinvite"
  weight: 30
```

`auth: false` because the public guest route exists. Authelia protection is applied selectively via Traefik labels, not universally to the entire domain.

### 7.1 Injected Environment Variables

`appctl` injects these standard environment variables from the manifest:

| Variable | Value |
|---|---|
| `SERVICE_NAME` | `bdinvite` |
| `CONTAINER_NAME` | `bdinvite` |
| `SERVICE_DOMAIN` | `demos.roadtotech.me` |
| `DOMAIN` | `demos.roadtotech.me` |
| `PROXY_NETWORK` | `proxy-net` |
| `BASE_PATH` | `/birthday` |

Additional secrets are sourced from `/run/secrets/traefik-deployments.env`.

---

## 8. Network Topology

```
Guest Browser
      │
      ▼ HTTPS
demos.roadtotech.me (Traefik :443)
      │
      ├─ /birthday/* (priority 10, public)
      │     │
      │     ▼
      │   bdinvite:8000 (FastAPI)
      │
      └─ /birthday/admin/* (priority 20, Authelia)
            │
            ▼ ForwardAuth
          authelia:9091
            │
            ├── 200 OK → bdinvite:8000 (+ Remote-User header)
            │
            └── 401 → redirect to auth.roadtotech.me
```

All containers communicate over the `proxy-net` external Docker network. Traefik discovers routing configuration via Docker labels on the `bdinvite` container.

---

## 9. Local Development

### 9.1 Backend Only

```bash
cd backend
uv sync --dev
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 9.2 Frontend Only (Separate Terminal)

```bash
cd frontend
npm install
npm run dev
```

Vite's dev server proxies `/birthday/api` to `http://localhost:8000`.

### 9.3 Full Docker Build

```bash
cd Sites/bdinvite
docker compose build
docker compose up -d
curl -s http://localhost:8000/birthday/api/config | python3 -m json.tool
```

---

## 10. Deployment Procedure

The user owns all production transitions. Agents provide deployment runbooks but never execute deployment commands.

After changes are validated locally:

1. Commit changes on feature branch
2. Push to Gitea remote
3. Merge to `main` (user action)
4. On server:

```bash
cd ~/Sites/bdinvite
git fetch && git pull origin main
appctl restart bdinvite
# Or for full rebuild:
docker compose up -d --build
```

Or via `appctl`:

```bash
appctl update bdinvite
```

`appctl update` performs: verify clean working tree → `git pull --ff-only` → `docker compose pull` → `docker compose up -d` → `appctl sync`.

---

## 11. Post-Deployment Verification

```bash
# Container status
ssh server-local "docker ps -a | grep bdinvite"

# Container logs
ssh server-local "docker logs --tail 20 bdinvite"

# API health
ssh server-local "curl -s http://localhost:8000/birthday/api/config | python3 -m json.tool"

# Public access (returns HTML)
curl -s https://demos.roadtotech.me/birthday/ | head -5

# Authelia protection (redirects to auth portal)
curl -sI https://demos.roadtotech.me/birthday/admin

# Admin API without auth (returns 401)
curl -sI https://demos.roadtotech.me/birthday/api/admin/rsvps

# appctl status
ssh server-local "appctl info bdinvite"
```

---

## 12. Rollback Procedure

```bash
# On server:
cd ~/Sites/bdinvite
git log --oneline -5        # identify previous good commit
git checkout <commit-hash>
docker compose up -d --build

# Verify rollback:
ssh server-local "docker logs --tail 10 bdinvite"
curl -s https://demos.roadtotech.me/birthday/api/config

# If database migration issues, restore from backup:
# (SQLite file is in ./data/bdinvite.db)
cp data/bdinvite.db.bak data/bdinvite.db
docker compose restart
```

---

## 13. Data Persistence

| Item | Detail |
|---|---|
| Database | SQLite at `./data/bdinvite.db` (volume-mounted via `./data:/app/data`) |
| Git tracking | `data/` directory is gitignored |
| Backups | Operator responsibility |
| WAL mode files | `-wal` and `-shm` are transient; managed by SQLite |
