"use client";

import { useState, useMemo, useEffect, Fragment } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import * as z from "zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { createAgent, type CreateAgentRequest } from "@/lib/api/agents";
import { AVAILABLE_INTEGRATIONS } from "@/lib/integrations";
import { getLanguagesForTier, getFallbackLanguage } from "@/lib/languages";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ChevronDown, AlertTriangle, Shield, ShieldAlert } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { PRICING_TIERS } from "@/lib/pricing-tiers";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Sparkles,
  Zap,
  Crown,
  Bot,
  MessageSquare,
  Wrench,
  Settings,
  Play,
} from "lucide-react";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { cn } from "@/lib/utils";

// OpenAI Realtime API voices (only for Premium tier)
// marin and cedar are the new recommended voices (most natural and expressive)
const REALTIME_VOICES = [
  {
    id: "marin",
    name: "Marin",
    description: "Professional & clear (Recommended)",
    recommended: true,
  },
  {
    id: "cedar",
    name: "Cedar",
    description: "Natural & conversational (Recommended)",
    recommended: true,
  },
  { id: "shimmer", name: "Shimmer", description: "Energetic and expressive" },
  { id: "alloy", name: "Alloy", description: "Neutral and balanced" },
  { id: "coral", name: "Coral", description: "Warm and friendly" },
  { id: "echo", name: "Echo", description: "Warm and engaging" },
  { id: "sage", name: "Sage", description: "Calm and thoughtful" },
  { id: "verse", name: "Verse", description: "Versatile and expressive" },
  { id: "ash", name: "Ash", description: "Clear and precise" },
  { id: "ballad", name: "Ballad", description: "Melodic and smooth" },
] as const;

// Get integrations that have tools defined
const INTEGRATIONS_WITH_TOOLS = AVAILABLE_INTEGRATIONS.filter((i) => i.tools && i.tools.length > 0);

// Helper to get risk level badge variant and icon
function getRiskLevelBadge(level: "safe" | "moderate" | "high") {
  switch (level) {
    case "safe":
      return {
        variant: "safe" as const,
        icon: Shield,
      };
    case "moderate":
      return {
        variant: "moderate" as const,
        icon: AlertTriangle,
      };
    case "high":
      return {
        variant: "high" as const,
        icon: ShieldAlert,
      };
  }
}

const WIZARD_STEPS = [
  { id: 1, label: "Pricing", icon: Sparkles },
  { id: 2, label: "Basics", icon: Bot },
  { id: 3, label: "Prompt", icon: MessageSquare },
  { id: 4, label: "Tools", icon: Wrench },
  { id: 5, label: "Settings", icon: Settings },
] as const;

const agentFormSchema = z.object({
  pricingTier: z.enum(["budget", "balanced", "premium-mini", "premium"]).default("balanced"),
  name: z.string().min(2, "Name must be at least 2 characters"),
  description: z.string().optional(),
  language: z.string().default("en-US"),
  voice: z.string().default("marin"), // marin is the most natural & professional voice
  systemPrompt: z.string().min(10, "System prompt is required"),
  enabledTools: z.array(z.string()).default([]),
  enabledToolIds: z.record(z.string(), z.array(z.string())).default({}),
  phoneNumberId: z.string().optional(),
  enableRecording: z.boolean().default(true),
  enableTranscript: z.boolean().default(true),
});

type AgentFormValues = z.infer<typeof agentFormSchema>;

