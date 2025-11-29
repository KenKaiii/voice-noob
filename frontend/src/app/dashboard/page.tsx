"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Bot,
  Phone,
  Clock,
  CheckCircle,
  Plus,
  ArrowRight,
  Calendar,
  Users,
  PhoneCall,
  Settings,
} from "lucide-react";
import { fetchAgents } from "@/lib/api/agents";
import { listCalls } from "@/lib/api/calls";
import { api } from "@/lib/api";

interface Workspace {
  id: string;
  name: string;
  contact_count: number;
  agent_count: number;
}

interface Appointment {
  id: number;
  status: string;
  scheduled_at: string;
  contact_name: string | null;
}

export default function DashboardPage() {
  // Fetch agents
  const { data: agents = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
  });

  // Fetch recent calls
  const { data: callsData } = useQuery({
    queryKey: ["calls", 1],
    queryFn: () => listCalls({ page: 1, page_size: 5 }),
  });

  // Fetch workspaces
  const { data: workspaces = [] } = useQuery<Workspace[]>({
    queryKey: ["workspaces"],
    queryFn: async () => {
      const response = await api.get("/api/v1/workspaces");
      return response.data;
    },
  });

  // Fetch upcoming appointments
  const { data: appointments = [] } = useQuery<Appointment[]>({
    queryKey: ["appointments", "scheduled"],
    queryFn: async () => {
      const response = await api.get("/api/v1/crm/appointments?status=scheduled");
      return response.data;
    },
  });

  const activeAgents = agents.filter((a) => a.is_active).length;
  const totalCalls = callsData?.total ?? 0;
  const completedCalls = callsData?.calls?.filter((c) => c.status === "completed").length ?? 0;
  const avgDuration =
    callsData?.calls && callsData.calls.length > 0
      ? Math.round(
          callsData.calls.reduce((sum, c) => sum + c.duration_seconds, 0) / callsData.calls.length
        )
      : 0;
  const totalContacts = workspaces.reduce((sum, w) => sum + w.contact_count, 0);
  const upcomingAppointments = appointments.filter(
    (a) => new Date(a.scheduled_at) > new Date()
  ).length;

  const formatDuration = (seconds: number) => {
    if (seconds === 0) return "0s";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins === 0) return `${secs}s`;
    return `${mins}m ${secs}s`;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Dashboard</h1>
          <p className="text-sm text-muted-foreground">Overview of your voice agent platform</p>
        </div>
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

      {/* Stats Cards - Compact style like other pages */}
      <div className="grid gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Active Agents</p>
                <p className="text-lg font-semibold">{activeAgents}</p>
              </div>
              <Bot className="h-4 w-4 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Total Calls</p>
                <p className="text-lg font-semibold">{totalCalls}</p>
              </div>
              <Phone className="h-4 w-4 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Completed</p>
                <p className="text-lg font-semibold">{completedCalls}</p>
              </div>
              <CheckCircle className="h-4 w-4 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Avg Duration</p>
                <p className="text-lg font-semibold">{formatDuration(avgDuration)}</p>
              </div>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Contacts</p>
                <p className="text-lg font-semibold">{totalContacts}</p>
              </div>
              <Users className="h-4 w-4 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Upcoming</p>
                <p className="text-lg font-semibold">{upcomingAppointments}</p>
              </div>
              <Calendar className="h-4 w-4 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Grid */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Recent Calls */}
        <Card className="lg:col-span-2">
          <CardContent className="p-4">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-medium">Recent Calls</h3>
              <Button variant="ghost" size="sm" className="h-7 text-xs" asChild>
                <Link href="/dashboard/calls">
                  View all
                  <ArrowRight className="ml-1 h-3 w-3" />
                </Link>
              </Button>
            </div>
            {callsData?.calls && callsData.calls.length > 0 ? (
              <div className="space-y-2">
                {callsData.calls.slice(0, 5).map((call) => (
                  <Link
                    key={call.id}
                    href={`/dashboard/calls/${call.id}`}
                    className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-accent"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10">
                        <PhoneCall className="h-4 w-4 text-primary" />
                      </div>
                      <div>
                        <p className="text-sm font-medium">
                          {call.contact_name ?? call.from_number}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {call.agent_name ?? "Unknown Agent"} &middot;{" "}
                          {formatDuration(call.duration_seconds)}
                        </p>
                      </div>
                    </div>
                    <span
                      className={`inline-flex h-5 items-center rounded-full px-2 text-[10px] font-medium ${
                        call.status === "completed"
                          ? "bg-green-100 text-green-800"
                          : call.status === "failed"
                            ? "bg-red-100 text-red-800"
                            : "bg-gray-100 text-gray-800"
                      }`}
                    >
                      {call.status}
                    </span>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Phone className="mb-3 h-10 w-10 text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground">No calls yet</p>
                <p className="text-xs text-muted-foreground">
                  Calls will appear here once your agents start handling them
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardContent className="p-4">
            <h3 className="mb-4 text-sm font-medium">Quick Actions</h3>
            <div className="space-y-2">
              {workspaces.length > 0 ? (
                <Link
                  href="/dashboard/agents/create-agent"
                  className="flex items-center gap-3 rounded-lg border p-3 transition-colors hover:bg-accent"
                >
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">Create Agent</p>
                    <p className="text-xs text-muted-foreground">Configure a new voice agent</p>
                  </div>
                </Link>
              ) : (
                <Link
                  href="/dashboard/workspaces"
                  className="flex items-center gap-3 rounded-lg border border-dashed p-3 transition-colors hover:bg-accent"
                >
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-muted">
                    <Bot className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      Create Workspace First
                    </p>
                    <p className="text-xs text-muted-foreground">Required before creating agents</p>
                  </div>
                </Link>
              )}
              <Link
                href="/dashboard/phone-numbers"
                className="flex items-center gap-3 rounded-lg border p-3 transition-colors hover:bg-accent"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10">
                  <Phone className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium">Get Phone Number</p>
                  <p className="text-xs text-muted-foreground">Purchase a number</p>
                </div>
              </Link>
              <Link
                href="/dashboard/crm"
                className="flex items-center gap-3 rounded-lg border p-3 transition-colors hover:bg-accent"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10">
                  <Users className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium">Manage Contacts</p>
                  <p className="text-xs text-muted-foreground">Add or import contacts</p>
                </div>
              </Link>
              <Link
                href="/dashboard/settings"
                className="flex items-center gap-3 rounded-lg border p-3 transition-colors hover:bg-accent"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10">
                  <Settings className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium">Configure API Keys</p>
                  <p className="text-xs text-muted-foreground">OpenAI, Deepgram, ElevenLabs</p>
                </div>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Agents Grid */}
      {agents.length > 0 && (
        <div>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-medium">Your Agents</h3>
            <Button variant="ghost" size="sm" className="h-7 text-xs" asChild>
              <Link href="/dashboard/agents">
                View all
                <ArrowRight className="ml-1 h-3 w-3" />
              </Link>
            </Button>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {agents.slice(0, 4).map((agent) => (
              <Link key={agent.id} href={`/dashboard/agents/${agent.id}`} prefetch={false}>
                <Card className="cursor-pointer transition-all hover:border-primary/50">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10">
                        <Bot className="h-4 w-4 text-primary" />
                      </div>
                      <div className="min-w-0">
                        <h3 className="truncate text-sm font-medium">{agent.name}</h3>
                        <p className="text-xs text-muted-foreground">
                          {agent.pricing_tier.charAt(0).toUpperCase() + agent.pricing_tier.slice(1)}{" "}
                          &middot; {agent.total_calls} calls
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
