# Voice Noob

Build AI voice agents that handle phone calls. No PhD required.

Built by [Ken Kai](https://www.youtube.com/@kenkaidoesai) · [Join the community](https://www.skool.com/kenkai/about)

![Voice Noob](voicenoob.png)

---

## What Is This?

Voice Noob is an open-source platform for creating AI-powered phone agents. Configure an agent, connect a phone number, and let it handle calls — booking appointments, answering questions, or qualifying leads while you sleep.

**The problem:** Building voice AI is painful. You need to stitch together speech-to-text, LLMs, text-to-speech, telephony, and a dozen APIs. Then pray it doesn't sound like a robot.

**The solution:** Voice Noob handles the plumbing. Pick your AI tier, write a system prompt, enable tools, and deploy.

---

## Why Voice Noob?

| Feature | Voice Noob | Vapi | Retell | Bland AI |
|---------|------------|------|--------|----------|
| Open source | Yes | No | No | No |
| Self-hostable | Yes | No | No | No |
| Transparent pricing | Per-minute breakdown | Per-minute | Per-minute | Per-minute |
| Multi-LLM support | 4 tiers (OpenAI, Google, Cerebras) | Limited | Limited | OpenAI only |
| Built-in CRM | Yes | No | No | No |
| Tool integrations | 30+ (Shopify, HubSpot, Calendly, etc.) | Via custom code | Limited | Limited |
| Embeddable widget | Yes | Yes | Yes | No |

**TL;DR:** Same capabilities as the paid platforms, but you own it.

---

## Features

![Dashboard](dashboard.png)

### Voice Calling

- Inbound and outbound calls via Telnyx or Twilio
- Real-time transcription and call recording
- ~320ms latency on Premium tier

### AI Flexibility

![Create Agent](create-agent.png)

- Choose your price-to-quality tradeoff
- OpenAI GPT-4 Realtime, Google Gemini, or Cerebras Llama
- 13+ voice options

### Built-in Tools

- Contact management (search, create, update)
- Appointment booking (check availability, schedule, reschedule)
- Call controls (transfer, end call, DTMF)

### 30+ Integrations

![Integrations](integrations.png)

- CRM: HubSpot, Salesforce, Pipedrive, Zoho, GoHighLevel
- Calendars: Google Calendar, Outlook, Calendly, Cal.com
- E-commerce: Shopify (orders, inventory, customers)
- Communication: Slack, Gmail, SendGrid, SMS
- Data: Airtable, Notion, Google Sheets
- Payments: Stripe

### Website Widget

- Embed a voice agent on any website
- One line of code
- Domain allowlisting for security

---

## Pricing Tiers

Pick based on your budget and quality needs:

| Tier | Cost/Min | AI Provider | Latency | Best For |
|------|----------|-------------|---------|----------|
| **Premium** | $0.032 | OpenAI GPT-4 Realtime | ~320ms | Quality-first use cases |
| **Premium Mini** | $0.009 | OpenAI GPT-4o Mini Realtime | ~350ms | High volume, good quality |
| **Balanced** | $0.023 | Google Gemini 2.5 Flash | ~400ms | Speed + cost balance |
| **Budget** | $0.014 | Cerebras Llama 3.3 70B | ~530ms | Maximum savings |

**Example:** 1,000 calls/month × 5 min avg = 5,000 minutes

- Premium: ~$160/month AI + ~$50 telephony = **~$210/month**
- Budget: ~$70/month AI + ~$50 telephony = **~$120/month**

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Node.js 20+
- API keys for your chosen providers (OpenAI, Telnyx, etc.)

### Setup

```bash
# Clone the repo
git clone https://github.com/yourusername/voice-noob.git
cd voice-noob

# Copy environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Start PostgreSQL and Redis
docker-compose up -d

# Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000> and create your first agent.

---

## Tech Stack

**Voice & AI:** Pipecat, OpenAI Realtime, Google Gemini, Deepgram, ElevenLabs
**Backend:** FastAPI, PostgreSQL 17, Redis 7, SQLAlchemy 2.0
**Frontend:** Next.js 15, React 19, TypeScript, Tailwind, shadcn/ui
**Telephony:** Telnyx (primary), Twilio (optional)

---

## Project Structure

```text
voice-noob/
├── backend/           # FastAPI Python backend
│   ├── app/api/       # API routes
│   ├── app/services/  # Business logic & integrations
│   └── app/models/    # Database models
├── frontend/          # Next.js frontend
│   ├── src/app/       # Pages (dashboard, agents, CRM)
│   └── src/lib/       # API clients, utilities
└── docker-compose.yml # PostgreSQL + Redis
```

---

## Contributing

Pull requests welcome. For major changes, open an issue first.

---

## License

AGPL-3.0
