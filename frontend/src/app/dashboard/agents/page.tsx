"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Plus,
  Bot,
  MoreVertical,
  Play,
  Pause,
  AlertCircle,
  Phone,
  PhoneOff,
  PhoneOutgoing,
  Wrench,
  Clock,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { fetchAgents, deleteAgent, createAgent, getAgent, type Agent } from "@/lib/api/agents";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MakeCallDialog } from "@/components/make-call-dialog";

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffInSeconds < 60) return "just now";
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
  if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)}d ago`;
  return date.toLocaleDateString();
}

export default function AgentsPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const [callDialogOpen, setCallDialogOpen] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);

  // Fetch agents from API
  const {
    data: agents = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAgent,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["agents"] });
      toast.success("Agent deleted successfully");
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete agent: ${error.message}`);
    },
  });

  const duplicateMutation = useMutation({
    mutationFn: async (agentId: string) => {
      const agent = await getAgent(agentId);
      return createAgent({
        name: `${agent.name} (Copy)`,
        description: agent.description ?? undefined,
        pricing_tier: agent.pricing_tier as "budget" | "balanced" | "premium",
        system_prompt: agent.system_prompt,
        language: agent.language,
        enabled_tools: agent.enabled_tools,
        phone_number_id: undefined, // Don't copy phone number
        enable_recording: agent.enable_recording,
        enable_transcript: agent.enable_transcript,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["agents"] });
      toast.success("Agent duplicated successfully");
    },
    onError: (error: Error) => {
      toast.error(`Failed to duplicate agent: ${error.message}`);
    },
  });

  const handleDelete = (agentId: string) => {
    void deleteMutation.mutateAsync(agentId);
  };

  const handleDuplicate = (agentId: string) => {
    void duplicateMutation.mutateAsync(agentId);
  };

  const handleTest = (agentId: string) => {
    // Navigate to test page with the agent pre-selected
    router.push(`/dashboard/test?agent=${agentId}`);
  };

  const handleMakeCall = (agent: Agent) => {
    setSelectedAgent(agent);
    setCallDialogOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Voice Agents</h1>
          <p className="text-muted-foreground">Manage and configure your AI voice agents</p>
        </div>
        <Button asChild>
          <Link href="/dashboard/agents/new-simplified">
            <Plus className="mr-2 h-4 w-4" />
            Create Agent
          </Link>
        </Button>
      </div>

      {isLoading ? (
        <Card>
          <CardContent className="flex items-center justify-center py-16">
            <p className="text-muted-foreground">Loading agents...</p>
          </CardContent>
        </Card>
      ) : error ? (
        <Card className="border-destructive">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <AlertCircle className="mb-4 h-16 w-16 text-destructive" />
            <h3 className="mb-2 text-lg font-semibold">Failed to load agents</h3>
            <p className="mb-4 text-center text-sm text-muted-foreground">
              {error instanceof Error ? error.message : "An unexpected error occurred"}
            </p>
            <Button variant="outline" onClick={() => window.location.reload()}>
              Try Again
            </Button>
          </CardContent>
        </Card>
      ) : agents.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Bot className="mb-4 h-16 w-16 text-muted-foreground/50" />
            <h3 className="mb-2 text-lg font-semibold">No voice agents yet</h3>
            <p className="mb-4 max-w-sm text-center text-sm text-muted-foreground">
              Create your first voice agent to handle inbound and outbound calls with AI
            </p>
            <Button asChild>
              <Link href="/dashboard/agents/new-simplified">
                <Plus className="mr-2 h-4 w-4" />
                Create Your First Agent
              </Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <Card key={agent.id} className="transition-shadow hover:shadow-md">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                      <Bot className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <CardTitle className="text-lg">{agent.name}</CardTitle>
                      <CardDescription className="text-xs">
                        {agent.pricing_tier.charAt(0).toUpperCase() + agent.pricing_tier.slice(1)} •{" "}
                        {agent.language}
                      </CardDescription>
                    </div>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem asChild>
                        <Link href={`/dashboard/agents/${agent.id}`}>Edit</Link>
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleTest(agent.id)}>Test</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleMakeCall(agent)}>
                        <PhoneOutgoing className="mr-2 h-4 w-4" />
                        Make Call
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleDuplicate(agent.id)}>
                        Duplicate
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => handleDelete(agent.id)}
                      >
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Status</span>
                    <Badge variant={agent.is_active ? "default" : "secondary"}>
                      {agent.is_active ? (
                        <>
                          <Play className="mr-1 h-3 w-3" /> Active
                        </>
                      ) : (
                        <>
                          <Pause className="mr-1 h-3 w-3" /> Inactive
                        </>
                      )}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Phone</span>
                    {agent.phone_number_id ? (
                      <Badge variant="outline" className="font-mono text-xs">
                        <Phone className="mr-1 h-3 w-3 text-green-500" />
                        Assigned
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="text-xs text-muted-foreground">
                        <PhoneOff className="mr-1 h-3 w-3" />
                        Not assigned
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Tools</span>
                    {agent.enabled_tools.length > 0 ? (
                      <Badge variant="outline" className="text-xs">
                        <Wrench className="mr-1 h-3 w-3" />
                        {agent.enabled_tools.length} enabled
                      </Badge>
                    ) : (
                      <Badge variant="destructive" className="text-xs">
                        No tools
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Calls</span>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{agent.total_calls}</span>
                      {agent.last_call_at && (
                        <span
                          className="flex items-center text-xs text-muted-foreground"
                          title={`Last call: ${new Date(agent.last_call_at).toLocaleString()}`}
                        >
                          <Clock className="mr-1 h-3 w-3" />
                          {formatRelativeTime(agent.last_call_at)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Make Call Dialog */}
      {selectedAgent && (
        <MakeCallDialog
          open={callDialogOpen}
          onOpenChange={setCallDialogOpen}
          agent={selectedAgent}
        />
      )}
    </div>
  );
}
