# Google OAuth Ingestion Microservice

A production-grade **FastAPI** service that lets your app connect a user's Google account and ingest **Drive**, **Docs**, **Sheets**, and **Slides** content (read-only). It implements a complete OAuth flow, secure token storage (encrypted at rest), internal-only token retrieval, rate limiting, health checks, Dockerized runtime, and a tiny sample HTML page for the consent flow.

---

## ✨ Features

- **Google OAuth 2.0**: consent URL + callback + token exchange (offline access)
- **Token management**: auto-refresh, revoke, **encrypted at rest**
- **Google APIs**: Drive (profile + list files), Docs (full JSON + extracted text), Sheets (read ranges), Slides (summary + full JSON)
- **Security**: internal key check, optional IP allow-list, fixed-window **rate-limits** per API key and per user
- **Ops ready**: health endpoint, rotating file logs, Dockerfile + docker-compose
- **DevX**: interactive docs at `/docs`, **sample HTML** for the consent redirect

---

## 🏗️ Architecture (high level)

```
App / Frontend
    │
    │ 1) GET /auth/google/url?user_id=...
    ▼
Auth Service (this repo) ──► Google Consent Screen
    ▲                              │
    │ 2) GET /auth/google/callback?code=...&state=...
    │    - Exchanges code for access/refresh
    │    - Saves encrypted tokens
    │
    │ 3) Internal ingestors:
    │    GET /auth/google/token?user_id=... (internal-only)
    │    - Returns valid access token (auto-refresh if needed)
    │
    └──► Use returned token to call Google APIs via the /google/* routes
```

---

## 🔐 Security Notes

- **Internal-only endpoints** (e.g., `/auth/google/token`) require the `X-API-Key` header and can optionally be restricted by an IP allow-list.
- Fixed-window rate-limits protect the service per key and per user.
- **Encryption at rest**: access/refresh tokens are encrypted using a Fernet key from the environment.
- `state` parameter is signed and time-limited to prevent CSRF/replay.

> See the **Environment** section for all required keys and how to set them.

---

## ▶️ Quickstart (Docker)

1) Create a `.env` (or copy `.env.example`) and fill in values (see below).  
2) Build & run:

```bash
docker compose up --build -d
```

3) Open API docs: http://localhost:8000/docs  
4) Health check: http://localhost:8000/healthz

Docker compose mounts a persistent SQLite DB at `./data/app.sqlite3` and logs at `./logs/app.log`.

---

## ⚙️ Environment Variables

| Variable | Description |
|---|---|
| `GOOGLE_CLIENT_ID` | OAuth client ID from Google Cloud |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret from Google Cloud |
| `GOOGLE_REDIRECT_BASE` | Base URL for the callback (e.g., `https://example.com`) |
| `API_INTERNAL_KEY` | Secret value for `X-API-Key` header to protect internal routes |
| `INTERNAL_ALLOWED_IPS` | (Optional) Comma-separated IPs/CIDRs allowed to call internal routes (e.g., `127.0.0.1,10.0.0.0/8`) |
| `ENCRYPTION_KEY` | 32-byte base64 Fernet key (generate one; see below) |
| `RATE_LIMIT_MAX_PER_KEY` | Requests per window per API key (e.g., `60`) |
| `RATE_LIMIT_MAX_PER_USER` | Requests per window per user (e.g., `60`) |
| `RATE_LIMIT_WINDOW_SECONDS` | Window size in seconds (e.g., `60`) |
| `CORS_ORIGINS` | (Optional) Comma-separated list of allowed origins for browsers (e.g., `https://yourapp.com`) |
| `DATABASE_URL` | (Optional) Override DB URL; defaults to SQLite in `./data/app.sqlite3` |

**Generate a Fernet key:**

```bash
python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

Set the output as `ENCRYPTION_KEY`.

---

## 🔧 Google Cloud Setup

1. Go to **Google Cloud Console** → **APIs & Services** → **Credentials**.
2. Create an **OAuth 2.0 Client ID** (type: Web application).
3. Add an **Authorized redirect URI**:  
   `https://YOUR_DOMAIN/auth/google/callback` (or `http://localhost:8000/auth/google/callback` for local).
4. Enable APIs: **Drive API**, **Docs API**, **Sheets API**, **Slides API**.
5. Copy the Client ID/Secret into your `.env`.

**Scopes used (read-only):**

- `https://www.googleapis.com/auth/drive.readonly`
- `https://www.googleapis.com/auth/documents.readonly`
- `https://www.googleapis.com/auth/spreadsheets.readonly`
- `https://www.googleapis.com/auth/presentations.readonly`

---

## 🌐 Endpoints (high level)

