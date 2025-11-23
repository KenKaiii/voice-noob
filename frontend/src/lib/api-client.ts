import api from "./api";

// Auth types
export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Voice Agent types
export interface VoiceAgentCreate {
  name: string;
  description?: string;
  pricing_tier: string;
  llm_config: Record<string, unknown>;
  stt_config: Record<string, unknown>;
  tts_config: Record<string, unknown>;
  system_prompt: string;
  voice_id?: string;
  temperature?: number;
  phone_number_id?: number;
  enabled_integrations?: number[];
  is_active?: boolean;
}

export interface VoiceAgentResponse extends VoiceAgentCreate {
  id: number;
  user_id: number;
  created_at: string;
  updated_at: string;
}

// Integration types
export interface IntegrationCreate {
  integration_type: string;
  name: string;
  api_key?: string;
  api_secret?: string;
  is_active?: boolean;
}

export interface IntegrationResponse {
  id: number;
  user_id: number;
  integration_type: string;
  name: string;
  account_id: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Auth API
export const authApi = {
  register: async (data: RegisterRequest): Promise<UserResponse> => {
    const response = await api.post<UserResponse>("/auth/register", data);
    return response.data;
  },

  login: async (data: LoginRequest): Promise<TokenResponse> => {
    const response = await api.post<TokenResponse>("/auth/login", data);
    const { access_token, refresh_token } = response.data;
    localStorage.setItem("access_token", access_token);
    localStorage.setItem("refresh_token", refresh_token);
    return response.data;
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  },

  getCurrentUser: async (): Promise<UserResponse> => {
    const response = await api.get<UserResponse>("/users/me");
    return response.data;
  },
};

// Voice Agent API
export const agentApi = {
  create: async (data: VoiceAgentCreate): Promise<VoiceAgentResponse> => {
    const response = await api.post<VoiceAgentResponse>("/agents", data);
    return response.data;
  },

  list: async (): Promise<VoiceAgentResponse[]> => {
    const response = await api.get<VoiceAgentResponse[]>("/agents");
    return response.data;
  },

  get: async (id: number): Promise<VoiceAgentResponse> => {
    const response = await api.get<VoiceAgentResponse>(`/agents/${id}`);
    return response.data;
  },

  update: async (
    id: number,
    data: Partial<VoiceAgentCreate>
  ): Promise<VoiceAgentResponse> => {
    const response = await api.patch<VoiceAgentResponse>(`/agents/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/agents/${id}`);
  },
};

// Integration API
export const integrationApi = {
  create: async (data: IntegrationCreate): Promise<IntegrationResponse> => {
    const response = await api.post<IntegrationResponse>("/integrations", data);
    return response.data;
  },

  list: async (): Promise<IntegrationResponse[]> => {
    const response = await api.get<IntegrationResponse[]>("/integrations");
    return response.data;
  },

  update: async (
    id: number,
    data: Partial<IntegrationCreate>
  ): Promise<IntegrationResponse> => {
    const response = await api.patch<IntegrationResponse>(
      `/integrations/${id}`,
      data
    );
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/integrations/${id}`);
  },
};
