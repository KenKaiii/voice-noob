"use client";

import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { TierSelector, TierComparison } from "@/components/tier-selector";
import { PRICING_TIERS } from "@/lib/pricing-tiers";
import { ChevronRight } from "lucide-react";

const agentFormSchema = z.object({
  // Step 1: Pricing & Basic
  pricingTier: z.enum(["budget", "balanced", "premium"]).default("balanced"),
  name: z.string().min(2, "Name must be at least 2 characters"),
  description: z.string().optional(),
  language: z.string().default("en-US"),
  systemPrompt: z.string().min(10, "System prompt is required"),

  // Step 2: Tools
  enabledTools: z.array(z.string()).default([]),

  // Step 3: Phone & Advanced
  phoneNumberId: z.string().optional(),
  enableRecording: z.boolean().default(true),
  enableTranscript: z.boolean().default(true),
});

type AgentFormValues = z.infer<typeof agentFormSchema>;

export default function NewAgentSimplifiedPage() {
  const [step, setStep] = useState(1);

  const form = useForm<AgentFormValues>({
    resolver: zodResolver(agentFormSchema),
    defaultValues: {
      pricingTier: "balanced",
      language: "en-US",
      enabledTools: [],
      enableRecording: true,
      enableTranscript: true,
    },
  });

  const selectedTier = PRICING_TIERS.find((t) => t.id === form.watch("pricingTier"));

  function onSubmit(data: AgentFormValues) {
    console.log("Creating agent with tier config:", {
      ...data,
      tierConfig: selectedTier?.config,
    });
    // TODO: API call to create agent
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Create Voice Agent</h1>
        <p className="text-muted-foreground">
          Simple setup with pricing tiers - all technical details handled for you
        </p>
      </div>

      {/* Progress Indicator */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            {[
              { num: 1, label: "Pricing & Setup" },
              { num: 2, label: "Tools" },
              { num: 3, label: "Review & Create" },
            ].map((s, idx) => (
              <div key={s.num} className="flex items-center gap-2 flex-1">
                <div className="flex items-center gap-3 flex-1">
                  <div
                    className={`h-10 w-10 rounded-full flex items-center justify-center text-sm font-semibold transition-all ${
                      s.num === step
                        ? "bg-primary text-primary-foreground ring-4 ring-primary/20"
                        : s.num < step
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {s.num < step ? "✓" : s.num}
                  </div>
                  <div className="flex flex-col">
                    <span
                      className={`text-sm font-medium ${
                        s.num === step ? "text-foreground" : "text-muted-foreground"
                      }`}
                    >
                      Step {s.num}
                    </span>
                    <span
                      className={`text-xs ${
                        s.num === step ? "text-foreground" : "text-muted-foreground"
                      }`}
                    >
                      {s.label}
                    </span>
                  </div>
                </div>
                {idx < 2 && (
                  <ChevronRight
                    className={`h-5 w-5 flex-shrink-0 ${
                      s.num < step ? "text-primary" : "text-muted-foreground"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          {/* Step 1: Pricing & Basic Info */}
          {step === 1 && (
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Choose Your Pricing Tier</CardTitle>
                  <CardDescription>
                    Select the right balance of cost and performance
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <TierSelector
                    selectedTier={form.watch("pricingTier")}
                    onTierChange={(tierId) =>
                      form.setValue("pricingTier", tierId as "budget" | "balanced" | "premium")
                    }
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Basic Information</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Agent Name</FormLabel>
                        <FormControl>
                          <Input placeholder="Customer Support Agent" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="description"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Description (optional)</FormLabel>
                        <FormControl>
                          <Textarea
                            placeholder="Handles customer inquiries..."
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="language"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Language</FormLabel>
                        <Select onValueChange={field.onChange} defaultValue={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="en-US">English (US)</SelectItem>
                            <SelectItem value="en-GB">English (UK)</SelectItem>
                            <SelectItem value="es-ES">Spanish</SelectItem>
                            <SelectItem value="fr-FR">French</SelectItem>
                            <SelectItem value="de-DE">German</SelectItem>
                            <SelectItem value="ja-JP">Japanese</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="systemPrompt"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>System Prompt</FormLabel>
                        <FormControl>
                          <Textarea
                            placeholder="You are a helpful customer support agent. Be polite, professional, and concise..."
                            className="min-h-[100px]"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Instructions that define your agent's personality
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>

              <div className="flex justify-end">
                <Button type="button" onClick={() => setStep(2)}>
                  Next: Configure Tools
                </Button>
              </div>
            </div>
          )}

          {/* Step 2: Tools */}
          {step === 2 && (
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Tools & Integrations</CardTitle>
                  <CardDescription>
                    Enable integrations for your agent (optional)
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                      Connect integrations on the{" "}
                      <a
                        href="/dashboard/integrations"
                        className="text-primary underline"
                        target="_blank"
                      >
                        Integrations page
                      </a>{" "}
                      first, then enable them here for this agent.
                    </p>

                    <div className="space-y-2">
                      {["google-calendar", "salesforce", "hubspot", "notion", "slack"].map(
                        (toolId) => (
                          <FormField
                            key={toolId}
                            control={form.control}
                            name="enabledTools"
                            render={({ field }) => {
                              const toolConfig = {
                                "google-calendar": {
                                  name: "Google Calendar",
                                  desc: "Schedule meetings, check availability",
                                },
                                salesforce: { name: "Salesforce", desc: "Access CRM data" },
                                hubspot: { name: "HubSpot", desc: "Manage contacts" },
                                notion: { name: "Notion", desc: "Query databases" },
                                slack: { name: "Slack", desc: "Send messages" },
                              }[toolId];

                              return (
                                <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                                  <FormControl>
                                    <input
                                      type="checkbox"
                                      className="h-4 w-4 mt-0.5"
                                      checked={field.value?.includes(toolId)}
                                      onChange={(e) => {
                                        const current = field.value || [];
                                        field.onChange(
                                          e.target.checked
                                            ? [...current, toolId]
                                            : current.filter((v) => v !== toolId)
                                        );
                                      }}
                                    />
                                  </FormControl>
                                  <div className="space-y-1 leading-none">
                                    <FormLabel className="font-medium cursor-pointer">
                                      {toolConfig?.name}
                                    </FormLabel>
                                    <FormDescription>{toolConfig?.desc}</FormDescription>
                                  </div>
                                </FormItem>
                              );
                            }}
                          />
                        )
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div className="flex justify-between">
                <Button type="button" variant="outline" onClick={() => setStep(1)}>
                  Back
                </Button>
                <Button type="button" onClick={() => setStep(3)}>
                  Next: Final Settings
                </Button>
              </div>
            </div>
          )}

          {/* Step 3: Phone & Advanced */}
          {step === 3 && (
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Phone Number</CardTitle>
                  <CardDescription>Assign a phone number (optional)</CardDescription>
                </CardHeader>
                <CardContent>
                  <FormField
                    control={form.control}
                    name="phoneNumberId"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Phone Number</FormLabel>
                        <Select onValueChange={field.onChange}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="No phone number assigned" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="none">No number assigned</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormDescription>
                          Purchase numbers on the Phone Numbers page
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Call Settings</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="enableRecording"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                        <div className="space-y-0.5">
                          <FormLabel className="text-base">Enable Call Recording</FormLabel>
                          <FormDescription>
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
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                        <div className="space-y-0.5">
                          <FormLabel className="text-base">Enable Transcripts</FormLabel>
                          <FormDescription>
                            Save conversation transcripts
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

              <Card className="border-primary/50 bg-primary/5">
                <CardHeader>
                  <CardTitle>Configuration Summary</CardTitle>
                  <CardDescription>Review your agent setup</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Pricing Tier:</span>
                      <div className="font-medium">{selectedTier?.name}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Cost:</span>
                      <div className="font-medium">
                        ${selectedTier?.costPerHour.toFixed(2)}/hour
                      </div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">LLM:</span>
                      <div className="font-mono text-xs">
                        {selectedTier?.config.llmModel}
                      </div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Performance:</span>
                      <div className="font-medium">{selectedTier?.performance.speed}</div>
                    </div>
                  </div>

                  {form.watch("enabledTools").length > 0 && (
                    <div>
                      <span className="text-muted-foreground text-sm">
                        Tools enabled:
                      </span>
                      <div className="font-medium text-sm">
                        {form.watch("enabledTools").length} integration(s)
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              <div className="flex justify-between">
                <Button type="button" variant="outline" onClick={() => setStep(2)}>
                  Back
                </Button>
                <Button type="submit">Create Agent</Button>
              </div>
            </div>
          )}
        </form>
      </Form>
    </div>
  );
}
