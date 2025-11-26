"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Plus,
  Loader2,
  AlertCircle,
  FolderOpen,
  Users,
  Bot,
  Settings,
  Trash2,
  Globe,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";

interface WorkspaceSettings {
  timezone?: string;
  business_hours?: Record<string, { start: string; end: string; enabled: boolean }>;
  booking_buffer_minutes?: number;
  max_advance_booking_days?: number;
  default_appointment_duration?: number;
  allow_same_day_booking?: boolean;
}

interface Workspace {
  id: string;
  user_id: number;
  name: string;
  description: string | null;
  settings: WorkspaceSettings;
  is_default: boolean;
  agent_count: number;
  contact_count: number;
}

interface WorkspaceAgent {
  agent_id: string;
  agent_name: string;
  is_default: boolean;
  pricing_tier: string;
}

type WorkspaceFormData = {
  name: string;
  description: string;
  timezone: string;
  booking_buffer_minutes: number;
  max_advance_booking_days: number;
  default_appointment_duration: number;
  allow_same_day_booking: boolean;
};

const TIMEZONES = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Phoenix",
  "America/Anchorage",
  "Pacific/Honolulu",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Asia/Tokyo",
  "Asia/Shanghai",
  "Asia/Singapore",
  "Australia/Sydney",
  "UTC",
];

const emptyFormData: WorkspaceFormData = {
  name: "",
  description: "",
  timezone: "America/New_York",
  booking_buffer_minutes: 15,
  max_advance_booking_days: 30,
  default_appointment_duration: 30,
  allow_same_day_booking: true,
};

