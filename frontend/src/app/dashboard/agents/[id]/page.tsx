"use client";

import { use } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import * as z from "zod";
import Link from "next/link";
import { getAgent, updateAgent, deleteAgent, type UpdateAgentRequest } from "@/lib/api/agents";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, ArrowLeft, Loader2, Trash2, FolderOpen } from "lucide-react";
import { api } from "@/lib/api";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Checkbox } from "@/components/ui/checkbox";

interface Workspace {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
}

interface AgentWorkspace {
  workspace_id: string;
  workspace_name: string;
}

const agentFormSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  description: z.string().optional(),
  language: z.string().min(1, "Please select a language"),

  // Voice Settings
  ttsProvider: z.enum(["elevenlabs", "openai", "google"]),
  elevenLabsModel: z.string().default("turbo-v2.5"),
  elevenLabsVoiceId: z.string().optional(),
  ttsSpeed: z.number().min(0.5).max(2).default(1),

  // STT Settings
  sttProvider: z.enum(["deepgram", "openai", "google"]),
  deepgramModel: z.string().default("nova-3"),

  // LLM Settings
  llmProvider: z.enum(["openai", "openai-realtime", "anthropic", "google"]),
  llmModel: z.string().default("gpt-4o"),
  systemPrompt: z.string().min(10, "System prompt is required"),
  temperature: z.number().min(0).max(2).default(0.7),
  maxTokens: z.number().min(100).max(16000).default(2000),

  // Telephony
  telephonyProvider: z.enum(["telnyx", "twilio"]),
  phoneNumberId: z.string().optional(),

  // Advanced
  enableRecording: z.boolean().default(true),
  enableTranscript: z.boolean().default(true),
  turnDetectionMode: z.enum(["server-vad", "pushToTalk"]).default("server-vad"),
  isActive: z.boolean().default(true),

  // Tools & Integrations
  enabledTools: z.array(z.string()).default([]),

  // Workspaces
  selectedWorkspaces: z.array(z.string()).default([]),
});

type AgentFormValues = z.infer<typeof agentFormSchema>;

interface EditAgentPageProps {
  params: Promise<{ id: string }>;
}

