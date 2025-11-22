export interface PricingTier {
  id: string;
  name: string;
  description: string;
  costPerHour: number;
  costPerMinute: number;
  recommended?: boolean;
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
    id: "budget",
    name: "Budget",
    description: "Maximum cost savings - perfect for high-volume operations",
    costPerHour: 0.86,
    costPerMinute: 0.0143,
    features: [
      "56% cheaper than premium",
      "Ultra-fast: 450 tokens/sec",
      "Enterprise-grade quality",
      "All standard features",
    ],
    config: {
      llmProvider: "cerebras",
      llmModel: "llama-3.1-70b",
      sttProvider: "deepgram",
      sttModel: "nova-2",
      ttsProvider: "elevenlabs",
      ttsModel: "flash-v2.5",
      telephonyProvider: "telnyx",
    },
    performance: {
      latency: "~530ms",
      speed: "450 tokens/sec",
      quality: "Excellent",
    },
  },
  {
    id: "balanced",
    name: "Balanced",
    description: "Best performance-to-cost ratio with multimodal capabilities",
    costPerHour: 1.35,
    costPerMinute: 0.0225,
    recommended: true,
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
    id: "premium",
    name: "Premium",
    description: "Best quality with OpenAI's production-ready voice platform",
    costPerHour: 1.92,
    costPerMinute: 0.032,
    features: [
      "Lowest latency: ~320ms",
      "Best instruction following",
      "Production-tested",
      "Built-in tool connectors",
      "Premium support",
    ],
    config: {
      llmProvider: "openai-realtime",
      llmModel: "gpt-realtime",
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
  const premiumTier = PRICING_TIERS.find((t) => t.id === "premium")!;
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
