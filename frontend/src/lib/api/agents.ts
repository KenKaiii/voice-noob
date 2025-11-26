/**
 * API client for agent management
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Fetch with timeout to prevent hanging requests
 */
async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeoutMs = 10000
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return response;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("Request timed out - please check if the backend is running");
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export interface Agent {
  id: string;
  name: string;
  description: string | null;
  pricing_tier: string;
  system_prompt: string;
  language: string;
  enabled_tools: string[];
  phone_number_id: string | null;
  enable_recording: boolean;
  enable_transcript: boolean;
  is_active: boolean;
  is_published: boolean;
  total_calls: number;
  total_duration_seconds: number;
  created_at: string;
  updated_at: string;
  last_call_at: string | null;
}

export interface CreateAgentRequest {
  name: string;
  description?: string;
  pricing_tier: "budget" | "balanced" | "premium";
  system_prompt: string;
  language: string;
  enabled_tools: string[];
  phone_number_id?: string;
  enable_recording: boolean;
  enable_transcript: boolean;
}

/**
 * Create a new voice agent
 */
export async function createAgent(request: CreateAgentRequest): Promise<Agent> {
  const response = await fetchWithTimeout(`${API_BASE}/api/v1/agents`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail ?? "Failed to create agent");
  }

  return response.json();
}

/**
 * List all agents
 */
export async function fetchAgents(): Promise<Agent[]> {
  const response = await fetchWithTimeout(`${API_BASE}/api/v1/agents`);
  if (!response.ok) {
    throw new Error(`Failed to fetch agents: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Get a specific agent
 */
export async function getAgent(agentId: string): Promise<Agent> {
  const response = await fetchWithTimeout(`${API_BASE}/api/v1/agents/${agentId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch agent: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Delete an agent
 */
export async function deleteAgent(agentId: string): Promise<void> {
  const response = await fetchWithTimeout(`${API_BASE}/api/v1/agents/${agentId}`, {
    method: "DELETE",
  });

  if (!response.ok && response.status !== 204) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail ?? "Failed to delete agent");
  }
}
