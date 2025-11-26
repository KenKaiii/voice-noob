# Voice Agent Platform

AI-powered voice agent platform for configuring and deploying custom voice agents with tool calling, multi-provider support, and transparent pricing tiers.

## Project Structure

```
voice-noob/
├── backend/                    # FastAPI Python backend
│   ├── app/
│   │   ├── api/               # API routes (agents, crm, realtime, workspaces, tools)
│   │   ├── core/              # Config, security, logging
│   │   ├── db/                # Database session, Redis client
│   │   ├── middleware/        # Request/response middleware
│   │   ├── models/            # SQLAlchemy models (user, agent, contact, appointment, workspace)
│   │   └── services/          # Business logic
│   │       └── tools/         # Tool integrations (crm_tools, registry)
│   ├── migrations/versions/   # Alembic database migrations
│   └── tests/                 # Backend tests (unit, integration, api, models)
├── frontend/                   # Next.js 15 React frontend
│   ├── src/
│   │   ├── app/dashboard/     # Dashboard pages
│   │   │   ├── agents/        # Agent CRUD & config
│   │   │   ├── crm/           # Contact management
│   │   │   ├── appointments/  # Appointment scheduling
│   │   │   ├── calls/         # Call history & transcripts
│   │   │   ├── workspaces/    # Workspace management
│   │   │   └── settings/      # User settings
│   │   ├── components/ui/     # shadcn/ui components
│   │   ├── hooks/             # Custom React hooks
│   │   └── lib/api/           # API client functions
│   └── public/                # Static assets
└── docker-compose.yml         # PostgreSQL 17 + Redis 7
```

## Organization Rules

**Backend:**
- API routes → `app/api/`, one file per resource
- Business logic → `app/services/`, organized by domain
- Models → `app/models/`, one model per file
- Tools/integrations → `app/services/tools/`, one class per integration

**Frontend:**
- Pages → `src/app/dashboard/`, using Next.js App Router
- Components → `src/components/`, reusable UI elements
- Lib → `src/lib/`, utilities, types, config
- One component per file, co-locate related files

## Code Quality - Zero Tolerance

### Backend:
```bash
cd backend
uv run ruff check app tests --fix        # Lint + auto-fix
uv run ruff format app tests             # Format
uv run mypy app                          # Type check (strict)
```

### Frontend:
```bash
cd frontend
npm run check                            # eslint + tsc + prettier
npm run lint:fix && npm run format       # Auto-fix
```

### Server Checks:
```bash
cd backend && uv run uvicorn app.main:app --reload   # Check runtime warnings
cd frontend && npm run dev                            # Check compilation warnings
```

**Fix ALL errors/warnings before continuing!**

## Key Commands

- `/update-app` - Update dependencies, fix deprecations
- `/check` - Run all quality checks, auto-fix issues
- `/commit` - Run checks, commit with AI message, push

## Tech Stack

**Voice & AI**: Pipecat, Deepgram, ElevenLabs, OpenAI, Claude, Gemini
**Backend**: FastAPI, PostgreSQL 17, Redis 7, SQLAlchemy 2.0, Python 3.12+, uv
**Frontend**: Next.js 15, React 19, TypeScript 5.7, Tailwind, shadcn/ui
**Telephony**: Telnyx (primary), Twilio (optional)