export default function WorkspacesPage() {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isAgentsModalOpen, setIsAgentsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<"add" | "edit" | "view">("add");
  const [selectedWorkspace, setSelectedWorkspace] = useState<Workspace | null>(null);
  const [formData, setFormData] = useState<WorkspaceFormData>(emptyFormData);

  // Fetch workspaces
  const {
    data: workspaces = [],
    isLoading,
    error,
  } = useQuery<Workspace[]>({
    queryKey: ["workspaces"],
    queryFn: async () => {
      const response = await api.get("/api/v1/workspaces");
      return response.data;
    },
  });

  // Fetch agents for selected workspace
  const { data: workspaceAgents = [], isLoading: isLoadingAgents } = useQuery<WorkspaceAgent[]>({
    queryKey: ["workspace-agents", selectedWorkspace?.id],
    queryFn: async () => {
      if (!selectedWorkspace) return [];
      const response = await api.get(`/api/v1/workspaces/${selectedWorkspace.id}/agents`);
      return response.data;
    },
    enabled: !!selectedWorkspace && isAgentsModalOpen,
  });

  // Create workspace mutation
  const createWorkspaceMutation = useMutation({
    mutationFn: async (data: WorkspaceFormData) => {
      const payload = {
        name: data.name,
        description: data.description || null,
        settings: {
          timezone: data.timezone,
          booking_buffer_minutes: data.booking_buffer_minutes,
          max_advance_booking_days: data.max_advance_booking_days,
          default_appointment_duration: data.default_appointment_duration,
          allow_same_day_booking: data.allow_same_day_booking,
        },
      };
      const response = await api.post("/api/v1/workspaces", payload);
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      toast.success("Workspace created successfully");
      closeModal();
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to create workspace");
    },
  });

  // Update workspace mutation
  const updateWorkspaceMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: WorkspaceFormData }) => {
      const payload = {
        name: data.name,
        description: data.description || null,
        settings: {
          timezone: data.timezone,
          booking_buffer_minutes: data.booking_buffer_minutes,
          max_advance_booking_days: data.max_advance_booking_days,
          default_appointment_duration: data.default_appointment_duration,
          allow_same_day_booking: data.allow_same_day_booking,
        },
      };
      const response = await api.put(`/api/v1/workspaces/${id}`, payload);
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      toast.success("Workspace updated successfully");
      closeModal();
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to update workspace");
    },
  });

  // Delete workspace mutation
  const deleteWorkspaceMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/api/v1/workspaces/${id}`);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      toast.success("Workspace deleted successfully");
      closeModal();
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to delete workspace");
    },
  });

  const openAddModal = () => {
    setFormData(emptyFormData);
    setSelectedWorkspace(null);
    setModalMode("add");
    setIsModalOpen(true);
  };

  const openViewModal = (workspace: Workspace) => {
    setSelectedWorkspace(workspace);
    setFormData({
      name: workspace.name,
      description: workspace.description ?? "",
      timezone: workspace.settings.timezone ?? "America/New_York",
      booking_buffer_minutes: workspace.settings.booking_buffer_minutes ?? 15,
      max_advance_booking_days: workspace.settings.max_advance_booking_days ?? 30,
      default_appointment_duration: workspace.settings.default_appointment_duration ?? 30,
      allow_same_day_booking: workspace.settings.allow_same_day_booking ?? true,
    });
    setModalMode("view");
    setIsModalOpen(true);
  };

  const openAgentsModal = (workspace: Workspace) => {
    setSelectedWorkspace(workspace);
    setIsAgentsModalOpen(true);
  };

  const switchToEditMode = () => {
    setModalMode("edit");
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setSelectedWorkspace(null);
    setFormData(emptyFormData);
  };

  const closeAgentsModal = () => {
    setIsAgentsModalOpen(false);
    setSelectedWorkspace(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (modalMode === "add") {
      createWorkspaceMutation.mutate(formData);
    } else if (modalMode === "edit" && selectedWorkspace) {
      updateWorkspaceMutation.mutate({ id: selectedWorkspace.id, data: formData });
    }
  };

  const handleDelete = () => {
    if (selectedWorkspace) {
      if (selectedWorkspace.is_default) {
        toast.error("Cannot delete the default workspace");
        return;
      }
      if (
        confirm(
          "Are you sure you want to delete this workspace? All associated data will be moved to your default workspace."
        )
      ) {
        deleteWorkspaceMutation.mutate(selectedWorkspace.id);
      }
    }
  };

  const isSubmitting = createWorkspaceMutation.isPending || updateWorkspaceMutation.isPending;

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Workspaces</h1>
          <p className="text-muted-foreground">
            Organize your agents, contacts, and appointments into separate workspaces
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertCircle className="mb-4 h-12 w-12 text-destructive" />
            <h3 className="mb-2 text-lg font-semibold">Failed to load workspaces</h3>
            <p className="text-sm text-muted-foreground">
              {error instanceof Error ? error.message : "An error occurred"}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Workspaces</h1>
          <p className="text-muted-foreground">
            Organize your agents, contacts, and appointments into separate workspaces
          </p>
        </div>
        <Button onClick={openAddModal}>
          <Plus className="mr-2 h-4 w-4" />
          New Workspace
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Workspaces</CardTitle>
            <FolderOpen className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{workspaces.length}</div>
            <p className="text-xs text-muted-foreground">Active workspaces</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Contacts</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {workspaces.reduce((sum, w) => sum + w.contact_count, 0)}
            </div>
            <p className="text-xs text-muted-foreground">Across all workspaces</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Assigned Agents</CardTitle>
            <Bot className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {workspaces.reduce((sum, w) => sum + w.agent_count, 0)}
            </div>
            <p className="text-xs text-muted-foreground">Total agent assignments</p>
          </CardContent>
        </Card>
      </div>

      {/* Workspaces List */}
      <Card>
        <CardHeader>
          <CardTitle>Your Workspaces</CardTitle>
          <CardDescription>
            {isLoading
              ? "Loading workspaces..."
              : workspaces.length === 0
                ? "No workspaces yet. Create your first workspace to get started."
                : `Showing ${workspaces.length} workspace${workspaces.length !== 1 ? "s" : ""}`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="mb-4 h-8 w-8 animate-spin text-muted-foreground" />
              <p className="text-sm text-muted-foreground">Loading workspaces...</p>
            </div>
          ) : workspaces.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="mb-4 rounded-full bg-muted p-3">
                <FolderOpen className="h-6 w-6 text-muted-foreground" />
              </div>
              <p className="text-lg font-medium">No workspaces yet</p>
              <p className="mb-4 text-sm text-muted-foreground">
                Create workspaces to organize your agents, contacts, and appointments
              </p>
              <Button onClick={openAddModal}>
                <Plus className="mr-2 h-4 w-4" />
                Create Your First Workspace
              </Button>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {workspaces.map((workspace) => (
                <Card key={workspace.id} className="relative">
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <CardTitle className="flex items-center gap-2 text-lg">
                          {workspace.name}
                          {workspace.is_default && (
                            <Badge variant="secondary" className="text-xs">
                              Default
                            </Badge>
                          )}
                        </CardTitle>
                        <CardDescription className="line-clamp-2">
                          {workspace.description ?? "No description"}
                        </CardDescription>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Users className="h-4 w-4" />
                        <span>{workspace.contact_count} contacts</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Bot className="h-4 w-4" />
                        <span>{workspace.agent_count} agents</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Globe className="h-4 w-4" />
                      <span>{workspace.settings.timezone ?? "Not set"}</span>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1"
                        onClick={() => openViewModal(workspace)}
                      >
                        <Settings className="mr-2 h-4 w-4" />
                        Settings
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1"
                        onClick={() => openAgentsModal(workspace)}
                      >
                        <Bot className="mr-2 h-4 w-4" />
                        Agents
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Workspace Settings Modal */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="sm:max-w-[550px]">
          <DialogHeader>
            <DialogTitle>
              {modalMode === "add" && "Create New Workspace"}
              {modalMode === "edit" && "Edit Workspace"}
              {modalMode === "view" && "Workspace Settings"}
            </DialogTitle>
            <DialogDescription>
              {modalMode === "add" &&
                "Create a new workspace to organize your agents and CRM data."}
              {modalMode === "edit" && "Update workspace settings."}
              {modalMode === "view" && "View and manage workspace settings."}
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit}>
            <div className="grid gap-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="name">Workspace Name *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  disabled={modalMode === "view"}
                  required
                  placeholder="e.g., Sales Team, Support, Marketing"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  disabled={modalMode === "view"}
                  rows={2}
                  placeholder="Describe what this workspace is for..."
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="timezone">Timezone</Label>
                <Select
                  value={formData.timezone}
                  onValueChange={(value) => setFormData({ ...formData, timezone: value })}
                  disabled={modalMode === "view"}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select timezone" />
                  </SelectTrigger>
                  <SelectContent>
                    {TIMEZONES.map((tz) => (
                      <SelectItem key={tz} value={tz}>
                        {tz}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="default_appointment_duration">Default Duration (min)</Label>
                  <Input
                    id="default_appointment_duration"
                    type="number"
                    min="5"
                    max="480"
                    value={formData.default_appointment_duration}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        default_appointment_duration: parseInt(e.target.value) || 30,
                      })
                    }
                    disabled={modalMode === "view"}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="booking_buffer_minutes">Buffer Time (min)</Label>
                  <Input
                    id="booking_buffer_minutes"
                    type="number"
                    min="0"
                    max="120"
                    value={formData.booking_buffer_minutes}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        booking_buffer_minutes: parseInt(e.target.value) || 0,
                      })
                    }
                    disabled={modalMode === "view"}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="max_advance_booking_days">Max Advance Booking (days)</Label>
                <Input
                  id="max_advance_booking_days"
                  type="number"
                  min="1"
                  max="365"
                  value={formData.max_advance_booking_days}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      max_advance_booking_days: parseInt(e.target.value) || 30,
                    })
                  }
                  disabled={modalMode === "view"}
                />
              </div>

              <div className="flex items-center justify-between rounded-lg border p-4">
                <div className="space-y-0.5">
                  <Label htmlFor="allow_same_day_booking">Allow Same-Day Booking</Label>
                  <p className="text-sm text-muted-foreground">
                    Allow customers to book appointments for today
                  </p>
                </div>
                <Switch
                  id="allow_same_day_booking"
                  checked={formData.allow_same_day_booking}
                  onCheckedChange={(checked) =>
                    setFormData({ ...formData, allow_same_day_booking: checked })
                  }
                  disabled={modalMode === "view"}
                />
              </div>
            </div>

            <DialogFooter className="gap-2">
              {modalMode === "view" && (
                <>
                  {!selectedWorkspace?.is_default && (
                    <Button
                      type="button"
                      variant="destructive"
                      onClick={handleDelete}
                      disabled={deleteWorkspaceMutation.isPending}
                    >
                      {deleteWorkspaceMutation.isPending ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="mr-2 h-4 w-4" />
                      )}
                      Delete
                    </Button>
                  )}
                  <Button type="button" onClick={switchToEditMode}>
                    Edit Workspace
                  </Button>
                </>
              )}
              {(modalMode === "add" || modalMode === "edit") && (
                <>
                  <Button type="button" variant="outline" onClick={closeModal}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    {modalMode === "add" ? "Create Workspace" : "Save Changes"}
                  </Button>
                </>
              )}
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Workspace Agents Modal */}
      <Dialog open={isAgentsModalOpen} onOpenChange={setIsAgentsModalOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Agents in {selectedWorkspace?.name}</DialogTitle>
            <DialogDescription>
              View and manage which agents are assigned to this workspace.
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            {isLoadingAgents ? (
              <div className="flex flex-col items-center justify-center py-8">
                <Loader2 className="mb-4 h-8 w-8 animate-spin text-muted-foreground" />
                <p className="text-sm text-muted-foreground">Loading agents...</p>
              </div>
            ) : workspaceAgents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <div className="mb-4 rounded-full bg-muted p-3">
                  <Bot className="h-6 w-6 text-muted-foreground" />
                </div>
                <p className="text-lg font-medium">No agents assigned</p>
                <p className="mb-4 text-sm text-muted-foreground">
                  Assign agents to this workspace from the Voice Agents page
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {workspaceAgents.map((agent) => (
                  <div
                    key={agent.agent_id}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                        <Bot className="h-5 w-5 text-primary" />
                      </div>
                      <div>
                        <p className="font-medium">{agent.agent_name}</p>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-xs">
                            {agent.pricing_tier}
                          </Badge>
                          {agent.is_default && (
                            <Badge variant="secondary" className="text-xs">
                              Default
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeAgentsModal}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
