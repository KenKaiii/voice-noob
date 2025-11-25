/**
 * API client for user settings
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface SettingsResponse {
  openai_api_key_set: boolean;
  deepgram_api_key_set: boolean;
  elevenlabs_api_key_set: boolean;
  telnyx_api_key_set: boolean;
  twilio_account_sid_set: boolean;
}

export interface UpdateSettingsRequest {
  openai_api_key?: string;
  deepgram_api_key?: string;
  elevenlabs_api_key?: string;
  telnyx_api_key?: string;
  telnyx_public_key?: string;
  twilio_account_sid?: string;
  twilio_auth_token?: string;
}

export async function fetchSettings(): Promise<SettingsResponse> {
  const response = await fetch(`${API_BASE}/api/v1/settings`);
  if (!response.ok) {
    throw new Error(`Failed to fetch settings: ${response.statusText}`);
  }
  return response.json();
}

export async function updateSettings(request: UpdateSettingsRequest): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/api/v1/settings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail ?? "Failed to update settings");
  }

  return response.json();
}
