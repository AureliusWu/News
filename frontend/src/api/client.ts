const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
const isLocalhost = typeof window !== "undefined" &&
  (/^localhost$/i.test(window.location.hostname) || /^127\./.test(window.location.hostname));
const isLocalDefault = configuredApiBaseUrl?.startsWith("http://localhost") || configuredApiBaseUrl?.startsWith("http://127.");
const hasValidConfiguredApiBaseUrl = Boolean(configuredApiBaseUrl) && !(isLocalDefault && !isLocalhost);
const API_BASE_URL = hasValidConfiguredApiBaseUrl
  ? configuredApiBaseUrl
  : isLocalhost
    ? "http://localhost:8000"
    : null;

export interface HealthInfo {
  status: string;
  app_name: string;
  app_version: string;
  environment: string;
  database_connected: boolean;
  checked_at: string;
}

export async function getHealth(): Promise<HealthInfo> {
  if (!API_BASE_URL) {
    throw new Error(
      "Backend API base URL is not configured. Set VITE_API_BASE_URL to your backend endpoint."
    );
  }

  const base = API_BASE_URL.replace(/\/$/, "");
  const res = await fetch(`${base}/api/v1/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }

  return res.json();
}
