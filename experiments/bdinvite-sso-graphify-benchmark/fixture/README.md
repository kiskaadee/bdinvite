# OIDC Benchmark Fixture

This fixture provides a standards-compliant, disposable OpenID Connect (OIDC) identity provider using `ghcr.io/navikt/mock-oauth2-server:2.1.10`.

## Endpoints

* **Base Issuer**: `http://localhost:8088/default`
* **Discovery Endpoint**: `http://localhost:8088/default/.well-known/openid-configuration`
* **Authorization Endpoint**: `http://localhost:8088/default/authorize`
* **Token Endpoint**: `http://localhost:8088/default/token`
* **JWKS URI**: `http://localhost:8088/default/jwks`
* **Userinfo Endpoint**: `http://localhost:8088/default/userinfo`

## Pre-Seeded Test Users

| Username / Email | Password | Subject | Name | Groups Claim | Expected Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `admin@example.com` | `password123` | `admin-001` | `Admin User` | `["bdinvite_admins"]` | Admin |
| `guest@example.com` | `password123` | `guest-001` | `Guest User` | `["guests"]` | Non-Admin |

## Client Configuration

* **Client ID**: `bdinvite-client` (or any string)
* **Client Secret**: `bdinvite-secret` (or any string)
* **Redirect URI**: `http://localhost:8000/birthday/api/auth/callback` (or configured callback)
* **Supported PKCE**: `S256` (RFC 7636)
* **Supported Signing Alg**: `RS256`

## Management

```bash
# Start container and await readiness
./start.sh

# Stop container
./stop.sh
```
