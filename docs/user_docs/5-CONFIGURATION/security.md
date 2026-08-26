# Security Configuration

Lumina·Omax uses a **multi-user JWT-based authentication system** with admin-driven registration approval. This page covers authentication setup, user management, and production hardening.

---

## Authentication Overview

Lumina·Omax supports two authentication paths:

| Path | Purpose | Credential |
|------|---------|------------|
| **JWT Login** (primary) | Regular users | Username + Password → JWT token |
| **Master Password** (backdoor) | Emergency admin access | `OPEN_NOTEBOOK_PASSWORD` env var |

### User Flow

```
Register (pending) → Admin approves → User logs in → JWT issued → All API calls authenticated
                          ↓
                    Admin can: reject, disable, change role, reset password
```

---

## Configuration

### Required Environment Variables

```bash
# JWT signing secret (REQUIRED for production)
# Falls back to OPEN_NOTEBOOK_ENCRYPTION_KEY if not set
AUTH_JWT_SECRET=your-jwt-secret-key

# Master password for emergency admin backdoor access
OPEN_NOTEBOOK_PASSWORD=your-master-password
```

> **Warning**: In non-development environments, the system will **refuse to start** if neither `AUTH_JWT_SECRET` nor `OPEN_NOTEBOOK_ENCRYPTION_KEY` is configured. The default JWT secret is only allowed in dev/local/test modes (controlled by `OPEN_NOTEBOOK_ENV`).

### JWT Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `AUTH_JWT_SECRET` | (required) | HS256 signing key for JWT tokens |
| JWT expiry | 7 days | Hard-coded, tokens expire after 7 days |
| Algorithm | HS256 | HMAC-SHA256 |

---

## User Registration & Management

### Self-Registration

1. Users register via the login page **Register** tab
2. New accounts are created with **pending** status
3. Pending users cannot log in

### Admin Approval (Administrator Only)

Administrators manage users from **Settings → User Approval Dashboard**:

| Action | Effect |
|--------|--------|
| **Approve** | User status → active, can log in |
| **Reject** | User status → rejected, cannot log in |
| **Disable** | Active user → rejected |
| **Change Role** | Toggle between User ↔ Admin |
| **Reset Password** | Set new password (secure modal with confirmation) |

Only users with `role: admin` can access the User Approval Dashboard.

### Rate Limiting

To prevent brute-force attacks:

| Endpoint | Limit |
|----------|-------|
| `POST /api/auth/login` | 10 requests per minute per IP |
| `POST /api/auth/register` | 5 requests per 5 minutes per IP |

---

## API Authentication

### JWT Token (Primary)

All protected endpoints require a valid JWT token:

```bash
# Login to get a token
curl -X POST http://localhost:5055/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "secure-pass-123"}'

# Response: {"access_token": "eyJ...", "token_type": "bearer", "user": {...}}

# Use token for subsequent requests
curl -H "Authorization: Bearer eyJ..." \
  http://localhost:5055/api/notebooks
```

### Master Password Backdoor

For emergency access, the master password can be used directly:

```bash
TOKEN=$OPEN_NOTEBOOK_PASSWORD
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:5055/api/notebooks
```

### Admin Password for Destructive Source Operations

Deleting a source that is referenced by multiple notebooks requires admin password verification. The check is enforced **server-side** via the `X-Admin-Password` header against `OPEN_NOTEBOOK_PASSWORD`:

```bash
curl -X DELETE "http://localhost:5055/api/sources/{id}" \
  -H "X-Admin-Password: $OPEN_NOTEBOOK_PASSWORD"
```

- Frontend no longer holds `NEXT_PUBLIC_MASTER_NOTEBOOK_PASSWORD`; deletion validation is unified to the backend `OPEN_NOTEBOOK_PASSWORD` to avoid mismatched values.
- Sources you created and that are not referenced by other notebooks can be deleted without a password.
- Sources created by others can only be "removed" (unlinked), not physically deleted.

### Unprotected Endpoints

These endpoints bypass authentication:

- `/api/auth/login` — User login
- `/api/auth/register` — Self-registration
- `/api/auth/status` — Check if auth is enabled
- `/api/config` — Backend configuration
- `/health` — System health check
- `/docs` — API documentation

---

## API Key Encryption

Lumiton·Omax encrypts API keys stored in the database using Fernet symmetric encryption (AES-128-CBC with HMAC-SHA256).

### Configuration Methods

| Method | Documentation |
|--------|---------------|
| **Settings UI** | [API Configuration Guide](../3-USER-GUIDE/api-configuration.md) |
| **Environment Variables** | This page (below) |

### Setup

Set the encryption key to any secret string:

```bash
# .env or docker.env
OPEN_NOTEBOOK_ENCRYPTION_KEY=my-secret-passphrase
```

Any string works — it will be securely derived via SHA-256 internally. Use a strong passphrase for production deployments.

### Default Credentials

| Setting | Default | Security Level |
|---------|---------|----------------|
| Password | `open-notebook-change-me` | Development only |
| Encryption Key | **None** (must be configured) | Required for API key storage |

**The encryption key has no default.** You must set `OPEN_NOTEBOOK_ENCRYPTION_KEY` before using the API key configuration feature. Without it, encrypting/decrypting API keys will fail.

### Docker Secrets Support

Both settings support Docker secrets via `_FILE` suffix:

```yaml
environment:
  - OPEN_NOTEBOOK_PASSWORD_FILE=/run/secrets/app_password
  - OPEN_NOTEBOOK_ENCRYPTION_KEY_FILE=/run/secrets/encryption_key
```

### Security Notes

| Scenario | Behavior |
|----------|----------|
| Key configured | API keys encrypted with your key |
| No key configured | Encryption/decryption will fail (key is required) |
| Key changed | Old encrypted keys become unreadable |
| Legacy data | Unencrypted keys still work (graceful fallback) |

