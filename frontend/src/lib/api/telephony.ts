/**
 * API client for telephony management (phone numbers, calls)
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getAuthHeaders(): HeadersInit {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Fetch with timeout to prevent hanging requests
 */
async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeoutMs = 15000
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  // Merge auth headers with any provided headers
  const headers = {
    ...getAuthHeaders(),
    ...(options.headers ?? {}),
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
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

export type Provider = "twilio" | "telnyx";

export interface PhoneNumber {
  id: string;
  phone_number: string;
  friendly_name: string | null;
  provider: string;
  capabilities: {
    voice?: boolean;
    sms?: boolean;
    mms?: boolean;
  } | null;
  assigned_agent_id: string | null;
}

export interface SearchPhoneNumbersRequest {
  provider: Provider;
  country?: string;
  area_code?: string;
  contains?: string;
  limit?: number;
}

export interface PurchasePhoneNumberRequest {
  provider: Provider;
  phone_number: string;
}

export interface InitiateCallRequest {
  to_number: string;
  from_number: string;
  agent_id: string;
}

export interface CallResponse {
  call_id: string;
  call_control_id: string | null;
  from_number: string;
  to_number: string;
  direction: "inbound" | "outbound";
  status: string;
  agent_id: string | null;
}

/**
 * List all phone numbers for the user's account
 */
export async function listPhoneNumbers(provider: Provider): Promise<PhoneNumber[]> {
  const response = await fetchWithTimeout(
    `${API_BASE}/api/v1/telephony/phone-numbers?provider=${provider}`
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail ?? "Failed to list phone numbers");
  }

  return response.json();
}

/**
 * Search for available phone numbers to purchase
 */
export async function searchPhoneNumbers(
  request: SearchPhoneNumbersRequest
): Promise<PhoneNumber[]> {
  const response = await fetchWithTimeout(`${API_BASE}/api/v1/telephony/phone-numbers/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      provider: request.provider,
      country: request.country ?? "US",
      area_code: request.area_code,
      contains: request.contains,
      limit: request.limit ?? 10,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail ?? "Failed to search phone numbers");
  }

  return response.json();
}

/**
 * Purchase a phone number
 */
export async function purchasePhoneNumber(
  request: PurchasePhoneNumberRequest
): Promise<PhoneNumber> {
  const response = await fetchWithTimeout(`${API_BASE}/api/v1/telephony/phone-numbers/purchase`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail ?? "Failed to purchase phone number");
  }

  return response.json();
}

/**
 * Release a phone number
 */
export async function releasePhoneNumber(phoneNumberId: string, provider: Provider): Promise<void> {
  const response = await fetchWithTimeout(
    `${API_BASE}/api/v1/telephony/phone-numbers/${phoneNumberId}?provider=${provider}`,
    {
      method: "DELETE",
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail ?? "Failed to release phone number");
  }
}

/**
 * Initiate an outbound call
 */
export async function initiateCall(request: InitiateCallRequest): Promise<CallResponse> {
  const response = await fetchWithTimeout(`${API_BASE}/api/v1/telephony/calls`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail ?? "Failed to initiate call");
  }

  return response.json();
}

/**
 * Hang up an active call
 */
export async function hangupCall(callId: string, provider: Provider): Promise<void> {
  const response = await fetchWithTimeout(
    `${API_BASE}/api/v1/telephony/calls/${callId}/hangup?provider=${provider}`,
    {
      method: "POST",
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail ?? "Failed to hang up call");
  }
}