export default function EditAgentPage({ params }: EditAgentPageProps) {
  const { id: agentId } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();

  const {
    data: agent,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["agent", agentId],
    queryFn: () => getAgent(agentId),
  });

  // Fetch all workspaces
  const { data: workspaces = [] } = useQuery({
    queryKey: ["workspaces"],
    queryFn: async () => {
      const response = await api.get<Workspace[]>("/api/v1/workspaces");
      return response.data;
    },
  });

  // Fetch agent's current workspace assignments
  const { data: agentWorkspaces = [] } = useQuery({
    queryKey: ["agent-workspaces", agentId],
    queryFn: async () => {
      const response = await api.get<AgentWorkspace[]>(`/api/v1/workspaces/agent/${agentId}`);
      return response.data;
    },
    enabled: !!agentId,
  });

  const form = useForm<AgentFormValues>({
    resolver: zodResolver(agentFormSchema),
    values: agent
      ? {
          name: agent.name,
          description: agent.description ?? "",
          language: agent.language,
          ttsProvider: "elevenlabs",
          elevenLabsModel: "turbo-v2.5",
          elevenLabsVoiceId: undefined,
          ttsSpeed: 1,
          sttProvider: "deepgram",
          deepgramModel: "nova-3",
          llmProvider: agent.pricing_tier === "premium" ? "openai-realtime" : "openai",
          llmModel: agent.pricing_tier === "premium" ? "gpt-realtime" : "gpt-4o",
          systemPrompt: agent.system_prompt,
          temperature: 0.7,
          maxTokens: 2000,
          telephonyProvider: "telnyx",
          phoneNumberId: agent.phone_number_id ?? undefined,
          enableRecording: agent.enable_recording,
          enableTranscript: agent.enable_transcript,
          turnDetectionMode: "server-vad",
          isActive: agent.is_active,
          enabledTools: agent.enabled_tools,
          selectedWorkspaces: agentWorkspaces.map((aw) => aw.workspace_id),
        }
      : undefined,
  });

  const updateAgentMutation = useMutation({
    mutationFn: (data: UpdateAgentRequest) => updateAgent(agentId, data),
    onSuccess: () => {
      toast.success("Agent updated successfully");
      void queryClient.invalidateQueries({ queryKey: ["agents"] });
      void queryClient.invalidateQueries({ queryKey: ["agent", agentId] });
      router.push("/dashboard/agents");
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to update agent");
    },
  });

  const deleteAgentMutation = useMutation({
    mutationFn: () => deleteAgent(agentId),
    onSuccess: () => {
      toast.success("Agent deleted successfully");
      void queryClient.invalidateQueries({ queryKey: ["agents"] });
      router.push("/dashboard/agents");
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to delete agent");
    },
  });

  const assignWorkspacesMutation = useMutation({
    mutationFn: async (workspaceIds: string[]) => {
      await api.put(`/api/v1/workspaces/agent/${agentId}/workspaces`, {
        workspace_ids: workspaceIds,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["agent-workspaces", agentId] });
    },
  });

  async function onSubmit(data: AgentFormValues) {
    // Determine pricing tier based on LLM provider
    let pricingTier: "budget" | "balanced" | "premium" = "balanced";
    if (data.llmProvider === "openai-realtime") {
      pricingTier = "premium";
    } else if (data.llmModel === "gpt-4o-mini" || data.llmModel === "claude-haiku-4-5") {
      pricingTier = "budget";
    }

    const request: UpdateAgentRequest = {
      name: data.name,
      description: data.description,
      pricing_tier: pricingTier,
      system_prompt: data.systemPrompt,
      language: data.language,
      enabled_tools: data.enabledTools,
      phone_number_id: data.phoneNumberId,
      enable_recording: data.enableRecording,
      enable_transcript: data.enableTranscript,
      is_active: data.isActive,
    };

    // Update agent and workspaces
    try {
      await Promise.all([
        updateAgentMutation.mutateAsync(request),
        assignWorkspacesMutation.mutateAsync(data.selectedWorkspaces),
      ]);
    } catch {
      // Error handling is done in individual mutations
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" asChild>
          <Link href="/dashboard/agents">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Agents
          </Link>
        </Button>
        <Card className="border-destructive">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <AlertCircle className="mb-4 h-16 w-16 text-destructive" />
            <h3 className="mb-2 text-lg font-semibold">Agent not found</h3>
            <p className="mb-4 text-center text-sm text-muted-foreground">
              {error instanceof Error
                ? error.message
                : "The agent you're looking for doesn't exist"}
            </p>
            <Button asChild>
              <Link href="/dashboard/agents">Return to Agents</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/dashboard/agents">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold tracking-tight">Edit Agent</h1>
              <Badge variant={agent.is_active ? "default" : "secondary"}>
                {agent.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
            <p className="text-muted-foreground">Update configuration for {agent.name}</p>
          </div>
        </div>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="destructive" size="sm">
              <Trash2 className="mr-2 h-4 w-4" />
              Delete Agent
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Are you sure?</AlertDialogTitle>
              <AlertDialogDescription>
                This action cannot be undone. This will permanently delete the agent &ldquo;
                {agent.name}&rdquo; and all associated call history.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => deleteAgentMutation.mutate()}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                {deleteAgentMutation.isPending ? "Deleting..." : "Delete"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>

      <Form {...form}>
        <form
          onSubmit={(e) => {
            void form.handleSubmit(onSubmit)(e);
          }}
          className="space-y-6"
        >
          <Tabs defaultValue="basic" className="w-full">
            <TabsList className="grid w-full grid-cols-5">
              <TabsTrigger value="basic">Basic</TabsTrigger>
              <TabsTrigger value="voice">Voice & Speech</TabsTrigger>
              <TabsTrigger value="llm">AI Model</TabsTrigger>
              <TabsTrigger value="tools">Tools</TabsTrigger>
              <TabsTrigger value="advanced">Advanced</TabsTrigger>
            </TabsList>

            <TabsContent value="basic" className="mt-6 space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Basic Information</CardTitle>
                  <CardDescription>General settings for your voice agent</CardDescription>
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
                        <FormDescription>A friendly name to identify this agent</FormDescription>
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
                            placeholder="Handles customer inquiries and support"
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
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Select a language" />
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
                    name="selectedWorkspaces"
                    render={() => (
                      <FormItem>
                        <div className="mb-4">
                          <FormLabel className="flex items-center gap-2 text-base">
                            <FolderOpen className="h-4 w-4" />
                            Workspaces
                          </FormLabel>
                          <FormDescription>
                            Assign this agent to workspaces. CRM contacts and appointments in these
                            workspaces will be accessible to this agent.
                          </FormDescription>
                        </div>
                        {workspaces.length === 0 ? (
                          <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
                            No workspaces created yet.{" "}
                            <Link href="/dashboard/workspaces" className="text-primary underline">
                              Create a workspace
                            </Link>{" "}
                            to organize your contacts and appointments.
                          </div>
                        ) : (
                          <div className="space-y-2">
                            {workspaces.map((workspace) => (
                              <FormField
                                key={workspace.id}
                                control={form.control}
                                name="selectedWorkspaces"
                                render={({ field }) => (
                                  <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-3">
                                    <FormControl>
                                      <Checkbox
                                        checked={field.value?.includes(workspace.id)}
                                        onCheckedChange={(checked: boolean) => {
                                          const current = field.value || [];
                                          field.onChange(
                                            checked
                                              ? [...current, workspace.id]
                                              : current.filter((v) => v !== workspace.id)
                                          );
                                        }}
                                      />
                                    </FormControl>
                                    <div className="space-y-1 leading-none">
                                      <FormLabel className="cursor-pointer font-medium">
                                        {workspace.name}
                                        {workspace.is_default && (
                                          <Badge variant="secondary" className="ml-2">
                                            Default
                                          </Badge>
                                        )}
                                      </FormLabel>
                                      {workspace.description && (
                                        <FormDescription>{workspace.description}</FormDescription>
                                      )}
                                    </div>
                                  </FormItem>
                                )}
                              />
                            ))}
                          </div>
                        )}
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="isActive"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                        <div className="space-y-0.5">
                          <FormLabel className="text-base">Active Status</FormLabel>
                          <FormDescription>Enable or disable this agent</FormDescription>
                        </div>
                        <FormControl>
                          <Switch checked={field.value} onCheckedChange={field.onChange} />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="voice" className="mt-6 space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Text-to-Speech (TTS)</CardTitle>
                  <CardDescription>Configure how your agent speaks</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="ttsProvider"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>TTS Provider</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="elevenlabs">ElevenLabs (Recommended)</SelectItem>
                            <SelectItem value="openai">OpenAI TTS</SelectItem>
                            <SelectItem value="google">Google Gemini TTS</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormDescription>Choose your text-to-speech provider</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="elevenLabsModel"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>ElevenLabs Model</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="turbo-v2.5">
                              Turbo v2.5 (Recommended - Best Quality)
                            </SelectItem>
                            <SelectItem value="flash-v2.5">
                              Flash v2.5 (Fastest - 75ms latency)
                            </SelectItem>
                            <SelectItem value="eleven-multilingual-v2">
                              Multilingual v2 (29 languages)
                            </SelectItem>
                          </SelectContent>
                        </Select>
                        <FormDescription>
                          Turbo v2.5: ~300ms latency, best quality | Flash v2.5: ~75ms latency
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="elevenLabsVoiceId"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Voice</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Select a voice" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="21m00Tcm4TlvDq8ikWAM">
                              Rachel (Female, American)
                            </SelectItem>
                            <SelectItem value="ErXwobaYiN019PkySvjV">
                              Antoni (Male, American)
                            </SelectItem>
                            <SelectItem value="MF3mGyEYCl7XYWbV9V6O">
                              Elli (Female, American)
                            </SelectItem>
                            <SelectItem value="pNInz6obpgDQGcFmaJgB">
                              Adam (Male, American)
                            </SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Speech-to-Text (STT)</CardTitle>
                  <CardDescription>Configure how your agent listens</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="sttProvider"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>STT Provider</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="deepgram">Deepgram (Recommended)</SelectItem>
                            <SelectItem value="openai">OpenAI Whisper</SelectItem>
                            <SelectItem value="google">Google Gemini STT</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormDescription>
                          Deepgram Nova-3: 6.84% WER, multilingual, PII redaction
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="deepgramModel"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Deepgram Model</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="nova-3">Nova-3 (Latest - 54% better WER)</SelectItem>
                            <SelectItem value="nova-2">
                              Nova-2 (25% cheaper, still excellent)
                            </SelectItem>
                            <SelectItem value="enhanced">Enhanced</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormDescription>
                          Nova-3: Multilingual, keyterm prompting, PII redaction
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="llm" className="mt-6 space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Language Model Configuration</CardTitle>
                  <CardDescription>Configure the AI brain of your voice agent</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="llmProvider"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>LLM Provider</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="openai-realtime">
                              OpenAI Realtime (Recommended)
                            </SelectItem>
                            <SelectItem value="openai">OpenAI Standard</SelectItem>
                            <SelectItem value="anthropic">Anthropic Claude</SelectItem>
                            <SelectItem value="google">Google Gemini</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormDescription>
                          Realtime API: End-to-end speech, SIP support, production-ready
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="llmModel"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Model</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="gpt-realtime">
                              gpt-realtime (Best for Voice - Nov 2025)
                            </SelectItem>
                            <SelectItem value="gpt-4o">
                              GPT-4o (Multimodal - 232ms latency)
                            </SelectItem>
                            <SelectItem value="gpt-4o-mini">
                              GPT-4o-mini (25x cheaper, fast)
                            </SelectItem>
                            <SelectItem value="claude-sonnet-4-5">
                              Claude Sonnet 4.5 (Sep 2025 - Best coding/agents)
                            </SelectItem>
                            <SelectItem value="claude-opus-4-1">
                              Claude Opus 4.1 (Aug 2025 - Most capable)
                            </SelectItem>
                            <SelectItem value="claude-haiku-4-5">
                              Claude Haiku 4.5 (Oct 2025 - Fast & cheap)
                            </SelectItem>
                            <SelectItem value="gemini-2.5-flash">
                              Gemini 2.5 Flash (Multimodal voice)
                            </SelectItem>
                          </SelectContent>
                        </Select>
                        <FormDescription>
                          gpt-realtime: Voice | Claude Sonnet 4.5: Agents/Coding | Haiku 4.5: Budget
                        </FormDescription>
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
                            className="min-h-[120px]"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Instructions that define your agent&apos;s personality and behavior
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      control={form.control}
                      name="temperature"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Temperature</FormLabel>
                          <FormControl>
                            <Input
                              type="number"
                              step="0.1"
                              min="0"
                              max="2"
                              {...field}
                              onChange={(e) => field.onChange(parseFloat(e.target.value))}
                            />
                          </FormControl>
                          <FormDescription>0 = focused, 2 = creative</FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="maxTokens"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Max Tokens</FormLabel>
                          <FormControl>
                            <Input
                              type="number"
                              step="100"
                              min="100"
                              max="4000"
                              {...field}
                              onChange={(e) => field.onChange(parseInt(e.target.value))}
                            />
                          </FormControl>
                          <FormDescription>Response length limit</FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="tools" className="mt-6 space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Built-in Tools</CardTitle>
                  <CardDescription>
                    Enable CRM and booking capabilities for your agent
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <FormField
                    control={form.control}
                    name="enabledTools"
                    render={() => (
                      <FormItem>
                        <div className="mb-4">
                          <FormLabel className="text-base">CRM & Booking Tools</FormLabel>
                          <FormDescription>
                            These tools allow your agent to search customers, create contacts, check
                            availability, and book appointments.
                          </FormDescription>
                        </div>
                        <div className="space-y-2">
                          {[
                            {
                              id: "crm",
                              name: "CRM Tools",
                              desc: "Search customers, create contacts, manage customer data",
                            },
                            {
                              id: "bookings",
                              name: "Booking Tools",
                              desc: "Check availability, book/cancel/reschedule appointments",
                            },
                          ].map((tool) => (
                            <FormField
                              key={tool.id}
                              control={form.control}
                              name="enabledTools"
                              render={({ field }) => (
                                <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                                  <FormControl>
                                    <input
                                      type="checkbox"
                                      className="mt-0.5 h-4 w-4"
                                      checked={field.value?.includes(tool.id)}
                                      onChange={(e) => {
                                        const checked = e.target.checked;
                                        const current = field.value || [];
                                        field.onChange(
                                          checked
                                            ? [...current, tool.id]
                                            : current.filter((v) => v !== tool.id)
                                        );
                                      }}
                                    />
                                  </FormControl>
                                  <div className="space-y-1 leading-none">
                                    <FormLabel className="cursor-pointer font-medium">
                                      {tool.name}
                                    </FormLabel>
                                    <FormDescription>{tool.desc}</FormDescription>
                                  </div>
                                </FormItem>
                              )}
                            />
                          ))}
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>External Integrations</CardTitle>
                  <CardDescription>Connect external services (coming soon)</CardDescription>
                </CardHeader>
                <CardContent>
                  <FormField
                    control={form.control}
                    name="enabledTools"
                    render={() => (
                      <FormItem>
                        <div className="space-y-2">
                          {[
                            {
                              id: "google-calendar",
                              name: "Google Calendar",
                              desc: "Schedule meetings",
                            },
                            { id: "salesforce", name: "Salesforce", desc: "Access CRM data" },
                            { id: "hubspot", name: "HubSpot", desc: "Manage contacts" },
                          ].map((tool) => (
                            <FormField
                              key={tool.id}
                              control={form.control}
                              name="enabledTools"
                              render={() => (
                                <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4 opacity-50">
                                  <FormControl>
                                    <input type="checkbox" className="mt-0.5 h-4 w-4" disabled />
                                  </FormControl>
                                  <div className="space-y-1 leading-none">
                                    <FormLabel className="cursor-not-allowed font-medium">
                                      {tool.name}
                                    </FormLabel>
                                    <FormDescription>{tool.desc} (Coming soon)</FormDescription>
                                  </div>
                                </FormItem>
                              )}
                            />
                          ))}
                          <div className="pt-4">
                            <Button type="button" variant="outline" size="sm" asChild>
                              <Link href="/dashboard/integrations">Manage Integrations</Link>
                            </Button>
                          </div>
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="advanced" className="mt-6 space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Telephony Settings</CardTitle>
                  <CardDescription>Phone number and call settings</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="telephonyProvider"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Telephony Provider</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="telnyx">Telnyx (Recommended)</SelectItem>
                            <SelectItem value="twilio">Twilio</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="phoneNumberId"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Phone Number</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Select a phone number" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="none">No phone number assigned</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormDescription>Assign a phone number to this agent</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <Separator />

                  <FormField
                    control={form.control}
                    name="enableRecording"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                        <div className="space-y-0.5">
                          <FormLabel className="text-base">Enable Call Recording</FormLabel>
                          <FormDescription>Record all calls for quality assurance</FormDescription>
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
                          <FormDescription>Save conversation transcripts</FormDescription>
                        </div>
                        <FormControl>
                          <Switch checked={field.value} onCheckedChange={field.onChange} />
                        </FormControl>
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="turnDetectionMode"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Turn Detection</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="server-vad">Server VAD (Recommended)</SelectItem>
                            <SelectItem value="pushToTalk">Push to Talk</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormDescription>
                          How the agent detects when the user has finished speaking
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Statistics</CardTitle>
                  <CardDescription>Agent usage statistics</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                    <div className="rounded-lg border p-4">
                      <p className="text-sm text-muted-foreground">Total Calls</p>
                      <p className="text-2xl font-bold">{agent.total_calls}</p>
                    </div>
                    <div className="rounded-lg border p-4">
                      <p className="text-sm text-muted-foreground">Total Duration</p>
                      <p className="text-2xl font-bold">
                        {Math.round(agent.total_duration_seconds / 60)}m
                      </p>
                    </div>
                    <div className="rounded-lg border p-4">
                      <p className="text-sm text-muted-foreground">Created</p>
                      <p className="text-sm font-medium">
                        {new Date(agent.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="rounded-lg border p-4">
                      <p className="text-sm text-muted-foreground">Last Call</p>
                      <p className="text-sm font-medium">
                        {agent.last_call_at
                          ? new Date(agent.last_call_at).toLocaleDateString()
                          : "Never"}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

          <div className="flex justify-end gap-4">
            <Button
              type="button"
              variant="outline"
              asChild
              disabled={updateAgentMutation.isPending}
            >
              <Link href="/dashboard/agents">Cancel</Link>
            </Button>
            <Button type="submit" disabled={updateAgentMutation.isPending}>
              {updateAgentMutation.isPending ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
}
