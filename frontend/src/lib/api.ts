import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
});

// Request interceptor for adding auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for handling errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    // Log authentication failures
    if (error.response?.status === 401) {
      console.error("Authentication failed - redirecting to login", {
        endpoint: error.config?.url,
        status: error.response.status,
      });
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    } else if (error.response) {
      // Log API errors with details
      console.error("API error:", {
        endpoint: error.config?.url,
        method: error.config?.method?.toUpperCase(),
        status: error.response.status,
        message: error.response.data?.message ?? error.message,
      });
    } else if (error.request) {
      // Log network errors
      console.error("Network error - no response received:", {
        endpoint: error.config?.url,
        method: error.config?.method?.toUpperCase(),
      });
    } else {
      // Log request setup errors
      console.error("Request error:", error.message);
    }
    return Promise.reject(error);
  }
);

export default api;
