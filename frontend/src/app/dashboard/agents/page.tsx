"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Plus, Bot, MoreVertical, Play, Pause, AlertCircle } from "lucide-react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { fetchAgents, deleteAgent } from "@/lib/api/agents";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export default function AgentsPage() {
  const queryClient = useQueryClient();

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

  const handleDelete = (agentId: string) => {
    void deleteMutation.mutateAsync(agentId);
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
                      <DropdownMenuItem>
                        <Link href={`/dashboard/agents/${agent.id}`}>Edit</Link>
                      </DropdownMenuItem>
                      <DropdownMenuItem>Test</DropdownMenuItem>
                      <DropdownMenuItem>Duplicate</DropdownMenuItem>
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
                    <span className="font-mono text-xs">
                      {agent.phone_number_id ?? "Not assigned"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Tools</span>
                    <span className="font-semibold">{agent.enabled_tools.length}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Total Calls</span>
                    <span className="font-semibold">{agent.total_calls}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
