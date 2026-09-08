const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
const isHttps = typeof window !== "undefined" && window.location.protocol === "https:";
const isLocalDefault = configuredApiBaseUrl?.startsWith("http://localhost") || configuredApiBaseUrl?.startsWith("http://127.");
const API_BASE_URL = isHttps && isLocalDefault
  ? window.location.origin
  : configuredApiBaseUrl || (isHttps ? window.location.origin : "http://localhost:8000");

export interface HealthInfo {
  status: string;
  app_name: string;
  app_version: string;
  environment: string;
  database_connected: boolean;
  checked_at: string;
}

export async function getHealth(): Promise<HealthInfo> {
  const base = API_BASE_URL.replace(/\/$/, "");
  const res = await fetch(`${base}/api/v1/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }

  return res.json();
}
