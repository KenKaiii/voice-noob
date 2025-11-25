export type IntegrationType =
  | "crm"
  | "calendar"
  | "database"
  | "productivity"
  | "communication"
  | "other";

export type AuthType = "oauth" | "api_key" | "basic" | "none";

export interface Integration {
  id: string;
  name: string;
  slug: string;
  description: string;
  category: IntegrationType;
  authType: AuthType;
  icon: string;
  enabled: boolean;
  isPopular?: boolean;
  fields?: IntegrationField[];
  scopes?: string[];
  documentationUrl?: string;
}

export interface IntegrationField {
  name: string;
  label: string;
  type: "text" | "password" | "url" | "email";
  placeholder?: string;
  required: boolean;
  description?: string;
}

export const AVAILABLE_INTEGRATIONS: Integration[] = [
  // Internal Tools (No external API needed)
  {
    id: "crm",
    name: "Internal CRM",
    slug: "crm",
    description: "Search customers, view contact details, manage customer data",
    category: "crm",
    authType: "none",
    icon: "https://cdn.simpleicons.org/database",
    enabled: true,
    isPopular: true,
    documentationUrl: "/docs/crm-tools",
  },
  {
    id: "bookings",
    name: "Appointment Booking",
    slug: "bookings",
    description: "Check availability, book appointments, cancel/reschedule bookings",
    category: "calendar",
    authType: "none",
    icon: "https://cdn.simpleicons.org/googlecalendar",
    enabled: true,
    isPopular: true,
    documentationUrl: "/docs/booking-tools",
  },

  // External CRM
  {
    id: "salesforce",
    name: "Salesforce",
    slug: "salesforce",
    description: "Access customer data, create leads, update opportunities",
    category: "crm",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/salesforce",
    enabled: true,
    isPopular: true,
    fields: [
      {
        name: "access_token",
        label: "Access Token",
        type: "password",
        required: true,
        description: "Salesforce session/access token",
      },
      {
        name: "instance_url",
        label: "Instance URL",
        type: "url",
        required: true,
        placeholder: "https://yourinstance.salesforce.com",
        description: "Your Salesforce instance URL",
      },
    ],
    documentationUrl: "https://developer.salesforce.com/docs/",
  },
  {
    id: "hubspot",
    name: "HubSpot",
    slug: "hubspot",
    description: "Manage contacts, deals, and customer interactions (free MCP)",
    category: "crm",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/hubspot",
    enabled: true,
    isPopular: true,
    fields: [
      {
        name: "access_token",
        label: "Private App Access Token",
        type: "password",
        required: true,
        placeholder: "pat-na1-...",
        description: "Create Private App at app.hubspot.com",
      },
      {
        name: "portal_id",
        label: "Portal ID",
        type: "text",
        required: true,
        placeholder: "12345678",
        description: "Your HubSpot account/portal ID",
      },
    ],
    documentationUrl: "https://developers.hubspot.com/docs/api/private-apps",
  },
  {
    id: "pipedrive",
    name: "Pipedrive",
    slug: "pipedrive",
    description: "Sales pipeline and deal management",
    category: "crm",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/pipedrive",
    enabled: true,
    fields: [
      {
        name: "api_token",
        label: "API Token",
        type: "password",
        required: true,
        description: "Found in Settings > Personal > API",
      },
      {
        name: "domain",
        label: "Domain",
        type: "text",
        placeholder: "yourcompany.pipedrive.com",
        required: true,
      },
    ],
  },
  {
    id: "zoho-crm",
    name: "Zoho CRM",
    slug: "zoho-crm",
    description: "Customer relationship management",
    category: "crm",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/zoho",
    enabled: true,
    fields: [
      {
        name: "api_token",
        label: "Auth Token",
        type: "password",
        required: true,
        description: "Zoho CRM Auth Token",
      },
      {
        name: "domain",
        label: "API Domain",
        type: "text",
        required: true,
        placeholder: "www.zohoapis.com",
        description: "Zoho API domain (e.g., zohoapis.com, zohoapis.eu)",
      },
    ],
    documentationUrl: "https://www.zoho.com/crm/developer/docs/api/v2/auth-request.html",
  },

  // Calendar
  {
    id: "google-calendar",
    name: "Google Calendar",
    slug: "google-calendar",
    description: "Schedule meetings, check availability, create events",
    category: "calendar",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/googlecalendar",
    enabled: true,
    isPopular: true,
    fields: [
      {
        name: "access_token",
        label: "OAuth Access Token",
        type: "password",
        required: true,
        description: "Google OAuth 2.0 access token",
      },
      {
        name: "refresh_token",
        label: "Refresh Token",
        type: "password",
        required: false,
        description: "Optional: OAuth refresh token for long-term access",
      },
    ],
    documentationUrl: "https://developers.google.com/calendar/api/guides/auth",
  },
  {
    id: "microsoft-calendar",
    name: "Microsoft Calendar",
    slug: "microsoft-calendar",
    description: "Outlook calendar integration (free MCP)",
    category: "calendar",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/microsoftoutlook",
    enabled: true,
    isPopular: true,
    fields: [
      {
        name: "access_token",
        label: "Access Token",
        type: "password",
        required: true,
        description: "Microsoft Graph API access token",
      },
      {
        name: "refresh_token",
        label: "Refresh Token",
        type: "password",
        required: false,
        description: "Optional: OAuth refresh token",
      },
    ],
    documentationUrl: "https://learn.microsoft.com/en-us/graph/auth/",
  },
  {
    id: "cal-com",
    name: "Cal.com",
    slug: "cal-com",
    description: "Open-source scheduling platform",
    category: "calendar",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/caldotcom",
    enabled: true,
    fields: [
      {
        name: "api_key",
        label: "API Key",
        type: "password",
        required: true,
      },
    ],
  },

  // Database & Storage
  {
    id: "airtable",
    name: "Airtable",
    slug: "airtable",
    description: "Access and update database records (via free MCP server)",
    category: "database",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/airtable",
    enabled: true,
    fields: [
      {
        name: "api_key",
        label: "Personal Access Token",
        type: "password",
        required: true,
        placeholder: "pat...",
        description: "Create token at airtable.com/create/tokens",
      },
      {
        name: "base_id",
        label: "Base ID",
        type: "text",
        required: true,
        placeholder: "appXXXXXXXXXXXXXX",
        description: "Your Airtable base ID (from URL)",
      },
    ],
    documentationUrl: "https://airtable.com/developers/web/api/authentication",
  },
  {
    id: "notion",
    name: "Notion",
    slug: "notion",
    description: "Query and update Notion databases (free MCP)",
    category: "database",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/notion",
    enabled: true,
    isPopular: true,
    fields: [
      {
        name: "access_token",
        label: "Integration Token",
        type: "password",
        required: true,
        placeholder: "secret_...",
        description: "Create internal integration at notion.so/my-integrations",
      },
    ],
    documentationUrl: "https://developers.notion.com/docs/create-a-notion-integration",
  },
  {
    id: "google-sheets",
    name: "Google Sheets",
    slug: "google-sheets",
    description: "Read and write spreadsheet data",
    category: "database",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/googlesheets",
    enabled: true,
    isPopular: true,
    fields: [
      {
        name: "access_token",
        label: "OAuth Access Token",
        type: "password",
        required: true,
        description: "Google OAuth 2.0 access token",
      },
      {
        name: "refresh_token",
        label: "Refresh Token",
        type: "password",
        required: false,
        description: "Optional: OAuth refresh token",
      },
    ],
    documentationUrl: "https://developers.google.com/sheets/api/guides/authorizing",
  },

  // Productivity
  {
    id: "slack",
    name: "Slack",
    slug: "slack",
    description: "Send messages, notifications, and alerts (via free MCP server)",
    category: "communication",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/slack",
    enabled: true,
    isPopular: true,
    fields: [
      {
        name: "bot_token",
        label: "Bot Token",
        type: "password",
        required: true,
        placeholder: "xoxb-...",
        description: "Create Slack App and get Bot User OAuth Token",
      },
      {
        name: "workspace_id",
        label: "Workspace ID",
        type: "text",
        required: true,
        placeholder: "T01234567",
        description: "Your Slack workspace/team ID",
      },
    ],
    documentationUrl: "https://api.slack.com/authentication/token-types",
  },
  {
    id: "gmail",
    name: "Gmail",
    slug: "gmail",
    description: "Send emails and search inbox",
    category: "communication",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/gmail",
    enabled: true,
    isPopular: true,
    fields: [
      {
        name: "access_token",
        label: "OAuth Access Token",
        type: "password",
        required: true,
        description: "Google OAuth 2.0 access token",
      },
      {
        name: "refresh_token",
        label: "Refresh Token",
        type: "password",
        required: false,
        description: "Optional: OAuth refresh token",
      },
    ],
    documentationUrl: "https://developers.google.com/gmail/api/auth/about-auth",
  },
  {
    id: "sendgrid",
    name: "SendGrid",
    slug: "sendgrid",
    description: "Transactional email sending",
    category: "communication",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/sendgrid",
    enabled: true,
    fields: [
      {
        name: "api_key",
        label: "API Key",
        type: "password",
        required: true,
      },
    ],
  },

  // Other Tools
  {
    id: "stripe",
    name: "Stripe",
    slug: "stripe",
    description: "Payment processing and subscription management",
    category: "other",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/stripe",
    enabled: true,
    isPopular: true,
    fields: [
      {
        name: "api_key",
        label: "Secret Key",
        type: "password",
        required: true,
        placeholder: "sk_...",
      },
    ],
  },
  {
    id: "github",
    name: "GitHub",
    slug: "github",
    description: "Repository and issue management (via free MCP server)",
    category: "productivity",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/github",
    enabled: true,
    isPopular: true,
    fields: [
      {
        name: "personal_access_token",
        label: "Personal Access Token",
        type: "password",
        required: true,
        placeholder: "ghp_...",
        description: "Create token at github.com/settings/tokens",
      },
    ],
    documentationUrl:
      "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token",
  },
  {
    id: "jira",
    name: "Jira",
    slug: "jira",
    description: "Project management and issue tracking (via free MCP server)",
    category: "productivity",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/jira",
    enabled: true,
    fields: [
      {
        name: "api_token",
        label: "API Token",
        type: "password",
        required: true,
        description: "Atlassian API token",
      },
      {
        name: "email",
        label: "Email",
        type: "email",
        required: true,
        description: "Your Atlassian account email",
      },
      {
        name: "domain",
        label: "Domain",
        type: "text",
        required: true,
        placeholder: "yourcompany.atlassian.net",
        description: "Your Jira cloud instance domain",
      },
    ],
    documentationUrl:
      "https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/",
  },
  {
    id: "zendesk",
    name: "Zendesk",
    slug: "zendesk",
    description: "Customer support ticketing",
    category: "crm",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/zendesk",
    enabled: true,
    fields: [
      {
        name: "api_token",
        label: "API Token",
        type: "password",
        required: true,
        description: "Zendesk API token",
      },
      {
        name: "email",
        label: "Email",
        type: "email",
        required: true,
        description: "Your Zendesk account email",
      },
      {
        name: "subdomain",
        label: "Subdomain",
        type: "text",
        required: true,
        placeholder: "yourcompany",
        description: "Your Zendesk subdomain (e.g., yourcompany.zendesk.com)",
      },
    ],
    documentationUrl: "https://developer.zendesk.com/api-reference/",
  },
  {
    id: "intercom",
    name: "Intercom",
    slug: "intercom",
    description: "Customer messaging and support",
    category: "communication",
    authType: "api_key",
    icon: "https://cdn.simpleicons.org/intercom",
    enabled: true,
    fields: [
      {
        name: "access_token",
        label: "Access Token",
        type: "password",
        required: true,
        description: "Intercom access token",
      },
    ],
    documentationUrl:
      "https://developers.intercom.com/docs/build-an-integration/learn-more/authentication/",
  },
];

export interface UserIntegration {
  id: string;
  integrationId: string;
  userId: string;
  isConnected: boolean;
  connectedAt?: Date;
  credentials?: Record<string, string>;
  metadata?: Record<string, unknown>;
}