export default function CreateAgentPage() {
  const [step, setStep] = useState(1);
  const router = useRouter();

  const form = useForm<AgentFormValues>({
    resolver: zodResolver(agentFormSchema),
    defaultValues: {
      name: "",
      description: "",
      systemPrompt: "",
      pricingTier: "balanced",
      language: "en-US",
      voice: "marin",
      enabledTools: [],
      enabledToolIds: {},
      phoneNumberId: "",
      enableRecording: true,
      enableTranscript: true,
    },
  });

  const pricingTier = useWatch({ control: form.control, name: "pricingTier" });
  const enabledTools = useWatch({ control: form.control, name: "enabledTools" });
  const agentName = useWatch({ control: form.control, name: "name" });
  const systemPrompt = useWatch({ control: form.control, name: "systemPrompt" });
  const currentLanguage = useWatch({ control: form.control, name: "language" });

  const selectedTier = useMemo(
    () => PRICING_TIERS.find((t) => t.id === pricingTier),
    [pricingTier]
  );

  // Get available languages for the current pricing tier
  const availableLanguages = useMemo(() => getLanguagesForTier(pricingTier), [pricingTier]);

  // Reset language to fallback if current selection is not valid for new tier
  useEffect(() => {
    const fallback = getFallbackLanguage(currentLanguage, pricingTier);
    if (fallback !== currentLanguage) {
      form.setValue("language", fallback);
    }
  }, [pricingTier, currentLanguage, form]);

  const createAgentMutation = useMutation({
    mutationFn: createAgent,
    onSuccess: (agent) => {
      toast.success(`Agent "${agent.name}" created successfully!`);
      router.push("/dashboard/agents");
    },
    onError: (error: Error) => {
      toast.error(`Failed to create agent: ${error.message}`);
    },
  });

  function onSubmit(data: AgentFormValues) {
    // Derive enabled_tools (integration IDs) from enabledToolIds
    // An integration is enabled if it has at least one tool selected
    const enabledIntegrations = Object.entries(data.enabledToolIds)
      .filter(([, toolIds]) => toolIds.length > 0)
      .map(([integrationId]) => integrationId);

    const request: CreateAgentRequest = {
      name: data.name,
      description: data.description,
      pricing_tier: data.pricingTier,
      system_prompt: data.systemPrompt,
      language: data.language,
      voice:
        data.pricingTier === "premium" || data.pricingTier === "premium-mini"
          ? data.voice
          : undefined,
      enabled_tools: enabledIntegrations,
      enabled_tool_ids: data.enabledToolIds,
      phone_number_id: data.phoneNumberId,
      enable_recording: data.enableRecording,
      enable_transcript: data.enableTranscript,
    };
    createAgentMutation.mutate(request);
  }

  const validateStep = async (currentStep: number): Promise<boolean> => {
    switch (currentStep) {
      case 1:
        return true; // Pricing tier always has a default
      case 2:
        return form.trigger("name");
      case 3:
        return form.trigger("systemPrompt");
      case 4:
        return true; // Tools are optional
      case 5:
        return true; // Settings have defaults
      default:
        return true;
    }
  };

  const handleNext = async () => {
    const isValid = await validateStep(step);
    if (isValid && step < 5) {
      setStep(step + 1);
    }
  };

  const handleBack = () => {
    if (step > 1) setStep(step - 1);
  };

  const getTierIcon = (tierId: string) => {
    switch (tierId) {
      case "budget":
        return Zap;
      case "balanced":
        return Sparkles;
      case "premium-mini":
        return Sparkles;
      case "premium":
        return Crown;
      default:
        return Sparkles;
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
          <Link href="/dashboard/agents">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-xl font-semibold">Create Voice Agent</h1>
          <p className="text-sm text-muted-foreground">
            Step {step} of 5 &middot; {WIZARD_STEPS[step - 1]?.label ?? ""}
          </p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="grid grid-cols-[1fr_1.5rem_1fr_1.5rem_1fr_1.5rem_1fr_1.5rem_1fr] items-center">
        {WIZARD_STEPS.map((s, idx) => {
          const Icon = s.icon;
          const isActive = s.id === step;
          const isCompleted = s.id < step;
          const isNextStep = s.id === step + 1;
          const prevCompleted = idx > 0 && step > idx;

          return (
            <Fragment key={s.id}>
              {/* Step card */}
              <button
                type="button"
                onClick={() => s.id < step && setStep(s.id)}
                disabled={s.id > step}
                className={cn(
                  "relative z-10 flex items-center gap-2 rounded-lg border p-2 transition-all duration-300",
                  isActive &&
                    "border-primary bg-primary/10 shadow-[0_0_12px_hsl(var(--primary)/0.4)] ring-1 ring-primary",
                  isCompleted &&
                    "cursor-pointer border-primary bg-primary/5 shadow-[0_0_8px_hsl(var(--primary)/0.3)] hover:bg-primary/10",
                  !isActive && !isCompleted && "cursor-not-allowed border-border bg-muted/30",
                  isNextStep && "border-primary/30"
                )}
              >
                <div
                  className={cn(
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-medium transition-all duration-300",
                    isActive &&
                      "bg-primary text-primary-foreground shadow-[0_0_8px_hsl(var(--primary))]",
                    isCompleted && "bg-primary text-primary-foreground",
                    !isActive && !isCompleted && "bg-muted text-muted-foreground"
                  )}
                >
                  {isCompleted ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : (
                    <Icon className="h-3.5 w-3.5" />
                  )}
                </div>
                <span
                  className={cn(
                    "hidden text-xs font-medium sm:block",
                    isActive && "text-foreground",
                    isCompleted && "text-foreground",
                    !isActive && !isCompleted && "text-muted-foreground"
                  )}
                >
                  {s.label}
                </span>

                {/* Active step pulsing glow */}
                {isActive && (
                  <div className="absolute inset-0 -z-10 animate-pulse-glow rounded-lg bg-primary/10" />
                )}

                {/* Left connector point - where line enters card */}
                {idx > 0 && (
                  <div
                    className={cn(
                      "absolute -left-1 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full transition-all duration-300",
                      prevCompleted || isActive
                        ? "bg-primary shadow-[0_0_6px_hsl(var(--primary))]"
                        : "bg-border"
                    )}
                  />
                )}

                {/* Right connector point - where line exits card */}
                {idx < WIZARD_STEPS.length - 1 && (
                  <div
                    className={cn(
                      "absolute -right-1 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full transition-all duration-300",
                      isCompleted ? "bg-primary shadow-[0_0_6px_hsl(var(--primary))]" : "bg-border"
                    )}
                  />
                )}
              </button>

              {/* Connector line between steps */}
              {idx < WIZARD_STEPS.length - 1 && (
                <div className="relative -mx-1 h-1 overflow-hidden">
                  {/* Base track */}
                  <div className="absolute inset-0 bg-border/50" />
                  {/* Completed glow line */}
                  {isCompleted && (
                    <>
                      <div className="absolute inset-0 bg-primary shadow-[0_0_8px_hsl(var(--primary)),0_0_16px_hsl(var(--primary)/0.5)]" />
                      {/* Shimmer */}
                      <div
                        className="absolute inset-0 animate-shimmer-flow bg-gradient-to-r from-transparent via-white/50 to-transparent"
                        style={{ animationDelay: `${idx * 0.3}s` }}
                      />
                    </>
                  )}
                </div>
              )}
            </Fragment>
          );
        })}
      </div>

      <Form {...form}>
        <form
          onSubmit={(e) => {
            void form.handleSubmit(onSubmit)(e);
          }}
        >
          {/* Step 1: Pricing Tier */}
          {step === 1 && (
            <Card>
              <CardContent className="p-6">
                <div className="mb-4">
                  <h2 className="text-lg font-medium">Choose Your Pricing Tier</h2>
                  <p className="text-sm text-muted-foreground">
                    Select the right balance of cost and quality for your use case
                  </p>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  {PRICING_TIERS.map((tier) => {
                    const TierIcon = getTierIcon(tier.id);
                    const isSelected = pricingTier === tier.id;

                    return (
                      <button
                        key={tier.id}
                        type="button"
                        onClick={() =>
                          form.setValue(
                            "pricingTier",
                            tier.id as "budget" | "balanced" | "premium-mini" | "premium"
                          )
                        }
                        className={cn(
                          "relative flex flex-col rounded-lg border p-4 text-left transition-all hover:border-primary/50",
                          isSelected && "border-primary bg-primary/5 ring-2 ring-primary"
                        )}
                      >
                        {tier.recommended && (
                          <Badge className="absolute -top-2 right-3 text-[10px]">Popular</Badge>
                        )}
                        <div className="mb-3 flex items-center gap-2">
                          <div
                            className={cn(
                              "flex h-8 w-8 items-center justify-center rounded-md",
                              isSelected ? "bg-primary text-primary-foreground" : "bg-muted"
                            )}
                          >
                            <TierIcon className="h-4 w-4" />
                          </div>
                          <div>
                            <div className="font-medium">{tier.name}</div>
                            <div className="text-xs text-muted-foreground">
                              ${tier.costPerHour.toFixed(2)}/hr
                            </div>
                          </div>
                        </div>
                        <p className="mb-3 text-xs text-muted-foreground">{tier.description}</p>
                        <div className="space-y-1 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">Speed</span>
                            <span className="font-medium">{tier.performance.speed}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">Quality</span>
                            <span className="font-medium">{tier.performance.quality}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">Model</span>
                            <span className="font-mono text-[10px]">{tier.config.llmModel}</span>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Step 2: Basic Info */}
          {step === 2 && (
            <Card>
              <CardContent className="space-y-4 p-6">
                <div className="mb-2">
                  <h2 className="text-lg font-medium">Basic Information</h2>
                  <p className="text-sm text-muted-foreground">
                    Give your agent a name and identity
                  </p>
                </div>

                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Agent Name *</FormLabel>
                      <FormControl>
                        <Input placeholder="Customer Support Agent" {...field} />
                      </FormControl>
                      <FormDescription>A friendly name to identify your agent</FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="description"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Description</FormLabel>
                      <FormControl>
                        <Textarea
                          placeholder="Handles customer inquiries and support requests..."
                          className="min-h-[80px]"
                          {...field}
                        />
                      </FormControl>
                      <FormDescription>Optional description for your reference</FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <div className="grid gap-4 md:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="language"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Language ({availableLanguages.length} available)</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent className="max-h-[300px]">
                            {availableLanguages.map((lang) => (
                              <SelectItem key={lang.code} value={lang.code}>
                                {lang.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {(pricingTier === "premium" || pricingTier === "premium-mini") && (
                    <FormField
                      control={form.control}
                      name="voice"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Voice</FormLabel>
                          <Select onValueChange={field.onChange} value={field.value}>
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue placeholder="Select voice" />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {REALTIME_VOICES.map((voice) => (
                                <SelectItem key={voice.id} value={voice.id}>
                                  {voice.name} - {voice.description}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Step 3: System Prompt */}
          {step === 3 && (
            <Card>
              <CardContent className="space-y-4 p-6">
                <div className="mb-2">
                  <h2 className="flex items-center gap-2 text-lg font-medium">
                    System Prompt
                    <InfoTooltip content="The system prompt defines how your agent behaves. Include its role, personality, guidelines, and any rules it should follow. This is the most important setting." />
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    Define your agent&apos;s personality and behavior
                  </p>
                </div>

                <FormField
                  control={form.control}
                  name="systemPrompt"
                  render={({ field }) => {
                    const charCount = field.value?.length ?? 0;
                    const isOptimal = charCount >= 100 && charCount <= 2000;
                    const isTooShort = charCount > 0 && charCount < 100;

                    return (
                      <FormItem>
                        <div className="flex items-center justify-between">
                          <FormLabel>Instructions *</FormLabel>
                          <span
                            className={cn(
                              "text-xs",
                              isOptimal && "text-green-600",
                              isTooShort && "text-yellow-600"
                            )}
                          >
                            {charCount} characters
                            {isTooShort && " (aim for 100+)"}
                          </span>
                        </div>
                        <FormControl>
                          <Textarea
                            placeholder={`You are a helpful customer support agent for [Company Name].

Your role:
- Answer questions about our products and services
- Help customers troubleshoot issues
- Be polite, professional, and concise

Guidelines:
- Keep responses brief and to the point
- If you don't know something, say so honestly
- Always offer to escalate to a human if needed`}
                            className="min-h-[240px] font-mono text-sm"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Tell your agent who they are, how to behave, and what rules to follow
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    );
                  }}
                />
              </CardContent>
            </Card>
          )}

          {/* Step 4: Tools */}
          {step === 4 && (
            <Card>
              <CardContent className="space-y-4 p-6">
                <div className="mb-2">
                  <h2 className="flex items-center gap-2 text-lg font-medium">
                    Tools & Integrations
                    <InfoTooltip content="Tools give your agent abilities like looking up customer info or booking appointments. Enable integrations and select which specific tools your agent can access." />
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    Enable integrations and select which tools your agent can access. High-risk
                    tools (like cancellations) are disabled by default for security.
                  </p>
                </div>

                <div className="space-y-3">
                  {INTEGRATIONS_WITH_TOOLS.map((integration) => (
                    <FormField
                      key={integration.id}
                      control={form.control}
                      name="enabledTools"
                      render={({ field }) => {
                        const isEnabled = field.value?.includes(integration.id);
                        return (
                          <Collapsible>
                            <div className="rounded-lg border">
                              <div className="flex items-center justify-between p-4">
                                <div className="flex items-center space-x-3">
                                  <Checkbox
                                    checked={isEnabled}
                                    onCheckedChange={(checked) => {
                                      const current = field.value ?? [];
                                      if (checked) {
                                        field.onChange([...current, integration.id]);
                                        // Auto-enable default tools when integration is enabled
                                        const defaultTools =
                                          integration.tools
                                            ?.filter((t) => t.defaultEnabled)
                                            .map((t) => t.id) ?? [];
                                        if (defaultTools.length > 0) {
                                          const currentToolIds =
                                            form.getValues("enabledToolIds") ?? {};
                                          form.setValue("enabledToolIds", {
                                            ...currentToolIds,
                                            [integration.id]: defaultTools,
                                          });
                                        }
                                      } else {
                                        field.onChange(current.filter((v) => v !== integration.id));
                                        // Clear tool selection when integration is disabled
                                        const currentToolIds =
                                          form.getValues("enabledToolIds") ?? {};
                                        const { [integration.id]: _removed, ...rest } =
                                          currentToolIds;
                                        form.setValue("enabledToolIds", rest);
                                      }
                                    }}
                                  />
                                  <div>
                                    <div className="flex items-center gap-2">
                                      <span className="font-medium">{integration.name}</span>
                                      {integration.isBuiltIn && (
                                        <Badge variant="secondary" className="text-xs">
                                          Built-in
                                        </Badge>
                                      )}
                                    </div>
                                    <p className="text-sm text-muted-foreground">
                                      {integration.description}
                                    </p>
                                  </div>
                                </div>
                                {isEnabled && integration.tools && integration.tools.length > 0 && (
                                  <CollapsibleTrigger asChild>
                                    <Button variant="ghost" size="sm">
                                      <ChevronDown className="h-4 w-4" />
                                      <span className="ml-1">
                                        {form.watch(`enabledToolIds.${integration.id}`)?.length ??
                                          0}{" "}
                                        / {integration.tools.length} tools
                                      </span>
                                    </Button>
                                  </CollapsibleTrigger>
                                )}
                              </div>

                              {isEnabled && integration.tools && integration.tools.length > 0 && (
                                <CollapsibleContent>
                                  <div className="border-t bg-muted/30 p-4">
                                    <div className="mb-3 flex items-center justify-between">
                                      <span className="text-sm font-medium">Available Tools</span>
                                      <div className="flex gap-2">
                                        <Button
                                          type="button"
                                          variant="outline"
                                          size="sm"
                                          onClick={() => {
                                            const allToolIds =
                                              integration.tools?.map((t) => t.id) ?? [];
                                            const currentToolIds =
                                              form.getValues("enabledToolIds") ?? {};
                                            form.setValue("enabledToolIds", {
                                              ...currentToolIds,
                                              [integration.id]: allToolIds,
                                            });
                                          }}
                                        >
                                          Select All
                                        </Button>
                                        <Button
                                          type="button"
                                          variant="outline"
                                          size="sm"
                                          onClick={() => {
                                            const currentToolIds =
                                              form.getValues("enabledToolIds") ?? {};
                                            form.setValue("enabledToolIds", {
                                              ...currentToolIds,
                                              [integration.id]: [],
                                            });
                                          }}
                                        >
                                          Clear All
                                        </Button>
                                      </div>
                                    </div>
                                    <div className="space-y-2">
                                      {integration.tools.map((tool) => {
                                        const riskBadge = getRiskLevelBadge(tool.riskLevel);
                                        const RiskIcon = riskBadge.icon;
                                        const currentTools =
                                          form.watch(`enabledToolIds.${integration.id}`) ?? [];
                                        const isToolEnabled = currentTools.includes(tool.id);
                                        return (
                                          <div
                                            key={tool.id}
                                            className="flex items-center justify-between rounded-md border bg-background p-3"
                                          >
                                            <div className="flex items-center space-x-3">
                                              <Checkbox
                                                checked={isToolEnabled}
                                                onCheckedChange={(checked) => {
                                                  const enabledToolIds =
                                                    form.getValues("enabledToolIds") ?? {};
                                                  const toolsForIntegration =
                                                    enabledToolIds[integration.id] ?? [];
                                                  const newTools = checked
                                                    ? [...toolsForIntegration, tool.id]
                                                    : toolsForIntegration.filter(
                                                        (t) => t !== tool.id
                                                      );
                                                  form.setValue("enabledToolIds", {
                                                    ...enabledToolIds,
                                                    [integration.id]: newTools,
                                                  });
                                                }}
                                              />
                                              <div>
                                                <span className="text-sm font-medium">
                                                  {tool.name}
                                                </span>
                                                <p className="text-xs text-muted-foreground">
                                                  {tool.description}
                                                </p>
                                              </div>
                                            </div>
                                            <Badge variant={riskBadge.variant}>
                                              <RiskIcon className="mr-1 h-3 w-3" />
                                              {tool.riskLevel}
                                            </Badge>
                                          </div>
                                        );
                                      })}
                                    </div>
                                  </div>
                                </CollapsibleContent>
                              )}
                            </div>
                          </Collapsible>
                        );
                      }}
                    />
                  ))}
                </div>

                <div className="rounded-lg border border-dashed p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">Need more integrations?</p>
                      <p className="text-xs text-muted-foreground">
                        Connect Google Calendar, Salesforce, HubSpot and more
                      </p>
                    </div>
                    <Button variant="outline" size="sm" asChild>
                      <Link href="/dashboard/integrations" target="_blank">
                        Manage Integrations
                      </Link>
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Step 5: Settings & Review */}
          {step === 5 && (
            <div className="space-y-4">
              <Card>
                <CardContent className="space-y-4 p-6">
                  <div className="mb-2">
                    <h2 className="text-lg font-medium">Call Settings</h2>
                    <p className="text-sm text-muted-foreground">
                      Configure recording and transcription
                    </p>
                  </div>

                  <FormField
                    control={form.control}
                    name="enableRecording"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel className="text-sm font-medium">Call Recording</FormLabel>
                          <FormDescription className="text-xs">
                            Record all calls for quality assurance
                          </FormDescription>
                        </div>
                        <FormControl>
                          <Switch checked={field.value} onCheckedChange={field.onChange} />
                        </FormControl>
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="enableTranscript"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel className="text-sm font-medium">Transcripts</FormLabel>
                          <FormDescription className="text-xs">
                            Save searchable conversation transcripts
                          </FormDescription>
                        </div>
                        <FormControl>
                          <Switch checked={field.value} onCheckedChange={field.onChange} />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>

              {/* Summary Card */}
              <Card className="border-primary/30 bg-primary/5">
                <CardContent className="p-6">
                  <h2 className="mb-4 text-lg font-medium">Review Your Agent</h2>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-3">
                      <div>
                        <p className="text-xs text-muted-foreground">Name</p>
                        <p className="font-medium">{agentName || "Not set"}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Pricing Tier</p>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{selectedTier?.name}</span>
                          <Badge variant="outline" className="text-[10px]">
                            ${selectedTier?.costPerHour.toFixed(2)}/hr
                          </Badge>
                        </div>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">AI Model</p>
                        <p className="font-mono text-sm">{selectedTier?.config.llmModel}</p>
                      </div>
                    </div>

                    <div className="space-y-3">
                      <div>
                        <p className="text-xs text-muted-foreground">System Prompt</p>
                        <p className="text-sm">
                          {systemPrompt
                            ? `${systemPrompt.slice(0, 80)}${systemPrompt.length > 80 ? "..." : ""}`
                            : "Not set"}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Tools Enabled</p>
                        <p className="font-medium">
                          {enabledTools.length > 0
                            ? `${enabledTools.length} tool${enabledTools.length > 1 ? "s" : ""}`
                            : "None"}
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Navigation */}
          <div className="mt-6 flex items-center justify-between">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleBack}
              disabled={step === 1}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>

            {step < 5 ? (
              <Button type="button" size="sm" onClick={() => void handleNext()}>
                Next
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            ) : (
              <Button type="submit" size="sm" disabled={createAgentMutation.isPending}>
                <Play className="mr-2 h-4 w-4" />
                {createAgentMutation.isPending ? "Creating..." : "Create Agent"}
              </Button>
            )}
          </div>
        </form>
      </Form>
    </div>
  );
}
