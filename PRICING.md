# Pricing Tiers & Cost Analysis

Complete cost breakdown for voice agent operations (November 2025).

## 💰 Pricing Tiers

### **Budget Tier** - $0.86/hour
**Best for**: High-volume operations, cost-conscious businesses

**Stack:**
- LLM: Cerebras Llama 3.1 70B
- STT: Deepgram Nova-2
- TTS: ElevenLabs Flash v2.5
- Telephony: Telnyx

**Performance:**
- Latency: ~530ms
- Speed: 450 tokens/sec
- Quality: Excellent

**Cost per minute**: $0.0143
**Savings vs Premium**: 56% cheaper

---

### **Balanced Tier** - $1.35/hour ⭐ RECOMMENDED
**Best for**: Most use cases, best value

**Stack:**
- LLM: Gemini 2.5 Flash (with Live API)
- STT: Built-in (Gemini)
- TTS: Built-in (Gemini, 30+ voices)
- Telephony: Telnyx

**Performance:**
- Latency: ~400ms
- Speed: 268 tokens/sec (fastest!)
- Quality: Excellent
- **Bonus**: Multimodal (voice + vision)

**Cost per minute**: $0.0225
**Savings vs Premium**: 30% cheaper

---

### **Premium Tier** - $1.92/hour
**Best for**: Enterprise, best quality, built-in connectors

**Stack:**
- LLM: OpenAI Realtime API (gpt-realtime)
- STT: Built-in (OpenAI)
- TTS: Built-in (OpenAI, voices: Cedar, Marin)
- Telephony: Telnyx

**Performance:**
- Latency: ~320ms (lowest)
- Speed: Good
- Quality: Best
- **Bonus**: 8 built-in tool connectors (Google Calendar, Gmail, etc.)

**Cost per minute**: $0.032

---

## 📊 Detailed Cost Breakdown

### Per-Minute Costs:

| Component | Budget | Balanced | Premium |
|-----------|--------|----------|---------|
| **LLM** | $0.0005 | $0.015 | $0.032 |
| **STT** | $0.0043 | Included | Included |
| **TTS** | $0.002 | Included | Included |
| **Telephony (in)** | $0.0075 | $0.0075 | $0.0075 |
| **Total (inbound)** | $0.0143 | $0.0225 | $0.0395 |
| **Total (outbound)** | $0.0193 | $0.0275 | $0.0425 |

### Monthly Cost Examples:

#### **1,000 calls/month (5 min avg) = 5,000 minutes**

| Tier | Monthly Cost | Annual Cost | vs Premium |
|------|--------------|-------------|------------|
| Budget | $72 | $864 | Save $1,488 (63%) |
| Balanced | $113 | $1,356 | Save $996 (42%) |
| Premium | $198 | $2,376 | Baseline |

#### **10,000 calls/month (5 min avg) = 50,000 minutes**

| Tier | Monthly Cost | Annual Cost | vs Premium |
|------|--------------|-------------|------------|
| Budget | $720 | $8,640 | Save $14,880 (63%) |
| Balanced | $1,125 | $13,500 | Save $9,960 (42%) |
| Premium | $1,975 | $23,700 | Baseline |

#### **100,000 calls/month (5 min avg) = 500,000 minutes**

| Tier | Monthly Cost | Annual Cost | vs Premium |
|------|--------------|-------------|------------|
| Budget | $7,200 | $86,400 | Save $148,800 (63%) |
| Balanced | $11,250 | $135,000 | Save $99,600 (42%) |
| Premium | $19,750 | $237,000 | Baseline |

### **At Scale (1M calls/month = 5M minutes)**

| Tier | Monthly | Annual | Savings vs Premium |
|------|---------|--------|-------------------|
| Budget | $72,000 | $864,000 | **$1,488,000/year** |
| Balanced | $112,500 | $1,350,000 | **$996,000/year** |
| Premium | $197,500 | $2,370,000 | Baseline |

---

## 🎯 Which Tier Should You Choose?

### Choose **Budget** if:
- ✅ High call volume (>10K calls/month)
- ✅ Cost is primary concern
- ✅ English-only or limited languages
- ✅ Simple use cases
- ✅ Don't need vision capabilities

**ROI**: Save up to $150K/year at scale

### Choose **Balanced** if: ⭐
- ✅ Want best performance-to-cost ratio
- ✅ Need multimodal (voice + vision)
- ✅ Want fastest responses (268 tok/sec)
- ✅ All-in-one simplicity (no separate STT/TTS)
- ✅ 30+ voices, 24+ languages

**ROI**: Save up to $100K/year at scale

### Choose **Premium** if:
- ✅ Enterprise requirements
- ✅ Need lowest latency (<350ms)
- ✅ Want built-in tool connectors (Google, Outlook, etc.)
- ✅ Production-tested reliability
- ✅ Best instruction following

**ROI**: Best quality, established platform

---

## 💡 Additional Costs

### Platform Infrastructure:
```
Monthly Platform Costs:
- Hosting (Fly.io): $35-110/month
- Database: Included in hosting
- Storage (recordings): $10-100/month
- Monitoring: $0-50/month (optional)

Total: ~$45-260/month regardless of call volume
```

### Phone Numbers (Telnyx):
```
- Local number: $0.08/month
- Toll-free: $2/month
- International: Varies by country
```

---

## 🔄 Switching Between Tiers

**Easy migration**: Change tier anytime via dashboard
- Settings auto-adjust to tier configuration
- No downtime
- Gradual rollout option

---

## 📈 ROI Calculator

**Example: Customer Support Center**
- 50K calls/month
- 8 min average duration
- 400K minutes/month

| Tier | Monthly Cost | Annual Cost |
|------|--------------|-------------|
| **Budget** | $5,760 | $69,120 |
| **Balanced** | $9,000 | $108,000 |
| **Premium** | $15,800 | $189,600 |

**Switching from Premium to Budget**: **Save $120,480/year**

---

## 🎁 Your Platform's Value Proposition

**vs Hosted Solutions (ElevenLabs, Vapi, Retell AI):**

| Feature | Your Platform | Hosted Solutions |
|---------|---------------|------------------|
| **Cost Control** | Choose your tier | Fixed pricing |
| **Provider Mix** | Any combination | Locked in |
| **Custom Tools** | Unlimited | Limited |
| **Data Ownership** | 100% yours | Shared |
| **Scaling** | Linear costs | Often tiered |

**Bottom Line**: Save 30-60% while maintaining full control! 🚀

---

## 📚 Sources

- [Gemini Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Deepgram Voice Agent API](https://deepgram.com/learn/introducing-ai-voice-agent-api)
- [Cerebras Pricing](https://www.cerebras.ai/pricing)
- [Groq Pricing](https://groq.com/pricing)
- [LLM Pricing Comparison 2025](https://intuitionlabs.ai/articles/llm-api-pricing-comparison-2025)
