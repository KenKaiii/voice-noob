"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
  Phone,
  Mail,
  Building2,
  Tag,
  Loader2,
  AlertCircle,
  X,
  FolderOpen,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "sonner";
import Link from "next/link";

interface Workspace {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
}

interface Contact {
  id: number;
  user_id: number;
  workspace_id: string | null;
  first_name: string;
  last_name: string | null;
  email: string | null;
  phone_number: string;
  company_name: string | null;
  status: string;
  tags: string | null;
  notes: string | null;
}

type ContactFormData = {
  first_name: string;
  last_name: string;
  email: string;
  phone_number: string;
  company_name: string;
  status: string;
  tags: string;
  notes: string;
  workspace_id: string;
};

const emptyFormData: ContactFormData = {
  first_name: "",
  last_name: "",
  email: "",
  phone_number: "",
  company_name: "",
  status: "new",
  tags: "",
  notes: "",
  workspace_id: "",
};

export default function CRMPage() {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<"add" | "edit" | "view">("add");
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [formData, setFormData] = useState<ContactFormData>(emptyFormData);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string>("all");

  // Fetch workspaces
  const { data: workspaces = [] } = useQuery<Workspace[]>({
    queryKey: ["workspaces"],
    queryFn: async () => {
      const response = await api.get("/api/v1/workspaces");
      return response.data;
    },
  });

  const {
    data: contacts = [],
    isLoading,
    error,
  } = useQuery<Contact[]>({
    queryKey: ["contacts", selectedWorkspaceId],
    queryFn: async () => {
      const url =
        selectedWorkspaceId && selectedWorkspaceId !== "all"
          ? `/api/v1/crm/contacts?workspace_id=${selectedWorkspaceId}`
          : "/api/v1/crm/contacts";
      const response = await api.get(url);
      return response.data;
    },
  });

  const createContactMutation = useMutation({
    mutationFn: async (data: ContactFormData) => {
      const response = await api.post("/api/v1/crm/contacts", data);
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["contacts"] });
      toast.success("Contact created successfully");
      closeModal();
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to create contact");
    },
  });

  const updateContactMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: ContactFormData }) => {
      const response = await api.put(`/api/v1/crm/contacts/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["contacts"] });
      toast.success("Contact updated successfully");
      closeModal();
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to update contact");
    },
  });

  const deleteContactMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/api/v1/crm/contacts/${id}`);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["contacts"] });
      toast.success("Contact deleted successfully");
      closeModal();
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to delete contact");
    },
  });

  const openAddModal = () => {
    // Pre-fill workspace_id if a workspace is selected
    const defaultWorkspaceId =
      selectedWorkspaceId !== "all" ? selectedWorkspaceId : (workspaces[0]?.id ?? "");
    setFormData({ ...emptyFormData, workspace_id: defaultWorkspaceId });
    setSelectedContact(null);
    setModalMode("add");
    setIsModalOpen(true);
  };

  const openViewModal = (contact: Contact) => {
    setSelectedContact(contact);
    setFormData({
      first_name: contact.first_name,
      last_name: contact.last_name ?? "",
      email: contact.email ?? "",
      phone_number: contact.phone_number,
      company_name: contact.company_name ?? "",
      status: contact.status,
      tags: contact.tags ?? "",
      notes: contact.notes ?? "",
      workspace_id: contact.workspace_id ?? "",
    });
    setModalMode("view");
    setIsModalOpen(true);
  };

  const switchToEditMode = () => {
    setModalMode("edit");
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setSelectedContact(null);
    setFormData(emptyFormData);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (modalMode === "add") {
      createContactMutation.mutate(formData);
    } else if (modalMode === "edit" && selectedContact) {
      updateContactMutation.mutate({ id: selectedContact.id, data: formData });
    }
  };

  const handleDelete = () => {
    if (selectedContact && confirm("Are you sure you want to delete this contact?")) {
      deleteContactMutation.mutate(selectedContact.id);
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      new: "bg-blue-100 text-blue-800",
      contacted: "bg-yellow-100 text-yellow-800",
      qualified: "bg-green-100 text-green-800",
      converted: "bg-purple-100 text-purple-800",
      lost: "bg-gray-100 text-gray-800",
    };
    return colors[status] ?? "bg-gray-100 text-gray-800";
  };

  const isSubmitting = createContactMutation.isPending || updateContactMutation.isPending;

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">CRM</h1>
          <p className="text-muted-foreground">
            Manage your contacts, appointments, and call interactions
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertCircle className="mb-4 h-12 w-12 text-destructive" />
            <h3 className="mb-2 text-lg font-semibold">Failed to load contacts</h3>
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
          <h1 className="text-3xl font-bold tracking-tight">CRM</h1>
          <p className="text-muted-foreground">
            Manage your contacts, appointments, and call interactions
          </p>
        </div>
        <div className="flex items-center gap-3">
          {workspaces.length > 0 ? (
            <Select value={selectedWorkspaceId} onValueChange={setSelectedWorkspaceId}>
              <SelectTrigger className="w-[200px]">
                <FolderOpen className="mr-2 h-4 w-4" />
                <SelectValue placeholder="All Workspaces" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Workspaces</SelectItem>
                {workspaces.map((ws) => (
                  <SelectItem key={ws.id} value={ws.id}>
                    {ws.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Link
              href="/dashboard/workspaces"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Create a workspace
            </Link>
          )}
          <Button onClick={openAddModal}>
            <Plus className="mr-2 h-4 w-4" />
            Add Contact
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Contacts</CardTitle>
            <Phone className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{contacts.length}</div>
            <p className="text-xs text-muted-foreground">Across all statuses</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Appointments</CardTitle>
            <Building2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
            <p className="text-xs text-muted-foreground">Scheduled this month</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Call Interactions</CardTitle>
            <Phone className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
            <p className="text-xs text-muted-foreground">Total interactions logged</p>
          </CardContent>
        </Card>
      </div>

      {/* Contacts List */}
      <Card>
        <CardHeader>
          <CardTitle>Contacts</CardTitle>
          <CardDescription>
            {isLoading
              ? "Loading contacts..."
              : contacts.length === 0
                ? "No contacts yet. Add your first contact to get started."
                : `Showing ${contacts.length} contact${contacts.length !== 1 ? "s" : ""}`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="mb-4 h-8 w-8 animate-spin text-muted-foreground" />
              <p className="text-sm text-muted-foreground">Loading contacts...</p>
            </div>
          ) : contacts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="mb-4 rounded-full bg-muted p-3">
                <Phone className="h-6 w-6 text-muted-foreground" />
              </div>
              <p className="text-lg font-medium">No contacts yet</p>
              <p className="mb-4 text-sm text-muted-foreground">
                Add contacts manually or they&apos;ll be created automatically from voice agent
                calls
              </p>
              <Button onClick={openAddModal}>
                <Plus className="mr-2 h-4 w-4" />
                Add Your First Contact
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {contacts.map((contact) => (
                <div
                  key={contact.id}
                  className="flex items-center justify-between rounded-lg border p-4 transition-colors hover:bg-accent"
                >
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium">
                        {contact.first_name} {contact.last_name}
                      </p>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${getStatusColor(contact.status)}`}
                      >
                        {contact.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      {contact.phone_number && (
                        <div className="flex items-center gap-1">
                          <Phone className="h-3 w-3" />
                          {contact.phone_number}
                        </div>
                      )}
                      {contact.email && (
                        <div className="flex items-center gap-1">
                          <Mail className="h-3 w-3" />
                          {contact.email}
                        </div>
                      )}
                      {contact.company_name && (
                        <div className="flex items-center gap-1">
                          <Building2 className="h-3 w-3" />
                          {contact.company_name}
                        </div>
                      )}
                      {contact.tags && (
                        <div className="flex items-center gap-1">
                          <Tag className="h-3 w-3" />
                          {contact.tags}
                        </div>
                      )}
                    </div>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => openViewModal(contact)}>
                    View Details
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Contact Modal */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="flex items-center justify-between">
              {modalMode === "add" && "Add New Contact"}
              {modalMode === "edit" && "Edit Contact"}
              {modalMode === "view" && "Contact Details"}
            </DialogTitle>
            <DialogDescription>
              {modalMode === "add" && "Fill in the contact information below."}
              {modalMode === "edit" && "Update the contact information."}
              {modalMode === "view" && "View and manage contact information."}
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit}>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="first_name">First Name *</Label>
                  <Input
                    id="first_name"
                    value={formData.first_name}
                    onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                    disabled={modalMode === "view"}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="last_name">Last Name</Label>
                  <Input
                    id="last_name"
                    value={formData.last_name}
                    onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                    disabled={modalMode === "view"}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="phone_number">Phone Number *</Label>
                <Input
                  id="phone_number"
                  type="tel"
                  value={formData.phone_number}
                  onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                  disabled={modalMode === "view"}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  disabled={modalMode === "view"}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="company_name">Company</Label>
                <Input
                  id="company_name"
                  value={formData.company_name}
                  onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                  disabled={modalMode === "view"}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="status">Status</Label>
                <Select
                  value={formData.status}
                  onValueChange={(value) => setFormData({ ...formData, status: value })}
                  disabled={modalMode === "view"}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="new">New</SelectItem>
                    <SelectItem value="contacted">Contacted</SelectItem>
                    <SelectItem value="qualified">Qualified</SelectItem>
                    <SelectItem value="converted">Converted</SelectItem>
                    <SelectItem value="lost">Lost</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {workspaces.length > 0 && (
                <div className="space-y-2">
                  <Label htmlFor="workspace">
                    <span className="flex items-center gap-2">
                      <FolderOpen className="h-4 w-4" />
                      Workspace
                    </span>
                  </Label>
                  <Select
                    value={formData.workspace_id}
                    onValueChange={(value) => setFormData({ ...formData, workspace_id: value })}
                    disabled={modalMode === "view"}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select workspace" />
                    </SelectTrigger>
                    <SelectContent>
                      {workspaces.map((ws) => (
                        <SelectItem key={ws.id} value={ws.id}>
                          {ws.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="tags">Tags</Label>
                <Input
                  id="tags"
                  value={formData.tags}
                  onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                  disabled={modalMode === "view"}
                  placeholder="e.g., VIP, Enterprise, Lead"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="notes">Notes</Label>
                <Textarea
                  id="notes"
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  disabled={modalMode === "view"}
                  rows={3}
                />
              </div>
            </div>

            <DialogFooter className="gap-2">
              {modalMode === "view" && (
                <>
                  <Button
                    type="button"
                    variant="destructive"
                    onClick={handleDelete}
                    disabled={deleteContactMutation.isPending}
                  >
                    {deleteContactMutation.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <X className="mr-2 h-4 w-4" />
                    )}
                    Delete
                  </Button>
                  <Button type="button" onClick={switchToEditMode}>
                    Edit Contact
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
                    {modalMode === "add" ? "Create Contact" : "Save Changes"}
                  </Button>
                </>
              )}
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
