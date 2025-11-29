# Railway Deployment Guide

This guide walks you through deploying the Voice Agent platform to Railway.

## Architecture

The deployment consists of 4 services:
- **Backend** - FastAPI Python API (from `backend/`)
- **Frontend** - Next.js React app (from `frontend/`)
- **PostgreSQL** - Database (Railway plugin)
- **Redis** - Cache & async tasks (Railway plugin)

## Prerequisites

1. A [Railway account](https://railway.app)
2. Railway CLI installed: `npm install -g @railway/cli`
3. Your API keys ready:
   - OpenAI API key
   - Deepgram API key
   - ElevenLabs API key
   - Telnyx/Twilio credentials (for telephony)

## Step 1: Create Railway Project

```bash
# Login to Railway
railway login

# Create a new project
railway init
```

Or create via the Railway dashboard at https://railway.app/new

## Step 2: Add Database Services

In the Railway dashboard:

1. Click **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Click **"+ New"** → **"Database"** → **"Redis"**

Railway will automatically provision these services and generate connection URLs.

## Step 3: Deploy Backend Service

1. Click **"+ New"** → **"GitHub Repo"**
2. Select your repository
3. Configure the service:
   - **Root Directory**: `backend`
   - **Build Command**: (auto-detected from Dockerfile)
   - **Start Command**: (auto-detected from Dockerfile)

### Backend Environment Variables

Add these variables in the Railway dashboard (Settings → Variables):

```bash
# Database (auto-populated if you link the PostgreSQL service)
DATABASE_URL=${{Postgres.DATABASE_URL}}

# Redis (auto-populated if you link the Redis service)
REDIS_URL=${{Redis.REDIS_URL}}

# Security - GENERATE A STRONG SECRET
SECRET_KEY=<generate-with: openssl rand -hex 32>

# Admin account (created on first startup)
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=<secure-password>
ADMIN_NAME=Admin

# Voice AI Services
OPENAI_API_KEY=sk-...
DEEPGRAM_API_KEY=...
ELEVENLABS_API_KEY=...

# Telephony (optional)
TELNYX_API_KEY=...
TELNYX_PUBLIC_KEY=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...

# CORS - set to your frontend URL
CORS_ORIGINS=https://your-frontend.railway.app
```

## Step 4: Deploy Frontend Service

1. Click **"+ New"** → **"GitHub Repo"**
2. Select your repository (same repo, different service)
3. Configure the service:
   - **Root Directory**: `frontend`
   - **Build Command**: (auto-detected from Dockerfile)

### Frontend Environment Variables

```bash
# API URL - your backend Railway URL
NEXT_PUBLIC_API_URL=https://your-backend.railway.app

# WebSocket URL
NEXT_PUBLIC_WS_URL=wss://your-backend.railway.app
```

**Important**: These are build-time variables. After adding them, trigger a redeploy.

## Step 5: Configure Networking

### Generate Domain Names

For each service (backend & frontend):
1. Go to **Settings** → **Networking**
2. Click **"Generate Domain"**

### Link Services

In the backend service:
1. Go to **Variables**
2. Click **"Add Reference"**
3. Link `DATABASE_URL` from PostgreSQL
4. Link `REDIS_URL` from Redis

## Step 6: Verify Deployment

### Check Backend Health

```bash
curl https://your-backend.railway.app/health
# Should return: {"status":"healthy"}

curl https://your-backend.railway.app/health/db
# Should return: {"status":"healthy","latency_ms":...}

curl https://your-backend.railway.app/health/redis
# Should return: {"status":"healthy","latency_ms":...}
```

### Check Frontend

Visit `https://your-frontend.railway.app` - you should see the login page.

## Environment Variables Reference

### Required for Backend

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `SECRET_KEY` | JWT signing key (32+ chars) |
| `ADMIN_EMAIL` | Initial admin email |
| `ADMIN_PASSWORD` | Initial admin password |

### Voice AI Services

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4o |
| `DEEPGRAM_API_KEY` | Deepgram for speech-to-text |
| `ELEVENLABS_API_KEY` | ElevenLabs for text-to-speech |

### Telephony (Optional)

| Variable | Description |
|----------|-------------|
| `TELNYX_API_KEY` | Telnyx API key |
| `TELNYX_PUBLIC_KEY` | Telnyx public key |
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |

### Frontend

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend API URL |
| `NEXT_PUBLIC_WS_URL` | Backend WebSocket URL |

## Troubleshooting

### Database Migrations Failed

Check the deploy logs. Common issues:
- Database not yet ready - wait and redeploy
- Connection string format - ensure it uses `postgresql+asyncpg://`

### Frontend Can't Connect to Backend

1. Verify CORS_ORIGINS includes your frontend URL
2. Check NEXT_PUBLIC_API_URL is correct (no trailing slash)
3. Ensure backend service is running

### WebSocket Issues

- Ensure NEXT_PUBLIC_WS_URL uses `wss://` (not `ws://`)
- Check Railway networking allows WebSocket connections (it does by default)

## Cost Estimation

Railway pricing (as of 2024):
- **Hobby Plan**: $5/month + usage
- **PostgreSQL**: ~$5-15/month depending on size
- **Redis**: ~$5-10/month
- **Backend/Frontend**: ~$5-20/month each based on usage

Total estimated: **$20-50/month** for small-medium usage.

## Production Checklist

- [ ] Strong SECRET_KEY generated
- [ ] Admin password is secure
- [ ] CORS_ORIGINS set correctly
- [ ] All API keys configured
- [ ] Health checks passing
- [ ] SSL enabled (automatic on Railway)
- [ ] Monitoring set up (Sentry optional)
