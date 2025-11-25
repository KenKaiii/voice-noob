"use client";

import { useState, useMemo, memo } from "react";
import { useDebounce } from "use-debounce";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Search,
  Check,
  Settings as SettingsIcon,
  Zap,
  Calendar,
  Users,
  Database,
  MessageSquare,
  Mail,
  Table,
  CreditCard,
  LifeBuoy,
  Code,
  Briefcase,
  FileText,
  Send,
  Clock,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { AVAILABLE_INTEGRATIONS, type Integration } from "@/lib/integrations";

const getIntegrationIcon = (integrationId: string) => {
  const iconMap: Record<string, React.ComponentType> = {
    salesforce: Users,
    hubspot: Users,
    pipedrive: Users,
    "zoho-crm": Users,
    "google-calendar": Calendar,
    "microsoft-calendar": Calendar,
    "cal-com": Clock,
    airtable: Table,
    notion: FileText,
    "google-sheets": Table,
    slack: MessageSquare,
    gmail: Mail,
    sendgrid: Send,
    intercom: MessageSquare,
    stripe: CreditCard,
    github: Code,
    jira: Briefcase,
    zendesk: LifeBuoy,
  };
  return iconMap[integrationId] ?? Database;
};

export default function IntegrationsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery] = useDebounce(searchQuery, 300);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  // Internal tools are always "connected" (no credentials needed)
  const internalTools = new Set<string>(["crm", "bookings"]);
  const connectedIntegrations = internalTools;

  const categories = [
    { value: "all", label: "All" },
    { value: "crm", label: "CRM" },
    { value: "calendar", label: "Calendar" },
    { value: "database", label: "Database" },
    { value: "communication", label: "Communication" },
    { value: "productivity", label: "Productivity" },
    { value: "other", label: "Other" },
  ];

  // Memoize filtered integrations to prevent unnecessary recalculations
  const filteredIntegrations = useMemo(() => {
    return AVAILABLE_INTEGRATIONS.filter((integration) => {
      const matchesSearch =
        integration.name.toLowerCase().includes(debouncedSearchQuery.toLowerCase()) ||
        integration.description.toLowerCase().includes(debouncedSearchQuery.toLowerCase());
      const matchesCategory =
        selectedCategory === "all" || integration.category === selectedCategory;
      return matchesSearch && matchesCategory;
    });
  }, [debouncedSearchQuery, selectedCategory]);

  const connectedCount = Array.from(connectedIntegrations).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Integrations & Tools</h1>
        <p className="text-muted-foreground">
          Connect external services for your voice agents to use
        </p>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="font-normal">
            {connectedCount} Connected
          </Badge>
          <Badge variant="outline" className="font-normal">
            {AVAILABLE_INTEGRATIONS.length} Available
          </Badge>
        </div>
        <div className="relative w-[300px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search integrations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      <Tabs defaultValue="all" onValueChange={setSelectedCategory}>
        <TabsList>
          {categories.map((cat) => (
            <TabsTrigger key={cat.value} value={cat.value}>
              {cat.label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value={selectedCategory} className="mt-6">
          {filteredIntegrations.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-16">
                <Zap className="mb-4 h-16 w-16 text-muted-foreground/50" />
                <h3 className="mb-2 text-lg font-semibold">No integrations found</h3>
                <p className="text-sm text-muted-foreground">
                  Try adjusting your search or category filter
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {filteredIntegrations.map((integration) => (
                <IntegrationCard
                  key={integration.id}
                  integration={integration}
                  isConnected={connectedIntegrations.has(integration.id)}
                />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

const IntegrationCard = memo(function IntegrationCard({
  integration,
  isConnected,
}: {
  integration: Integration;
  isConnected: boolean;
}) {
  const [isConfigDialogOpen, setIsConfigDialogOpen] = useState(false);
  const Icon = getIntegrationIcon(integration.id);

  return (
    <Card className="transition-shadow hover:shadow-md">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Icon className="h-5 w-5 text-primary" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">{integration.name}</CardTitle>
                {integration.isPopular && (
                  <Badge variant="secondary" className="text-xs">
                    Popular
                  </Badge>
                )}
              </div>
              <CardDescription className="mt-1 text-xs">
                {integration.category.toUpperCase()}
              </CardDescription>
            </div>
          </div>
          {isConnected && <Check className="h-5 w-5 text-green-600 dark:text-green-400" />}
        </div>
      </CardHeader>
      <CardContent>
        <p className="mb-4 line-clamp-2 text-sm text-muted-foreground">{integration.description}</p>
        <div className="flex gap-2">
          <Dialog open={isConfigDialogOpen} onOpenChange={setIsConfigDialogOpen}>
            <DialogTrigger asChild>
              <Button variant={isConnected ? "outline" : "default"} className="flex-1" size="sm">
                {isConnected ? (
                  <>
                    <SettingsIcon className="mr-2 h-3 w-3" />
                    Configure
                  </>
                ) : (
                  "Connect"
                )}
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-md">
              <DialogHeader>
                <DialogTitle>Connect {integration.name}</DialogTitle>
                <DialogDescription>
                  {integration.authType === "oauth"
                    ? "Click Connect to authorize access via OAuth"
                    : "Enter your API credentials below"}
                </DialogDescription>
              </DialogHeader>
              <IntegrationConfigForm
                integration={integration}
                isConnected={isConnected}
                onClose={() => setIsConfigDialogOpen(false)}
              />
            </DialogContent>
          </Dialog>
          {integration.documentationUrl && (
            <Button variant="ghost" size="sm" asChild>
              <a href={integration.documentationUrl} target="_blank" rel="noopener noreferrer">
                Docs
              </a>
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
});

const IntegrationConfigForm = memo(function IntegrationConfigForm({
  integration,
  isConnected: _isConnected,
  onClose,
}: {
  integration: Integration;
  isConnected: boolean;
  onClose: () => void;
}) {
  // For internal tools (authType: "none"), just show info
  if (integration.authType === "none") {
    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-green-500/20 bg-green-500/10 p-4">
          <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
            <Check className="h-4 w-4" />
            <span className="text-sm font-medium">Always Available</span>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            This is an internal tool that works with your existing CRM data. No configuration
            needed.
          </p>
        </div>
        <Button onClick={onClose} className="w-full">
          Close
        </Button>
      </div>
    );
  }

  // External integrations - coming soon
  const handleExternalIntegration = () => {
    toast.info("External integrations coming soon! Use internal CRM and Bookings tools for now.");
    onClose();
  };

  // All other integrations - show coming soon message
  return (
    <div className="space-y-4">
      <div className="rounded-lg border p-4">
        <p className="text-sm text-muted-foreground">
          External integrations are coming soon! For now, use the internal CRM and Bookings tools
          which work with your existing data.
        </p>
      </div>
      <Button onClick={handleExternalIntegration} className="w-full">
        Coming Soon
      </Button>
    </div>
  );
});
