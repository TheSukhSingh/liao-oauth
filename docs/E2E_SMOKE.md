# E2E Smoke Test Guide

This guide walks you through a local end-to-end test of the Google OAuth microservice using Docker and curl.

## 0) Pre-flight
- Ensure `.env` has:
  - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
  - `GOOGLE_REDIRECT_BASE=http://localhost:8000` (for local)
  - `API_INTERNAL_KEY` and `ENCRYPTION_KEY`
- Start Docker Desktop.

## 1) Start the service
```bash
docker compose up --build -d
docker compose ps
docker compose logs -f --tail=100
