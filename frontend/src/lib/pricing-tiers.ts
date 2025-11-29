export interface PricingTier {
  id: string;
  name: string;
  description: string;
  costPerHour: number;
  costPerMinute: number;
  recommended?: boolean;
  underConstruction?: boolean;
  features: string[];
  config: {
    llmProvider: string;
    llmModel: string;
    sttProvider: string;
    sttModel: string;
    ttsProvider: string;
    ttsModel: string;
    telephonyProvider: string;
  };
  performance: {
    latency: string;
    speed: string;
    quality: string;
  };
}

export const PRICING_TIERS: PricingTier[] = [
  {
    id: "premium",
    name: "Premium",
    description: "Best quality with OpenAI's latest gpt-realtime model",
    costPerHour: 1.92,
    costPerMinute: 0.032,
    recommended: true,
    features: [
      "Lowest latency: ~320ms",
      "Most natural & expressive voice",
      "Best instruction following",
      "New voices: marin, cedar",
      "Production-ready (Aug 2025)",
    ],
    config: {
      llmProvider: "openai-realtime",
      llmModel: "gpt-realtime-2025-08-28",
      sttProvider: "openai",
      sttModel: "built-in",
      ttsProvider: "openai",
      ttsModel: "built-in",
      telephonyProvider: "telnyx",
    },
    performance: {
      latency: "~320ms",
      speed: "Good",
      quality: "Best",
    },
  },
  {
    id: "premium-mini",
    name: "Premium Mini",
    description: "OpenAI Realtime at a fraction of the cost",
    costPerHour: 0.54,
    costPerMinute: 0.009,
    features: [
      "72% cheaper than Premium",
      "OpenAI Realtime quality",
      "Low latency: ~350ms",
      "Built-in tool connectors",
      "Great for high volume",
    ],
    config: {
      llmProvider: "openai-realtime",
      llmModel: "gpt-4o-mini-realtime",
      sttProvider: "openai",
      sttModel: "built-in",
      ttsProvider: "openai",
      ttsModel: "built-in",
      telephonyProvider: "telnyx",
    },
    performance: {
      latency: "~350ms",
      speed: "Good",
      quality: "Very Good",
    },
  },
  {
    id: "balanced",
    name: "Balanced",
    description: "Best performance-to-cost ratio with multimodal capabilities",
    costPerHour: 1.35,
    costPerMinute: 0.0225,
    underConstruction: true,
    features: [
      "53% cheaper than premium",
      "Fastest: 268 tokens/sec",
      "Multimodal (voice + vision)",
      "All-in-one simplicity",
      "30+ built-in voices",
    ],
    config: {
      llmProvider: "google",
      llmModel: "gemini-2.5-flash",
      sttProvider: "google",
      sttModel: "built-in",
      ttsProvider: "google",
      ttsModel: "built-in",
      telephonyProvider: "telnyx",
    },
    performance: {
      latency: "~400ms",
      speed: "268 tokens/sec",
      quality: "Excellent",
    },
  },
  {
    id: "budget",
    name: "Budget",
    description: "Maximum cost savings - perfect for high-volume operations",
    costPerHour: 0.86,
    costPerMinute: 0.0143,
    underConstruction: true,
    features: [
      "56% cheaper than premium",
      "Ultra-fast: 450 tokens/sec",
      "Enterprise-grade quality",
      "All standard features",
    ],
    config: {
      llmProvider: "cerebras",
      llmModel: "llama-3.3-70b",
      sttProvider: "deepgram",
      sttModel: "nova-3",
      ttsProvider: "elevenlabs",
      ttsModel: "eleven_flash_v2_5",
      telephonyProvider: "telnyx",
    },
    performance: {
      latency: "~530ms",
      speed: "450 tokens/sec",
      quality: "Excellent",
    },
  },
];

export function calculateMonthlyCost(
  tier: PricingTier,
  callsPerMonth: number,
  avgDurationMinutes: number,
  inboundPercentage: number = 50
): {
  totalMinutes: number;
  aiCost: number;
  telephonyCost: number;
  totalCost: number;
  costPerCall: number;
} {
  const totalMinutes = callsPerMonth * avgDurationMinutes;
  const inboundMinutes = totalMinutes * (inboundPercentage / 100);
  const outboundMinutes = totalMinutes - inboundMinutes;

  // AI costs (same for inbound/outbound)
  const aiCostPerMinute = tier.costPerMinute - (inboundPercentage >= 50 ? 0.0075 : 0.01);
  const aiCost = totalMinutes * aiCostPerMinute;

  // Telephony costs (different for inbound/outbound)
  const telephonyCost = inboundMinutes * 0.0075 + outboundMinutes * 0.01;

  const totalCost = aiCost + telephonyCost;
  const costPerCall = totalCost / callsPerMonth;

  return {
    totalMinutes,
    aiCost,
    telephonyCost,
    totalCost,
    costPerCall,
  };
}

export function compareTiers(
  callsPerMonth: number,
  avgDurationMinutes: number
): Array<{
  tier: PricingTier;
  cost: ReturnType<typeof calculateMonthlyCost>;
  savingsVsPremium: number;
}> {
  const premiumTier = PRICING_TIERS.find((t) => t.id === "premium");
  if (!premiumTier) throw new Error("Premium tier not found");
  const premiumCost = calculateMonthlyCost(premiumTier, callsPerMonth, avgDurationMinutes);

  return PRICING_TIERS.map((tier) => {
    const cost = calculateMonthlyCost(tier, callsPerMonth, avgDurationMinutes);
    const savingsVsPremium = premiumCost.totalCost - cost.totalCost;

    return {
      tier,
      cost,
      savingsVsPremium,
    };
  });
}
