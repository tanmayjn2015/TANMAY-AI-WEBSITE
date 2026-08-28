# CHAYA MAX 2.0 — Full Stack

A production-ready FastAPI + PostgreSQL/SQLite backend with a responsive AI frontend.

## Included upgrades
- Secure environment-based database/admin configuration (no hard-coded production password or secret).
- Health endpoint and deployment health check.
- Login, registration, logout and session expiry.
- Admin dashboard with user search, enable/disable, role management, session revocation and deletion.
- Usage analytics endpoint.
- Full chat CRUD API.
- New device-native Voice Studio using Web Speech API: voice picker, speed, pitch, volume, test and stop.
- Native TTS is used first so a broken external TTS service does not break voice playback.
- Mobile-friendly UI and graceful offline/online handling.

## Required production environment variables
Set these on Render/Railway/etc.:
- `DATABASE_URL`
- `SESSION_SECRET`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `FRONTEND_ORIGIN` (your deployed frontend origin)
- `COOKIE_SECURE=true`

`ADMIN_USERNAME` defaults to `tanmay`.

Never commit real passwords, session secrets, API keys, or database credentials.

## Run locally
```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API docs are available at `/docs`; health check is `/api/health`.