### Key Management

- **Keep secret**: Never commit the encryption key to version control
- **Backup securely**: Store the key separately from database backups
- **No rotation yet**: Changing the key requires re-saving all API keys
- **Per-deployment**: Each instance should have its own encryption key

---

## Security Features

| Feature | Status |
|---------|--------|
| Password hashing | PBKDF2-HMAC-SHA256 (600,000 iterations) |
| Password comparison | Constant-time (`hmac.compare_digest`) |
| JWT signing | HS256, 7-day expiry |
| Rate limiting | Per-IP sliding window on login/register |
| Token cookie sync | `SameSite=Lax`, cleared on logout |
| Server-side logout | `POST /api/auth/logout` |
| Error messages | Generic (no internal detail leakage) |
| Frontend route guard | Next.js middleware with cookie check |
| Admin actions | Confirmation dialog before approve/reject/disable |

---

## How Authentication Works

### Frontend

1. User submits login form → JWT token stored in Zustand persist (localStorage)
2. `auth-token` cookie set for server-side middleware access
3. All API requests include `Authorization: Bearer <token>` header
4. 401 responses trigger automatic redirect to login
5. Logout clears token, cookie, and Zustand state; calls server logout endpoint

### Backend

1. `PasswordAuthMiddleware` intercepts all protected routes
2. Checks for `Authorization: Bearer <token>` header
3. If token matches master password → super admin access (backdoor)
4. Otherwise → JWT decode + validate user status (pending/rejected blocked)
5. User info stored in `request.state.user` for downstream handlers

---

## Docker Deployment

```yaml
services:
  lumina-omax:
    image: lumina-omax:latest
    environment:
      - AUTH_JWT_SECRET=your-strong-jwt-secret
      - OPEN_NOTEBOOK_PASSWORD=your-master-backdoor-password
      - OPEN_NOTEBOOK_ENCRYPTION_KEY=your-encryption-key
      - OPEN_NOTEBOOK_ENV=production
    # ...
```

---

## API Authentication Examples

### curl

```bash
# Login
curl -X POST http://localhost:5055/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secure123"}'

# Use token
TOKEN="eyJ..."
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:5055/api/notebooks
```

### Python

```python
import requests

def login(base_url: str, username: str, password: str) -> str:
    resp = requests.post(f"{base_url}/api/auth/login", json={
        "username": username, "password": password
    })
    return resp.json()["access_token"]

token = login("http://localhost:5055", "alice", "secure123")
headers = {"Authorization": f"Bearer {token}"}
notebooks = requests.get("http://localhost:5055/api/notebooks", headers=headers).json()
```

---

## Production Hardening

### Docker Security

```yaml
# Add to your docker-compose.yml (requires surrealdb service, see installation guide)
services:
  open_notebook:
    image: lfnovo/open_notebook:v1-latest
    pull_policy: always
    ports:
      - "127.0.0.1:3000:3000"  # Bind to localhost only
    environment:
      - OPEN_NOTEBOOK_PASSWORD=your_secure_password
    security_opt:
      - no-new-privileges:true
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "1.0"
    restart: always
```

### Firewall Configuration

```bash
# UFW (Ubuntu)
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 3000/tcp   # Block direct access
sudo ufw deny 5055/tcp   # Block direct API access
sudo ufw enable

# iptables
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
iptables -A INPUT -p tcp --dport 3000 -j DROP
iptables -A INPUT -p tcp --dport 5055 -j DROP
```

### Reverse Proxy with SSL

See [Reverse Proxy Configuration](reverse-proxy.md) for complete nginx/Caddy/Traefik setup with HTTPS.

---

## Security Limitations

| Feature | Status |
|---------|--------|
| Multi-user authentication | ✅ JWT + password hashing |
| Role-based access | ✅ Admin / User |
| Rate limiting | ✅ Login & registration |
| Password transmission | Requires HTTPS |
| Token refresh | Not yet implemented |
| Token revocation | Not yet implemented |
| Session management | Token-based (7-day expiry) |
| Audit logging | Not yet implemented |
| 2FA / MFA | Not yet implemented |

---

## Troubleshooting

### Login Failed

```bash
# Check user status
# Pending users cannot log in — needs admin approval
# Rejected users cannot log in — contact administrator
```

### 401 Unauthorized Errors

```bash
# Verify JWT token is valid and not expired
# Tokens expire after 7 days — re-login required
curl -v -H "Authorization: Bearer $TOKEN" \
  http://localhost:5055/api/notebooks
```

### Cannot Access After Setting Password

1. Clear browser cache and cookies
2. Try incognito/private mode
3. Check browser console for errors
4. Verify password is correct

### Registration Not Working

1. Username must be 3-50 characters
2. Password must be at least 6 characters
3. Username "admin" is reserved
4. Duplicate usernames are rejected
5. Rate limit: 5 registrations per 5 minutes per IP

### JWT Secret Not Configured

If the system fails to start with:
```
RuntimeError: JWT secret is not configured.
```

Set `AUTH_JWT_SECRET` or `OPEN_NOTEBOOK_ENCRYPTION_KEY`, or set `OPEN_NOTEBOOK_ENV=dev` for development.

---

## Reporting Security Issues

If you discover security vulnerabilities:

1. **Do NOT open public issues**
2. Contact maintainers directly
3. Provide detailed information
4. Allow time for fixes before disclosure

---

## Related

- **[Reverse Proxy](reverse-proxy.md)** - HTTPS and SSL setup
- **[Advanced Configuration](advanced.md)** - Ports, timeouts, and SSL settings
- **[Environment Reference](environment-reference.md)** - All configuration options
