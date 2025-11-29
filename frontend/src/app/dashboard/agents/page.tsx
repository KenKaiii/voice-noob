"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Plus,
  Bot,
  MoreVertical,
  AlertCircle,
  Phone,
  Wrench,
  Clock,
  FolderOpen,
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { MakeCallDialog } from "@/components/make-call-dialog";
import { EmbedAgentDialog } from "@/components/embed-agent-dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";

interface Workspace {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
}

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
  const [embedDialogOpen, setEmbedDialogOpen] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [agentToDelete, setAgentToDelete] = useState<Agent | null>(null);
  const [deletingAgentIds, setDeletingAgentIds] = useState<Set<string>>(new Set());
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string>("all");

  // Fetch workspaces
  const { data: workspaces = [] } = useQuery<Workspace[]>({
    queryKey: ["workspaces"],
    queryFn: async () => {
      const response = await api.get("/api/v1/workspaces");
      return response.data;
    },
  });

  // Fetch all agents (for "All Workspaces" / admin mode)
  const {
    data: allAgents = [],
    isLoading: isLoadingAllAgents,
    error: allAgentsError,
  } = useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
    enabled: selectedWorkspaceId === "all",
  });

  // Fetch workspace-specific agents
  const {
    data: workspaceAgents = [],
    isLoading: isLoadingWorkspaceAgents,
    error: workspaceAgentsError,
  } = useQuery<{ agent_id: string; agent_name: string; is_default: boolean }[]>({
    queryKey: ["workspace-agents", selectedWorkspaceId],
    queryFn: async () => {
      if (!selectedWorkspaceId || selectedWorkspaceId === "all") return [];
      const response = await api.get(`/api/v1/workspaces/${selectedWorkspaceId}/agents`);
      return response.data;
    },
    enabled: !!selectedWorkspaceId && selectedWorkspaceId !== "all",
  });

  // Get the filtered agents based on selection mode
  const agents =
    selectedWorkspaceId === "all"
      ? allAgents
      : allAgents.filter((a) => workspaceAgents.some((wa) => wa.agent_id === a.id));

  const isLoading =
    selectedWorkspaceId === "all"
      ? isLoadingAllAgents
      : isLoadingAllAgents || isLoadingWorkspaceAgents;
  const error =
    selectedWorkspaceId === "all" ? allAgentsError : (allAgentsError ?? workspaceAgentsError);

  const deleteMutation = useMutation({
    mutationFn: deleteAgent,
    onMutate: async (agentId) => {
      // Cancel any outgoing refetches to prevent race conditions
      await queryClient.cancelQueries({ queryKey: ["agent", agentId] });
      await queryClient.cancelQueries({ queryKey: ["agent-workspaces", agentId] });
      await queryClient.cancelQueries({ queryKey: ["agents"] });
      // Remove the specific agent query from cache to prevent 404 errors
      queryClient.removeQueries({ queryKey: ["agent", agentId] });
      queryClient.removeQueries({ queryKey: ["agent-workspaces", agentId] });

      // Optimistically remove the agent from the list cache
      const previousAgents = queryClient.getQueryData<Agent[]>(["agents"]);
      if (previousAgents) {
        queryClient.setQueryData<Agent[]>(
          ["agents"],
          previousAgents.filter((a) => a.id !== agentId)
        );
      }
      return { previousAgents };
    },
    onSuccess: () => {
      // Refetch to ensure fresh data
      void queryClient.refetchQueries({ queryKey: ["agents"] });
      toast.success("Agent deleted successfully");
    },
    onError: (error: Error, _agentId, context) => {
      // Restore previous agents on error
      if (context?.previousAgents) {
        queryClient.setQueryData(["agents"], context.previousAgents);
      }
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

  const handleDeleteClick = (agent: Agent) => {
    setAgentToDelete(agent);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!agentToDelete) return;

    const agentId = agentToDelete.id;

    // Mark as deleting BEFORE closing dialog
    setDeletingAgentIds((prev) => new Set(prev).add(agentId));
    setDeleteDialogOpen(false);
    setAgentToDelete(null);

    try {
      await deleteMutation.mutateAsync(agentId);
    } finally {
      setDeletingAgentIds((prev) => {
        const next = new Set(prev);
        next.delete(agentId);
        return next;
      });
    }
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

  const handleEmbed = (agent: Agent) => {
    setSelectedAgent(agent);
    setEmbedDialogOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Voice Agents</h1>
          <p className="text-sm text-muted-foreground">Manage and configure your AI voice agents</p>
        </div>
        <div className="flex items-center gap-2">
          {workspaces.length > 0 && (
            <Select
              value={selectedWorkspaceId}
              onValueChange={(value) => {
                setSelectedWorkspaceId(value);
                const wsName =
                  value === "all"
                    ? "All Workspaces"
                    : workspaces.find((ws) => ws.id === value)?.name;
                toast.info(`Switched to ${wsName}`);
              }}
            >
              <SelectTrigger className="h-8 w-[220px] text-sm">
                <FolderOpen className="mr-2 h-3.5 w-3.5" />
                <SelectValue placeholder="All Workspaces" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Workspaces (Admin)</SelectItem>
                {workspaces.map((ws) => (
                  <SelectItem key={ws.id} value={ws.id}>
                    {ws.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {workspaces.length > 0 ? (
            <Button size="sm" asChild>
              <Link href="/dashboard/agents/create-agent">
                <Plus className="mr-2 h-4 w-4" />
                Create Agent
              </Link>
            </Button>
          ) : (
            <Button size="sm" asChild>
              <Link href="/dashboard/workspaces">
                <Plus className="mr-2 h-4 w-4" />
                Create Workspace
              </Link>
            </Button>
          )}
        </div>
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
              {workspaces.length === 0
                ? "Create a workspace first, then create your voice agent"
                : "Create your first voice agent to handle inbound and outbound calls with AI"}
            </p>
            {workspaces.length > 0 ? (
              <Button size="sm" asChild>
                <Link href="/dashboard/agents/create-agent">
                  <Plus className="mr-2 h-4 w-4" />
                  Create Your First Agent
                </Link>
              </Button>
            ) : (
              <Button size="sm" asChild>
                <Link href="/dashboard/workspaces">
                  <Plus className="mr-2 h-4 w-4" />
                  Create Workspace
                </Link>
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {agents
            .filter((agent) => !deletingAgentIds.has(agent.id))
            .map((agent) => (
              <Card
                key={agent.id}
                className="group cursor-pointer transition-all hover:border-primary/50"
                onClick={() => router.push(`/dashboard/agents/${agent.id}`)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2.5 overflow-hidden">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10">
                        <Bot className="h-4 w-4 text-primary" />
                      </div>
                      <div className="min-w-0">
                        <h3 className="truncate text-sm font-medium">{agent.name}</h3>
                        <p className="text-xs text-muted-foreground">
                          {agent.pricing_tier.charAt(0).toUpperCase() + agent.pricing_tier.slice(1)}
                        </p>
                      </div>
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 shrink-0"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <MoreVertical className="h-3.5 w-3.5" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                        <DropdownMenuItem asChild>
                          <Link href={`/dashboard/agents/${agent.id}`} prefetch={false}>
                            Edit
                          </Link>
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => handleTest(agent.id)}>
                          Test
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => handleMakeCall(agent)}>
                          Make Call
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => handleDuplicate(agent.id)}>
                          Duplicate
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => handleEmbed(agent)}>
                          Embed
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-destructive"
                          onSelect={() => handleDeleteClick(agent)}
                        >
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>

                  <div className="mt-3 flex flex-wrap items-center gap-1.5">
                    <Badge
                      variant={agent.is_active ? "default" : "secondary"}
                      className="h-5 px-1.5 text-[10px]"
                    >
                      {agent.is_active ? "Active" : "Inactive"}
                    </Badge>
                    {agent.phone_number_id ? (
                      <Badge variant="outline" className="h-5 px-1.5 text-[10px]">
                        <Phone className="mr-0.5 h-2.5 w-2.5 text-green-500" />
                        Phone
                      </Badge>
                    ) : null}
                    {agent.enabled_tools.length > 0 && (
                      <Badge variant="outline" className="h-5 px-1.5 text-[10px]">
                        <Wrench className="mr-0.5 h-2.5 w-2.5" />
                        {agent.enabled_tools.length}
                      </Badge>
                    )}
                  </div>

                  <div className="mt-2.5 flex items-center justify-between border-t border-border/50 pt-2.5 text-xs text-muted-foreground">
                    <span>{agent.total_calls} calls</span>
                    {agent.last_call_at && (
                      <span className="flex items-center">
                        <Clock className="mr-1 h-3 w-3" />
                        {formatRelativeTime(agent.last_call_at)}
                      </span>
                    )}
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

      {/* Embed Dialog */}
      {selectedAgent && (
        <EmbedAgentDialog
          open={embedDialogOpen}
          onOpenChange={setEmbedDialogOpen}
          agent={selectedAgent}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent className="max-w-sm gap-3 p-4">
          <AlertDialogHeader className="space-y-1">
            <AlertDialogTitle className="text-sm font-medium">Delete agent?</AlertDialogTitle>
            <AlertDialogDescription className="text-xs">
              &ldquo;{agentToDelete?.name}&rdquo; will be permanently deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="gap-2 sm:gap-2">
            <AlertDialogCancel className="h-8 text-xs">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                void handleConfirmDelete();
              }}
              className="h-8 bg-destructive text-xs text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