### Auth
- `GET /auth/google/url?user_id=...` → Returns the Google consent URL
- `GET /auth/google/callback?code=...&state=...` → Exchanges code and stores tokens
- `GET /auth/google/token?user_id=...` → **Internal-only**: returns valid access token (auto-refresh)
- `POST /auth/google/revoke` (JSON: `{ "user_id": "..." }`) → Revokes token & clears storage

### Google APIs
- `GET /google/drive/me?user_id=...` → Drive profile (`about.user`)
- `GET /google/drive/files?user_id=...&page_size=10&q=name contains 'report'` → List files
- `GET /google/sheets/{spreadsheet_id}/values?user_id=...&range=Sheet1!A1:D10` → Read values
- `GET /google/docs/{document_id}` → Fetch full doc JSON
- `GET /google/docs/{document_id}/text?user_id=...` → Extracted plain text
- `GET /google/slides/{presentation_id}` → Full presentation JSON
- `GET /google/slides/{presentation_id}/summary?user_id=...` → Slide summaries (title/subtitle/body)

### Health & Internal
- `GET /healthz` → Liveness check
- `GET /internal/ping` → Requires `X-API-Key` (and IP allow-list if configured)

---

## 🧪 cURL Examples

> Replace `YOUR_API_KEY` and `USER123` accordingly.

**1) Get consent URL**
```bash
curl "http://localhost:8000/auth/google/url?user_id=USER123"
```

**2) After consent → callback is handled automatically**

**3) Internal: get valid access token (auto-refresh)**
```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  "http://localhost:8000/auth/google/token?user_id=USER123"
```

**4) List Drive files (internal)**
```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  "http://localhost:8000/google/drive/files?user_id=USER123&page_size=10"
```

**5) Get Docs text (internal)**
```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  "http://localhost:8000/google/docs/DOC_ID/text?user_id=USER123"
```

**6) Revoke a user’s tokens**
```bash
curl -X POST -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"user_id":"USER123"}' \
  "http://localhost:8000/auth/google/revoke"
```

---

## 🔄 End-to-End Test Checklist

1. Start the service (`docker compose up -d`) and open `/docs`.
2. Call `GET /auth/google/url?user_id=USER123` → open `auth_url` in a browser.
3. Sign in to Google and accept permissions → you should land on the callback; tokens are stored.
4. Call `GET /auth/google/token?user_id=USER123` with `X-API-Key` → receive a valid token.
5. Call Drive/Docs/Sheets/Slides endpoints (with `X-API-Key`) → verify results.
6. (Optional) Revoke with `POST /auth/google/revoke` and confirm access is removed.

---

## 📊 Rate Limiting

- Fixed-window counters per **API key** and per **user**.
- When exceeded, responses return **HTTP 429** with a `Retry-After` header.
- Configure with `RATE_LIMIT_MAX_PER_KEY`, `RATE_LIMIT_MAX_PER_USER`, and `RATE_LIMIT_WINDOW_SECONDS`.

---

## 📝 Logging

- Rotating file logs under `./logs/app.log` (size-based rotation).
- For production, ship logs to your aggregator or mount a persistent volume.

---

## 🛡️ CORS

If you will call these APIs from a browser, set `CORS_ORIGINS` with the allowed origins (comma-separated). Otherwise, leave it empty/disabled for server-to-server use.

---

## 🧰 Local Development

- Python 3.11+ recommended.
- Install deps: `pip install -r requirements.txt`
- Run: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

---

## 🚀 Deployment Notes

- Keep `API_INTERNAL_KEY` and `ENCRYPTION_KEY` secret (use your secrets manager).
- Restrict `/auth/google/token` and other internal routes to your network via IP allow-list + API key.
- Rotate keys periodically; revoke tokens if compromise is suspected.
- Ensure your public domain and `GOOGLE_REDIRECT_BASE` match.

---

## 📎 Sample Frontend

A minimal HTML page is included under `static/sample/` which demonstrates generating the consent URL and redirecting the user to Google. Extend it to call list/read endpoints after the user connects.

---

## ❓ Troubleshooting

- **Callback returns an error**: Confirm your Google OAuth **Authorized redirect URI** exactly matches `GOOGLE_REDIRECT_BASE + /auth/google/callback`.
- **401/403 on internal endpoints**: Ensure `X-API-Key` is correct and (if configured) the caller’s IP is in `INTERNAL_ALLOWED_IPS`.
- **429 rate limit**: Check the `Retry-After` response header; adjust limits via env vars if needed.
- **Empty Drive results**: Verify the user’s account actually has content and you’re using the correct `user_id`.
- **Token refresh errors**: Re-connect the user via the consent flow to obtain a fresh refresh token.
