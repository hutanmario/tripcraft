# Setup Guide

This guide describes a local development setup for TripCraft.

## Prerequisites

- Python with virtual environment support
- Node.js and npm
- PostgreSQL
- Expo CLI through `npx expo`

## Backend

From the repository root:

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
```

Edit `backend/.env`:

```env
DATABASE_URL=postgresql://postgres@localhost:5432/tripcraft
SECRET_KEY=replace-with-a-random-secret
ALLOWED_ORIGINS=http://localhost:3000
```

Run migrations:

```powershell
python -m alembic upgrade head
```

Start the API:

```powershell
python -m uvicorn app.main:app --reload
```

Useful endpoints:

- `GET /health`
- `GET /docs`

## Mobile

```powershell
cd mobile
npm install
copy .env.example .env
```

Edit `mobile/.env`:

```env
EXPO_PUBLIC_API_URL=http://YOUR_LOCAL_IP:8000
```

For a physical device, use the computer's LAN IP instead of `localhost`.

Start Expo:

```powershell
npx expo start
```

## Tests

```powershell
cd backend
venv\Scripts\python.exe -m pytest -q
```

## Validation Commands

```powershell
cd backend
venv\Scripts\python.exe -m compileall -q app
venv\Scripts\python.exe -m alembic heads
```

```powershell
cd mobile
npx expo-doctor
```

## Environment Variables

Backend variables are documented in `backend/.env.example`.

Mobile variables are documented in `mobile/.env.example`.

Never commit real `.env` files.
